"""Extract reusable poker strategy concepts/heuristics from book chunks via Claude.

Output (checkpointed): knowledge_base/concepts/concepts.jsonl  (one record per chunk)
Final merged file:      knowledge_base/concepts/concepts.json

Run:  python -m extraction.extract_concepts [--limit N] [--book KEY]
"""
from __future__ import annotations

import argparse
import json

from pokerbot import config
from extraction.llm import Checkpoint, claude_json

CATEGORIES = [
    "preflop", "postflop", "pot_odds_equity", "bet_sizing", "bluffing",
    "value_betting", "position", "hand_reading", "board_texture",
    "exploitative", "gto_theory", "ranges", "bankroll_variance",
    "tournament_icm", "psychology", "general",
]

SYSTEM = (
    "You are a world-class poker theorist and software architect building the knowledge "
    "base for a No-Limit Hold'em bot. You read passages from three classic poker books and "
    "extract DISCRETE, REUSABLE strategy concepts a program can act on.\n\n"
    "For each concept produce: a short title; the best-fitting category; a 1-2 sentence summary; "
    "deeper details (the reasoning/conditions/math behind it); the situations it applies to "
    "(streets, positions, stack depths, opponent types); whether it is primarily an EXPLOITATIVE "
    "adjustment (true) or GTO/fundamental (false); and an ACTIONABLE RULE phrased imperatively so "
    "it can drive a decision (e.g. 'On the river, bet ~2/3 pot with value hands and bluff at a "
    "frequency that makes the opponent indifferent'). "
    "Extract only genuine strategic knowledge — skip anecdotes, author bios, and filler. "
    "If the passage is mostly numeric range tables, extract the underlying PRINCIPLES, not every number. "
    "Prefer a handful of high-quality, non-redundant concepts over many shallow ones."
)

CONCEPT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "summary": {"type": "string"},
                    "details": {"type": "string"},
                    "applies_to": {"type": "array", "items": {"type": "string"}},
                    "exploitative": {"type": "boolean"},
                    "actionable_rule": {"type": "string"},
                },
                "required": ["title", "category", "summary", "details",
                             "applies_to", "exploitative", "actionable_rule"],
            },
        }
    },
    "required": ["concepts"],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process at most N new chunks")
    ap.add_argument("--book", type=str, default=None, help="only this book key")
    args = ap.parse_args()

    chunks = [json.loads(l) for l in (config.CHUNK_DIR / "all_chunks.jsonl").open(encoding="utf-8")]
    if args.book:
        chunks = [c for c in chunks if c["book"] == args.book]

    ckpt = Checkpoint(config.CONCEPTS_DIR / "concepts.jsonl")
    todo = [c for c in chunks if not ckpt.has(c["id"])]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(chunks)} chunks total | {len(ckpt.done)} already done | processing {len(todo)} now")

    tot_in = tot_out = tot_cache = 0
    for i, c in enumerate(todo, 1):
        user = (f"Book: {config.BOOK_TITLES[c['book']]}\n"
                f"Pages {c['page_start']}-{c['page_end']}.\n\n"
                f"Extract the strategy concepts from this passage:\n\n{c['text']}")
        try:
            data, (ti, to, tc) = claude_json(SYSTEM, user, CONCEPT_SCHEMA, max_tokens=8000)
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(todo)}] {c['id']} ERROR: {e}")
            continue
        concepts = data.get("concepts", [])
        for con in concepts:
            con["book"] = c["book"]
            con["pages"] = [c["page_start"], c["page_end"]]
        ckpt.add(c["id"], {"book": c["book"], "concepts": concepts})
        tot_in += ti; tot_out += to; tot_cache += tc
        print(f"  [{i}/{len(todo)}] {c['id']}: {len(concepts)} concepts "
              f"(in={ti} out={to} cache={tc})")

    # merge
    merged: list[dict] = []
    for rec in ckpt.all():
        merged.extend(rec.get("concepts", []))
    (config.CONCEPTS_DIR / "concepts.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    ckpt.close()

    cost = tot_in / 1e6 * 5 + tot_out / 1e6 * 25
    print(f"\nMerged {len(merged)} concepts -> concepts.json")
    print(f"Usage this run: in={tot_in:,} out={tot_out:,} cache_read={tot_cache:,} "
          f"(~${cost:.2f} on Opus 4.8)")


if __name__ == "__main__":
    main()
