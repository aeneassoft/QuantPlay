"""The serverless dispatcher behind the browser trainer (web/) must behave like the FastAPI routes.
Run: python -m tests.test_browser_bridge   (or pytest)."""
from __future__ import annotations

import json

from pokerbot.web import browser_bridge as B


def _call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    out = json.loads(B.dispatch(method, path, json.dumps(body) if body is not None else None))
    return out["status"], json.loads(out["body"])


def test_new_session_and_full_hand():
    status, view = _call("POST", "/api/new_session", {"stack_bb": 100, "mode": "gto", "step": True, "seed": 7})
    assert status == 200 and view["hand_no"] == 1 and isinstance(view["seats"], list)
    for _ in range(300):
        if view.get("hand_over"):
            break
        legal = view.get("legal") or {}
        if legal.get("to_act") == view["human_seat"]:
            action = "check" if "check" in legal else ("call" if "call" in legal else "fold")
            status, view = _call("POST", "/api/action", {"action": action, "step": True})
        else:
            status, view = _call("POST", "/api/step", {})
        assert status == 200, view
    assert view["hand_over"], "hand did not finish within 300 steps"
    status, fb = _call("GET", "/api/feedback/last")
    assert status == 200 and "text" in fb


def test_query_string_is_ignored():
    status, view = _call("GET", "/api/state?x=1")
    assert status == 200 and "seats" in view


def test_unknown_route_is_404_for_frontend_fallbacks():
    status, body = _call("GET", "/api/glossar")
    assert status == 404 and "error" in body
    status, body = _call("POST", "/api/feedback", {})
    assert status == 404


def test_invalid_body_is_422_not_crash():
    status, body = _call("POST", "/api/new_session", {"stack_bb": "hundert", "mode": "gto"})
    assert status == 422 and "error" in body


def test_optional_body_model_defaults():
    _call("POST", "/api/new_session", {"stack_bb": 100, "mode": "gto", "step": True})
    status, view = _call("POST", "/api/hand", None)     # HandReq | None with an empty body
    assert status == 200 and view["hand_no"] == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
