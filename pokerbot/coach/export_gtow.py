"""Trainer-Session -> PokerStars-6-max-HH fuer den GTOW-Analyzer (P4-B, externe Zweitmeinung).

WHY (docs/doctrine/TRAINER_DESIGN.md par.4): die Menschen-Haende einer Trainer-Session werden im
PokerStars-Format exportiert, damit der GTOW-Analyzer unsere eigenen Grades unabhaengig
gegenprueft. Wiederverwendet wird research/sixmax_export.format_hand (verifizierte Signatur
format_hand(hand_id, dt, h) mit h = {names, button, holes, history, result}).

RUNOUT-FIX (Code schlaegt Plan): sixmax_export.format_hand emittiert Street-Header NUR aus
'deal'-Events — der Post-hoc-Runout-Fix existiert nur im HU-Exporter (pokerstars_export.py:151-162),
NICHT im 6-max-Exporter. All-in-Runouts werden silent gedealt (table.py:223, keine deal-Events),
darum injiziert dieser Export fehlende deal-Events synthetisch VOR dem Formatieren.

OFF-TREE-ENTSCHEIDUNG (dokumentiert, docs/plans/TRAINER_PLAN.md P4-B Schritt 5): exportiert werden die ROHEN
Groessen des Menschen — nachtraegliches Snappen (_snap_hero) wuerde die Pot-Buchhaltung aller
Folgeaktionen desynchronisieren. Stattdessen warnt der Export pro Hero-Bet, deren Pot-Fraktion
> 10% von der naechsten Tree-Groesse abweicht: 'diese Spots graded der Analyzer degradiert/nicht'.

CRLF PFLICHT: der Analyzer parst nur CRLF-Dateien (pokerstars_export.py:243-246) — LF-only
Uploads scheitern SILENT. Hand-ID-Gesetz: IDs verbrennen beim ERSTEN Kontakt (auch bei
gescheiterten Uploads) — idbase wird frisch abgeleitet, gegen data/trainer/hh_ledger.jsonl
kollisionsgeprueft und VOR dem Schreiben ins Ledger eingetragen. Nie idbase wiederverwenden.

Run:  python -m pokerbot.coach.export_gtow <session.jsonl|latest> [out.txt]
      python -m pokerbot.coach.export_gtow --selftest
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

SB, BB, STACK = 50, 100, 10000        # must match sixmax_export geometry or the HH stack lines lie
ID_FLOOR = 50000                      # burned legacy range ends far below this (STATE ledger)
ID_SPACING = 2000                     # reserved block per export (Hand-ID-Gesetz)
OFFTREE_WARN_FRAC = 0.10              # pot-fraction deviation that triggers the gradability warning
STREET_CARDS = {"flop": 3, "turn": 4, "river": 5}
LEDGER_NAME = "hh_ledger.jsonl"


class ExportError(ValueError):
    """Session verletzt die Export-Geometrie/-Annahmen — Export wird VERWEIGERT (klare Meldung)."""


def _ledger_path() -> Path:
    from pokerbot import config
    return config.DATA_DIR / "trainer" / LEDGER_NAME


def _load_records(session_path: Path) -> list[dict]:
    if not session_path.exists():
        raise ExportError(f"Session-Datei fehlt: {session_path}")
    recs = []
    for line in session_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            recs.append(json.loads(line))
    if not recs:
        raise ExportError(f"Session-Datei ist leer: {session_path}")
    return recs


def _geometry_guard(rec: dict) -> None:
    """SB/BB/STACK = 50/100/10000 sind Exporter-Konstanten; andere Geometrie => HH-Zeilen luegen.
    (Der Reset-Stack 10000 steht nicht im Record — Session mit stack_bb=100 ist die Annahme.)"""
    if rec.get("bb") != BB or rec.get("sb") != SB:
        raise ExportError(f"Hand {rec.get('hand_no')}: sb/bb = {rec.get('sb')}/{rec.get('bb')} passt "
                          f"nicht zur Export-Geometrie SB/BB/STACK = {SB}/{BB}/{STACK} — Export verweigert.")
    hs = rec.get("human_seat")
    if hs not in (None, 0):
        raise ExportError(f"Hand {rec.get('hand_no')}: human_seat={hs}, der Exporter markiert Sitz 0 "
                          "als Hero ('Dealt to') — Export verweigert.")


def _int_keyed(d: dict) -> dict:
    """JSON round-trips dict keys to strings; hand records are consumed both fresh and re-loaded."""
    return {int(k): v for k, v in d.items()}


def _ensure_runout_deals(history: list[dict], board: list[str]) -> list[dict]:
    """Inject synthetic deal events for silently-dealt runout streets (see RUNOUT-FIX docstring)."""
    dealt = {ev.get("street") for ev in history if ev.get("action") == "deal"}
    out = list(history)
    for street, need in STREET_CARDS.items():
        if len(board) >= need and street not in dealt:
            out.append({"action": "deal", "street": street, "board": board[:need]})
    return out


def _rebuild_history(rec: dict) -> list[dict]:
    """build_hand_record drops 'blinds'/'deal' events and merges raise-'to' with call-'amount'
    (session_log.py:14-22) — rebuild the table.history shape format_hand consumes."""
    board = rec.get("board") or []
    history: list[dict] = []
    cur_street = "preflop"
    for a in rec.get("actions", []):
        street, act, seat = a.get("street"), a.get("action"), a.get("seat")
        if street != cur_street and street in STREET_CARDS:
            history.append({"action": "deal", "street": street, "board": board[:STREET_CARDS[street]]})
            cur_street = street
        if act in ("bet", "raise"):
            history.append({"player": seat, "action": act, "street": street, "to": a.get("amount")})
        elif act == "call":
            history.append({"player": seat, "action": act, "street": street, "amount": a.get("amount") or 0})
        else:  # fold / check ('allin' never appears: table.act logs it as bet/raise, table.py:189)
            history.append({"player": seat, "action": act, "street": street})
    return history


def record_to_export(rec: dict) -> dict:
    """One hand record -> the {names, button, holes, history, result} dict format_hand consumes.
    Prefers the planned session_log 'export' extension (P4-B step 1, parallel builder); falls back
    to reconstruction from the shipped build_hand_record fields."""
    _geometry_guard(rec)
    board = (rec.get("result") or {}).get("board") or rec.get("board") or []
    if isinstance(rec.get("export"), dict):
        h = dict(rec["export"])
        h["history"] = _ensure_runout_deals(list(h.get("history", [])), board)
        return h
    holes_d = _int_keyed(rec["hole"])
    n = max(holes_d) + 1
    holes = [holes_d.get(i, []) for i in range(n)]
    names = ["Hero"] + [f"Villain{i}" for i in range(1, n)]   # 'Dealt to Hero' marks seat 0
    history = _ensure_runout_deals(_rebuild_history(rec), board)
    return {"names": names, "button": rec["button"], "holes": holes,
            "history": history, "result": rec.get("result")}


def _offtree_warnings(rec: dict) -> list[str]:
    """Hero-Bets, deren Pot-Fraktion > OFFTREE_WARN_FRAC von der naechsten Tree-Groesse abweicht.
    Pot-Walk mit den verifizierten Semantiken: call-amount = added chips, raise-amount = TO-total."""
    from pokerbot.strategy import postflop as pf
    n = len(rec.get("positions", {})) or 6
    button = rec["button"]
    sb_i, bb_i = (button + 1) % n, (button + 2) % n
    pot = SB + BB
    committed = {sb_i: SB, bb_i: BB}
    cur_bet, cur_street = BB, "preflop"
    warnings = []
    for a in rec.get("actions", []):
        street, act, seat, amount = a.get("street"), a.get("action"), a.get("seat"), a.get("amount")
        if street != cur_street:
            committed, cur_bet, cur_street = {}, 0, street
        if act == "call":
            pot += amount or 0
            committed[seat] = committed.get(seat, 0) + (amount or 0)
            continue
        if act not in ("bet", "raise") or amount is None:
            continue
        pot_before = pot
        delta = amount - committed.get(seat, 0)
        if a.get("is_human") and street != "preflop" and pot_before > 0:
            if cur_bet == 0:                                   # first-in bet: tree pot-fractions
                snapped = pf.snap_to_tree(int(delta), pot_before, street)
                dev = abs(delta - snapped) / pot_before
            else:                                              # raise: increment over call, post-call pot
                to_call = cur_bet - committed.get(seat, 0)
                snapped = pf.snap_raise_to_tree(int(amount), cur_bet, pot_before, to_call, street)
                dev = abs(amount - snapped) / pot_before
            if dev > OFFTREE_WARN_FRAC:
                warnings.append(f"Hand {rec.get('hand_no')} {street}: Hero {act} {amount} "
                                f"(Abweichung {dev:.0%} Pot von Tree-Groesse {snapped}) -- "
                                "diesen Spot graded der Analyzer degradiert/nicht.")
        pot += delta
        committed[seat] = amount
        cur_bet = amount
    return warnings


def _fresh_idbase(ledger_path: Path) -> int:
    """Timestamp-derived idbase >= ID_FLOOR, bumped past any ledger-reserved block (never reuse)."""
    reserved = []
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                reserved.append(int(e["idbase"]))
    idbase = ID_FLOOR + (int(time.time()) % 10 ** 7) * ID_SPACING
    while any(abs(idbase - r) < ID_SPACING for r in reserved):
        idbase += ID_SPACING
    return idbase


def export_session(session_path: Path, out_path: Path | None = None,
                   ledger_path: Path | None = None) -> dict:
    """Convert one trainer session JSONL to an uploadable CRLF PokerStars-HH file."""
    from pokerbot.web.session_log import append_record
    from research.sixmax_export import format_hand   # verified: format_hand(hand_id, dt, h)

    ledger_path = ledger_path or _ledger_path()
    recs = _load_records(session_path)
    n = len(recs)
    if n > ID_SPACING:
        raise ExportError(f"{n} Haende > ID-Blockgroesse {ID_SPACING} — Export splitten.")
    idbase = _fresh_idbase(ledger_path)
    if out_path is None:
        out_path = _ledger_path().parent / f"trainer_hh_{time.strftime('%Y%m%d_%H%M%S')}.txt"

    # IDs burn on FIRST contact: reserve in the ledger BEFORE writing/uploading anything
    append_record(ledger_path, {"idbase": idbase, "n_hands": n, "file": str(out_path),
                                "session": str(session_path),
                                "ts": time.strftime("%Y-%m-%d %H:%M:%S")})

    base_dt = datetime.datetime.now() - datetime.timedelta(minutes=2 * n)
    blocks, warnings = [], []
    for i, rec in enumerate(recs):
        h = record_to_export(rec)
        blocks.append(format_hand(idbase + i, base_dt + datetime.timedelta(minutes=2 * i), h))
        warnings.extend(_offtree_warnings(rec))

    text = "\n\n".join(blocks) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # newline='\r\n': the Analyzer only parses CRLF (pokerstars_export.py:243-246) — pin on every platform
    with open(out_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)

    print(f"WROTE {n} Haende -> {out_path}  (idbase {idbase}, Ledger {ledger_path})")
    for w in warnings:
        print(f"  OFF-TREE: {w}")
    print("Upload-Workflow: GTO Wizard -> Analyze -> Upload hands (PokerStars-Format).")
    print("Merke: CRLF ist Pflicht; Hand-IDs verbrennen beim ERSTEN Kontakt -- "
          "diesen idbase nie wiederverwenden (Ledger-Eintrag ist gesetzt).")
    return {"n_hands": n, "idbase": idbase, "out": str(out_path), "warnungen": warnings}


def _latest_session() -> Path:
    from pokerbot import config
    cands = sorted((config.DATA_DIR / "sessions").glob("session_*.jsonl"))
    if not cands:
        raise ExportError("Keine session_*.jsonl unter data/sessions gefunden.")
    return cands[-1]


# ------------------------------------------------------------------------------------ selftest
def _selftest() -> int:
    """Synthetic session via the real Table engine (schema fidelity for free): a snapped-bet hand,
    an off-tree-bet hand, an all-in runout hand; then CRLF/section/ledger/geometry asserts."""
    import tempfile

    from pokerbot.engine.table import Table
    from pokerbot.web.session_log import append_record, build_hand_record

    tmp = Path(tempfile.mkdtemp(prefix="export_gtow_selftest_"))
    session, ledger, out1, out2 = (tmp / "session_t.jsonl", tmp / LEDGER_NAME,
                                   tmp / "hh1.txt", tmp / "hh2.txt")
    t = Table(["Du", "Ava", "Ben", "Cleo", "Dex", "Eve"], starting_stack=STACK, sb=SB, bb=BB,
              seed=11, human_seat=0)

    def play(hero_flop_bet: int | None, allin: bool) -> None:
        for s in t.seats:
            s.stack = STACK                                    # cash-game reset (exporter geometry)
        t.start_hand()
        allin_done = call_done = hero_bet_done = False
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 200:
            guard += 1
            la = t.legal_actions()
            i = la["to_act"]
            if allin:
                if not allin_done and la.get("can_raise"):
                    t.act("raise", la["raise_max"]); allin_done = True
                elif la.get("to_call", 0) > 0 and not call_done:
                    t.act("call"); call_done = True
                elif la.get("can_check"):
                    t.act("check")
                else:
                    t.act("fold")
                continue
            if (i == 0 and t.street == "flop" and not hero_bet_done
                    and la.get("can_raise") and t.current_bet == 0 and hero_flop_bet):
                t.act("bet", hero_flop_bet); hero_bet_done = True
            elif la.get("can_check"):
                t.act("check")
            elif la.get("can_call"):
                t.act("call")
            else:
                t.act("fold")
        append_record(session, build_hand_record(t))

    play(hero_flop_bet=450, allin=False)      # 0.75x pot of the 600 limp pot = on-tree in every grid
    play(hero_flop_bet=100, allin=False)      # 0.167x pot = off-tree (>10% from any tree size)
    play(hero_flop_bet=None, allin=True)      # preflop stack-off -> silent runout (deal injection)

    s1 = export_session(session, out1, ledger_path=ledger)
    raw = out1.read_bytes()
    assert raw.count(b"\r\n") > 0 and raw.count(b"\n") == raw.count(b"\r\n"), "CRLF-Verletzung"
    text = raw.decode("utf-8")
    assert text.count("PokerStars Hand #") == 3, "Hand-Block-Anzahl != Session-Haende"
    assert "Hold'em No Limit" in text and text.count("*** SUMMARY ***") == 3
    runout_block = text.split("\r\n\r\n")[2]
    for sec in ("*** FLOP ***", "*** TURN ***", "*** RIVER ***"):
        assert sec in runout_block, f"Runout-Sektion fehlt: {sec}"
    assert s1["idbase"] >= ID_FLOOR
    assert any("Hand 2" in w for w in s1["warnungen"]), "Off-Tree-Warnung (Hand 2) fehlt"
    assert not any("Hand 1" in w for w in s1["warnungen"]), "falsche Warnung auf der On-Tree-Hand"
    assert ledger.exists() and len(ledger.read_text(encoding="utf-8").splitlines()) == 1

    s2 = export_session(session, out2, ledger_path=ledger)     # same second -> collision -> bump
    assert s2["idbase"] != s1["idbase"], "idbase wiederverwendet (Hand-ID-Gesetz verletzt)"

    bad = json.loads(session.read_text(encoding="utf-8").splitlines()[0])
    bad["bb"] = 200
    try:
        record_to_export(bad)
        raise AssertionError("Geometrie-Guard hat bb=200 nicht verweigert")
    except ExportError as e:
        assert "Geometrie" in str(e)
    print("SELFTEST PASS: CRLF, 3 Bloecke, Runout-Sektionen, Off-Tree-Warnung, "
          f"Ledger-Dedup (idbase {s1['idbase']} -> {s2['idbase']}), Geometrie-Guard")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session", nargs="?", default="latest",
                    help="Pfad zur session_*.jsonl oder 'latest'")
    ap.add_argument("out", nargs="?", default=None, help="Ziel-HH-Datei (.txt)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    try:
        sess = _latest_session() if args.session == "latest" else Path(args.session)
        export_session(sess, Path(args.out) if args.out else None)
    except ExportError as e:
        print(f"EXPORT VERWEIGERT: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
