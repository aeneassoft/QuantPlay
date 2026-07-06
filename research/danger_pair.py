"""DANGER-PAIRED arm builder: the class-dense A/B instrument for rare-class levers (born 2026-07-06).

Rare-class levers (e.g. POKERB_RAISE_COMMIT) are invisible on normal 1500-hand sets (family-E lesson)
and a naive per-arm danger filter would SELECT AWAY the lever's successes (the lever defuses danger ->
smaller pots -> the hand drops out of its own arm's filter). THE DESIGN: danger is judged on the ANCHOR
arm ONLY (deal indices where the CURRENT bot got into danger); the SAME deal indices are then taken from
the lever arm regardless of how it played them. Pairing stays exact; the question stays sharp: on the
deals where the champion bleeds, does the lever bleed less?

Usage: python -m research.danger_pair ANCHOR_RAW LEVER_RAW OUT_ANCHOR OUT_LEVER [n=1500]
"""
from __future__ import annotations

import re
import sys

POT = re.compile(r"Total pot [^0-9]?([\d.]+)")


def blocks(path: str) -> list[str]:
    txt = open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    return [b for b in txt.split("\n\n") if b.strip()]


def dangerous(b: str) -> bool:
    board = re.search(r"Board \[([^\]]*)\]", b)
    if board and len(board.group(1).split()) >= 5:
        return True
    m = POT.search(b)
    if m and float(m.group(1)) >= 20.0:
        return True
    post = b.split("*** FLOP", 1)
    return len(post) > 1 and "raises" in post[1]


def main() -> None:
    a_raw, l_raw, a_out, l_out = sys.argv[1:5]
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 1500
    A, L = blocks(a_raw), blocks(l_raw)
    assert len(A) == len(L), f"arm length mismatch: {len(A)} vs {len(L)} (same seed/count required)"
    idx = [i for i, b in enumerate(A) if dangerous(b)][:n]
    for path, src in ((a_out, A), (l_out, L)):
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write("\n\n".join(src[i] for i in idx) + "\n")
    print(f"{len(idx)}/{len(A)} anchor-dangerous deals -> both arms carry the SAME deal indices")


if __name__ == "__main__":
    main()
