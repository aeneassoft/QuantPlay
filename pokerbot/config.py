"""Central configuration: API keys, model IDs, and project paths.

API keys are read from the user's existing key files (kept out of source) with an
environment-variable override. Nothing here is committed with a secret baked in.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Project paths ---------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # ...\Desktop\PokerB
INFORMATION_DIR = ROOT / "books" / "poker"      # the 6 source poker books (merged from the old Information/)
DATA_DIR = ROOT / "data"                        # intermediate artifacts
KNOWLEDGE_DIR = ROOT / "knowledge_base"         # final extracted knowledge (JSON/MD)

TEXT_DIR = DATA_DIR / "text"                    # per-page extracted text (jsonl)
CHUNK_DIR = DATA_DIR / "chunks"                 # chunked text for the LLM
PAGE_IMAGE_DIR = DATA_DIR / "page_images"       # rendered page PNGs (range grids)

CONCEPTS_DIR = KNOWLEDGE_DIR / "concepts"       # strategy concepts / heuristics
RANGES_DIR = KNOWLEDGE_DIR / "ranges"           # structured preflop ranges
MATH_DIR = KNOWLEDGE_DIR / "math"               # verified math formulas + code

# The training-data assets ("the gold"). `dataset/registry.py` is the ONE place that enumerates + describes them;
# these constants are just the roots it builds on (mirrors DATA_DIR/KNOWLEDGE_DIR).
DATASET_DIR = ROOT / "dataset"                  # the dataset builders + shards
SHARDS_DIR = DATASET_DIR / "shards"             # the self-growing DSL gold (a_contract, solver_mass, ...)
MODELS_DIR = ROOT / "models"                    # Qwen SFT/GRPO adapters + checkpoints
POSTFLOP_DIR = KNOWLEDGE_DIR / "postflop"       # the trained street bet-frequency advisors (advisor/turn/river .pt)

for _d in (DATA_DIR, KNOWLEDGE_DIR, TEXT_DIR, CHUNK_DIR, PAGE_IMAGE_DIR,
           CONCEPTS_DIR, RANGES_DIR, MATH_DIR, DATASET_DIR, SHARDS_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- API keys --------------------------------------------------------------
_SECRET_DIR = Path(r"C:\Users\hampe\Desktop\Secret keys\AI")
_CLAUDE_KEY_FILE = _SECRET_DIR / "Claude API key.txt"
_OPENAI_KEY_FILE = _SECRET_DIR / "OpenAI - API key - Goldbach.txt"


def _read_key(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or _read_key(_CLAUDE_KEY_FILE)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _read_key(_OPENAI_KEY_FILE)
# GTO Wizard AI Benchmark (researcher API). Key file lives in Secret keys/Poker/ (moved there 2026-06 — was the root;
# the stale root path silently fell back to the env var, which a PC restart then lost). Env override still wins.
# Never hardcode/commit the key. Two fallback paths so a future move/rename doesn't break it again.
_GTOW_KEY_FILE = _SECRET_DIR.parent / "Poker" / "GTO Wizard API Key!.txt"
GTOWIZARD_API_KEY = (os.environ.get("GTOWIZARD_API_KEY")
                     or _read_key(_GTOW_KEY_FILE)
                     or _read_key(_SECRET_DIR.parent / "GTO Wizard API Key!.txt"))

# --- Models ----------------------------------------------------------------
# Claude: user chose Opus 4.8 for the book analysis.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
# Claude Haiku 4.5 — cheap/fast model for the in-loop pod-run meta-coach (frequent calls).
CLAUDE_HAIKU_MODEL = os.environ.get("CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001")

# OpenAI: the exact best model depends on what this key can access, so the
# pipeline resolves it at runtime against GET /v1/models using this preference
# order (best first). Override with OPENAI_MODEL to pin one.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")  # None => auto-resolve
OPENAI_MODEL_PREFERENCE = [
    "gpt-5.1", "gpt-5", "o3", "o3-pro", "o4-mini",
    "gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini",
]

# --- Source books ----------------------------------------------------------
BOOKS = {
    "modern_poker_theory": "Modern Poker Theory_ Building an unbeatable strategy based on GTO principles_1.pdf",
    "nlhe_theory_practice": "No Limit Hold 'em_ Theory and Practice (The Theory of Poker Series Book 3).pdf",
    "theory_of_poker": "The Theory of Poker_ A Professional Poker Player Teaches You How To Think Like One.pdf",
}

BOOK_TITLES = {
    "modern_poker_theory": "Modern Poker Theory (Acevedo) — GTO ranges & principles",
    "nlhe_theory_practice": "No Limit Hold'em: Theory and Practice (Sklansky/Miller)",
    "theory_of_poker": "The Theory of Poker (Sklansky)",
}


def pdf_path(book_key: str) -> Path:
    return INFORMATION_DIR / BOOKS[book_key]
