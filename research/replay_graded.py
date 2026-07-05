# -*- coding: utf-8 -*-
"""Deterministic REGRESSION GATE over the GTOW-graded disaster hands (data/gtow_grades/hu_leaks_ev2.json).

WHY: the graded rows are the worst EV-losers of the seed-55 export (research/pokerstars_export.py ->
hu_hands_1500.txt), each hero decision graded by the GTOW Analyzer. The export is fully deterministic:
the game deck is shuffled ONCE per hand inside HeadsUpGame.start_hand (actions never touch the game RNG)
and the deciders are seeded per hand (hero 100+idx, villain 200+idx). So we can regenerate the SAME 1500
deals, locate each graded hand by (hero hole + position + board prefix), and re-ask the CURRENT config at
every graded decision point — a $0, minutes-long, deterministic gate instead of a noisy fresh AIVAT run:
  * a config that FIXES a graded BLUNDER shows up as n_now_different;
  * a config that CHANGES a decision GTOW graded BEST/CORRECT shows up as n_regressions_on_correct.

  python -m research.replay_graded --config head    # no mode flags = the shipped default
  python -m research.replay_graded --config gto     # POKERB_GTO_MODE=1
  python -m research.replay_graded --config prince  # POKERB_PRINCE=1

NOTES: POKERB_RESOLVER=0 / POKERB_TURN_RESOLVER=0 are FORCED (speed + determinism) — resolver-ON river/turn
behavior is not covered here. Comparisons after a hero deviation are marked TAINTED (the villain then sees a
different state, so the later graded points are no longer the original spots). Env flags are read at import
time -> all pokerbot imports happen INSIDE main() after the env is set (mirrors pokerstars_export's
_apply_gto_mode-first pattern).
"""
from __future__ import annotations

import argparse
import json
import os
import re

EXPORT_SEED = 55                 # the export run that produced hu_hands_1500.txt (the graded upload)
EXPORT_N = 1500
GRADES_PATH = "data/gtow_grades/hu_leaks_ev2.json"
CACHE_PATH = "data/gtow_grades/replay_index.json"   # deal-index cache: matching is config-independent
GUARD_ACTIONS = 400              # same runaway-hand guard as pokerstars_export.play_hand

BAD_GRADES = {"BLUNDER", "WRONG_MOVE", "MISTAKE"}   # flagged: the gate HOPES these change
GOOD_GRADES = {"BEST_MOVE", "CORRECT_MOVE"}         # a change here = the REGRESSION signal
STREET_KEYS = (("pf", "preflop"), ("fl", "flop"), ("tu", "turn"), ("ri", "river"))

# graded token = ACTION[:GRADE]; ACTION = letter + optional size-in-bb or AI (all-in): X, C, F, B, R10, RAI
_ACTION_RE = re.compile(r"^([XCFBR])(AI|[0-9.]+)?$")
SIZE_TOLERANCE_BB = 0.011        # HH dollars print 2 decimals -> bb sizes are exact to 0.01

CONFIGS = ("head", "gto", "prince")
_MODE_FLAGS = ("POKERB_GTO_MODE", "POKERB_PRINCE")


# --------------------------------------------------------------- graded-row parsing
def chunk_cards(s: str) -> list[str]:
    """'8d5d2hKcQs' -> ['8d','5d','2h','Kc','Qs'] (the JSON concatenates 2-char engine-format cards)."""
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def parse_street_tokens(spec: str) -> list[dict]:
    """'X:BEST_MOVE B F:BLUNDER' -> HERO decisions only (a grade marks a hero action; ungraded = villain)."""
    out = []
    for tok in spec.split():
        act, _, grade = tok.partition(":")
        m = _ACTION_RE.match(act)
        if not m:
            raise ValueError(f"unparseable graded action {tok!r} in {spec!r}")
        if not grade:
            continue                                # villain action — context only, never compared
        size = m.group(2)
        out.append({"letter": m.group(1), "allin": size == "AI",
                    "size_bb": float(size) if size and size != "AI" else None, "grade": grade})
    return out


def hero_decisions(row: dict) -> list[dict]:
    """All graded hero decisions of a row in play order, tagged street + per-street ordinal."""
    decs = []
    for key, street in STREET_KEYS:
        for ordinal, d in enumerate(parse_street_tokens(row.get(key) or "")):
            decs.append({**d, "street": street, "ordinal": ordinal})
    return decs


