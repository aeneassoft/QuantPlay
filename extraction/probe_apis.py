"""Probe: confirm both API keys work and resolve the best available OpenAI model.

Run from the project root:  python -m extraction.probe_apis
"""
from __future__ import annotations

from pokerbot import config


def probe_claude() -> bool:
    import anthropic

    if not config.ANTHROPIC_API_KEY:
        print("CLAUDE: no API key found")
        return False
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        resp = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=32,
            messages=[{"role": "user", "content": "Reply with exactly: POKERBOT_OK"}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        print(f"CLAUDE: model={resp.model} OK | reply={text!r} | "
              f"usage in/out={resp.usage.input_tokens}/{resp.usage.output_tokens}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"CLAUDE: ERROR {type(e).__name__}: {e}")
        return False


def probe_openai() -> str | None:
    from openai import OpenAI

    if not config.OPENAI_API_KEY:
        print("OPENAI: no API key found")
        return None
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        models = {m.id for m in client.models.list()}
    except Exception as e:  # noqa: BLE001
        print(f"OPENAI: ERROR listing models {type(e).__name__}: {e}")
        return None

    chosen = config.OPENAI_MODEL
    if not chosen:
        for cand in config.OPENAI_MODEL_PREFERENCE:
            if cand in models:
                chosen = cand
                break
    if not chosen:  # fallback: newest-looking gpt model
        gpts = sorted(m for m in models if m.startswith("gpt"))
        chosen = gpts[-1] if gpts else None

    relevant = sorted(m for m in models if m.startswith(("gpt", "o1", "o3", "o4")))
    print(f"OPENAI: {len(models)} models available. Chosen: {chosen}")
    print("OPENAI: relevant models:", ", ".join(relevant[:40]))
    if not chosen:
        return None

    try:  # tiny connectivity test (reasoning models need token headroom)
        r = client.chat.completions.create(
            model=chosen,
            messages=[{"role": "user", "content": "Reply with exactly: POKERBOT_OK"}],
            max_completion_tokens=2000,
        )
        print(f"OPENAI: test reply={r.choices[0].message.content!r}")
    except Exception as e:  # noqa: BLE001
        print(f"OPENAI: test call ERROR {type(e).__name__}: {e}")
    return chosen


if __name__ == "__main__":
    ok_c = probe_claude()
    model_o = probe_openai()
    print("\nSUMMARY:", {"claude_ok": ok_c, "openai_model": model_o})
