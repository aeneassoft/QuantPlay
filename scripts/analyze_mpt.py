"""Calibrate range-page detection in Modern Poker Theory before spending vision $$."""
from __future__ import annotations
import json
import re
from collections import Counter
from pokerbot import config

LABEL = re.compile(r"Hand\s+Range\s*(\d+)", re.I)
HU = re.compile(r"heads-?up|blind\s+vs\.?\s+blind|\bBvB\b|\bSB\b\s*vs\.?\s*\bBB\b", re.I)

pages = [json.loads(l) for l in (config.TEXT_DIR / "modern_poker_theory.jsonl").open(encoding="utf-8")]

label_pages = []
all_labels = []
hu_pages = []
for p in pages:
    labels = LABEL.findall(p["text"])
    if labels:
        label_pages.append(p["page"])
        all_labels += labels
    if HU.search(p["text"]):
        hu_pages.append(p["page"])

print(f"Total pages: {len(pages)}")
print(f"Pages with a 'Hand Range N' caption: {len(label_pages)}")
print(f"Distinct 'Hand Range N' ids: {len(set(all_labels))} (max id seen: {max((int(x) for x in all_labels), default=0)})")
print(f"Pages with images: {sum(1 for p in pages if p['n_images'] > 0)}")
print(f"HU / blind-vs-blind mention pages: {len(hu_pages)} -> {hu_pages[:40]}")

# Pages that have a label AND are HU-relevant
hu_label = sorted(set(label_pages) & set(hu_pages))
print(f"Pages with BOTH a range caption and HU/BvB mention: {len(hu_label)} -> {hu_label}")

# image-count distribution on label pages (grids are often a single big image or many cells)
imgc = Counter(p["n_images"] for p in pages if p["page"] in set(label_pages))
print(f"Image-count distribution on caption pages: {dict(sorted(imgc.items()))}")

# Show a sample caption page's text so we can see the layout
if label_pages:
    sample = next(p for p in pages if p["page"] == label_pages[len(label_pages)//2])
    print(f"\n--- SAMPLE caption page {sample['page']} (n_images={sample['n_images']}, {sample['n_chars']} chars) ---")
    print(sample["text"][:1200])