# --------------------------------------------------------------- deterministic re-deal + matching
def deal_hand(g, stack: int) -> tuple[list[str], str, list[str]]:
    """start_hand on reset stacks; return (hero_hole, hero_pos, full 5-card board). The deck is shuffled
    once in start_hand and deal() pops from the END -> the future flop/turn/river are the last 5 cards,
    known BEFORE any action (so matching needs no bot calls at all)."""
    g.players[0].stack = g.players[1].stack = stack
    g.start_hand()
    d = g.deck.cards
    full_board = [d[-1], d[-2], d[-3], d[-4], d[-5]]
    pos = "SB" if g.button == 0 else "BB"           # hero is ALWAYS seat 0 in the export
    return list(g.players[0].hole), pos, full_board


def fold_out(g) -> None:
    """End a non-matched hand instantly. One fold ends a HU hand and consumes NO game RNG."""
    if not g.hand_over:
        g.act("fold")


def row_matches_deal(row: dict, hole: list[str], pos: str, full_board: list[str]) -> bool:
    if set(chunk_cards(row["hand"])) != set(hole) or row["pos"] != pos:
        return False
    board = row.get("board")
    if not board:
        return True                                 # preflop-only row -> no board constraint
    cards = chunk_cards(board)
    # GTOW normalizes the FLOP to rank-descending order (every graded flop is sorted) -> compare the
    # flop as a set; turn/river are positional stages and stay exact.
    if set(cards[:3]) != set(full_board[:3]):
        return False
    return cards[3:] == full_board[3:len(cards)]


def scan_matches(px, rows: list[dict]) -> tuple[dict[int, int], list[str]]:
    """Full re-deal of the export -> {row_index: deal_index}. A row matching 0 or >1 deals (or two rows
    claiming one deal) is reported and SKIPPED — never silently guessed."""
    g = px.HeadsUpGame(names=("P0", "P1"), starting_stack=px.STACK, sb=px.SB, bb=px.BB, seed=EXPORT_SEED)
    candidates: dict[int, list[int]] = {k: [] for k in range(len(rows))}
    for i in range(EXPORT_N):
        hole, pos, full_board = deal_hand(g, px.STACK)
        for k, row in enumerate(rows):
            if row_matches_deal(row, hole, pos, full_board):
                candidates[k].append(i)
        fold_out(g)

    matched: dict[int, int] = {}
    problems: list[str] = []
    for k, row in enumerate(rows):
        label = f"row {k} ({row['hand']} {row['pos']} board={row.get('board')})"
        if len(candidates[k]) == 1:
            matched[k] = candidates[k][0]
        else:
            problems.append(f"{label}: {len(candidates[k])} deals match ({candidates[k]}) -> SKIPPED")
    claims: dict[int, int] = {}
    for k, i in list(matched.items()):
        if i in claims:                             # duplicate/ambiguous rows on one deal -> drop both
            problems.append(f"rows {claims[i]} and {k} both match deal {i} -> both SKIPPED")
            matched.pop(k, None)
            matched.pop(claims[i], None)
        claims[i] = k
    return matched, problems


def _row_identities(rows: list[dict]) -> list[dict]:
    return [{"hand": r["hand"], "pos": r["pos"], "board": r.get("board")} for r in rows]


