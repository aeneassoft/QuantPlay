"""Measure the FULL LLM brain (QwenPolicy) vs Slumbot — a real external HU near-GTO reference (bb/100).

The brain DRIVES via program-of-thought: each Slumbot decision point -> our `Spot` -> the brain emits + executes a
DSL program -> a legal action -> translated back to Slumbot. Reuses `slumbot.play_hand` (duck-typed bot: `.decide(st)`
+ `.hero_idx`).

Two GENERATION backends share the SAME prompt (`build_messages`) + parse (`parse_completion`):
  - `transformers` (default): local 4-bit model, ~28s/hand SEQUENTIAL — the original $0 path, kept intact.
  - `vllm`: POST the chat messages to a local vLLM OpenAI-compatible server (`/v1/chat/completions`). With
    `--concurrency K`, K independent Slumbot games run in a ThreadPool, all hitting the shared vLLM server (which
    BATCHES server-side) -> the fast pod path. enable_thinking=False (non-thinking, like every other gen path).

HONEST framing: a weak baseline MUST lose. `--baseline allcall` is the self-deception check — a model-free always
check/call bot; it must post a clearly NEGATIVE bb/100 vs Slumbot or the harness is lying to us. We report bb/100 with
± stderr and frac_bad; small samples are noisy, so the stderr is part of the result, not decoration.

Run (local, $0 sanity):  python -m pokerbot.benchmark.slumbot_llm --baseline allcall --concurrency 2 --hands 8
Run (pod, vLLM):          python -m pokerbot.benchmark.slumbot_llm --backend vllm --vllm-url http://127.0.0.1:8000 \
                              --model grpo --concurrency 8 --hands 3000 --progress-out /root/slumbot_progress.jsonl
Run (local transformers): python -m pokerbot.benchmark.slumbot_llm --hands 100 [--adapter models/qwen_local_sft]
Run (LOCAL solver parallel, $0): SOLVE_THREADS=6 python -m pokerbot.benchmark.slumbot_llm --bot solver --concurrency 4 \
                              --hands 3000 --progress-out data/slumbot_solver.jsonl   # K games share api._SOLVE_CACHE
                              # (concurrency-safe per Req A); rich per-hand log -> pokerbot.benchmark.slumbot_adjust.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from pokerbot.benchmark.slumbot import BB, play_hand, play_hand_verbose
from pokerbot.brain import api, modes
from pokerbot.brain.format_spot import Spot
from pokerbot.brain.policy import QwenPolicy, build_messages, parse_completion
from pokerbot.strategy.preflop_blueprint import SIZES_BB

DEFAULT_PROGRESS = os.path.join("data", "slumbot_progress.jsonl")
VLLM_TIMEOUT_S = 120          # per-request HTTP cap (a batched vLLM reply for ~160-320 tokens is well under this)


def _pos(k: int, button: int) -> str:
    return "SB" if k == button else "BB"          # HU: the button posts the small blind


def spot_from_slumbot(st: dict) -> Spot:
    """Slumbot/HU state dict (slumbot.build_state) -> our canonical Spot (so the brain can decide on it)."""
    hero, button, bb = st["to_act"], st["button"], st["bb"]
    players, L = st["players"], st["legal"]
    seats = [{"seat": k, "pos": _pos(k, button), "stack": p["stack"],
              "committed_total": p["committed_total"], "folded": p.get("folded", False),
              "all_in": p.get("all_in", False)} for k, p in enumerate(players)]
    line = [{"street": h["street"], "pos": _pos(h["player"], button), "action": h["action"],
             "amount_bb": (round(h["to"] / bb, 1) if "to" in h else None),
             "hero": h["player"] == hero} for h in st.get("history", [])]
    return Spot(street=st["street"], board=list(st["board"]), bb=bb, hero_seat=hero,
                hero_pos=_pos(hero, button), hero_hole=list(players[hero]["hole"]),
                pot=st["pot"], to_call=L["to_call"], n_active=2, seats=seats,
                legal={k: L.get(k) for k in ("can_fold", "can_check", "can_call", "can_raise",
                                             "raise_min", "raise_max")},
                line=line)


# ----------------------------------------------------------------------------------------------------------------------
# Generation backends — each is just `messages -> raw_text`. The bot wraps one; parse_completion is shared.
# ----------------------------------------------------------------------------------------------------------------------
class VLLMBackend:
    """Generate via a local vLLM OpenAI-compatible server. MIRRORS QwenPolicy._generate (same messages, greedy
    temperature=0, the mode's token budget, non-thinking) but over HTTP so K concurrent games share ONE batched
    server. Stateless + thread-safe (each call opens its own request), so it's the unit the ThreadPool fans out."""

    def __init__(self, url: str, model: str, max_new_tokens: int | None = None):
        self.endpoint = url.rstrip("/") + "/v1/chat/completions"
        self.model = model                          # the served name (e.g. "grpo" lora-module, or the base repo id)
        self.max_new_tokens = max_new_tokens or modes.current().max_new_tokens

    def _generate(self, messages: list[dict]) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,                     # greedy — eval/continuation is deterministic (matches sampling=False)
            "max_tokens": self.max_new_tokens,
            # non-thinking: Qwen3 else emits a long <think> ramble that fills the cap before decide() -> frac_bad.
            # The OpenAI-compat server forwards chat_template_kwargs to apply_chat_template (= the transformers switch).
            "chat_template_kwargs": {"enable_thinking": False},
        }
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.endpoint, data=data,
                                     headers={"Content-Type": "application/json"})
        for attempt in range(3):                    # transient server hiccup -> a short retry (the pod just started it)
            try:
                resp = json.loads(urllib.request.urlopen(req, timeout=VLLM_TIMEOUT_S).read())
                return resp["choices"][0]["message"]["content"] or ""
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    raise
                time.sleep(1.0 * (attempt + 1))
        return ""


