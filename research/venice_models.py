"""List models available on the Venice.ai API (filtered to strong open models). Key stays out of output.
Run: python -m extraction.venice_models
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

KEY = (Path(r"C:\Users\hampe\Desktop\Secret keys\AI\Venice.ai - API key.txt")
       .read_text(encoding="utf-8").strip().splitlines()[0].strip())


def main() -> None:
    req = urllib.request.Request("https://api.venice.ai/api/v1/models",
                                 headers={"Authorization": "Bearer " + KEY})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:  # noqa: BLE001
        print("ERROR querying Venice:", e)
        return
    ids = [m.get("id", "") for m in d.get("data", [])]
    print(f"{len(ids)} models total")
    want = ("kimi", "moonshot", "deepseek", "qwen", "glm", "minimax", "llama", "mistral", "405", "70b")
    rel = [i for i in ids if any(x in i.lower() for x in want)]
    print("--- strong/relevant ---")
    for i in rel:
        print(" ", i)
    if not rel:
        print("(none matched; full list:)")
        for i in ids:
            print(" ", i)


if __name__ == "__main__":
    main()
