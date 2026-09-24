"""Live training dashboard — WATCH the LLM learn on RunPod, halfway-understandably.

FastAPI; `/api/metrics` reads `data/training_metrics.jsonl` (streamed from the pod by `infra/runpod_rl_campaign`'s
scp-thread) + `data/eval_gates.json` (the final GATE ladder). Hand-rolled Canvas charts (mirrors `web/six_server.py`:
fresh-read HTML, `--open`, all deps already present). Open it DURING the run.

Run: python -m pokerbot.web.train_dashboard --open
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from pokerbot import config

_HTML = Path(__file__).parent / "static" / "train_dashboard.html"
METRICS = config.DATA_DIR / "training_metrics.jsonl"
GATES = config.DATA_DIR / "eval_gates.json"
app = FastAPI(title="PokerB — Live Training")


def _read_jsonl(path) -> list:
    out = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _HTML.read_text(encoding="utf-8")               # fresh per request (edit HTML without restart)


@app.get("/api/metrics")
def metrics() -> JSONResponse:
    gates = None
    try:
        gates = json.loads(GATES.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse({"metrics": _read_jsonl(METRICS), "gates": gates})


def main() -> None:
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    url = f"http://{a.host}:{a.port}"
    print(f"Training dashboard: {url}  (Ctrl+C to stop)", flush=True)
    if a.open:
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
