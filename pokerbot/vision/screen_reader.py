"""Universal poker SCREEN READER (2026-07-04): read ANY poker table open on this PC into structured state.

Design: capture the window (or full screen) -> a VISION model (OpenAI, via research/llm.openai_json images=...)
parses the table into a strict JSON schema. No per-site templates/OCR — the VLM generalizes across sites/skins
(the user's hard requirement: "wirklich jedes Pokerspiel"). Cost control: a 64-bit dHash change detector so the
watch loop only pays for frames where the table actually CHANGED; images are downscaled to ~1280px.

Window targeting is dependency-free (ctypes/user32: EnumWindows + GetWindowRect); capture via PIL.ImageGrab.

Usage:
  python -m pokerbot.vision.screen_reader --list                       # visible windows
  python -m pokerbot.vision.screen_reader --once [--window "Coin"]     # one parse -> pretty print + JSON
  python -m pokerbot.vision.screen_reader --watch [--interval 2.0]     # continuous -> data/vision/table_states.jsonl
Frontier API = PC-hub only (CLAUDE.md rule) — this module never runs on a pod.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import time

from PIL import Image, ImageGrab

OUT_DIR = os.path.join("data", "vision")
MAX_W = 1280                      # downscale cap: plenty for card ranks, ~4x cheaper than raw 4K
HASH_DIST_MIN = 6                 # dHash hamming distance below this = "same frame" -> skip the API call

# ------------------------------------------------------------------ window targeting (ctypes, no deps)
_user32 = ctypes.windll.user32


def list_windows() -> list[dict]:
    """Visible top-level windows with a title -> [{title, bbox=(l,t,r,b)}]."""
    out: list[dict] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        n = _user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.GetWindowTextW(hwnd, buf, n + 1)
        r = wt.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left >= 300 and r.bottom - r.top >= 200:     # skip tiny tool windows
            out.append({"title": buf.value, "bbox": (r.left, r.top, r.right, r.bottom)})
        return True

    _user32.EnumWindows(_cb, 0)
    return out


def pick_window(pattern: str | None) -> dict | None:
    """First window whose title matches `pattern` (case-insensitive substring/regex); None -> full screen."""
    if not pattern:
        return None
    import re
    rx = re.compile(pattern, re.I)
    return next((w for w in list_windows() if rx.search(w["title"])), None)


# ------------------------------------------------------------------ capture + change detection
def capture(bbox=None) -> Image.Image:
    img = ImageGrab.grab(bbox=bbox, all_screens=bbox is None)
    if img.width > MAX_W:
        img = img.resize((MAX_W, int(img.height * MAX_W / img.width)), Image.LANCZOS)
    return img.convert("RGB")


def dhash(img: Image.Image) -> int:
    """64-bit difference hash — cheap frame-change detector (no imagehash dep)."""
    g = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


# ------------------------------------------------------------------ the VLM parse
_CARD = {"type": "string", "description": "2-char code: rank in 23456789TJQKA + suit in cdhs, e.g. 'As','Td'"}

TABLE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["table_found", "site_guess", "street", "board", "pot_text", "pot_bb", "stakes_text",
                 "hero", "players", "dealer_player", "action_on", "notes"],
    "properties": {
        "table_found": {"type": "boolean", "description": "is a poker table visible at all?"},
        "site_guess": {"type": "string", "description": "poker site/app guess from the skin, or 'unknown'"},
        "street": {"type": "string", "enum": ["preflop", "flop", "turn", "river", "showdown", "between_hands",
                                              "unknown"]},
        "board": {"type": "array", "items": _CARD, "maxItems": 5,
                  "description": "community cards, left to right. TRUST THE SUIT SYMBOL, not the color "
                                 "(4-color decks: diamonds often BLUE, clubs GREEN)"},
        "pot_text": {"type": "string", "description": "the pot exactly as displayed, e.g. 'Pot 10BB' or '$4.20'"},
        "pot_bb": {"type": ["number", "null"], "description": "pot in big blinds if the display is in BB, else null"},
        "stakes_text": {"type": "string", "description": "stakes/blinds if visible, else ''"},
        "hero": {"type": "object", "additionalProperties": False,
                 "required": ["seated", "cards", "seat_name"],
                 "properties": {
                     "seated": {"type": "boolean",
                                "description": "false when observing (all hole cards face-down / 'Find Seat' shown)"},
                     "cards": {"type": "array", "items": _CARD, "maxItems": 2,
                               "description": "hero's hole cards if face-up, else []"},
                     "seat_name": {"type": "string", "description": "hero's screen name if identifiable, else ''"}}},
        "players": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "stack_text", "stack_bb", "status", "bet_in_front_bb", "badge_text"],
            "properties": {
                "name": {"type": "string"},
                "stack_text": {"type": "string", "description": "stack exactly as displayed"},
                "stack_bb": {"type": ["number", "null"], "description": "stack in BB if displayed in BB, else null"},
                "status": {"type": "string", "enum": ["active", "folded", "all_in", "to_act", "sitting_out",
                                                      "empty", "unknown"],
                           "description": "'to_act' = the timer/progress bar is on this player"},
                "bet_in_front_bb": {"type": ["number", "null"],
                                    "description": "chips bet in front of this player this street (BB), else null"},
                "badge_text": {"type": "string",
                               "description": "any small badge next to the avatar (e.g. a number), verbatim"}}},
            "description": "every seat, clockwise from the top"},
        "dealer_player": {"type": "string", "description": "name of the player with the dealer button, or ''"},
        "action_on": {"type": "string", "description": "name of the player currently to act, or ''"},
        "notes": {"type": "string", "description": "anything odd/ambiguous in one sentence"},
    },
}

_SYSTEM = (
    "You read poker-table screenshots into exact structured state. Read numbers and names EXACTLY as displayed "
    "(don't convert units unless the display already shows BB). Cards: give 2-char codes (rank 23456789TJQKA + "
    "suit cdhs); ALWAYS trust the printed suit SYMBOL over the card color — many sites use 4-color decks "
    "(diamonds blue, clubs green). Face-down cards are never guessed. A bet chip sitting between a player and "
    "the pot belongs to that player. If no poker table is visible, table_found=false and leave the rest minimal."
)


def read_table(img: Image.Image, model: str | None = None) -> tuple[dict, tuple[int, int]]:
    from research.llm import openai_json
    return openai_json(_SYSTEM, "Read this poker table.", TABLE_SCHEMA, "poker_table",
                       images=[to_b64(img)], max_tokens=4000, model=model)


# ------------------------------------------------------------------ pretty print + CLI
def pretty(t: dict) -> str:
    if not t.get("table_found"):
        return "no poker table visible"
    who = " | ".join(
        f"{p['name']} {p['stack_text']}"
        + (f" [{p['status']}]" if p["status"] not in ("active", "unknown") else "")
        + (f" bet={p['bet_in_front_bb']}bb" if p.get("bet_in_front_bb") else "")
        for p in t.get("players", []))
    hero = t.get("hero") or {}
    hero_s = "observer" if not hero.get("seated") else (f"hero {' '.join(hero.get('cards') or []) or '??'}")
    return (f"[{t.get('site_guess')}] {t.get('street')}  board={' '.join(t.get('board') or []) or '-'}  "
            f"{t.get('pot_text')}  D={t.get('dealer_player') or '?'}  act={t.get('action_on') or '?'}  "
            f"({hero_s})\n  {who}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list visible windows and exit")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--window", default="", help="window-title pattern (regex); empty = full screen")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "table_states.jsonl"))
    args = ap.parse_args()

    if args.list:
        for w in list_windows():
            print(f"  {w['bbox']}  {w['title'][:90]}")
        return

    win = pick_window(args.window)
    bbox = win["bbox"] if win else None
    src = f"window '{win['title'][:50]}'" if win else "full screen"
    os.makedirs(OUT_DIR, exist_ok=True)

    if args.once or not args.watch:
        img = capture(bbox)
        t, (ti, to) = read_table(img, model=args.model)
        print(pretty(t))
        print(f"\n(tokens {ti} in / {to} out)  full JSON:")
        print(json.dumps(t, ensure_ascii=False, indent=1))
        return

    print(f"watching {src} every {args.interval}s -> {args.out}  (Ctrl+C to stop)")
    last_hash = None
    while True:
        img = capture(bbox)
        h = dhash(img)
        if last_hash is None or hamming(h, last_hash) >= HASH_DIST_MIN:
            last_hash = h
            try:
                t, _ = read_table(img, model=args.model)
                t["_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(args.out, "a", encoding="utf-8") as f:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
                print(pretty(t))
            except Exception as e:  # noqa: BLE001 — a failed parse never kills the watcher
                print(f"  parse failed: {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
