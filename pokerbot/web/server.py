"""FastAPI backend: drives a HU NLHE game between the human (seat 0) and the bot (seat 1),
with on-demand Claude coaching.

Run:  python -m pokerbot.web.server     (or: uvicorn pokerbot.web.server:app --reload)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# AUSLESE-Verdrahtung (2026-08-18): die v4-Env-Flags MUESSEN vor dem bot-Import
# stehen (Import-Zeit-Konstanten). POKERB_AUSLESE=0 schaltet auf den nackten Bot.
if os.environ.get("POKERB_AUSLESE", "1") != "0":
    from pokerbot.strategy.auslese import setze_env
    setze_env()                          # resolver-OFF-Kanal: volle v4-Env inkl. RAISE_NARROW

from pokerbot import config
from pokerbot.coach.coach import Coach
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.bot import PokerBot

HUMAN, BOT = 0, 1
_INDEX = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

app = FastAPI(title="PokerB — Heads-Up GTO Bot")


class Session:
    def __init__(self, stack=10000, sb=50, bb=100):
        self.game = HeadsUpGame(names=("You", "Bot"), starting_stack=stack, sb=sb, bb=bb)
        self.bot = PokerBot(BOT, seed=None, exploit=True)      # plays the bot seat
        # AUSLESE-Wrapper-Kette (r6_button(turn_wert(sel_m15))) um decide — die
        # externen Anker vermessen damit erstmals den AMTIERENDEN Stand.
        self._bot_decide = self.bot.decide
        if os.environ.get("POKERB_AUSLESE", "1") != "0":
            from pokerbot.strategy.auslese import wickle_decide
            self._bot_decide = wickle_decide(self.bot)
        self.advisor = PokerBot(HUMAN, seed=None, exploit=False)  # GTO reco for the human
        self.coach = Coach(language="de")
        self.last_bot: dict | None = None       # {state, decision} for "explain"
        self.last_human: dict | None = None      # {state, action, amount, reco} for "review"
        self.counted = True
        # harvest the human's play: append each finished hand (full state incl. holes/history/result)
        self.log_path = config.DATA_DIR / "sessions" / f"hu_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.comments: list[dict] = []           # free-text notes the human leaves while playing

    # ---- flow helpers --------------------------------------------------
    def _maybe_end(self) -> None:
        if self.game.hand_over and not self.counted:
            self.bot.observe_hand_end()
            try:                                  # harvest: append the finished hand (full state)
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(self.game.state(), ensure_ascii=False) + "\n")
            except OSError:
                pass
            self.counted = True

    def start_hand(self) -> list[dict]:
        self.game.start_hand()
        self.counted = False
        return self.advance()

    def advance(self) -> list[dict]:
        """Let the bot act until it's the human's turn or the hand ends."""
        events: list[dict] = []
        g = self.game
        while not g.hand_over and g.to_act == BOT:
            st_full = g.state()                       # bot sees its own cards
            dec = self._bot_decide(st_full)
            self.last_bot = {"state": g.state(hide=BOT), "decision": dec}
            events.append({"who": "Bot", "action": dec["action"], "amount": dec["amount"],
                           "rationale": dec["rationale"], "street": g.street})
            g.act(dec["action"], dec["amount"])
        self._maybe_end()
        return events

    def human_action(self, action: str, amount: int | None) -> list[dict]:
        g = self.game
        st = g.state()
        # advisor recommendation (for later review) + feed bot's opponent model
        try:
            reco = self.advisor.decide(st)
        except Exception:  # noqa: BLE001
            reco = None
        facing = st["legal"].get("to_call", 0) > 0
        self.bot.observe_opponent(st["street"], action, facing)
        self.last_human = {"state": g.state(hide=BOT), "action": action,
                           "amount": amount, "reco": reco}
        g.act(action, amount)
        self._maybe_end()
        return self.advance()

    def view(self, events: list[dict] | None = None) -> dict:
        st = self.game.state(hide=BOT)
        return {
            "state": st,
            "human_idx": HUMAN, "bot_idx": BOT,
            "bot_events": events or [],
            "coach_available": self.coach.available,
            "match_over": self.game.match_over(),
        }


SESSION: Session | None = None


class NewGameReq(BaseModel):
    stack: int = 10000
    sb: int = 50
    bb: int = 100


class ActionReq(BaseModel):
    action: str
    amount: int | None = None


class AskReq(BaseModel):
    question: str


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX


@app.post("/api/new_game")
def new_game(req: NewGameReq) -> JSONResponse:
    global SESSION
    SESSION = Session(stack=req.stack, sb=req.sb, bb=req.bb)
    events = SESSION.start_hand()
    return JSONResponse(SESSION.view(events))


@app.post("/api/next_hand")
def next_hand() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no game"}, status_code=400)
    if SESSION.game.match_over():
        return JSONResponse({"error": "match over"}, status_code=400)
    events = SESSION.start_hand()
    return JSONResponse(SESSION.view(events))


@app.post("/api/action")
def action(req: ActionReq) -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no game"}, status_code=400)
    g = SESSION.game
    if g.hand_over or g.to_act != HUMAN:
        return JSONResponse({"error": "not your turn"}, status_code=400)
    try:
        events = SESSION.human_action(req.action, req.amount)
    except (ValueError, RuntimeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse(SESSION.view(events))


@app.get("/api/state")
def state() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no game"}, status_code=400)
    return JSONResponse(SESSION.view())


@app.post("/api/coach/explain")
def coach_explain() -> JSONResponse:
    if SESSION is None or not SESSION.last_bot:
        return JSONResponse({"text": "Noch kein Bot-Zug zum Erklären."})
    lb = SESSION.last_bot
    txt = SESSION.coach.explain_move(lb["state"], BOT, lb["decision"])
    return JSONResponse({"text": txt})


@app.post("/api/coach/review")
def coach_review() -> JSONResponse:
    if SESSION is None or not SESSION.last_human or not SESSION.last_human.get("reco"):
        return JSONResponse({"text": "Noch kein eigener Zug zum Bewerten."})
    lh = SESSION.last_human
    txt = SESSION.coach.review_user_move(lh["state"], HUMAN, lh["action"],
                                         lh["amount"], lh["reco"])
    return JSONResponse({"text": txt})


@app.post("/api/coach/ask")
def coach_ask(req: AskReq) -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"text": "Starte zuerst ein Spiel."})
    st = SESSION.game.state(hide=BOT)
    txt = SESSION.coach.ask(req.question, st, HUMAN)
    return JSONResponse({"text": txt})


def main() -> None:
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the browser automatically")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"PokerB läuft auf  {url}   (zum Beenden: Strg+C)")
    if args.open:
        import threading
        import webbrowser
        threading.Timer(1.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
