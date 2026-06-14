"""FastAPI server: play 6-max No-Limit Hold'em against 5 bots in the browser.

Fast — bots decide locally (no LLM during play). Every hand is logged to a session file; an
end-of-session analysis of the human's play is available via /api/analyze.

Run:  python -m pokerbot.web.six_server [--open]
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from pokerbot import config
from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table
from pokerbot.web.session_log import append_record, build_hand_record

NAMES = ["Du", "Ava", "Ben", "Cleo", "Dex", "Eve"]
HUMAN = 0
_INDEX = (Path(__file__).parent / "static" / "six.html").read_text(encoding="utf-8")
app = FastAPI(title="PokerB — 6-max")


class Session:
    def __init__(self, stack=10000, sb=50, bb=100):
        self.table = Table(NAMES, starting_stack=stack, sb=sb, bb=bb, human_seat=HUMAN)
        sid = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = config.DATA_DIR / "sessions" / f"session_{sid}.jsonl"
        self.logged_hand = -1
        self.human_net = 0          # cumulative human net (chips)
        self.hands_done = 0
        # five INDEPENDENT agents — each its own profile + its own opponent model (public info only)
        _assign = {1: "tag", 2: "lag", 3: "nit", 4: "station", 5: "maniac"}
        self.bots = {s: SixMaxBot(s, PROFILES[_assign.get(s, "tag")]) for s in range(1, self.table.n)}

    def _log_if_done(self):
        t = self.table
        if t.hand_over and t.result and t.hand_no != self.logged_hand:
            append_record(self.path, build_hand_record(t))
            self.logged_hand = t.hand_no
            won = {w["seat"]: w["amount"] for w in t.result.get("winners", [])}
            self.human_net += won.get(HUMAN, 0) - t.seats[HUMAN].committed_total
            self.hands_done += 1

    def _observe_all(self, actor, street, action, to_call, preflop_raises):
        # feed ONE public action to every bot's model (legitimate: all players see public actions)
        act = "raise" if action == "allin" else action
        for b in self.bots.values():
            b.observe(actor, street, act, to_call, preflop_raises)

    def advance(self) -> list[dict]:
        t = self.table
        events: list[dict] = []
        while not t.hand_over and t.to_act is not None and not t.seats[t.to_act].is_human:
            seat = t.to_act
            obs = t.obs_for(seat)
            street, to_call, praises = t.street, obs["to_call"], obs["preflop_raises"]
            try:
                dec = self.bots[seat].decide(obs)
                action, amount = dec["action"], dec["amount"]
                t.act(action, amount)
            except Exception:  # noqa: BLE001 — defensive: never crash the table on a bot
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
                amount = None
            self._observe_all(seat, street, action, to_call, praises)
            events.append({"seat": seat, "name": t.seats[seat].name, "pos": t.position_label(seat),
                           "action": action, "amount": amount, "street": street})
        self._log_if_done()
        return events

    def start_hand(self) -> list[dict]:
        self.table.start_hand()
        for b in self.bots.values():
            b.new_hand(list(range(self.table.n)))
        return self.advance()

    def human_action(self, action: str, amount):
        t = self.table
        street, praises = t.street, t.preflop_raises
        to_call = t.legal_actions().get("to_call", 0) or 0
        t.act(action, amount)
        self._observe_all(HUMAN, street, action, to_call, praises)
        return self.advance()

    def view(self, events=None) -> dict:
        t = self.table
        res = t.result or {}
        reveal = res.get("reveal")
        shown = res.get("shown", {}) if reveal else {}
        won = {w["seat"]: w["amount"] for w in res.get("winners", [])}

        def seat_view(i):
            s = t.seats[i]
            if s.is_human or (reveal and i in shown):
                hole = s.hole
            elif s.folded:
                hole = []
            else:
                hole = ["??", "??"]
            net = (won.get(i, 0) - s.committed_total) if t.hand_over else None
            return {"seat": i, "name": s.name, "stack": s.stack, "hole": hole,
                    "folded": s.folded, "all_in": s.all_in,
                    "committed_street": s.committed_street, "is_human": s.is_human,
                    "is_button": i == t.button, "is_turn": (t.to_act == i and not t.hand_over),
                    "pos": t.position_label(i), "net": net, "won": won.get(i, 0)}

        return {
            "hand_no": t.hand_no, "button": t.button, "sb": t.sb, "bb": t.bb,
            "street": t.street, "board": list(t.board), "pot": t.pot(),
            "current_bet": t.current_bet, "to_act": t.to_act, "hand_over": t.hand_over,
            "result": t.result, "human_seat": HUMAN,
            "session_net": self.human_net, "hands_done": self.hands_done,
            "seats": [seat_view(i) for i in range(t.n)],
            "legal": t.legal_actions() if (not t.hand_over and t.to_act == HUMAN) else {"to_act": None},
            "bot_events": events or [],
        }


SESSION: Session | None = None


class NewReq(BaseModel):
    stack_bb: int = 100


class ActionReq(BaseModel):
    action: str
    amount: int | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    # read fresh each load so UI tweaks show on refresh (no server restart needed)
    return (Path(__file__).parent / "static" / "six.html").read_text(encoding="utf-8")


@app.post("/api/new_session")
def new_session(req: NewReq) -> JSONResponse:
    global SESSION
    SESSION = Session(stack=req.stack_bb * 100, sb=50, bb=100)
    ev = SESSION.start_hand()
    return JSONResponse(SESSION.view(ev))


@app.post("/api/hand")
def next_hand() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    ev = SESSION.start_hand()
    return JSONResponse(SESSION.view(ev))


@app.post("/api/action")
def action(req: ActionReq) -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    t = SESSION.table
    if t.hand_over or t.to_act != HUMAN:
        return JSONResponse({"error": "not your turn"}, status_code=400)
    try:
        ev = SESSION.human_action(req.action, req.amount)
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(SESSION.view(ev))


@app.get("/api/state")
def state() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    return JSONResponse(SESSION.view())


@app.post("/api/analyze")
def analyze() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    from pokerbot.analysis.session_analysis import analyze_session
    return JSONResponse(analyze_session(SESSION.path))


def main() -> None:
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"PokerB 6-max läuft auf  {url}   (Strg+C zum Beenden)")
    if args.open:
        import threading
        import webbrowser
        threading.Timer(1.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
