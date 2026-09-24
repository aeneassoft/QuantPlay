# web/ — the browser build of the trainer (quantplay.io)

The same trainer as `python -m pokerbot.web.six_server`, running on the visitor's machine: Pyodide
(CPython 3.13 compiled to WebAssembly) in a Web Worker, no server, no data leaves the browser.

| File | Role |
|---|---|
| `build.py` | builds `dist/`: zips `pokerbot/` + the knowledge files the trainer reads, copies `wheels/`, injects the bridge into `training.html` → `dist/index.html`, writes `manifest.json` with the content hash |
| `src/bridge.js` | main thread: replaces `window.fetch` for `/api/*`, boot overlay with progress, request queue |
| `src/worker.js` | the Pyodide worker: CDN runtime → Pyodide packages → vendored wheels (`deps=False`) → bundle → `browser_bridge.dispatch` |
| `wheels/` | pure-Python wheels Pyodide does not ship: fastapi, starlette, treys, typing_inspection, annotated_doc |
| `vercel.json` | static host config: `dist/` is the output, immutable cache for `.zip/.whl`, no-cache for the entry files |
| `dist/` | **committed build output** — what Vercel serves; rebuild before every deploy |

```bash
python web/build.py                                   # from the repo root
python -m http.server 8765 --directory web/dist       # local check at http://127.0.0.1:8765
cd web && vercel deploy --prod                        # Vercel project "quantplay" → https://quantplay.io
```

Python side: [`pokerbot/web/browser_bridge.py`](../pokerbot/web/browser_bridge.py) (tests in
`tests/test_browser_bridge.py`). Why the routes are called directly instead of through the ASGI app:
Pyodide has no threads, and FastAPI runs sync endpoints in a threadpool.

Not in the bundle: the `.pt` advisor nets (no torch in the browser; the trainer's league and grader do not
need them), `pokerbot/vision`, `pokerbot/benchmark`. Session logs are written to the worker's in-memory
filesystem and vanish with the tab.