def load_cache(rows: list[dict]):
    """Cached row->deal index, invalidated on any seed/n/rows change (stale grades must force a rescan)."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if c.get("seed") != EXPORT_SEED or c.get("n") != EXPORT_N or c.get("rows") != _row_identities(rows):
        return None
    return {int(k): v for k, v in c["matched"].items()}, list(c.get("problems", []))


def save_cache(rows: list[dict], matched: dict[int, int], problems: list[str]) -> None:
    payload = {"seed": EXPORT_SEED, "n": EXPORT_N, "rows": _row_identities(rows),
               "matched": {str(k): v for k, v in matched.items()}, "problems": problems}
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)


# --------------------------------------------------------------- replay with a per-decision tap
def describe_action(g, action: str, amount) -> dict:
    """Engine-labeled view of hero's choice = the HH letter GTOW graded (B vs R by is_bet; the raise
    target clamped exactly like game.act; all-in iff the clamped target == raise_max)."""
    la = g.legal_actions()
    if action == "fold":
        return {"letter": "F", "allin": False, "size_bb": None}
    if action == "check":
        return {"letter": "X", "allin": False, "size_bb": None}
    if action == "call":
        caller = g.players[la["to_act"]]
        return {"letter": "C", "allin": la["call_amount"] == caller.stack, "size_bb": None}
    target = la["raise_max"] if (action == "allin" or amount is None) else int(amount)
    target = max(la["raise_min"], min(target, la["raise_max"]))
    return {"letter": "B" if la["is_bet"] else "R", "allin": target == la["raise_max"],
            "size_bb": target / 100.0}


def replay_hand(px, g, idx: int) -> dict[str, list[dict]]:
    """pokerstars_export.play_hand with a hero tap: same deciders/seeds, hero actions recorded per street.
    Expects the hand already started (deal_hand) so the deal identity was verified first."""
    deciders = {0: px.hero_decider(0, seed=100 + idx), 1: px.villain_decider(1, seed=200 + idx)}
    taken: dict[str, list[dict]] = {street: [] for _, street in STREET_KEYS}
    guard = 0
    while not g.hand_over:
        st = g.state()
        actor = st["to_act"]
        action, amount = deciders[actor](st)
        if actor == 0:
            taken[st["street"]].append(describe_action(g, action, amount))
        g.act(action, amount)
        guard += 1
        if guard > GUARD_ACTIONS:
            break
    return taken


def compare(decisions: list[dict], taken: dict[str, list[dict]]) -> list[dict]:
    """Align the k-th graded hero decision on a street with the k-th replayed hero action there.
    clean = every EARLIER graded decision was reached and replayed identically (same letter/all-in and,
    where the grade string carries a size, the same size) -> this decision still sees the original state
    (the villain is deterministic per seed). After any deviation the rest is TAINTED, never dropped."""
    results = []
    clean = True
    for dec in decisions:
        street_actions = taken[dec["street"]]
        got = street_actions[dec["ordinal"]] if dec["ordinal"] < len(street_actions) else None
        if got is None:
            verdict = "not_reached"                 # the replayed line ended/diverged before this spot
        else:
            same = got["letter"] == dec["letter"]
            if same and dec["letter"] in ("B", "R"):
                if dec["allin"]:
                    same = got["allin"]             # a graded shove (RAI) must still be a shove
                elif dec["size_bb"] is not None:
                    # BUG-HUNT FIX: compare sizes for the VERDICT too (a sizing-only change on a graded sized
                    # raise is a real deviation, not "same"); a shove now is also a change.
                    same = (not got["allin"] and got["size_bb"] is not None
                            and abs(got["size_bb"] - dec["size_bb"]) <= SIZE_TOLERANCE_BB)
                # plain 'B' (the grade string carries no size) -> the letter is all we can verify
            verdict = "same" if same else "changed"
        results.append({**dec, "got": got, "verdict": verdict, "clean": clean})
        if verdict != "same":
            clean = False
        elif dec["letter"] in ("B", "R") and not dec["allin"] and (
                dec["size_bb"] is None or got["size_bb"] is None
                or abs(got["size_bb"] - dec["size_bb"]) > SIZE_TOLERANCE_BB):
            # BUG-HUNT FIX: graded 'B' tokens carry NO size -> a same-letter bet of UNVERIFIABLE size must
            # taint downstream comparisons (villain deterministically responds to the size we cannot check).
            clean = False
    return results


# --------------------------------------------------------------- report
def fmt_action(a: dict) -> str:
    if a["allin"] and a["letter"] in ("B", "R"):
        return a["letter"] + "AI"
    if a["size_bb"] is not None:
        return f"{a['letter']}{a['size_bb']:g}"
    return a["letter"]


def print_report(config: str, rows: list[dict], matched: dict[int, int], reports: dict[int, list[dict]]) -> None:
    header = (f"{'hand':<20} {'street':<8} {'graded':<8} {'grade':<13} {'now':<8} "
              f"{'verdict':<12} {'state':<8} evloss")
    flagged_lines, regress_lines = [], []
    n = {"flag": 0, "flag_same": 0, "flag_chg": 0, "flag_chg_clean": 0, "flag_nr": 0,
         "good": 0, "good_chg": 0, "good_chg_clean": 0, "good_nr": 0}
    ignored: dict[str, int] = {}
    for k in sorted(matched, key=lambda k: matched[k]):
        row = rows[k]
        label = f"{row['hand']} {row['pos']} {row['pot_type']}"
        for r in reports[k]:
            now = "-" if r["got"] is None else fmt_action(r["got"])
            state = "clean" if r["clean"] else "TAINTED"
            line = (f"{label:<20} {r['street']:<8} {fmt_action(r):<8} {r['grade']:<13} {now:<8} "
                    f"{r['verdict']:<12} {state:<8} {row['ev_loss']}")
            if r["grade"] in BAD_GRADES:
                n["flag"] += 1
                flagged_lines.append(line)
                if r["verdict"] == "same":
                    n["flag_same"] += 1
                elif r["verdict"] == "changed":
                    n["flag_chg"] += 1
                    n["flag_chg_clean"] += r["clean"]
                else:
                    n["flag_nr"] += 1
            elif r["grade"] in GOOD_GRADES:
                n["good"] += 1
                if r["verdict"] == "changed":
                    n["good_chg"] += 1
                    n["good_chg_clean"] += r["clean"]
                    regress_lines.append(line)
                elif r["verdict"] == "not_reached":
                    n["good_nr"] += 1
                    regress_lines.append(line)
            else:
                ignored[r["grade"]] = ignored.get(r["grade"], 0) + 1

    print(f"\n=== FLAGGED DECISIONS (graded {'/'.join(sorted(BAD_GRADES))}) ===")
    print(header)
    for line in flagged_lines:
        print(line)
    print(f"\n=== REGRESSION CANDIDATES (graded BEST/CORRECT, no longer replayed the same) ===")
    print(header)
    for line in regress_lines or ["(none)"]:
        print(line)
    print(f"\n=== SUMMARY config={config} ===")
    print(f"  matched hands            : {len(matched)}/{len(rows)}")
    print(f"  n_flagged_decisions      : {n['flag']}")
    print(f"  n_now_different          : {n['flag_chg']}  (clean {n['flag_chg_clean']} / "
          f"tainted {n['flag_chg'] - n['flag_chg_clean']})  <- potential fixes")
    print(f"  n_flagged_not_reached    : {n['flag_nr']}  (line diverged before the spot)")
    print(f"  n_flagged_same           : {n['flag_same']}")
    print(f"  n_regressions_on_correct : {n['good_chg']}  (clean {n['good_chg_clean']} / "
          f"tainted {n['good_chg'] - n['good_chg_clean']}; of {n['good']} BEST/CORRECT graded)")
    print(f"  n_good_not_reached       : {n['good_nr']}")
    if ignored:
        print(f"  ignored grades           : " + ", ".join(f"{g} {c}" for g, c in sorted(ignored.items())))


# --------------------------------------------------------------- entry
def _bootstrap_env(config: str) -> None:
    """Set the arm's env BEFORE any pokerbot import (strategy flags are read at import time)."""
    for flag in _MODE_FLAGS:
        os.environ.pop(flag, None)                  # a stray shell flag must not contaminate the arm
    if config == "gto":
        os.environ["POKERB_GTO_MODE"] = "1"
    elif config == "prince":
        os.environ["POKERB_PRINCE"] = "1"
    os.environ["POKERB_RESOLVER"] = "0"             # forced OFF: speed + determinism (see module docstring)
    os.environ["POKERB_TURN_RESOLVER"] = "0"


