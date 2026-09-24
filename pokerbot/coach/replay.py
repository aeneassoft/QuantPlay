"""Replay compiler: rebuild a played hand as ordered animation steps from the session logs.

WHY: the trainer's replay walkthrough (docs/doctrine/TRAINER_DESIGN.md §6) must be FULLY deterministic
from the JSONL logs alone. build_hand_record (pokerbot/web/session_log.py:14) drops the
engine's 'blinds'/'deal' history events (the 'player' filter), so blind seats and the 3/1/1
board reveal are re-derived here from button + board order. Pure dict->dict — no FastAPI or
engine imports — so the HTTP route (server owner's job) stays a thin wrapper and this module
is unit-testable without a server.

Pot math follows the VERIFIED table.py history semantics (table.py:170-172 / 189-190):
'call' logs the chips ADDED; 'bet'/'raise' log the street commit-TO total ('to'; 'allin' is
normalized to bet/raise before logging). session_log merges both into one 'amount' field.

Hole exposure (anti-Ergebnisorientierung, TRAINER_DESIGN §1.1): the output carries the hero
hole + board; bot holes appear ONLY via result['shown'] when result['reveal'] is truthy —
the raw hole{} of unrevealed bots is stripped.

Run: python -m pokerbot.coach.replay   (selftest, no server needed)
"""
from __future__ import annotations

import json
from pathlib import Path

STREETS = ["preflop", "flop", "turn", "river"]
BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}  # cumulative reveal 0/3/4/5
# decision-record keys (P0 contract, TRAINER_DESIGN §4) -> coach fields
_ONE_LINER_KEYS = ("erklaerung_kurz", "erklärung_kurz")  # both spellings seen in the docs


# ---------------------------------------------------------------- small helpers
def _int_keys(d: dict) -> dict:
    """JSONL round-trips dict keys to str — normalize seat-keyed dicts back to int."""
    return {int(k): v for k, v in (d or {}).items()}


def _readable_action(a) -> str | None:
    """'call' / 'raise 6bb' — the replay overlay shows text, never a raw dict."""
    if a is None:
        return None
    if isinstance(a, str):
        return a
    if isinstance(a, dict):
        verb, amt = a.get("action"), a.get("amount")
        return f"{verb} {amt}" if verb and amt else (verb or None)
    return str(a)


def _coach_from(dec: dict) -> dict:
    """Map a P0 decision record onto the compact coach payload the replay UI renders."""
    one_liner = next((dec[k] for k in _ONE_LINER_KEYS if dec.get(k)), None)
    rec_action = dec.get("oracle_action")
    if rec_action is None:                       # P0-3 stores the oracle verdict nested under 'oracle'
        orc = dec.get("oracle") or {}
        rec_action = orc.get("oracle_action") or orc.get("action")
    # Voller Coaching-Text PRO Entscheidung (User-QA 2026-08-02): derselbe Renderer wie das Hand-Feedback
    # macht jeden Replay-Schritt einzigartig (Grund + Alternative + Bot-Frequenzen), statt nur one_liner.
    # Lazy + guarded: replay bleibt ohne templates_de lauffähig (Modul-Doktrin: pure, unit-testbar).
    text, dist = None, []
    try:
        from pokerbot.coach import templates_de as _tp
        text = _tp.render_decision_feedback(dec)["text"]
        # Frequenzen STRUKTURIERT statt in den Text gehängt: das UI zeigt sie nur, wenn der Spot wirklich
        # GEMISCHT ist (User-Regel 2026-08-02: Information nur, wo sie Sinn macht — nie doppelt/überladen).
        dist = [[a, round(p, 3)] for a, p in _tp._support_dist(dec)]
    except Exception:  # noqa: BLE001 — one_liner bleibt der Fallback im UI
        text = None
    return {
        "played": _readable_action(dec.get("human_action")),
        "recommended": _readable_action(rec_action),
        "grade": dec.get("grade"),
        "one_liner": one_liner,
        "text": text,
        "dist": dist,
    }


def _decisions_by_street(decisions: list[dict], hand_no) -> dict[str, list[dict]]:
    """Group decision records by street, preserving order; filter to this hand when the
    records carry an identity field (tolerant: hand_no int-equality, hand_id str-equality)."""
    by_street: dict[str, list[dict]] = {}
    for dec in decisions or []:
        if hand_no is not None:
            if "hand_no" in dec and dec["hand_no"] != hand_no:
                continue
            # P0-1 ships hand_id as "<session_id>-<hand_no>" — compare the SUFFIX, not the whole string
            # (the naive full-string compare filtered every real record out; found in the P2-6 UI check).
            if "hand_no" not in dec and "hand_id" in dec:
                hid = str(dec["hand_id"])
                if hid != str(hand_no) and hid.rsplit("-", 1)[-1] != str(hand_no):
                    continue
        by_street.setdefault(dec.get("street") or "preflop", []).append(dec)
    return by_street


