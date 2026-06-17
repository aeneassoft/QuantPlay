"""Parse the 'Hand Range N:' caption lines from Modern Poker Theory (no API needed).

Each caption encodes the action frequencies of a GTO range, e.g.:
  "Hand Range 153: BB vs SB Limp (60bb) -> Raise 3.5x 43.8% / Check 56.2%"

Output: knowledge_base/ranges/range_captions.json   (all captions, structured)
        knowledge_base/ranges/hu_range_pages.json    (HU/blind-vs-blind pages -> for vision)

Run:  python -m extraction.parse_ranges
"""
from __future__ import annotations

import json
import re

from pokerbot import config

POSITIONS = ["UTG+2", "UTG+1", "UTG", "LJ", "HJ", "MP", "EP", "CO", "BTN", "BN", "SB", "BB"]
POS_RE = re.compile(r"\b(UTG\+?\d?|LJ|HJ|MP|EP|CO|BTN|BN|SB|BB)\b")
ARROWS = "�→➤➜>"  # the book's arrow glyph decodes inconsistently
CAPTION_RE = re.compile(r"Hand\s+Range\s*(\d+)\s*:?\s*(.+)", re.I)
STACK_RE = re.compile(r"\((\d+)\s*bb\)", re.I)
FREQ_RE = re.compile(r"([\d.]+)\s*%")

# A range matters for Heads-Up if it's a blind-vs-blind / button spot.
HU_RE = re.compile(r"\b(SB|BB|BTN|BN)\b.*\b(SB|BB|BTN|BN)\b|limp|open", re.I)


def parse_actions(actions_part: str) -> list[dict]:
    actions = []
    for seg in actions_part.split("/"):
        seg = seg.strip().strip("".join(ARROWS)).strip()
        for ch in ARROWS:
            seg = seg.replace(ch, "")
        seg = seg.strip()
        fm = FREQ_RE.search(seg)
        if not fm:
            continue
        actions.append({"action": seg[:fm.start()].strip() or "?",
                        "freq": float(fm.group(1))})
    return actions


def split_situation(rest: str) -> tuple[str, str]:
    """Split 'LJ vs SB 3-bet -> 4-bet 11.5% / ...' into ('LJ vs SB 3-bet', '4-bet 11.5% / ...')."""
    for ch in ARROWS:
        if ch in rest:
            sit, _, act = rest.partition(ch)
            return sit.strip(), (ch + act)
    # no arrow: assume everything up to the first 'action NN%' is the situation
    fm = FREQ_RE.search(rest)
    if fm:
        # back up to the start of the action word
        head = rest[: fm.start()]
        cut = max(head.rfind(" "), 0)
        return rest[:cut].strip(), rest[cut:].strip()
    return rest.strip(), ""


def main() -> None:
    pages = [json.loads(l) for l in
             (config.TEXT_DIR / "modern_poker_theory.jsonl").open(encoding="utf-8")]

    captions: list[dict] = []
    for p in pages:
        for line in p["text"].splitlines():
            m = CAPTION_RE.search(line)
            if not m:
                continue
            rid, rest = m.group(1), m.group(2).strip()
            stack = STACK_RE.search(rest)
            sit, actions_part = split_situation(rest)
            positions = POS_RE.findall(sit)
            hero = positions[0] if positions else None
            villain = positions[1] if len(positions) > 1 else None
            captions.append({
                "id": rid,
                "page": p["page"],
                "label": sit,
                "hero": hero,
                "villain": villain,
                "stack_bb": int(stack.group(1)) if stack else None,
                "actions": parse_actions(actions_part),
                "hu_relevant": bool(HU_RE.search(sit)),
                "raw": line.strip(),
            })

    # de-dup by id (keep first occurrence)
    seen = set()
    uniq = []
    for c in captions:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        uniq.append(c)

    out = config.RANGES_DIR / "range_captions.json"
    out.write_text(json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")

    hu_pages = sorted({c["page"] for c in uniq if c["hu_relevant"]})
    (config.RANGES_DIR / "hu_range_pages.json").write_text(
        json.dumps(hu_pages, indent=2), encoding="utf-8")

    n_actions = sum(1 for c in uniq if c["actions"])
    print(f"Parsed {len(uniq)} unique range captions ({n_actions} with action frequencies).")
    print(f"HU/blind-vs-blind relevant pages: {len(hu_pages)} -> {hu_pages}")
    print("Samples:")
    for c in uniq[:3] + [c for c in uniq if c["hu_relevant"]][:3]:
        print(f"  #{c['id']} p{c['page']} hero={c['hero']} vs={c['villain']} "
              f"stack={c['stack_bb']} | {c['label']} | {c['actions']}")


if __name__ == "__main__":
    main()
