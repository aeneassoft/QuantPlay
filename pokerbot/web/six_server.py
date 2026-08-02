"""FastAPI server: play 6-max No-Limit Hold'em against 5 bots in the browser.

Fast — bots decide locally (no LLM during play). Every hand is logged to a session file; an
end-of-session analysis of the human's play is available via /api/analyze.

TRAINER (docs/TRAINER_PLAN.md): /training serves the coaching UI. Every human decision is captured
pre-action (P0-1), graded at hand end within the auto-deal window (P0-5), and rendered as warm German
feedback (P1). All coach modules load lazily + fail-soft: a trainer bug can never crash the game.

Run:  python -m pokerbot.web.six_server [--open]
"""
from __future__ import annotations

import time
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
GRADING_BUDGET_MS = 800          # whole-hand grading must fit the client's auto-deal window
TRAINER_MODES = ("gto", "exploit")
app = FastAPI(title="PokerB — 6-max")


def _coach(name: str):
    """Lazy, guarded import of a trainer module — fail-soft by doctrine (a coach bug never breaks play)."""
    import importlib
    try:
        return importlib.import_module(f"pokerbot.coach.{name}")
    except Exception:  # noqa: BLE001 — module absent/broken => the feature is simply off
        return None


class Session:
    def __init__(self, stack=10000, sb=50, bb=100, mode="gto"):
        self.table = Table(NAMES, starting_stack=stack, sb=sb, bb=bb, human_seat=HUMAN)
        sid = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = sid
        self.path = config.DATA_DIR / "sessions" / f"session_{sid}.jsonl"
        self.decisions_path = self.path.with_name(f"decisions_{sid}.jsonl")
        self.logged_hand = -1
        self.human_net = 0          # cumulative human net (chips)
        self.hands_done = 0
        self.mode = mode                          # 'gto' | 'exploit' (P0-0)
        self._pending_decisions: list[dict] = []  # captured this hand, graded+flushed at hand end (P0-1/P0-5)
        self.last_graded: list[dict] = []         # the graded records of the last completed hand
        self.last_hand_record: dict | None = None
        self.last_feedback: dict | None = None    # {text, html, terms} for /api/feedback/last
        self._grade_counts = {"ok": 0, "teuer": 0, "leak": 0}
        self.last_error_rate: float | None = None
        # five INDEPENDENT agents — each its own profile + its own opponent model (public info only)
        _assign = {1: "tag", 2: "lag", 3: "nit", 4: "station", 5: "maniac"}
        dif, reg = _coach("difficulty"), _coach("registry")
        if dif is not None and reg is not None:     # P3-D: adapt composition to the last session's error rate
            try:
                prev = [s for s in reg.sessions() if s.get("error_rate") is not None]
                if prev:
                    _assign = dif.update(prev[-1]["error_rate"], _assign) or _assign
            except Exception:  # noqa: BLE001 — controller optional; default composition on any trouble
                pass
        self.profile_assign = dict(_assign)
        self.bots = {s: SixMaxBot(s, PROFILES[_assign.get(s, "tag")]) for s in range(1, self.table.n)}
        if mode != "exploit":
            # GTO-Modus: the league's bounded exploit reads are OFF — bots play their profiles straight.
            for b in self.bots.values():
                b._read = lambda obs: {}
        if reg is not None:
            try:
                reg.register_start(self)
            except Exception:  # noqa: BLE001
                pass

    def _log_if_done(self):
        t = self.table
        if t.hand_over and t.result and t.hand_no != self.logged_hand:
            hand_rec = build_hand_record(t)
            append_record(self.path, hand_rec)
            self.last_hand_record = hand_rec
            self.logged_hand = t.hand_no
            won = {w["seat"]: w["amount"] for w in t.result.get("winners", [])}
            self.human_net += won.get(HUMAN, 0) - t.seats[HUMAN].committed_total
            self.hands_done += 1
            self._grade_and_flush()

    def _grade_and_flush(self):
        """P0-5: grade every captured decision of the finished hand + build the feedback. Runs INSIDE the
        client's 2400ms auto-advance window (budget 800ms, warned when exceeded); every failure degrades to
        an annotated record, never a crashed hand."""
        pending, self._pending_decisions = self._pending_decisions, []
        if not pending:
            self.last_graded = []
            self.last_feedback = None
            return
        t0 = time.perf_counter()
        gr = _coach("grader")
        for rec in pending:
            if gr is not None:
                try:
                    gr.grade_decision(rec)
                except Exception as e:  # noqa: BLE001 — visible, never silent (doctrine)
                    rec["grade_error"] = repr(e)
            try:
                append_record(self.decisions_path, rec)
            except Exception:  # noqa: BLE001
                pass
        self.last_graded = pending
        for rec in pending:                        # rolling error rate for the difficulty controller (P3-D)
            g = rec.get("grade")
            if g in self._grade_counts:
                self._grade_counts[g] += 1
        total = sum(self._grade_counts.values())
        if total:
            bad = self._grade_counts["teuer"] + self._grade_counts["leak"]
            self.last_error_rate = round(bad / total, 3)
        tp = _coach("templates_de")
        if tp is not None:
            try:
                fb = tp.render_hand_feedback(pending, self.table.result)
                fb.setdefault("hand_no", self.logged_hand)      # the UI header shows "Hand #n"
                fb.setdefault("grades", [                       # per-decision badges (✓/～/✗) in the panel
                    {"street": r.get("street"), "grade": r.get("grade"),
                     "human_action": (r.get("human_action") or {}).get("action")} for r in pending])
                self.last_feedback = fb
            except Exception as e:  # noqa: BLE001
                self.last_feedback = {"text": f"(Feedback derzeit nicht verfügbar: {e!r})", "html": "", "terms": []}
        ms = (time.perf_counter() - t0) * 1000
        if ms > GRADING_BUDGET_MS:
            print(f"WARN: Trainer-Grading {ms:.0f}ms > {GRADING_BUDGET_MS}ms Budget (Hand {self.logged_hand})")

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
        self._pending_decisions = []
        self.table.start_hand()
        for b in self.bots.values():
            b.new_hand(list(range(self.table.n)))
        return self.advance()

    def human_action(self, action: str, amount):
        t = self.table
        street, praises = t.street, t.preflop_raises
        to_call = t.legal_actions().get("to_call", 0) or 0
        # P0-1: build the pre-action snapshot BEFORE t.act (state is pre-mutation here), but append it only
        # AFTER t.act succeeds — an illegal action raises out of t.act (-> 400) and must leave NO record.
        rec = None
        dl = _coach("decision_log")
        if dl is not None:
            try:
                rec = dl.capture_decision(t, self.session_id, t.hand_no, self.mode, action, amount)
            except Exception:  # noqa: BLE001 — capture must never block the action itself
                rec = None
        t.act(action, amount)
        if rec is not None:
            self._pending_decisions.append(rec)
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
            # trainer extras (absent-safe for six.html, consumed by training.html)
            "mode": self.mode,
            "coach": self.last_feedback if t.hand_over else None,
            "difficulty": {"profiles": self.profile_assign, "error_rate": self.last_error_rate},
        }


