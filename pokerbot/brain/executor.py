"""The program-of-thought executor (docs/DATASET_SPEC.md): run the LLM's emitted Python "decision program" in a
RESTRICTED sandbox with `spot` + `api` + a `decide(...)` callback in scope, then LEGAL-GATE the result via the engine.

Contract for the program the brain writes:
    # reasoning as comments; compute with the api; then commit exactly once:
    eq = api.equity(spot.hero_hole, ['AA','KK','AQs'], spot.board)
    if eq > api.required_equity(spot.to_call, spot.pot):
        decide("call")
    else:
        decide("fold")
`run_program` returns {"action","amount","ok","error"} — action/amount are LEGAL + ready for `table.act(...)`.
`ok` is False if the program errored, made no decision, or emitted an illegal action (→ a hard-negative for RL).
Deterministic, side-effect-free (no import/open/file/network — restricted builtins). Optional wall-clock timeout (POSIX).
"""
from __future__ import annotations

from pokerbot.brain import api as _api
from pokerbot.brain.grammar import validate_program

# A small, safe builtins whitelist — NO __import__, open, exec, eval, compile, globals, getattr-tricks.
_SAFE_BUILTINS = {f.__name__: f for f in (
    min, max, abs, round, sum, len, sorted, range, float, int, bool, str, list, dict, tuple,
    enumerate, zip, any, all, map, filter, divmod, pow, repr, isinstance)}
_SAFE_BUILTINS["True"], _SAFE_BUILTINS["False"], _SAFE_BUILTINS["None"] = True, False, None


def run_program(program: str, spot, timeout_s: float | None = None, strict: bool = True, seed: int = 0) -> dict:
    """Execute a decision program against `spot`; return a legal, engine-ready action. With `strict` (default), the
    program must first pass the DSL GRAMMAR gate (pokerbot/brain/grammar.py) — only OUR language runs; any foreign
    construct is structurally rejected as a hard-negative, never executed. `decide_mix(...)` emits a MIXED strategy
    (frequencies over actions); ONE action is sampled (seeded by `seed` for CRN) for the realized rollout, and the full
    normalized `mix` is returned (for exact mix-EV / exploitability eval)."""
    captured: dict = {}

    def decide(action, size_bb=None):
        captured["action"] = action
        captured["size_bb"] = size_bb

    def decide_mix(mix, size=None):
        captured["mix"] = {str(k): float(v) for k, v in dict(mix).items() if float(v) > 0}
        captured["mix_size_bb"] = size

    if strict:
        ok_dsl, why = validate_program(program)
        if not ok_dsl:
            act, amt = _api.legalize(spot, "check", None)        # safe fallback; flagged not-ok for RL
            return {"action": act, "amount": amt, "ok": False, "error": f"grammar: {why}", "intended": None, "mix": None}

    g = {"__builtins__": _SAFE_BUILTINS, "api": _api, "spot": spot, "decide": decide, "decide_mix": decide_mix}
    error = None
    try:
        code = compile(program, "<decision_program>", "exec")
        if timeout_s and _alarm_available():
            with _time_limit(timeout_s):
                exec(code, g)
        else:
            exec(code, g)
    except Exception as e:  # noqa: BLE001 — a buggy/malicious program just falls back (and flags ok=False)
        error = f"{type(e).__name__}: {e}"

    mix = captured.get("mix")
    if "action" not in captured and mix:                         # MIXED: sample one realized action (seeded => CRN-safe)
        import random
        tot = sum(mix.values())
        if tot > 0:
            r, acc = random.Random(seed).random() * tot, 0.0
            for a in sorted(mix):
                acc += mix[a]
                if r <= acc:
                    captured["action"] = a
                    break
            captured.setdefault("action", max(mix, key=mix.get))
            chosen = captured["action"]
            captured["size_bb"] = captured.get("mix_size_bb") if chosen in ("bet", "raise", "allin", "all-in") else None

    if "action" in captured:
        act, amt = _api.legalize(spot, captured["action"], captured.get("size_bb"))
        # ok iff the program's intended action was itself legal (no silent illegal→fallback masking, for RL)
        ok = error is None and _was_legal(spot, captured["action"])
        return {"action": act, "amount": amt, "ok": ok, "error": error, "intended": captured["action"], "mix": mix}
    # no decision -> safe fallback, flagged not-ok
    act, amt = _api.legalize(spot, "check", None)
    return {"action": act, "amount": amt, "ok": False, "error": error or "no decide() call", "intended": None, "mix": mix}


def _was_legal(spot, action: str) -> bool:
    a = (action or "").lower()
    L = spot.legal
    return ((a == "fold" and L.get("can_fold")) or (a == "check" and L.get("can_check"))
            or (a == "call" and L.get("can_call")) or (a in ("bet", "raise", "allin", "all-in") and L.get("can_raise")))


# -- optional POSIX wall-clock guard (RL self-play runs millions of programs; a stray loop must not hang a worker) --
def _alarm_available() -> bool:
    try:
        import signal
        return hasattr(signal, "SIGALRM")
    except Exception:  # noqa: BLE001
        return False


import contextlib  # noqa: E402


@contextlib.contextmanager
def _time_limit(seconds: float):
    import signal

    def _handler(signum, frame):
        raise TimeoutError("decision program timed out")
    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
