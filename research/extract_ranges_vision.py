"""Vision-parse the Heads-Up range GRIDS in Modern Poker Theory via Claude Opus 4.8.

The text captions give frequencies; the 13x13 colored grids give which hands take which
action. We parse only HU/blind-vs-blind pages (selected by parse_ranges.py).

Output (checkpointed): knowledge_base/ranges/ranges_vision.jsonl   (per page)
Final merged:          knowledge_base/ranges/ranges_grids.json

Run:  python -m extraction.extract_ranges_vision [--limit N]
"""
from __future__ import annotations

import argparse
import json

import fitz

from pokerbot import config
from research.llm import Checkpoint, claude_json, image_block

SYSTEM = (
    "You are an expert at reading poker preflop range charts. You are shown a page from "
    "'Modern Poker Theory' that contains one or more 13x13 hand-range GRIDS plus their text "
    "captions. In a standard grid: pocket pairs run down the diagonal (AA top-left to 22 "
    "bottom-right), SUITED hands are in the upper-right triangle, OFFSUIT hands in the lower-left. "
    "Read the page's color legend to map each color to an action (e.g. raise/all-in/call/fold and "
    "their frequencies). For each grid on the page, output the range.\n\n"
    "Use standard hand notation: 'AA','KK',...,'22' for pairs; 'AKs','QTs' for suited; 'AKo','J9o' "
    "for offsuit. To keep output compact: list under 'pure' every hand that takes a SINGLE non-fold "
    "action ~100% of the time, and under 'mixed' every hand split across actions (with each action's "
    "approximate frequency 0-100). OMIT pure-fold hands entirely (folding is the default). "
    "Be faithful to the grid colors; if a grid is unreadable, return an empty 'pure' and 'mixed' for it."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ranges": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "hero_position": {"type": "string"},
                    "villain_action": {"type": "string"},
                    "stack_bb": {"type": "number"},
                    "actions_summary": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "properties": {"action": {"type": "string"},
                                           "frequency": {"type": "number"}},
                            "required": ["action", "frequency"],
                        },
                    },
                    "pure": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "properties": {"hand": {"type": "string"},
                                           "action": {"type": "string"}},
                            "required": ["hand", "action"],
                        },
                    },
                    "mixed": {
                        "type": "array",
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "properties": {
                                "hand": {"type": "string"},
                                "actions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object", "additionalProperties": False,
                                        "properties": {"action": {"type": "string"},
                                                       "freq": {"type": "number"}},
                                        "required": ["action", "freq"],
                                    },
                                },
                            },
                            "required": ["hand", "actions"],
                        },
                    },
                },
                "required": ["label", "hero_position", "villain_action", "stack_bb",
                             "actions_summary", "pure", "mixed"],
            },
        }
    },
    "required": ["ranges"],
}


def render(book_key: str, page_index: int, dpi: int = 200):
    out_dir = config.PAGE_IMAGE_DIR / book_key
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"page_{page_index:04d}.png"
    if not png.exists():
        doc = fitz.open(config.pdf_path(book_key))
        doc[page_index].get_pixmap(dpi=dpi).save(png)
        doc.close()
    return png


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    hu_pages = json.loads((config.RANGES_DIR / "hu_range_pages.json").read_text(encoding="utf-8"))
    captions = json.loads((config.RANGES_DIR / "range_captions.json").read_text(encoding="utf-8"))
    caps_by_page: dict[int, list] = {}
    for c in captions:
        caps_by_page.setdefault(c["page"], []).append(c)

    ckpt = Checkpoint(config.RANGES_DIR / "ranges_vision.jsonl")
    todo = [p for p in hu_pages if not ckpt.has(str(p))]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(hu_pages)} HU pages | {len(ckpt.done)} done | processing {len(todo)} now")

    tot_in = tot_out = 0
    for i, page in enumerate(todo, 1):
        png = render("modern_poker_theory", page)
        hint_caps = [c["raw"] for c in caps_by_page.get(page, [])]
        hint = "Captions detected on this page:\n" + "\n".join(hint_caps) if hint_caps else \
               "No captions detected on this page."
        content = [
            image_block(png),
            {"type": "text",
             "text": f"This is page {page} of Modern Poker Theory.\n{hint}\n\n"
                     "Read every range grid on this page and output the structured ranges."},
        ]
        try:
            data, (ti, to, _) = claude_json(SYSTEM, content, SCHEMA,
                                             max_tokens=16000, thinking=True)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(todo)}] page {page} ERROR: {e}")
            continue
        ranges = data.get("ranges", [])
        for r in ranges:
            r["page"] = page
        ckpt.add(str(page), {"page": page, "ranges": ranges})
        tot_in += ti; tot_out += to
        n_hands = sum(len(r.get("pure", [])) + len(r.get("mixed", [])) for r in ranges)
        print(f"  [{i}/{len(todo)}] page {page}: {len(ranges)} grids, {n_hands} hands "
              f"(in={ti} out={to})")

    merged: list[dict] = []
    for rec in ckpt.all():
        merged.extend(rec.get("ranges", []))
    (config.RANGES_DIR / "ranges_grids.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    ckpt.close()

    cost = tot_in / 1e6 * 5 + tot_out / 1e6 * 25
    print(f"\nMerged {len(merged)} grids -> ranges_grids.json")
    print(f"Usage this run: in={tot_in:,} out={tot_out:,} (~${cost:.2f} on Opus 4.8)")


if __name__ == "__main__":
    main()