def _step(type_, street, board_so_far, pot_after, seat=None, pos=None, action=None,
          amount=None, is_hero=False, coach=None, **extra) -> dict:
    step = {"type": type_, "seat": seat, "pos": pos, "action": action, "amount": amount,
            "street": street, "board_so_far": list(board_so_far), "pot_after": pot_after,
            "is_hero": is_hero, "coach": coach}
    step.update(extra)
    return step


# ---------------------------------------------------------------- the compiler
def compile_replay(hand_record: dict, decision_records: list[dict] | None = None) -> dict:
    """Compile a build_hand_record dict (+ graded P0 decision records) into ordered
    animation steps. Pure: reconstructs blinds/pot/board from the record alone.

    Returns {hand_no, button, sb, bb, human_seat, positions, hero_hole, board,
             steps: [...], result, net, final_pot}.
    """
    rec = hand_record
    positions = _int_keys(rec.get("positions"))
    n = len(positions) or 6
    button, sb, bb = rec["button"], rec["sb"], rec["bb"]
    human_seat = rec.get("human_seat")
    board = list(rec.get("board") or [])
    holes = _int_keys(rec.get("hole"))
    hero_hole = holes.get(human_seat) if human_seat is not None else None
    result = rec.get("result") or {}
    coach_queue = _decisions_by_street(decision_records or [], rec.get("hand_no"))

    steps: list[dict] = []
    committed: dict[int, int] = {}  # per-street commitment (reset on each street change)
    pot = 0
    street = "preflop"

    def reveal_through(target: str) -> None:
        """Emit 'street' steps (with their new cards) up to and including target."""
        nonlocal street
        while STREETS.index(street) < STREETS.index(target):
            nxt = STREETS[STREETS.index(street) + 1]
            if len(board) < BOARD_LEN[nxt]:
                return  # record's runout ended earlier (hand folded out)
            cards = board[BOARD_LEN[street]:BOARD_LEN[nxt]]
            street = nxt
            committed.clear()  # table.py _close_round resets street commits
            steps.append(_step("street", street, board[:BOARD_LEN[street]], pot, cards=cards))

    # 1) hole-card deal (hero only — bot holes stay hidden) + 2) blinds (re-derived,
    #    table.py:115-116: SB=button+1, BB=button+2, dropped from the record)
    steps.append(_step("deal", "preflop", [], 0, seat=human_seat,
                       pos=positions.get(human_seat), is_hero=human_seat is not None,
                       cards=hero_hole))
    for blind_seat, blind_amt, label in (((button + 1) % n, sb, "sb"),
                                         ((button + 2) % n, bb, "bb")):
        committed[blind_seat] = blind_amt
        pot += blind_amt
        steps.append(_step("blinds", "preflop", [], pot, seat=blind_seat,
                           pos=positions.get(blind_seat), action=label, amount=blind_amt,
                           is_hero=blind_seat == human_seat))

    # 3) actions, with street reveals interleaved by each action's street tag
    for act in rec.get("actions") or []:
        if act.get("street") != street:
            reveal_through(act["street"])
        seat = act["seat"]
        name, amount = act["action"], act.get("amount")
        if name == "call":                       # 'amount' = chips ADDED (table.py:170-172)
            committed[seat] = committed.get(seat, 0) + (amount or 0)
            pot += amount or 0
        elif name in ("bet", "raise"):           # 'amount' = street commit-TO total (:189-190)
            pot += (amount or 0) - committed.get(seat, 0)
            committed[seat] = amount or 0
        is_hero = bool(act.get("is_human")) or seat == human_seat
        coach = None
        if is_hero:
            queue = coach_queue.get(street)
            coach = _coach_from(queue.pop(0)) if queue else None
        steps.append(_step("action", street, board[:BOARD_LEN[street]], pot, seat=seat,
                           pos=act.get("pos") or positions.get(seat), action=name,
                           amount=amount, is_hero=is_hero, coach=coach))

    # 4) silent runout: streets with no actions (all-in earlier) — append remaining reveals
    for target in reversed(STREETS):
        if len(board) >= BOARD_LEN[target]:
            reveal_through(target)
            break

    # 5) showdown/payout step — the ONE step where the pot leaves the table.
    #    Bot holes only via result['shown'] when reveal is truthy (mucking respected).
    shown = result.get("shown") if result.get("reveal") else None
    steps.append(_step("showdown", street, board[:BOARD_LEN[street]], 0,
                       winners=result.get("winners") or [], reason=result.get("reason"),
                       shown=shown or {}))

    return {
        "hand_no": rec.get("hand_no"), "button": button, "sb": sb, "bb": bb,
        "human_seat": human_seat, "positions": positions, "hero_hole": hero_hole,
        "board": board, "steps": steps, "result": result,
        "net": _int_keys(rec.get("net")), "final_pot": pot,
    }