SESSION: Session | None = None


class NewReq(BaseModel):
    stack_bb: int = 100
    mode: str = "gto"               # P0-0: 'gto' | 'exploit'


class ActionReq(BaseModel):
    action: str
    amount: int | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    # read fresh each load so UI tweaks show on refresh (no server restart needed)
    return (Path(__file__).parent / "static" / "six.html").read_text(encoding="utf-8")


@app.get("/training", response_class=HTMLResponse)
def training() -> str:
    # the trainer UI — same fresh-read pattern as index() (six.html stays byte-identical, P2-7 gate)
    p = Path(__file__).parent / "static" / "training.html"
    if not p.exists():
        return "<h1>training.html fehlt — Build unvollständig (siehe docs/TRAINER_PLAN.md P2-1)</h1>"
    return p.read_text(encoding="utf-8")


@app.post("/api/new_session")
def new_session(req: NewReq) -> JSONResponse:
    global SESSION
    if req.mode not in TRAINER_MODES:
        return JSONResponse({"error": f"mode muss einer von {TRAINER_MODES} sein"}, status_code=400)
    reg = _coach("registry")
    if SESSION is not None and reg is not None:     # P0-6: end row BEFORE the replacement start row
        try:
            reg.register_end(SESSION)
        except Exception:  # noqa: BLE001
            pass
    SESSION = Session(stack=req.stack_bb * 100, sb=50, bb=100, mode=req.mode)
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
    reg = _coach("registry")
    if reg is not None:
        try:
            reg.register_end(SESSION)
        except Exception:  # noqa: BLE001
            pass
    from pokerbot.analysis.session_analysis import analyze_session
    return JSONResponse(analyze_session(SESSION.path))


# ----------------------------------------------------------------- trainer routes (P1-C / P2-2 / P2-5 / P3)
@app.get("/api/glossary")
def glossary() -> JSONResponse:
    g = _coach("glossar_de")
    return JSONResponse(g.as_json() if g is not None else [])


@app.get("/api/feedback/last")
def feedback_last() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    return JSONResponse(SESSION.last_feedback or {"text": "", "html": "", "terms": []})


@app.get("/api/replay/last")
def replay_last() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    if SESSION.last_hand_record is None:
        return JSONResponse({"error": "noch keine Hand beendet"}, status_code=400)
    rp = _coach("replay")
    if rp is None:
        return JSONResponse({"error": "replay-Modul fehlt"}, status_code=400)
    try:
        return JSONResponse(rp.compile_replay(SESSION.last_hand_record, SESSION.last_graded))
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Replay-Fehler: {e!r}"}, status_code=400)


@app.get("/api/opponent_panel")
def opponent_panel() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    op = _coach("opponent_panel")
    if op is None:
        return JSONResponse([])
    try:
        return JSONResponse(op.was_bot_gelernt(SESSION.bots))
    except Exception:  # noqa: BLE001
        return JSONResponse([])


@app.get("/api/report")
def trainer_report_route() -> JSONResponse:
    if SESSION is None:
        return JSONResponse({"error": "no session"}, status_code=400)
    tr = _coach("trainer_report")
    if tr is None:
        return JSONResponse({"error": "report-Modul fehlt"}, status_code=400)
    try:
        return JSONResponse(tr.report(SESSION.path, SESSION.decisions_path))
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"Report-Fehler: {e!r}"}, status_code=400)


def main() -> None:
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--trainer", action="store_true", help="open the trainer UI (/training) instead of the plain table")
    args = ap.parse_args()
    url = f"http://{args.host}:{args.port}"
    open_url = url + "/training" if args.trainer else url
    gr = _coach("grader")                      # P0-5: one-time model warmup so the first hand grades fast
    if gr is not None:
        try:
            gr.prewarm()
            print("Trainer-Grader vorgewärmt (Advisor + Orakel).")
        except Exception as e:  # noqa: BLE001
            print(f"Grader-Prewarm übersprungen: {e!r}")
    print(f"PokerB 6-max läuft auf  {url}   ·   Trainer: {url}/training   (Strg+C zum Beenden)")
    if args.open or args.trainer:
        import threading
        import webbrowser
        threading.Timer(1.8, lambda: webbrowser.open(open_url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