class Counters:
    """Decision tallies SHARED across all concurrent games (each stream has its own bot, but frac_bad is GLOBAL).
    One lock guards the two ints — decisions are cheap, contention is negligible vs the LLM call they bracket."""

    def __init__(self):
        self.bad = self.n = 0
        self._lock = threading.Lock()

    def add(self, is_bad: bool) -> None:
        with self._lock:
            self.n += 1
            self.bad += int(is_bad)

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self.bad, self.n


class _LLMBot:
    """Duck-typed for slumbot.play_hand. `.decide(st)` runs the brain's program-of-thought via `backend._generate`,
    then tallies frac_bad into the SHARED Counters. Backend = QwenPolicy (transformers) OR VLLMBackend (HTTP) — same
    prompt (`build_messages`) + same parse (`parse_completion`)."""

    def __init__(self, backend, counters: Counters):
        self.backend = backend
        self.counters = counters
        self.hero_idx = 0

    def decide(self, st: dict) -> dict:
        spot = spot_from_slumbot(st)
        res = parse_completion(self.backend._generate(build_messages(spot)), spot,
                               timeout_s=modes.current().time_budget_s)
        self.counters.add(not res["ok"])
        return {"action": res["action"], "amount": res["amount"]}


class AllCallBot:
    """The SANITY baseline (no model): always check, else call — never folds, never raises. A trivially weak strategy
    that MUST lose clearly to Slumbot. If it doesn't post a negative bb/100, the harness/sign is wrong (self-deception
    check). Model-free, so it runs the full pipeline at $0 and validates concurrency + the progress JSONL. Every action
    is legal by construction, so it's never 'bad' (frac_bad stays 0)."""

    def __init__(self, counters: Counters):
        self.counters = counters
        self.hero_idx = 0

    def decide(self, st: dict) -> dict:
        self.counters.add(False)                    # always a legal action -> never bad
        L = st["legal"]
        if L.get("can_check"):
            return {"action": "check", "amount": None}
        return {"action": "call", "amount": None}   # facing a bet -> flat call (calling station)