# ---------------------------------------------------------------- JSONL loading
def load_last_hand(session_path, decisions_path) -> tuple[dict, list[dict]]:
    """Read the LAST hand record from the session JSONL + its decision records.

    Raises ValueError('no hand yet') when the session file is missing/empty; a missing
    decisions file is graceful (returns []) — replay then shows played actions without
    recommendations."""
    session_path, decisions_path = Path(session_path), Path(decisions_path)
    lines = []
    if session_path.exists():
        lines = [ln for ln in session_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError("no hand yet")
    hand_record = json.loads(lines[-1])
    hand_no = hand_record.get("hand_no")

    decisions: list[dict] = []
    if decisions_path.exists():
        for ln in decisions_path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            dec = json.loads(ln)
            same_hand = (dec.get("hand_no") == hand_no if "hand_no" in dec
                         else str(dec.get("hand_id")) == str(hand_no) if "hand_id" in dec
                         else False)
            if same_hand:
                decisions.append(dec)
    return hand_record, decisions


# ---------------------------------------------------------------- selftest
def _synthetic_hand() -> tuple[dict, list[dict]]:
    """3-handed hand, hero=BB(2), button=0: BTN raises to 300, SB folds, hero calls;
    flop hero jams (bet TO 9700), BTN calls -> silent turn+river runout -> showdown.
    Exactly 2 hero decisions (preflop call, flop bet). Chips: 50/100 blinds."""
    rec = {
        "hand_no": 7, "button": 0, "sb": 50, "bb": 100, "human_seat": 2,
        "positions": {"0": "BTN", "1": "SB", "2": "BB"},
        "hole": {"0": ["Ah", "Kh"], "1": ["7d", "2c"], "2": ["Qs", "Qd"]},
        "board": ["Qh", "8s", "3c", "6d", "Jc"],
        "actions": [
            {"street": "preflop", "seat": 0, "pos": "BTN", "action": "raise", "amount": 300, "is_human": False},
            {"street": "preflop", "seat": 1, "pos": "SB", "action": "fold", "amount": None, "is_human": False},
            {"street": "preflop", "seat": 2, "pos": "BB", "action": "call", "amount": 200, "is_human": True},
            {"street": "flop", "seat": 2, "pos": "BB", "action": "bet", "amount": 9700, "is_human": True},
            {"street": "flop", "seat": 0, "pos": "BTN", "action": "call", "amount": 9700, "is_human": False},
        ],
        "result": {"reason": "showdown", "pot": 20050, "reveal": True,
                   "winners": [{"seat": 2, "name": "You", "amount": 20050, "rank": "Three of a Kind"}],
                   "shown": {"2": {"hole": ["Qs", "Qd"], "rank": "Three of a Kind"}},
                   "board": ["Qh", "8s", "3c", "6d", "Jc"]},
        "net": {"0": -10000, "1": -50, "2": 10050},
    }
    decisions = [
        {"hand_no": 7, "street": "preflop", "human_action": "call", "oracle_action": "raise",
         "grade": "ok", "erklaerung_kurz": "Call and raise are both fine — GTO mixes here."},
        {"hand_no": 7, "street": "flop", "human_action": "bet", "oracle_action": "bet",
         "grade": "ok", "erklaerung_kurz": "Top set on a dry board — pure value."},
    ]
    return rec, decisions


def _selftest():
    import tempfile

    rec, decisions = _synthetic_hand()
    out = compile_replay(rec, decisions)
    steps = out["steps"]

    # json round-trip (the route will serialize this): the whole payload serializes,
    # the steps round-trip byte-exactly (seat-keyed top-level dicts become str keys — JSON)
    round_tripped = json.loads(json.dumps(out, ensure_ascii=False))
    assert round_tripped["steps"] == steps, "steps must be pure JSON-typed"
    assert round_tripped["final_pot"] == out["final_pot"]

    # chronology: street monotonic across all steps
    order = [STREETS.index(s["street"]) for s in steps]
    assert order == sorted(order), f"street not monotonic: {[s['street'] for s in steps]}"

    # pot non-decreasing except the showdown payout step
    pots = [s["pot_after"] for s in steps]
    assert all(a <= b for a, b in zip(pots[:-2], pots[1:-1])), f"pot decreased mid-hand: {pots}"
    assert steps[-1]["type"] == "showdown" and steps[-1]["pot_after"] == 0

    # pot math: raise sets the TO-total, call adds chips (the session_log merge trap)
    # blinds 150 -> BTN to 300 = 450 -> BB call +200 = 650 -> jam TO 9700 = 10350 -> call +9700
    assert out["final_pot"] == 20050 == rec["result"]["pot"], out["final_pot"]
    action_pots = [s["pot_after"] for s in steps if s["type"] == "action"]
    assert action_pots == [450, 450, 650, 10350, 20050], action_pots

    # board reveals 0/3/4/5 (turn+river appended after the last action = silent runout)
    lens = sorted({len(s["board_so_far"]) for s in steps})
    assert lens == [0, 3, 4, 5], lens
    street_steps = [s for s in steps if s["type"] == "street"]
    assert [s["street"] for s in street_steps] == ["flop", "turn", "river"]
    last_action_i = max(i for i, s in enumerate(steps) if s["type"] == "action")
    assert all(i > last_action_i for i, s in enumerate(steps)
               if s["type"] == "street" and s["street"] in ("turn", "river"))

    # every hero decision carries coach; bot steps never do
    hero_actions = [s for s in steps if s["type"] == "action" and s["is_hero"]]
    assert len(hero_actions) == 2 and all(s["coach"] for s in hero_actions)
    assert all(s["coach"]["played"] and s["coach"]["grade"] for s in hero_actions)
    assert all(s["coach"] is None for s in steps if s["type"] == "action" and not s["is_hero"])

    # hole hygiene: hero hole + shown winner only; the folded SB's 7d2c must NOT leak
    assert out["hero_hole"] == ["Qs", "Qd"] and "hole" not in out
    assert "7d" not in json.dumps(out), "unrevealed bot hole leaked"

    # blinds re-derived from the button: SB=seat1 posts 50, BB=seat2 posts 100
    blinds = [s for s in steps if s["type"] == "blinds"]
    assert [(s["seat"], s["amount"]) for s in blinds] == [(1, 50), (2, 100)]
    assert steps[0]["type"] == "deal" and blinds[1]["is_hero"]

    # graceful without decisions: same steps, coach=None everywhere
    bare = compile_replay(rec, [])
    assert all(s["coach"] is None for s in bare["steps"])
    assert len(bare["steps"]) == len(steps)

    # fold-ends-hand case: no board, no street steps, showdown reason=fold, no holes shown
    fold_rec = dict(rec, board=[], hole={"2": ["Qs", "Qd"]}, net={"0": -50, "1": -100, "2": 150},
                    actions=[{"street": "preflop", "seat": 0, "pos": "BTN", "action": "fold",
                              "amount": None, "is_human": False},
                             {"street": "preflop", "seat": 1, "pos": "SB", "action": "fold",
                              "amount": None, "is_human": False}],
                    result={"reason": "fold", "pot": 150, "reveal": False,
                            "winners": [{"seat": 2, "name": "You", "amount": 150}]})
    fold_out = compile_replay(fold_rec, [])
    assert fold_out["final_pot"] == 150
    assert not any(s["type"] == "street" for s in fold_out["steps"])
    assert fold_out["steps"][-1]["shown"] == {}

    # load_last_hand: last record wins, decisions filtered to it; missing session -> ValueError
    with tempfile.TemporaryDirectory() as tmp:
        sess, decs = Path(tmp) / "session_t.jsonl", Path(tmp) / "decisions_t.jsonl"
        other = dict(rec, hand_no=6)
        sess.write_text(json.dumps(other) + "\n" + json.dumps(rec) + "\n", encoding="utf-8")
        decs.write_text("\n".join(json.dumps(d) for d in
                                  [dict(decisions[0], hand_no=6)] + decisions) + "\n",
                        encoding="utf-8")
        got_rec, got_decs = load_last_hand(sess, decs)
        assert got_rec["hand_no"] == 7 and len(got_decs) == 2
        # missing decisions file is graceful; missing session file is not
        _, none_decs = load_last_hand(sess, Path(tmp) / "absent.jsonl")
        assert none_decs == []
        try:
            load_last_hand(Path(tmp) / "absent.jsonl", decs)
            raise AssertionError("expected ValueError('no hand yet')")
        except ValueError as e:
            assert str(e) == "no hand yet"

    print("replay selftest: all checks PASS")


if __name__ == "__main__":
    _selftest()
