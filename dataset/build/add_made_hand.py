"""Make the SFT gold train==serve for the made-hand wiring — WITHOUT re-solving/re-generating.

The deployed adapter was SFT'd with `format_spot.INCLUDE_MADE_HAND` OFF, but it is now SERVED ON (the +40.65 lever).
That OOD gap is the documented "next re-SFT must rebuild the gold with it ON". The gold's `spot` field is plain
`format_spot` OFF text, and the made-hand line is a single deterministic insert at line index 2 (after 'Hero:',
before 'Stacks:') computed from hero's hole + the current board — BOTH parseable from the text. So we post-process the
existing shards to be BYTE-IDENTICAL to `format_spot` ON, no TexasSolver re-solve. Verified against the real
`format_spot` on fresh reconstructed spots before any shard is touched.

  python -m dataset.build.add_made_hand                 # verify only (byte-identity on fresh spots)
  python -m dataset.build.add_made_hand --apply         # verify, then rewrite the gold (backs up <shard>.off.bak)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil

from pokerbot.brain import api

_HOLE_RE = re.compile(r"holding (\S\S) (\S\S)")
_STREET_RE = re.compile(r"Hero to act on the (\w+)")
_GOLD = ["a_contract", "c_decide", "solver", "hu_blueprint"]   # the sft_gold shards built with made-hand OFF


def _board_for(lines: list, street: str):
    """The current street's board cards from the '<Street> [c1 c2 ...]: ...' line (= what format_spot feeds hand_rank)."""
    cap = street.capitalize()
    for ln in lines:
        if ln.startswith(cap + " ["):
            m = re.search(r"\[([^\]]+)\]", ln)
            if m:
                return m.group(1).split()
    return None


def add_made_hand_line(spot_text: str) -> str:
    """Return `spot_text` with the engine made-hand line inserted exactly as format_spot does (idempotent; a no-op for
    preflop or any spot we can't parse — never corrupts a row)."""
    if "Made hand (engine)" in spot_text:
        return spot_text
    sm = _STREET_RE.search(spot_text)
    if not sm or sm.group(1) not in ("flop", "turn", "river"):
        return spot_text
    lines = spot_text.split("\n")
    hm = _HOLE_RE.search(lines[1] if len(lines) > 1 else "")
    board = _board_for(lines, sm.group(1))
    if not hm or not board or len(board) < 3:
        return spot_text
    cat, strength = api.hand_rank([hm.group(1), hm.group(2)], board)
    lines.insert(2, f"Made hand (engine): {cat}, strength {strength:.2f}/1.0.")
    return "\n".join(lines)


def _fresh_spots(limit: int = 200) -> list:
    """Reconstruct postflop spots from a real session (independent of the gold) to verify byte-identity."""
    from research import study_grade as SG
    hands = [json.loads(l) for l in open(SG._SESSION, encoding="utf-8") if l.strip()]
    out = []
    for h in hands:
        btn = next((i for i, p in enumerate(h["players"]) if str(p.get("position", "")).upper() == "SB"), 1)
        for seat in (0, 1):
            for prefix, street in SG.hero_decision_points(h.get("history", []), btn, seat):
                if street != "preflop":
                    sp = SG.reconstruct_spot(h, seat, btn, prefix, street)
                    if sp is not None:
                        out.append(sp)
        if len(out) >= limit:
            break
    return out[:limit]


def verify() -> bool:
    """Assert add_made_hand_line(format_spot OFF) == format_spot ON, byte-for-byte, on fresh spots."""
    from pokerbot.brain import format_spot as FS
    spots = _fresh_spots()
    ok = bad = 0
    first_bad = None
    for sp in spots:
        FS.INCLUDE_MADE_HAND = False
        off = FS.format_spot(sp)
        FS.INCLUDE_MADE_HAND = True
        on = FS.format_spot(sp)
        if add_made_hand_line(off) == on:
            ok += 1
        else:
            bad += 1
            if first_bad is None:
                first_bad = (off, on, add_made_hand_line(off))
    FS.INCLUDE_MADE_HAND = os.environ.get("POKERB_MADE_HAND", "1") == "1"   # restore
    print(f"VERIFY byte-identity on {len(spots)} fresh postflop spots: {ok} ok, {bad} mismatch")
    if first_bad:
        print("  first mismatch:\n  EXPECTED:\n", first_bad[1], "\n  GOT:\n", first_bad[2])
    return bad == 0


def apply_to_gold() -> None:
    from pokerbot import config
    for name in _GOLD:
        p = config.SHARDS_DIR / f"{name}.jsonl"
        if not p.exists():
            print(f"  {name}: MISSING, skip")
            continue
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        shutil.copy(p, str(p) + ".off.bak")                     # reversible backup of the OFF gold
        added = 0
        for ex in rows:
            new = add_made_hand_line(ex.get("spot", ""))
            if new != ex.get("spot"):
                ex["spot"] = new
                added += 1
        with open(p, "w", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"  {name}: {added}/{len(rows)} rows got the made-hand line (backup {name}.jsonl.off.bak)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="rewrite the gold (after the byte-identity gate passes)")
    a = ap.parse_args()
    if not verify():
        print("BYTE-IDENTITY GATE FAILED — NOT touching the gold (train!=serve risk).")
        return
    print("byte-identity gate PASSED.")
    if a.apply:
        apply_to_gold()
    else:
        print("(verify-only; pass --apply to rewrite the gold)")


if __name__ == "__main__":
    main()