# The preflop blueprint emits ABSTRACT labels (open/3bet/4bet/...), not the engine verbs api.legalize understands.
# These raise-family labels are aggressive actions; each carries a TOTAL size (bb) in preflop_blueprint.SIZES_BB.
# We translate label -> (verb, size_bb) so legalize can coerce to a legal action; passing 'open' raw would silently
# degrade to a call (the exact leak the task warns about). limp = a min-action: check if first-in, else flat call.
_PREFLOP_RAISE_LABELS = ("open", "iso", "3bet", "4bet", "5bet")


def _blueprint_action(label: str, spot, sizes: dict):
    """Map a blueprint label (open/3bet/limp/call/fold/...) to (verb, size_bb) for api.legalize.

    fold/check/call pass straight through; the raise-family (open/iso/3bet/4bet/5bet) -> ('raise', SIZES_BB[label])
    when facing a bet, else ('bet', size) since legalize routes both through the raise branch; 'limp' is the minimal
    action (check unopened, else flat call). An unknown label falls back to call so it never crashes the loop.
    """
    if label in ("fold", "check", "call"):
        return label, None
    if label == "limp":
        return ("check" if spot.to_call <= 0 else "call"), None
    if label in _PREFLOP_RAISE_LABELS:
        verb = "raise" if spot.to_call > 0 else "bet"      # legalize handles both via the raise branch + min/max clamp
        return verb, sizes.get(label)
    return "call", None                                    # unknown label -> safe legal action (never seen in practice)


