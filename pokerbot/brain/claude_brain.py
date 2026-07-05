"""Claude Opus 4.8 as the poker BRAIN driving our engine via program-of-thought.

WHY (measured 2026-06-19, the GTOW leaderboard): frontier LLMs with high reasoning play HUNL at ~−9 bb/100 AIVAT
(GPT-5.2 −8.26, GPT-5.5 −9.23) — ~5× better than our −47 engine. So the strongest move is to let a frontier reasoner
DRIVE the engine: Claude emits a DSL program calling api.* (exact equity / math / the live solver), `run_program`
executes it → an exact, LEGAL action. **Math + legality by the engine, JUDGMENT by Claude.** This is the CLAUDE.md
program-of-thought thesis with a frontier brain instead of the (warm-start) Qwen-8B.

Reuses `policy.SYSTEM_PROMPT` (the DSL vocabulary the engine already speaks), `format_spot`, and the executor, so a
Claude decision is byte-identical DOWNSTREAM to a Qwen one. Frontier API = PC-hub ONLY (CLAUDE.md hard rule), never the
pod. `decide_spot(spot)` is the reusable core (gtow / slumbot / duplicate all call it) and is thread-safe (a stateless
HTTP call, no shared GPU model), so callers may run many concurrent hands.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass

from pokerbot.brain import api as _api
from pokerbot.brain import modes
from pokerbot.brain.executor import run_program
from pokerbot.brain.format_spot import ACTION_RE, format_spot
from pokerbot.brain.policy import SYSTEM_PROMPT, extract_program

# Claude needs MORE room than the Qwen budget: extended ("extra-high") reasoning is the leaderboard recipe
# (GPT-5.x XHigh = −8..−9), so we budget for a thinking block + the short program. STRICT grammar by default keeps
# Claude on the exact DSL the executor + dataset speak; relax (strict=False) only if a strong reasoner's
# richer-but-sandbox-safe Python is worth allowing.
_MAX_TOKENS = 6000

# Claude-specific addendum to the shared SYSTEM_PROMPT (NOT applied to Qwen). Targets the measured deep-jam SPEW: the
# bucket-diff (gtow_xray) + paired-diff (claude_vs_engine) showed Claude calls AKs off 175bb to a jam (program degenerated
# to "always call") = ~−7 bb/100 from ~2% of hands. Route jams to the MATH / the near-Nash blueprint instead of gut.
_CLAUDE_SUFFIX = (
    "\n\nEXTRA RULES (you are a strong reasoner driving an EXACT engine):\n"
    "- ALL-IN / JAM DISCIPLINE: when facing an all-in (or a bet that commits your stack), NEVER call a premium on "
    "reflex. DECIDE from the math: m = api.preflop_mix(spot) (EXACT at jam nodes) — play it if not None; ELSE "
    "eq = api.equity(spot.hero_hole, api.range_top(0.08), spot.board); req = api.required_equity(spot.to_call, spot.pot); "
    "and FOLD when eq < req. At 200bb vs a full jam, AK and QQ are typically FOLDS (the price does not justify a flip "
    "against a tight jamming range). Your edge is judgment in the CLOSE spots — never override the engine's exact numbers."
)

# Gated river-sizing rule (POKERB_CLAUDE_RIVERSIZE, default OFF). MEASURED 2026-06-29: Claude reflexively bets ~0.60x
# pot on the river, but the solver's OOP river bets skew SMALL — over 5 boards x 2 pot-types: CHECK 58%, and when it
# bets the median size is ~0.33x pot (0.25x = 42% of bets). So ~0.6x is a measured OVER-size leak vs GTOW's tree. This
# addendum (appended ONLY on the river when ON) nudges Claude toward the solver's small-skew sizing. Gated so the
# baseline stays byte-identical and the change is A/B-able (generate OFF vs ON at one seed -> compare the size dist).
_RIVER_SIZE_RULE = (
    "\n- RIVER SIZING (GTO-grounded, measured): the solver's river bets skew SMALL — OOP it CHECKS ~55-60% and when it "
    "bets the MEDIAN size is ~0.33x pot (0.25x is the single most common bet). A reflexive ~0.6x river bet OVER-sizes "
    "(a measured leak vs the GTO tree). Prefer SMALL value/thin bets (0.25-0.5x pot) and check more often; reserve "
    "large sizes (0.75x+) ONLY for a polarized max-value or bluff river. Let api.solver_freq guide the bet frequency."
)
_RIVER_SIZE = os.environ.get("POKERB_CLAUDE_RIVERSIZE", "0") == "1"


@dataclass
class ClaudeBrain:
    """Claude-as-brain policy core. `decide_spot(spot)` -> the parse_completion-shaped dict
    {action, amount, ok, error, intended, mix, program}. Tracks decision tallies + token usage for honest reporting."""
    model: str | None = None
    thinking: bool = True
    strict: bool = True
    max_tokens: int = _MAX_TOKENS

    def __post_init__(self):
        self._lock = threading.Lock()       # the instance is shared across concurrent hands; guard the counters
        self.decisions = 0
        self.valid = 0
        self.called_solve_node = 0
        self.errors = 0
        self.in_tok = 0
        self.out_tok = 0
        self.cache_tok = 0

    def decide_spot(self, spot) -> dict:
        """Ask Claude for a DSL program for this spot, execute it via the engine, return the legal action + metadata."""
        from research.llm import ask_claude          # deferred: pulls anthropic/openai; keep the brain import light

        try:
            suffix = _CLAUDE_SUFFIX + (_RIVER_SIZE_RULE if _RIVER_SIZE and spot.street == "river" else "")
            text, (i, o, c) = ask_claude(SYSTEM_PROMPT + suffix, format_spot(spot), model=self.model,
                                         max_tokens=self.max_tokens, thinking=self.thinking)
        except Exception as e:                        # noqa: BLE001 — an API failure must not crash the hand
            act, amt = _api.legalize(spot, "check", None)
            with self._lock:
                self.decisions += 1
                self.errors += 1
            return {"action": act, "amount": amt, "ok": False, "error": f"claude_api: {e}",
                    "intended": None, "mix": None, "program": ""}

        prog = extract_program(text)
        res = run_program(prog, spot, timeout_s=modes.current().time_budget_s, strict=self.strict)
        res["program"] = prog
        if not res["ok"]:                             # rejected program -> salvage a legal action from any ACTION: line
            m = ACTION_RE.search(text)
            if m:
                a, amt = _api.legalize(spot, m.group(1), float(m.group(2)) if m.group(2) else None)
                res["action"], res["amount"] = a, amt
        with self._lock:
            self.decisions += 1
            self.valid += int(bool(res["ok"]))
            self.called_solve_node += int("api.solve_node" in prog)
            self.in_tok += i
            self.out_tok += o
            self.cache_tok += c
        return res

    def report(self) -> dict:
        """Honest summary for the runner: decision split + token usage (cost transparency)."""
        n = max(1, self.decisions)
        return {
            "decisions": self.decisions, "valid": self.valid, "frac_bad": round(1 - self.valid / n, 3),
            "called_solve_node": self.called_solve_node, "errors": self.errors,
            "in_tok": self.in_tok, "out_tok": self.out_tok, "cache_tok": self.cache_tok,
        }
