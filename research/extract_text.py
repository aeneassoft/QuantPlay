"""Step 1 of the extraction pipeline: PDF -> per-page text + rendered range-chart images.

Outputs:
  data/text/<book>.jsonl            one JSON object per page (book, page, text, n_chars, n_images)
  data/page_images/<book>/page_*.png   rendered range-chart pages (MPT) for vision parsing
  data/page_images/range_pages_manifest.json

Run:  python -m extraction.extract_text
"""
from __future__ import annotations

import json
import re

import fitz  # PyMuPDF

from pokerbot import config

# A chart in Modern Poker Theory is captioned like "Hand Range 51:".
RANGE_LABEL_RE = re.compile(r"Hand\s+Range\s*\d+", re.I)
POSITION_RE = re.compile(r"\b(UTG\+?\d?|LJ|HJ|CO|BTN|SB|BB|MP|EP)\b")
ACTION_RE = re.compile(r"\b(3-?bet|4-?bet|5-?bet|open|RFI|raise|call|fold|limp|all-?in)\b", re.I)


def extract_book_text(book_key: str) -> list[dict]:
    doc = fitz.open(config.pdf_path(book_key))
    pages = []
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text("text")
        pages.append({
            "book": book_key,
            "page": i,                      # 0-based
            "text": text,
            "n_chars": len(text),
            "n_images": len(page.get_images()),
        })
    doc.close()
    out = config.TEXT_DIR / f"{book_key}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for p in pages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"  {book_key:24s}: {len(pages):4d} pages -> {out.name}")
    return pages


def is_range_page(text: str) -> bool:
    """Heuristic: does this page show a preflop range chart?"""
    if RANGE_LABEL_RE.search(text):
        return True
    if "%" in text and ACTION_RE.search(text) and len(POSITION_RE.findall(text)) >= 3:
        return True
    return False


def main() -> None:
    all_pages: dict[str, list[dict]] = {}
    print("Extracting text:")
    for book_key in config.BOOKS:
        all_pages[book_key] = extract_book_text(book_key)

    # Render likely range-chart pages from Modern Poker Theory for vision parsing.
    mpt = all_pages["modern_poker_theory"]
    range_pages = [p["page"] for p in mpt if is_range_page(p["text"])]
    print(f"\nMPT range-candidate pages: {len(range_pages)}")

    doc = fitz.open(config.pdf_path("modern_poker_theory"))
    out_dir = config.PAGE_IMAGE_DIR / "modern_poker_theory"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for idx in range_pages:
        pix = doc[idx].get_pixmap(dpi=170)
        png = out_dir / f"page_{idx:04d}.png"
        pix.save(png)
        manifest.append({"book": "modern_poker_theory", "page": idx,
                         "image": str(png), "kb": round(png.stat().st_size / 1024, 1)})
    doc.close()

    man_path = config.PAGE_IMAGE_DIR / "range_pages_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total_mb = sum(m["kb"] for m in manifest) / 1024
    print(f"Rendered {len(manifest)} range pages ({total_mb:.1f} MB) -> {man_path.name}")


if __name__ == "__main__":
    main()
