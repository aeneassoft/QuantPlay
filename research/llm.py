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


def ask_claude(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    thinking: bool = False,
    temperature: float = 1.0,
    cache_system: bool = True,
) -> tuple[str, tuple[int, int, int]]:
    """Plain-TEXT Claude call (vs claude_json's schema-constrained JSON), with retries + system-prompt caching.
    Returns (text, (input_tokens, output_tokens, cache_read_tokens)). With `thinking=True` the model reasons in
    internal thinking blocks (extended / "extra-high" reasoning — the GTOW-leaderboard recipe: GPT-5.x XHigh = −8..−9);
    those blocks are DROPPED from the returned text, so only the visible answer comes back. Extended thinking forces
    temperature=1, so `temperature` is honored only when thinking is OFF. Used by the Claude poker BRAIN
    (`pokerbot/brain/claude_brain.py`)."""
    client = anthropic_client()
    model = model or config.CLAUDE_MODEL
    sys_blocks: list[dict] = [{"type": "text", "text": system}]
    if cache_system:
        sys_blocks[-1]["cache_control"] = {"type": "ephemeral"}

    kwargs: dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=sys_blocks,
        messages=[{"role": "user", "content": user}],
    )
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}        # extended thinking; temperature must stay default (1.0)
    else:
        kwargs["temperature"] = temperature

    last_err: Exception | None = None
    for attempt in range(6):
        try:
            if thinking or max_tokens >= 16000:          # stream long/thinking requests (avoids the non-stream limit)
                with client.messages.stream(**kwargs) as stream:
                    msg = stream.get_final_message()
            else:
                msg = client.messages.create(**kwargs)
            text = "".join(b.text for b in msg.content if b.type == "text")
            u = msg.usage
            return text, (u.input_tokens, u.output_tokens, getattr(u, "cache_read_input_tokens", 0) or 0)
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
    raise RuntimeError(f"ask_claude failed after retries: {last_err}")


def openai_json(
    system: str,
    user: str,
    schema: dict,
    name: str,
    *,
    model: str | None = None,
    max_tokens: int = 12000,
    images: list[str] | None = None,
) -> tuple[dict, tuple[int, int]]:
    """Call OpenAI with a strict JSON-schema response. Returns (parsed, (prompt, completion)).
    `images`: optional base64-PNG strings -> a VISION call (the screen-reader path, 2026-07-04)."""
    client = openai_client()
    model = model or config.OPENAI_MODEL or "gpt-5.1"
    if images:
        user_content: str | list = [{"type": "text", "text": user}] + [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}} for b64 in images]
    else:
        user_content = user
    last_err: Exception | None = None
    for attempt in range(6):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user_content}],
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
