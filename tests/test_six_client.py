"""End-to-end test of the 6-max server: play several hands as the human + run analysis."""
from __future__ import annotations

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def wait_up(n=20):
    for _ in range(n):
        try:
            urllib.request.urlopen(BASE + "/", timeout=3)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise RuntimeError("server down")


def policy(L, bb):
    if L.get("can_check"):
        return "check", None
    if L.get("can_call") and L["call_amount"] <= bb * 3:
        return "call", None
    return "fold", None


def main():
    wait_up()
    v = post("/api/new_session", {"stack_bb": 100})
    print(f"new_session: hand #{v['hand_no']}, seats={len(v['seats'])}, "
          f"my turn={v['legal'].get('to_act') == v['human_seat']}")
    hands = 0
    for _ in range(15):
        guard = 0
        while not v["hand_over"]:
            L = v["legal"]
            if L.get("to_act") != v["human_seat"]:
                break
            a, amt = policy(L, v["bb"])
            v = post("/api/action", {"action": a, "amount": amt})
            if "error" in v:
                raise RuntimeError(v["error"])
            guard += 1
            assert guard < 100
        hands += 1
        v = post("/api/hand", {})
    print(f"played {hands} hands ok")
    an = post("/api/analyze", {})
    s = an["stats"]
    print(f"analysis stats: hands={s['hands']} VPIP={s['vpip_pct']}% PFR={s['pfr_pct']}% "
          f"AF={s['postflop_aggression_factor']} net={s['net_bb']}bb ({s['bb_per_100']} bb/100)")
    print("narrative:", (an.get("narrative", "") or "(none)")[:240].replace("\n", " "))
    print("6-MAX CLIENT TEST OK")


if __name__ == "__main__":
    main()
