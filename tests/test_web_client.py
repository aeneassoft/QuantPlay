"""End-to-end test of the running web server: play a few hands + call the coach."""
from __future__ import annotations

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def wait_up(tries: int = 20) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(BASE + "/", timeout=3)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("server did not come up")


def simple_policy(s: dict):
    L = s["legal"]
    if L.get("can_check"):
        return "check", None
    if L.get("can_call") and L["call_amount"] <= s["bb"] * 4:
        return "call", None
    return "fold", None


def main() -> None:
    wait_up()
    v = post("/api/new_game", {"stack": 10000, "sb": 50, "bb": 100})
    print(f"new_game: hand #{v['state']['hand_no']}, to_act={v['state']['to_act']}, "
          f"coach={v['coach_available']}")
    for hand in range(3):
        guard = 0
        while not v["state"]["hand_over"]:
            s = v["state"]
            if s["to_act"] != v["human_idx"]:
                break
            action, amount = simple_policy(s)
            v = post("/api/action", {"action": action, "amount": amount})
            if "error" in v:
                raise RuntimeError(v["error"])
            guard += 1
            assert guard < 200
        res = v["state"]["result"] or {}
        print(f"  hand #{v['state']['hand_no']} over: {res.get('reason')} winner={res.get('winner')} "
              f"pot={res.get('pot')}")
        if hand == 0:
            c = post("/api/coach/explain")
            print("  COACH(explain):", " ".join(c["text"].split())[:200])
        if not v.get("match_over"):
            v = post("/api/next_hand", {})
    print("WEB CLIENT TEST OK")


if __name__ == "__main__":
    main()
