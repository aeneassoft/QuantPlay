"""Driver for CLAUDE CODE to play GTO Wizard hand-by-hand via the ClaudeCodeAgent file handshake.

The gtow_client runs `--agent-type claudecode` (sequential): at each hero decision it writes data/claude_play/pending.json
(the spot + engine-computed features) and BLOCKS. This tool is how Claude Code reads that spot and submits an action:

  python -m research.play_gtow show
      -> wait for + print the current pending decision (the spot + engine features + legal options).
  python -m research.play_gtow act SEQ ACTION [AMOUNT_BB] ["reasoning"]
      -> write the action for decision SEQ, then wait for + print the NEXT pending (or report the run is done/stalled).

ACTION in {fold, check, call, bet, raise, allin}. AMOUNT_BB = the raise-TO total in bb (only for bet/raise; '-' otherwise;
the engine clamps it to the legal range). The engine does the math + legality; Claude Code provides the judgment.
"""
from __future__ import annotations

import json
import os
import sys
import time

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "claude_play")
_PENDING = os.path.join(_DIR, "pending.json")
_ACTION = os.path.join(_DIR, "action.json")


def _read_pending(seq_gt: int | None = None, timeout_s: int = 200) -> dict | None:
    """Return the pending decision (optionally only once its seq exceeds seq_gt = the one we just acted on). None on timeout."""
    waited = 0
    while waited < timeout_s:
        if os.path.exists(_PENDING):
            try:
                p = json.load(open(_PENDING, encoding="utf-8"))
                if seq_gt is None or p.get("seq", 0) > seq_gt:
                    return p
            except Exception:  # noqa: BLE001 — mid-write; retry
                pass
        time.sleep(2)
        waited += 2
    return None


def _show(p: dict | None) -> None:
    if not p:
        print("(no pending decision — the run is complete, stalled, or not started yet; check data/gtow_claudecode.log)")
        return
    print(json.dumps(p, indent=2, ensure_ascii=False))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "show":
        _show(_read_pending())
        return
    if cmd == "act":
        if len(sys.argv) < 4:
            print("usage: play_gtow.py act SEQ ACTION [AMOUNT_BB] [\"reasoning\"]")
            return
        seq = int(sys.argv[2])
        action = sys.argv[3].lower()
        amount_raw = sys.argv[4] if len(sys.argv) > 4 else "-"
        amount_bb = None if amount_raw in ("-", "none", "null", "") else float(amount_raw)
        reasoning = sys.argv[5] if len(sys.argv) > 5 else ""
        with open(_ACTION, "w", encoding="utf-8") as fh:
            json.dump({"seq": seq, "action": action, "amount_bb": amount_bb, "reasoning": reasoning}, fh, ensure_ascii=False)
        print(f"submitted seq={seq}: {action} {amount_bb if amount_bb is not None else ''}".rstrip())
        print("--- NEXT DECISION ---")
        _show(_read_pending(seq_gt=seq, timeout_s=200))
        return
    print(f"unknown command: {cmd} (use 'show' or 'act')")


if __name__ == "__main__":
    main()
