"""Chunk per-page book text into token-bounded chunks for the LLM.

Pages are packed greedily up to a token target (page boundaries are kept). Output:
  data/chunks/all_chunks.jsonl   { id, book, page_start, page_end, n_tokens, text }

Run:  python -m extraction.chunk
"""
from __future__ import annotations

import json

import tiktoken

from pokerbot import config

_enc = tiktoken.get_encoding("cl100k_base")


def ntok(s: str) -> int:
    return len(_enc.encode(s, disallowed_special=()))


def _make_chunk(book: str, page_start: int, page_end: int, parts: list[str]) -> dict:
    text = "\n\n".join(parts)
    return {
        "id": f"{book}:{page_start:04d}-{page_end:04d}",
        "book": book,
        "page_start": page_start,
        "page_end": page_end,
        "n_tokens": ntok(text),
        "text": text,
    }


def chunk_book(book_key: str, target_tokens: int = 6000) -> list[dict]:
    pages = [json.loads(l) for l in (config.TEXT_DIR / f"{book_key}.jsonl").open(encoding="utf-8")]
    chunks: list[dict] = []
    cur_parts: list[str] = []
    cur_tok = 0
    start = end = None
    for p in pages:
        t = p["text"].strip()
        if not t:
            continue
        tok = ntok(t)
        if cur_parts and cur_tok + tok > target_tokens:
            chunks.append(_make_chunk(book_key, start, end, cur_parts))
            cur_parts, cur_tok, start = [], 0, None
        if start is None:
            start = p["page"]
        end = p["page"]
        cur_parts.append(f"[page {p['page']}]\n{t}")
        cur_tok += tok
    if cur_parts:
        chunks.append(_make_chunk(book_key, start, end, cur_parts))
    return chunks


def main() -> None:
    all_chunks: list[dict] = []
    for book_key in config.BOOKS:
        cs = chunk_book(book_key)
        toks = sum(c["n_tokens"] for c in cs)
        print(f"  {book_key:24s}: {len(cs):3d} chunks, {toks:,} tokens")
        all_chunks += cs

    out = config.CHUNK_DIR / "all_chunks.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    total = sum(c["n_tokens"] for c in all_chunks)
    print(f"\nTotal: {len(all_chunks)} chunks, {total:,} tokens -> {out}")


if __name__ == "__main__":
    main()
