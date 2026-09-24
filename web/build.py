"""Build the static QuantPlay trainer site (web/dist) — the trainer that runs on the VISITOR's machine.

What it produces (all static, no server, deployable to any static host — we use Vercel at quantplay.io):
    dist/index.html            training.html with the browser bridge injected into <head>
    dist/bridge.js, worker.js  the fetch shim (main thread) + the Pyodide worker
    dist/pokerbot_bundle.zip   the Python trainer: pokerbot/ + the knowledge files it reads at runtime
    dist/wheels/*.whl          pure-Python deps not shipped by Pyodide (fastapi, starlette, treys)
    dist/vercel.json           static-host config (cache headers)
Run:  python web/build.py        (from the repo root; deterministic — same tree => same hash)
Verify locally:  python -m http.server 8765 --directory web/dist  -> http://127.0.0.1:8765
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIST = WEB / "dist"
BUNDLE_NAME = "pokerbot_bundle.zip"
PYODIDE_VERSION = "0.28.3"   # must match the CDN path in src/worker.js

# What the trainer reads at runtime (measured with an open()-tracer in Pyodide, 2026-09-24) plus everything
# `pokerbot` may import lazily. Whole package = no closure-tracking bugs; .py only, ~700 KB zipped.
BUNDLE_TREES = [
    ("pokerbot", ("*.py", "*.html")),                # six_server reads static/six.html at import
    ("knowledge_base/math", ("*.py", "*.json")),
    ("knowledge_base/ranges", ("*.json",)),
    ("knowledge_base/cfr", ("*.json",)),
    ("knowledge_base/postflop", ("*.json",)),      # no .pt nets: torch does not exist in the browser
    ("knowledge_base/tournament", ("*.md",)),
]
BUNDLE_FILES = [
    "data/preflop_strength.json",                   # the 169-class equity cache; recomputing it takes minutes
]
EXCLUDED_PACKAGES = {"pokerbot/vision", "pokerbot/benchmark"}   # screen reader / API harnesses: never in a browser


def _bundle_members() -> list[Path]:
    members: list[Path] = []
    for tree, patterns in BUNDLE_TREES:
        base = ROOT / tree
        for pattern in patterns:
            for p in sorted(base.rglob(pattern)):
                rel = p.relative_to(ROOT).as_posix()
                if "__pycache__" in rel or any(rel.startswith(x + "/") for x in EXCLUDED_PACKAGES):
                    continue
                members.append(p)
    members += [ROOT / f for f in BUNDLE_FILES]
    missing = [m for m in members if not m.exists()]
    if missing:
        sys.exit(f"bundle input missing: {missing[:3]}")
    return members


def _write_bundle(target: Path) -> str:
    """Deterministic zip (fixed timestamps) so the content hash only changes when a file changes."""
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in _bundle_members():
            info = zipfile.ZipInfo(p.relative_to(ROOT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, p.read_bytes())
    return hashlib.sha1(target.read_bytes()).hexdigest()[:10]


def _inject_bridge(html: str, build_id: str) -> str:
    """The bridge must be the FIRST script: it replaces window.fetch before the page's own code runs."""
    tag = (f'<script>window.QP_BUILD={json.dumps({"v": build_id, "pyodide": PYODIDE_VERSION})}</script>\n'
           f'<script src="bridge.js?v={build_id}"></script>\n')
    marker = "<head>\n"
    if marker not in html:
        sys.exit("training.html: <head> marker not found")
    return html.replace(marker, marker + tag, 1)


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "wheels").mkdir(parents=True)
    bundle_hash = _write_bundle(DIST / BUNDLE_NAME)
    wheels = sorted((WEB / "wheels").glob("*.whl"))
    for w in wheels:
        shutil.copy2(w, DIST / "wheels" / w.name)
    sources = {p.name: p.read_bytes() for p in (WEB / "src").glob("*.js")}
    build_id = hashlib.sha1(bundle_hash.encode() + b"".join(sources.values())
                            + b"".join(w.name.encode() for w in wheels)).hexdigest()[:10]
    for name, data in sources.items():
        (DIST / name).write_bytes(data)
    html = (ROOT / "pokerbot" / "web" / "static" / "training.html").read_text(encoding="utf-8")
    (DIST / "index.html").write_text(_inject_bridge(html, build_id), encoding="utf-8", newline="\n")
    (DIST / "manifest.json").write_text(json.dumps({
        "build": build_id, "bundle": BUNDLE_NAME, "bundle_sha1": bundle_hash,
        "wheels": [w.name for w in wheels], "pyodide": PYODIDE_VERSION,
    }, indent=2), encoding="utf-8")
    for extra in ("favicon.svg",):
        if (WEB / extra).exists():
            shutil.copy2(WEB / extra, DIST / extra)
    size_mb = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()) / 1e6
    print(f"web/dist built: build={build_id} bundle={bundle_hash} ({(DIST / BUNDLE_NAME).stat().st_size / 1e6:.2f} MB) "
          f"wheels={len(wheels)} total={size_mb:.2f} MB")


if __name__ == "__main__":
    build()
