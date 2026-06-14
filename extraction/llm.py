"""Shared LLM helpers: Claude (Opus 4.8) + OpenAI (gpt-5.1) calls with structured
output, prompt caching, retries, and a JSONL checkpoint store for resumable runs.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import anthropic
from openai import OpenAI

from pokerbot import config

_anthropic: anthropic.Anthropic | None = None
_openai: OpenAI | None = None


def anthropic_client() -> anthropic.Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _anthropic


def openai_client() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=config.OPENAI_API_KEY)
    return _openai


def image_block(path: str | Path) -> dict:
    data = base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def claude_json(
    system: str,
    content: str | list[dict],
    schema: dict,
    *,
    model: str | None = None,
    max_tokens: int = 8000,
    thinking: bool = False,
    cache_system: bool = True,
) -> tuple[dict, tuple[int, int, int]]:
    """Call Claude with a JSON-schema-constrained response. Returns (parsed, (in, out, cache_read))."""
    client = anthropic_client()
    model = model or config.CLAUDE_MODEL
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]

    sys_blocks: list[dict] = [{"type": "text", "text": system}]
    if cache_system:
        sys_blocks[-1]["cache_control"] = {"type": "ephemeral"}

    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=sys_blocks,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}

    last_err: Exception | None = None
    for attempt in range(6):
        try:
            if max_tokens >= 16000:
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
            else:
                msg = client.messages.create(**kwargs)
            text = next((b.text for b in msg.content if b.type == "text"), "")
            u = msg.usage
            return json.loads(text), (u.input_tokens, u.output_tokens,
                                       getattr(u, "cache_read_input_tokens", 0) or 0)
        except (anthropic.RateLimitError, anthropic.InternalServerError,
                anthropic.APIConnectionError) as e:
            last_err = e
            time.sleep(min(2 ** attempt, 30))
        except anthropic.APIStatusError as e:
            last_err = e
            if e.status_code >= 500:
                time.sleep(min(2 ** attempt, 30))
            else:
                raise
    raise RuntimeError(f"claude_json failed after retries: {last_err}")


def openai_json(
    system: str,
    user: str,
    schema: dict,
    name: str,
    *,
    model: str | None = None,
    max_tokens: int = 12000,
) -> tuple[dict, tuple[int, int]]:
    """Call OpenAI with a strict JSON-schema response. Returns (parsed, (prompt, completion))."""
    client = openai_client()
    model = model or config.OPENAI_MODEL or "gpt-5.1"
    last_err: Exception | None = None
    for attempt in range(6):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": name, "schema": schema, "strict": True}},
                max_completion_tokens=max_tokens,
            )
            txt = r.choices[0].message.content or "{}"
            u = r.usage
            return json.loads(txt), (u.prompt_tokens, u.completion_tokens)
        except Exception as e:  # noqa: BLE001 — broad retry; OpenAI exc hierarchy varies
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"openai_json failed after retries: {last_err}")


class Checkpoint:
    """Append-only JSONL store keyed by item id, for resumable extraction runs."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.done: dict[str, dict] = {}
        if self.path.exists():
            for line in self.path.open(encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    self.done[rec["id"]] = rec
                except json.JSONDecodeError:
                    pass
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("a", encoding="utf-8")

    def has(self, item_id: str) -> bool:
        return item_id in self.done

    def add(self, item_id: str, data: dict) -> None:
        rec = {"id": item_id, **data}
        self.done[item_id] = rec
        self._f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._f.flush()

    def all(self) -> list[dict]:
        return list(self.done.values())

    def close(self) -> None:
        self._f.close()