class SolverSlumbotBot:
    """SEARCH-AT-INFERENCE vs Slumbot (HU): postflop is decided by a LIVE TexasSolver solve (api.solve_node), preflop
    by the near-Nash blueprint (api.preflop_mix). Duck-typed for slumbot.play_hand (.decide(st) + .hero_idx). No model.

    REUSES SolverSearchPolicy's mapping exactly: drop the private '_sizes_bb' key, weight by max(0, prob), sample with
    a seeded random.Random.choices, take the bet/raise size from _sizes_bb, and legalize via api.legalize (the engine
    = legality truth). self.solved/self.postflop = the postflop SOLVE-RATE — the whole point of this validation.

    MEASURED (HU smoke, 2026-06-18): postflop solve-rate climbed 0.00 -> 0.29 -> 1.00 (25/25 postflop decisions) as
    api.solve_node's two coverage gaps were closed. (1) RANGES — the fixed tight SRP range (_IP/_OOP) excluded most
    hands the blueprint plays -> strategy_for None; fixed with WIDE HU ranges (_HU_IP/_HU_OOP) PLUS hero's own class
    force-added, so hero's hand is always in the acting node's range. (2) NAVIGATION — turn/river were un-navigable
    (the node after a flop check-through is a chance_node); fixed by RE-ROOTING the solve per street and walking only
    the current street's actions. A 90s solve timeout (was 45s) keeps the wide ~30-56s solves from timing out into a
    fall-back. The only residual fall-back is an OFF-TREE betting line (the lean tree carries no flop/turn raise size) —
    none arose in the sample. Counters: self.solved, self.fell_back, self.postflop, self.preflop_blueprint /
    self.preflop_default (which preflop SOURCE fired).
    """

    def __init__(self, seed: int = 0, sample_log: list | None = None):
        self.rng = random.Random(seed)
        self.hero_idx = 0
        self.solved = 0                # postflop decisions taken from a live solver solve
        self.fell_back = 0             # decisions from the blueprint or the simple default (not a live solve)
        self.postflop = 0             # total postflop decisions (denominator for the solve-rate)
        self.preflop_blueprint = 0     # preflop decisions sourced from api.preflop_mix
        self.preflop_default = 0       # preflop decisions sourced from the simple sane default (a LEAK if non-zero)
        self.sample_log = sample_log   # optional sink: append one (spot, mix) per solved decision for reporting

    def _sample_mix(self, mix: dict, spot):
        """Sample an action from a {action: prob} mix (+ optional '_sizes_bb') and legalize it. The mapping is the
        exact SolverSearchPolicy logic (so solve_node and preflop_mix go through one code path). Returns (action,
        amount_chips) or None if the mix is degenerate (all-zero weights)."""
        sizes = mix.get("_sizes_bb", {})
        actions = [a for a in mix if a != "_sizes_bb"]
        weights = [max(0.0, mix[a]) for a in actions]
        if sum(weights) <= 0:                                # degenerate mix -> caller falls back
            return None
        action = self.rng.choices(actions, weights=weights)[0]
        size_bb = sizes.get(action) if action in ("bet", "raise") else None
        return api.legalize(spot, action, size_bb)

    def decide(self, st: dict) -> dict:
        spot = spot_from_slumbot(st)
        is_postflop = spot.street != "preflop"
        if is_postflop:
            self.postflop += 1
            s = api.solve_node(spot)
            if s:
                acted = self._sample_mix(s, spot)
                if acted is not None:
                    self.solved += 1
                    if self.sample_log is not None:
                        self.sample_log.append((spot, s))
                    return {"action": acted[0], "amount": acted[1]}
            # postflop but unsolvable (degenerate/un-navigable) -> fall through to the same default as preflop-no-mix
        else:
            m = api.preflop_mix(spot)
            if m:
                acted = self._sample_preflop(m, spot)
                if acted is not None:
                    self.fell_back += 1
                    self.preflop_blueprint += 1
                    return {"action": acted[0], "amount": acted[1]}

        # SIMPLE sane default: no solve and no blueprint. to_call==0 -> check; small call vs pot -> call; else fold.
        self.fell_back += 1
        if not is_postflop:
            self.preflop_default += 1                        # a preflop LEAK: the blueprint gave nothing, Slumbot punishes
        L = st["legal"]
        if L.get("can_check"):
            return {"action": "check", "amount": None}
        to_call, pot = L.get("to_call", 0), max(1, st.get("pot", 1))
        if L.get("can_call") and to_call <= 0.33 * pot:      # cheap relative to pot -> call; else fold
            return {"action": "call", "amount": None}
        return {"action": "fold", "amount": None} if L.get("can_fold") else {"action": "check", "amount": None}

    def _sample_preflop(self, mix: dict, spot):
        """Sample the blueprint mix, translating each abstract label to a legal (action, amount). Mirrors _sample_mix
        but routes the sampled label through _blueprint_action first (the blueprint speaks open/3bet/limp, not verbs)."""
        actions = [a for a in mix if a != "_sizes_bb"]
        weights = [max(0.0, mix[a]) for a in actions]
        if sum(weights) <= 0:
            return None
        label = self.rng.choices(actions, weights=weights)[0]
        verb, size_bb = _blueprint_action(label, spot, SIZES_BB)
        return api.legalize(spot, verb, size_bb)


def _load_transformers(base: str, adapter: str) -> QwenPolicy:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(base)
    qc = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16)
    bm = AutoModelForCausalLM.from_pretrained(base, quantization_config=qc, device_map="cuda")
    m = PeftModel.from_pretrained(bm, adapter)
    m.eval()
    return QwenPolicy(m, tok, sampling=False)