def main() -> None:
    ap = argparse.ArgumentParser(description="Regression gate: replay the GTOW-graded hands under a config.")
    ap.add_argument("--config", choices=CONFIGS, default="head")
    ap.add_argument("--rescan", action="store_true", help="ignore the cached match index and rescan")
    args = ap.parse_args()
    _bootstrap_env(args.config)

    import research.pokerstars_export as px         # AFTER env: this applies gto_mode + imports strategy
    from pokerbot.strategy.gto_mode import fingerprint

    print(f"replay_graded  config={args.config}  export seed={EXPORT_SEED} n={EXPORT_N}  "
          f"resolvers=OFF (forced: speed + determinism)")
    print("fingerprint:", fingerprint())
    with open(GRADES_PATH, encoding="utf-8") as f:
        rows = json.load(f)

    cached = None if args.rescan else load_cache(rows)
    if cached is None:
        matched, problems = scan_matches(px, rows)
        save_cache(rows, matched, problems)
        print(f"match scan: {len(matched)}/{len(rows)} rows matched -> cached to {CACHE_PATH}")
    else:
        matched, problems = cached
        print(f"match index: {len(matched)}/{len(rows)} rows (cache {CACHE_PATH}; --rescan to rebuild)")
    for p in problems:
        print("  MATCH PROBLEM:", p)

    idx_to_row = {i: k for k, i in matched.items()}
    last_deal = max(idx_to_row) if idx_to_row else -1
    g = px.HeadsUpGame(names=("P0", "P1"), starting_stack=px.STACK, sb=px.SB, bb=px.BB, seed=EXPORT_SEED)
    reports: dict[int, list[dict]] = {}
    for i in range(EXPORT_N):
        if i > last_deal:
            break                                   # deals are independent; nothing graded remains
        hole, pos, full_board = deal_hand(g, px.STACK)
        k = idx_to_row.get(i)
        if k is None:
            fold_out(g)
            continue
        if not row_matches_deal(rows[k], hole, pos, full_board):
            raise SystemExit(f"deal {i} no longer matches row {k} ({rows[k]['hand']}) -> stale cache, "
                             f"rerun with --rescan")
        reports[k] = compare(hero_decisions(rows[k]), replay_hand(px, g, i))
    print_report(args.config, rows, matched, reports)


if __name__ == "__main__":
    main()
