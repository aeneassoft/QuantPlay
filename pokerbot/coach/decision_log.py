"""Per-decision capture for the trainer (schema ``trainer.decision.v1``, TRAINER_PLAN.md P0-1).

WHY a snapshot BEFORE ``table.act()``: the grader (P0-2..P0-5) must score the human's choice against
the exact PRE-mutation state — obs/legal/history/pot as the human saw them; after act() the table has
moved on. The six_server hook calls ``capture_decision()`` inside ``Session.human_action`` between the
street/to_call snapshot and ``t.act(action, amount)``, and appends the record to the pending list only
AFTER ``t.act()`` succeeded — an illegal move (400) must never leave a phantom record (binding fix P0-1).

Amount semantics (recon gotcha #5): bet/raise ``amount`` is the commit-TO TOTAL in chips (bb = 100),
matching ``legal_actions()['raise_min'/'raise_max']``; 'allin' carries amount=None and the effective
size is reconstructable from the stored ``legal`` dict (raise_max). Grade fields (checks / oracle /
grade / grade_typ / erklaerung_kurz / grade_ms) are added at hand end by grader.grade_decision (P0-5)
— the capture path stays cheap (< 5 ms, no equity/advisor/oracle call).

Run:  python -m pokerbot.coach.decision_log      (self-test: real engine Table, no server needed)
"""
from __future__ import annotations

import json
import zlib
from dataclasses import asdict
from datetime import datetime

from pokerbot.brain.format_spot import spot_from_table

SCHEMA_VERSION = "trainer.decision.v1"
HUMAN_SEAT = 0                    # the trainee always sits at seat 0 (six_server.HUMAN)
CAPTURE_BUDGET_MS = 5.0           # acceptance budget per P0-1 — capture must stay far below the UI


def spot_fingerprint(spot: dict) -> int:
    """crc32 of the canonical spot JSON — seeds the P0-3 oracle rng, keys spot dedup/drilling.

    NEVER Python hash(): it is salted per process (PYTHONHASHSEED trap, CLAUDE.md clean-code note);
    crc32 over sort_keys JSON is process- and session-stable for the identical spot.
    """
    canon = {"street": spot["street"], "board": spot["board"], "hero_hole": spot["hero_hole"],
             "pot": spot["pot"], "to_call": spot["to_call"], "line": spot["line"]}
    return zlib.crc32(json.dumps(canon, sort_keys=True).encode("utf-8"))


def capture_decision(table, session_id: str, hand_no: int, mode: str, action: str, amount) -> dict:
    """Build one ``trainer.decision.v1`` record from the live Table at the human's decision point.

    Must be called while it is the human's turn (table.to_act == 0), BEFORE table.act() — obs_for/
    legal_actions describe the current actor. Pure read: the table is not mutated.
    """
    spot = asdict(spot_from_table(table, HUMAN_SEAT))          # format_spot.py:81 — the canonical Spot
    return {
        "schema": SCHEMA_VERSION,
        "session_id": session_id,
        "hand_id": f"{session_id}-{hand_no}",
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "mode": mode,                                          # 'gto' | 'exploit' — from the Session (P0-0)
        "street": table.street,
        "spot": spot,
        "obs": table.obs_for(HUMAN_SEAT),                      # table.py:301, verbatim
        "legal": table.legal_actions(),                        # table.py:131-149, verbatim (is_bet/raise_min/raise_max)
        "history": [dict(h) for h in table.history if "player" in h],   # player entries — the P0-3 HU adapter input
        "human_action": {"action": action, "amount": amount},  # amount = commit-TO total in chips (see docstring)
        "spot_fp": spot_fingerprint(spot),
    }


# ----------------------------------------------------------------- offline self-test (no server)
_TEST_NAMES = ["Du", "Ava", "Ben", "Cleo", "Dex", "Eve"]
_EXPECTED_KEYS = {"schema", "session_id", "hand_id", "ts", "mode", "street", "spot", "obs",
                  "legal", "history", "human_action", "spot_fp"}


def _play_to_human(t) -> None:
    """Advance bots with the server's fallback policy (check > call > fold) until human turn / hand end."""
    while not t.hand_over and t.to_act is not None and t.to_act != HUMAN_SEAT:
        la = t.legal_actions()
        t.act("check" if la["can_check"] else ("call" if la["can_call"] else "fold"))


def _next_human_spot(t, max_hands: int = 50) -> None:
    for _ in range(max_hands):
        if t.hand_over or t.to_act is None:
            t.start_hand()
        _play_to_human(t)
        if not t.hand_over and t.to_act == HUMAN_SEAT:
            return
    raise AssertionError("no human decision point reached within 50 hands")


def _selftest() -> None:
    import time

    from pokerbot.engine.table import Table

    t = Table(_TEST_NAMES, starting_stack=10000, sb=50, bb=100, seed=42, human_seat=HUMAN_SEAT)
    _next_human_spot(t)
    la = t.legal_actions()
    act = "check" if la["can_check"] else "call"
    sid = "20260802_000000"

    pre_state = (t.pot(), t.street, t.to_act, len(t.history))
    rec = capture_decision(t, sid, t.hand_no, "gto", act, None)
    assert pre_state == (t.pot(), t.street, t.to_act, len(t.history)), "capture mutated the table"

    # schema shape
    assert set(rec) == _EXPECTED_KEYS, f"schema keys drifted: {set(rec) ^ _EXPECTED_KEYS}"
    assert rec["schema"] == SCHEMA_VERSION and rec["hand_id"] == f"{sid}-{t.hand_no}"
    for k in ("street", "board", "pot", "to_call", "legal", "line", "hero_hole", "hero_pos"):
        assert k in rec["spot"], f"spot missing {k}"
    for k in ("to_call", "is_bet", "raise_min", "raise_max", "can_call", "can_check", "pot"):
        assert k in rec["legal"], f"legal missing {k}"
    assert rec["obs"] == t.obs_for(HUMAN_SEAT)
    assert rec["history"] == [h for h in t.history if "player" in h]
    assert all("player" in h for h in rec["history"])
    assert isinstance(rec["spot_fp"], int)
    json.dumps(rec)                                            # JSONL-ready (grader appends via append_record)

    # fp determinism: identical state -> identical fp + identical record modulo ts
    rec2 = capture_decision(t, sid, t.hand_no, "gto", act, None)
    assert rec2["spot_fp"] == rec["spot_fp"], "spot_fp not deterministic"
    a, b = dict(rec), dict(rec2)
    a.pop("ts"), b.pop("ts")
    assert a == b, "capture not deterministic modulo ts"

    # latency budget (< 5 ms) — min over a few runs to dodge Windows timer/GC jitter
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        capture_decision(t, sid, t.hand_no, "gto", act, None)
        times.append((time.perf_counter() - t0) * 1000.0)
    assert min(times) < CAPTURE_BUDGET_MS, f"capture too slow: min {min(times):.2f} ms"

    # a different spot fingerprints differently (deterministic seed-42 walk to the next decision)
    t.act(act, None)
    _next_human_spot(t)
    rec3 = capture_decision(t, sid, t.hand_no, "gto", "check" if t.legal_actions()["can_check"] else "call", None)
    assert rec3["spot_fp"] != rec["spot_fp"], "distinct spots collided"

    print(f"OK - decision_log: schema v1 ({len(_EXPECTED_KEYS)} keys), fp deterministic, "
          f"capture min {min(times):.2f} ms (< {CAPTURE_BUDGET_MS:.0f} ms)")


if __name__ == "__main__":
    _selftest()