# ----------------------------------------------------------------------------------------------------------------------
# Live progress + aggregation
# ----------------------------------------------------------------------------------------------------------------------
class ProgressLog:
    """Append-and-flush one JSONL line per FINISHED hand so a watcher (the pod's scp-down daemon) can pull live — a
    crash/abort then loses at most the in-flight hand, not the whole run. Records the RUNNING cum bb/100 + frac_bad so
    the pulled file is a self-contained progress curve. Thread-safe (concurrent games append)."""

    def __init__(self, path: str, t0: float, counters: Counters):
        self.path = path
        self.t0 = t0
        self.counters = counters                            # GLOBAL frac_bad source (all streams' decisions)
        self.winnings: list[int] = []
        self._lock = threading.Lock()
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            open(path, "w", encoding="utf-8").close()       # truncate stale progress from a prior run

    def record(self, net_chips: int, extra: dict | None = None) -> int:
        """Log one finished hand; returns the hand index (1-based). net = chips won for seat0 this hand (bb=100 chips).
        `extra` (Req B, --bot solver) carries the rich showdown fields from play_hand_verbose (hero/villain hole cards,
        final board, action string, won_pot) — merged into the JSONL row so the all-in-EV analyzer can reconstruct the
        spot. Slumbot reveals bot_hole_cards ONLY at showdown, so it is null on folded hands (logged honestly)."""
        bad, n_dec = self.counters.snapshot()
        with self._lock:
            self.winnings.append(net_chips)
            i = len(self.winnings)
            cum_bb100 = sum(self.winnings) / i              # chips/hand == bb/100 here (BB=100, see slumbot.py)
            frac_bad = bad / max(1, n_dec)
            if self.path:
                row = {"i": i, "net_bb": net_chips / BB, "cum_bb100": round(cum_bb100, 2),
                       "frac_bad": round(frac_bad, 4), "t": round(time.time() - self.t0, 1)}
                if extra:
                    row.update({"hole_cards": extra.get("hole_cards"), "board": extra.get("board"),
                                "bot_hole_cards": extra.get("bot_hole_cards"), "action": extra.get("action"),
                                "winnings": extra.get("winnings", net_chips), "won_pot": extra.get("won_pot"),
                                "client_pos": extra.get("client_pos"), "button": extra.get("button")})
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                    f.flush()
            return i

    def summary(self) -> tuple[int, float, float, float]:
        """(n, bb100, stderr_bb100, frac_bad). stderr = sample-std of per-hand chips / BB / sqrt(n) * 100."""
        bad, n_dec = self.counters.snapshot()
        with self._lock:
            n = len(self.winnings)
            if n == 0:
                return 0, 0.0, 0.0, 0.0
            bb100 = sum(self.winnings) / n
            var = sum((w - bb100) ** 2 for w in self.winnings) / n
        stderr = (var ** 0.5 / BB) / math.sqrt(n) * 100
        return n, bb100, stderr, bad / max(1, n_dec)


def _run_stream(stream_id: int, bot, n_hands: int, prog: ProgressLog, total_hands: int, verbose: bool,
                rich: bool = False) -> None:
    """One independent Slumbot session: its OWN token, plays n_hands sequentially, logs each finished hand to the
    shared ProgressLog. K of these run in the ThreadPool (each is one Slumbot game in flight at a time). When `rich`
    (--bot solver), use play_hand_verbose to also capture the showdown fields for the all-in-EV analyzer (Req B)."""
    token = None
    for h in range(n_hands):
        try:
            vb = verbose and stream_id == 0 and h < 3
            if rich:
                w, token, extra = play_hand_verbose(bot, token, verbose=vb)
            else:
                w, token = play_hand(bot, token, verbose=vb)
                extra = None
        except Exception as e:  # noqa: BLE001 — a per-hand API error (rate-limit / network) must not kill the stream
            print(f"  [stream {stream_id}] hand error ({type(e).__name__}: {str(e)[:80]}); skipping, new session", flush=True)
            token = None                                    # drop the (possibly wedged) token -> next hand starts fresh
            time.sleep(1.0)
            continue
        i = prog.record(w, extra)
        if i % 50 == 0 or i == total_hands:
            _, bb100, stderr, fb = prog.summary()
            print(f"  {i:4d}/{total_hands} hands | {bb100:+.1f} bb/100 (+/-{stderr:.1f}) | "
                  f"frac_bad {fb:.2f} | {(time.time()-prog.t0)/i:.1f}s/hand", flush=True)


def _split_hands(total: int, k: int) -> list[int]:
    """Divide `total` hands across k streams as evenly as possible (the remainder spread over the first streams)."""
    base, rem = divmod(total, k)
    return [base + (1 if s < rem else 0) for s in range(k)]


