"""Open Poker (openpoker.ai) WebSocket arena client — connects our 6-max bot to the live arena.

Protocol (from docs.openpoker.ai): connect to wss://openpoker.ai/ws (auth via Bearer token or
?token=), -> 'connected' -> join_lobby -> 'table_joined' -> per decision a 'your_turn' message;
reply with an 'action' message echoing hand_id + turn_token. 6-max, blinds 10/20, ~2000 stacks.

It tracks a light table model from the event stream (dealer/positions, street, preflop raises) to
build the observation that pokerbot.arena.sixmax.decide_6max consumes. Unknown message types are
logged so the exact live protocol can be refined on first connection.

Get an API key:  POST https://api.openpoker.ai/api/register {name,email,terms_accepted:true}
Then:  set OPENPOKER_API_KEY=...   and run:  python -m pokerbot.arena.openpoker
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid

from pokerbot.arena.sixmax import decide_6max

WS_URL = "wss://openpoker.ai/ws"
RANK = set("23456789TJQKA")


def _norm_card(c: str) -> str:
    return c[0].upper() + c[1].lower() if len(c) >= 2 else c


class OpenPokerClient:
    def __init__(self, api_key: str, buy_in: int = 2000, verbose: bool = True):
        self.api_key = api_key
        self.buy_in = buy_in
        self.verbose = verbose
        # table model
        self.my_seat: int | None = None
        self.dealer_seat: int | None = None
        self.sb = 10.0
        self.bb = 20.0
        self.hole: list[str] = []
        self.board: list[str] = []
        self.street = "preflop"
        self.seat_stacks: dict[int, float] = {}
        self.preflop_raises = 0
        self.my_committed_street = 0.0
        self.hand_id: str | None = None
        self.hands = 0
        self.net = 0.0

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ---- positions -----------------------------------------------------
    def position_label(self, n_active: int) -> str:
        if self.dealer_seat is None or self.my_seat is None or not self.seat_stacks:
            return "CO"
        seats = sorted(self.seat_stacks.keys())
        order = [s for s in seats if s > self.dealer_seat] + [s for s in seats if s <= self.dealer_seat]
        if self.my_seat not in order:
            return "CO"
        i, n = order.index(self.my_seat), len(order)
        if i == 0:
            return "SB"
        if i == 1:
            return "BB"
        if i == n - 1:
            return "BTN"
        if i == n - 2:
            return "CO"
        if i == n - 3:
            return "HJ"
        return "EP" if i == 2 else "MP"

    # ---- per-hand reset ------------------------------------------------
    def reset_hand(self):
        self.board = []
        self.street = "preflop"
        self.preflop_raises = 0
        self.my_committed_street = 0.0

    # ---- build observation for the brain -------------------------------
    def build_obs(self, msg: dict) -> dict:
        valid = {a["action"]: a for a in msg.get("valid_actions", [])}
        to_call = float(valid.get("call", {}).get("amount", 0) or 0)
        players = msg.get("players", [])
        n_active = max(2, len(players)) if players else len(self.seat_stacks) or 2
        my_stack = next((p["stack"] for p in players if p.get("seat") == self.my_seat),
                        self.seat_stacks.get(self.my_seat, self.buy_in))
        raise_a = valid.get("raise", {})
        return {
            "hole": [_norm_card(c) for c in self.hole],
            "board": [_norm_card(c) for c in (msg.get("community_cards") or self.board)],
            "to_call": to_call,
            "pot": float(msg.get("pot", 0) or 0),
            "my_stack": float(my_stack),
            "bb": self.bb,
            "n_active": n_active,
            "position": self.position_label(n_active),
            "preflop_raises": self.preflop_raises,
            "cur_bet": to_call + self.my_committed_street,
            "my_committed_street": self.my_committed_street,
            "street": self.street if msg.get("community_cards") or self.board else "preflop",
            "can_check": "check" in valid,
            "can_call": "call" in valid,
            "can_raise": "raise" in valid or "all_in" in valid,
            "raise_min": float(raise_a.get("min", msg.get("min_raise", self.bb)) or self.bb),
            "raise_max": float(raise_a.get("max", msg.get("max_raise", my_stack)) or my_stack),
        }

    def to_action_msg(self, dec: dict, obs: dict, msg: dict) -> dict:
        action, amount = dec["action"], dec["amount"]
        out = {"type": "action", "hand_id": msg.get("hand_id", self.hand_id),
               "turn_token": msg.get("turn_token"),
               "client_action_id": str(uuid.uuid4())}
        if action == "raise":
            if amount is not None and amount >= obs["raise_max"] - 1e-6:
                out["action"] = "all_in"
            else:
                out["action"] = "raise"
                out["amount"] = float(amount)
        else:
            out["action"] = action
        return out

    # ---- message handling ----------------------------------------------
    def absorb_state(self, msg: dict):
        if "dealer_seat" in msg:
            self.dealer_seat = msg["dealer_seat"]
        if "small_blind" in msg:
            self.sb = float(msg["small_blind"])
        if "big_blind" in msg:
            self.bb = float(msg["big_blind"])
        for key in ("seats", "players"):
            for p in msg.get(key, []) or []:
                if "seat" in p and "stack" in p:
                    self.seat_stacks[p["seat"]] = float(p["stack"])

    async def run(self):
        try:
            import websockets
        except ImportError:
            print("pip install websockets")
            return
        uri = f"{WS_URL}?token={self.api_key}"
        self.log(f"Connecting to {WS_URL} ...")
        async with websockets.connect(uri, ping_interval=20, max_size=2**22) as ws:
            await ws.send(json.dumps({"type": "join_lobby", "buy_in": self.buy_in}))
            self.log(f"join_lobby buy_in={self.buy_in}")
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self.handle(ws, msg)

    async def handle(self, ws, msg: dict):
        t = msg.get("type")
        self.absorb_state(msg)
        if t == "connected":
            self.log(f"connected as {msg.get('name')} (agent {msg.get('agent_id')})")
        elif t in ("lobby_joined",):
            self.log("lobby joined, waiting for a table…")
        elif t == "table_joined":
            self.my_seat = msg.get("seat", self.my_seat)
            self.log(f"seated at table {msg.get('table_id')} seat {self.my_seat}")
        elif t == "hole_cards":
            self.hole = msg.get("cards", [])
            self.reset_hand()
            self.hands += 1
        elif t == "community_cards":
            self.board = msg.get("cards", self.board)
            self.street = msg.get("street", self.street)
        elif t == "player_action":
            if msg.get("seat") != self.my_seat and self.street == "preflop" \
                    and msg.get("action") in ("raise", "all_in"):
                self.preflop_raises += 1
        elif t == "your_turn":
            obs = self.build_obs(msg)
            dec = decide_6max(obs)
            if dec["action"] in ("raise", "all_in") or dec["action"] == "call":
                self.my_committed_street += obs["to_call"] if dec["action"] == "call" else 0
            am = self.to_action_msg(dec, obs, msg)
            self.log(f"  [{obs['position']} {obs['street']}] {obs['hole']} board {obs['board']} "
                     f"pot {obs['pot']:.0f} to_call {obs['to_call']:.0f} "
                     f"-> {am.get('action')} {am.get('amount','')}  | {dec['rationale']['reasoning']}")
            await ws.send(json.dumps(am))
        elif t == "action_ack":
            if msg.get("status") != "accepted":
                self.log(f"  action not accepted: {msg}")
        elif t == "hand_result":
            for w in msg.get("winners", []):
                if w.get("seat") == self.my_seat:
                    self.net += float(w.get("amount", 0))
            self.log(f"hand done. pot {msg.get('pot')}. session net {self.net:+.0f} "
                     f"({self.hands} hands)")
        elif t == "busted":
            self.log("busted -> rebuy")
            await ws.send(json.dumps({"type": "rebuy", "amount": self.buy_in}))
        elif t == "error":
            self.log(f"ERROR from server: {msg}")
        else:
            self.log(f"(unhandled msg) {t}: {json.dumps(msg)[:200]}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=os.environ.get("OPENPOKER_API_KEY"))
    ap.add_argument("--buy-in", type=int, default=2000)
    args = ap.parse_args()
    if not args.key:
        # optional key file
        kf = r"C:\Users\hampe\Desktop\Secret keys\OpenPoker key.txt"
        if os.path.exists(kf):
            args.key = open(kf, encoding="utf-8").read().strip()
    if not args.key:
        print("No API key. Register at https://api.openpoker.ai/api/register, then set "
              "OPENPOKER_API_KEY or pass --key.")
        return
    asyncio.run(OpenPokerClient(args.key, buy_in=args.buy_in).run())


if __name__ == "__main__":
    main()
