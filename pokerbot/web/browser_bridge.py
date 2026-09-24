"""Serverless route dispatcher for the 6-max trainer — the bridge that lets the WHOLE trainer run inside
the visitor's browser (Pyodide) with the same code the FastAPI server runs.

WHY not the ASGI app itself: FastAPI executes sync endpoints in a threadpool, and Pyodide has no threads
(`RuntimeError: can't start new thread`, measured 2026-09-24). So we bypass the HTTP layer and call the
route endpoints of `six_server.app` directly, rebuilding their pydantic request models from the JSON body.
The endpoints, the Session and the view stay byte-identical to the local server — no second trainer.

Contract (used by web/src/worker.js, also testable under CPython — tests/test_browser_bridge.py):
    dispatch(method, path, body_json) -> JSON string {"status": int, "body": str}
`body` is the endpoint's response body (JSON text for API routes), so the browser side can wrap it in a
`Response` with the right status and the front-end's `fetch('/api/...')` calls need no change at all.
"""
from __future__ import annotations

import inspect
import json
import typing
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from pokerbot.web import six_server as S

_ROUTES: dict[tuple[str, str], typing.Callable] | None = None


def _routes() -> dict[tuple[str, str], typing.Callable]:
    """(METHOD, path) -> endpoint function, read once from the FastAPI app's route table."""
    global _ROUTES
    if _ROUTES is None:
        _ROUTES = {}
        for route in S.app.routes:
            for method in getattr(route, "methods", None) or ():
                _ROUTES[(method, route.path)] = route.endpoint
    return _ROUTES


def _request_model(endpoint: typing.Callable) -> tuple[str, type[BaseModel]] | None:
    """The (parameter name, pydantic model) an endpoint takes as its JSON body, or None.
    Annotations are strings (`from __future__ import annotations`), hence get_type_hints."""
    hints = typing.get_type_hints(endpoint)
    for name, param in inspect.signature(endpoint).parameters.items():
        annotation = hints.get(name, param.annotation)
        for candidate in typing.get_args(annotation) or (annotation,):
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                return name, candidate
    return None


def _reply(status: int, body: str) -> str:
    return json.dumps({"status": status, "body": body})


def _error(status: int, message: str) -> str:
    return _reply(status, json.dumps({"error": message}))


def dispatch(method: str, path: str, body: str | None = None) -> str:
    """Run one trainer request without HTTP. Unknown routes give 404 so the front-end's documented
    fallbacks (`/api/feedback` -> `/api/feedback/last`, `/api/glossar` -> `/api/glossary`) keep working."""
    clean_path = urlsplit(path).path
    endpoint = _routes().get((method.upper(), clean_path))
    if endpoint is None:
        return _error(404, f"no route {method.upper()} {clean_path}")
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        return _error(400, f"invalid JSON body: {exc}")
    kwargs: dict[str, typing.Any] = {}
    model = _request_model(endpoint)
    if model is not None:
        name, cls = model
        try:
            kwargs[name] = cls(**(payload or {}))
        except ValidationError as exc:
            return _error(422, f"invalid request: {exc.errors()[0].get('msg', 'validation error')}")
    try:
        response = endpoint(**kwargs)
    except Exception as exc:  # noqa: BLE001 — the browser shows the message; the table must never freeze
        return _error(500, f"{type(exc).__name__}: {exc}")
    raw = getattr(response, "body", response)
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    return _reply(getattr(response, "status_code", 200), text)