def _report_solver(bots: "list[SolverSlumbotBot]", n: int, bb100: float, stderr: float) -> None:
    """Print the AGGREGATE solver result over all concurrent streams + the honest preflop SOURCE + one example spot.
    Each stream has its OWN SolverSlumbotBot (own seed/counters), so we SUM the per-bot tallies (Req D: the counters
    are per-bot, the _SOLVE_CACHE is the only shared state). postflop_solve_rate = solved/postflop (should be high in
    HU — the whole point). preflop_source is honest: 'default' (a LEAK) if ANY preflop decision fell to the default."""
    solved = sum(b.solved for b in bots)
    postflop = sum(b.postflop for b in bots)
    pf_bp = sum(b.preflop_blueprint for b in bots)
    pf_def = sum(b.preflop_default for b in bots)
    solve_rate = solved / max(1, postflop)
    pf_total = pf_bp + pf_def
    pf_source = "default" if pf_def > 0 else ("blueprint" if pf_total > 0 else "n/a")
    print(f"hands={n} | {bb100:+.1f} bb/100 (+/-{stderr:.1f} stderr) | "
          f"postflop_solve_rate={solve_rate:.2f} | preflop_source={pf_source}", flush=True)
    print(f"  postflop decisions={postflop} (solved={solved}, fell_back_postflop={postflop - solved}) | "
          f"preflop decisions={pf_total} (blueprint={pf_bp}, default={pf_def})", flush=True)
    if pf_def > 0:                                          # be loud about the leak Slumbot will punish
        print("  NOTE: some preflop decisions used the SIMPLE DEFAULT (blueprint returned None) — a real leak.", flush=True)
    sample = next((b.sample_log[0] for b in bots if b.sample_log), None)
    if sample:                                              # one concrete example: the spot + the solver mix sampled from
        spot, mix = sample
        shown = {k: round(v, 3) for k, v in mix.items() if k != "_sizes_bb"}
        sizes = mix.get("_sizes_bb")
        print("  example solved spot:")
        print(f"    board={spot.board} street={spot.street} hero={spot.hero_hole} pot={spot.b(spot.pot)}bb "
              f"to_call={spot.b(spot.to_call)}bb", flush=True)
        print(f"    solver mix={shown}" + (f" sizes_bb={ {k: round(v,1) for k,v in sizes.items()} }" if sizes else ""),
              flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=100)
    ap.add_argument("--bot", choices=["qwen", "solver", "allcall"], default="qwen",
                    help="qwen = the LLM brain (backend below); solver = search-at-inference (api.solve_node, no model "
                         "load); allcall = the model-free always check/call sanity baseline")
    ap.add_argument("--seed", type=int, default=0, help="(solver) RNG seed for sampling the solver/blueprint mixes")
    ap.add_argument("--backend", choices=["transformers", "vllm"], default="transformers")
    ap.add_argument("--vllm-url", dest="vllm_url", default="http://127.0.0.1:8000",
                    help="vLLM OpenAI-compatible server base URL (for --backend vllm)")
    ap.add_argument("--model", default="grpo",
                    help="vLLM served model name (a --lora-modules name, or the base repo id)")
    ap.add_argument("--base", default="Qwen/Qwen3-1.7B", help="(transformers) base model")
    ap.add_argument("--adapter", default="models/qwen_local_sft", help="(transformers) LoRA adapter dir")
    ap.add_argument("--concurrency", type=int, default=8, help="K independent Slumbot games in parallel (vLLM batches)")
    ap.add_argument("--baseline", choices=["none", "allcall"], default="none",
                    help="allcall = a model-free always check/call bot (the self-deception sanity check)")
    ap.add_argument("--progress-out", dest="progress_out", default=DEFAULT_PROGRESS,
                    help="append one JSONL row per finished hand here (live progress; '' to disable)")
    ap.add_argument("--mode", default="fast", help="compute mode (fast/standard) -> the gen token budget")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    modes.set_mode(a.mode)

    counters = Counters()                                   # GLOBAL frac_bad tally shared across all streams' bots
    bot_kind = "allcall" if a.baseline == "allcall" else a.bot   # --baseline allcall stays a back-compat alias for --bot
    solver_bots: list = []                                  # set only for --bot solver (we read the solve-rate at the end)
    rich = bot_kind == "solver"                             # --bot solver -> rich per-hand log (showdown cards for Req C)
    # An all-call bot needs no model -> $0, works with any backend (the backend is simply unused). Slumbot is the only
    # network dependency, so this validates the full pipeline (concurrency + progress JSONL + sign) for free.
    # make_bot(stream_id): ONE bot per concurrent stream. The id seeds the solver bots distinctly so K games don't
    # replay the SAME sampling sequence (Req D: per-stream own seed/counters; only _SOLVE_CACHE is shared module state).
    if bot_kind == "allcall":
        make_bot = lambda sid: AllCallBot(counters)  # noqa: E731 — one trivial bot per stream, shared counters
        model_label = "allcall(baseline)"
    elif bot_kind == "solver":
        # Search-at-inference (no model). Each stream gets its OWN SolverSlumbotBot: own RNG (seed a.seed+sid so streams
        # sample independently), own solve/postflop counters, own sample_log. They SHARE only api._SOLVE_CACHE — that's
        # the point: a board solved by one game is a cache HIT for the others (concurrency-safe per Req A). We keep the
        # bots to aggregate their solve-rate at the end.
        def make_bot(sid):  # noqa: E306
            b = SolverSlumbotBot(seed=a.seed + sid, sample_log=[])
            solver_bots.append(b)
            return b
        model_label = "solver-search(HU)"
    elif a.backend == "vllm":
        backend = VLLMBackend(a.vllm_url, a.model)          # ONE shared, stateless, thread-safe backend
        make_bot = lambda sid: _LLMBot(backend, counters)  # noqa: E731 — per-stream bot over the shared server+counters
        model_label = f"vllm:{a.model}@{a.vllm_url}"
    else:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        policy = _load_transformers(a.base, a.adapter)      # one local model; transformers is sequential anyway
        make_bot = lambda sid: _LLMBot(policy, counters)  # noqa: E731
        model_label = f"transformers:{a.adapter}"

    # transformers uses ONE shared model object -> force sequential (K=1). solver/vLLM/allcall fan out (the solver's
    # only shared state, _SOLVE_CACHE, is thread-safe per Req A; each stream gets its own bot).
    fan_out = bot_kind in ("allcall", "solver") or (bot_kind == "qwen" and a.backend == "vllm")
    k = a.concurrency if fan_out else 1
    k = max(1, min(k, a.hands))
    prog = ProgressLog(a.progress_out, time.time(), counters)
    per_stream = _split_hands(a.hands, k)
    print(f"START vs Slumbot | hands={a.hands} bot={bot_kind} concurrency={k} backend={a.backend} "
          f"model={model_label} | progress -> {a.progress_out or '(off)'}", flush=True)

    bots = [make_bot(s) for s in range(k)]
    if k == 1:
        _run_stream(0, bots[0], per_stream[0], prog, a.hands, a.verbose, rich)
    else:
        with ThreadPoolExecutor(max_workers=k) as ex:
            futs = [ex.submit(_run_stream, s, bots[s], per_stream[s], prog, a.hands, a.verbose, rich)
                    for s in range(k) if per_stream[s] > 0]
            for f in as_completed(futs):
                f.result()                                  # surface any stream-fatal error (per-hand errors are caught)

    n, bb100, stderr, frac_bad = prog.summary()
    print(f"\n=== vs Slumbot ({model_label}) ===")
    if solver_bots:
        _report_solver(solver_bots, n, bb100, stderr)
    else:
        print(f"hands={n} | {bb100:+.1f} bb/100 (+/-{stderr:.1f} stderr) | frac_bad={frac_bad:.2f} | "
              f"model={model_label}", flush=True)
    # write a tiny machine-readable final so the pod runner can pull ONE summary line (not just the streaming JSONL)
    if a.progress_out:
        with open(a.progress_out + ".final.json", "w", encoding="utf-8") as f:
            json.dump({"hands": n, "bb100": round(bb100, 2), "stderr": round(stderr, 2),
                       "frac_bad": round(frac_bad, 4), "model": model_label}, f)


if __name__ == "__main__":
    main()
