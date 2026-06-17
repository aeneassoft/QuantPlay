"""Per-situation-solutions ARCHITECTURE consult, grounded in a MEASURED finding: our floor matches the solver's
bet/check FREQUENCIES (GTO-gap 31%/29%) yet LOSES -160 +/-75 bb/100 to TexasSolver in a paired (variance-reduced)
head-to-head. The user's intuition: frequencies aren't enough -- we need MORE SOLUTIONS per individual situation.
Routing (per the user): POKER/GTO -> gpt-5.5 ; REASONING/theory/ML -> o3 ; TECHNICAL synthesis + vetting -> Claude
(done in-session, not here). Vet everything for hallucination. Run: python -m extraction.situational_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_POKER = "gpt-5.5"
O3 = "o3"

BRIEF = """\
OUR BOT (heads-up NLHE; described honestly, MEASURED not hyped):
- PREFLOP: CFR push/fold (verified Nash) + strength-model ranges + a PokerBench-distilled GTO lookup (88.6% match).
- POSTFLOP FLOOR = a HISTORY-FREE supervised approximation of the solver: a per-street "advisor" MLP that predicts
  the SOLVER's P(bet) per hand from BOARD+HAND features (made-tier, texture-class, draws, blockers) + role(OOP/IP),
  for the OOP-lead and IP-cbet-after-check nodes -- FLOP +43%, TURN +20%, RIVER +51% vs the frequency-only baseline
  (held out by board). Plus per-texture donk/cbet frequencies; defense = pot-odds/MDF shaded by villain bluffiness;
  bet SIZING = a fold-equity-optimal heuristic (one size). Equity = MC + exact river enumeration.
- EXPLOIT LAYER: a Dirichlet per-node opponent model + an LCB safe-exploit gate on the RIVER (max-EV deviation when
  confident) + a bounded prediction-gated off-tree size PROBE; falls back to the floor cold-start.
- NOT a real-time solver: no in-play re-solving. The floor is supervised-over-solver-caches + analytic heuristics.

THE MEASURED PROBLEM (this is the whole point -- ground every answer in it):
- vs TexasSolver, PAIRED/duplicate head-to-head (card luck cancelled, 160 hands, 40bb SRP, the oracle plays live
  TexasSolver solves): our floor LOSES **-160 +/- 75 bb/100** (~2 sigma). The earlier UNPAIRED +184 was pure card
  variance -- pairing flipped the sign.
- YET the deterministic GTO-gap says our floor MATCHES the solver's bet/check FREQUENCIES: gap 31% (flop) / 29%
  (river), with aggregate freqs aligned (our-bet ~= GTO-bet: 47/47, IP 75/74, OOP 22/22, river 30/31). The ~30%
  gap is largely the solver's own MIXING/indifference, not error.
- DIAGNOSIS: the advisor is CONTEXT-COLLAPSED / history-free. It maps (board+hand features, role) -> ONE P(bet),
  AVERAGING over distinct info-sets that share those features but differ by LINE, SPR, range-asymmetry, and the
  BET SIZE FACED. The EV loss lives in what a bet-vs-check frequency model does NOT represent: bet SIZING (the
  solver mixes multiple sizes), facing-bet DEFENSE (a full calling/raising range PER size faced), and turn/river
  LINES after a betting sequence. The GTO-gap only scores bet-vs-check at the lead/cbet nodes -- blind to all that.

RESOURCES: TexasSolver (open-source; solves ONE postflop spot in ~ms-to-seconds on CPU locally, dumps the exact
GTO strategy as JSON; this is literally what the oracle that beat us -160 does). Caches: ~1340 flop + 1308 river
solved spots (+ a turn subset). A supervised pipeline (solve -> extract -> train MLP). Modest local CPU + an
optional RunPod GPU (used before for Deep-CFR/distill). The cache stores STRATEGY FREQUENCIES only (no per-action
EVs). 6-max also in scope (multiplayer general-sum).

THE USER'S INTUITION (the question): frequencies alone don't capture it -- we need MORE SOLUTIONS per individual
situation (situation-specific GTO), at least theoretically. Tell us the best ARCHITECTURE to get there for THIS bot.
"""

POKER_SYSTEM = (
    "You are the world's strongest No-Limit Hold'em GTO architect AND a brutally honest game-theory analyst. "
    "Ground EVERY claim in the measured -160-vs-solver finding and THIS bot's actual design. No hype, no generic "
    "advice. Quantify where you can; explicitly flag self-deception and overkill."
)

POKER_Q = BRIEF + """

ANSWER CONCRETELY, ranked by EV-gained / effort, brutally honest:
1. DECOMPOSE THE -160. Of the loss vs the solver, roughly how much is (a) bet SIZING (single heuristic size vs the
   solver's mixed sizes), (b) facing-bet DEFENSE (we use pot-odds/MDF, not a solver calling/raising range per
   size), (c) turn/river LINES after betting (history-free advisor), (d) the OOP-caller's check-raise / probe
   game we don't model? Which is the biggest EV bleed for a history-free freq-floor?
2. THE ARCHITECTURE for "more solutions per situation". Compare for OUR resources, ranked by EV/effort:
   (i) REAL-TIME depth-limited subgame solving in-play (we have TexasSolver locally; this is exactly the oracle
       that beat us). What's the MINIMAL viable version that closes most of the -160 -- which nodes to re-solve,
       what ranges, depth, leaf values, and the speed reality for live play?
   (ii) a RICHER SUPERVISED strategy net conditioned on LINE / SPR / range-asymmetry / size-faced, covering MORE
       node types (facing-bet defense per size, sizing selection, turn/river-after-betting). How far does pure
       supervised-over-more-solves close the gap before it hits the same averaging wall?
   (iii) a value/CFV net (Supremus-style) for fast depth-limited resolving.
   (iv) a HYBRID: supervised blueprint + targeted real-time re-solve only at high-leverage nodes (Pluribus pattern).
   Which is THE move for us, and why? Reference the mitpoker-2024 (gtowizard-ai) depth-limited-solve + value recipe
   if relevant.
3. THE CONCRETE FIRST STEP that proves or kills the direction cheaply, and the honest live-play SPEED problem
   (per-spot solves take ~seconds) -- how do strong bots make real-time solving fast enough (subgame size, action
   abstraction, warm-starting, the value net), and what's the cheapest version that's still a real test?
4. Be explicit: is the user's intuition (more per-situation solutions, not better frequencies) CORRECT, and is
   real-time solving the honest answer, or is a richer supervised model enough? Where would each plateau?
"""

O3_SYSTEM = (
    "You are a rigorous researcher in game theory, online convex optimization, and ML for imperfect-information "
    "games. Cite the ACTUAL theory (CFR/CFR-D re-solving guarantees, depth-limited solving with value functions, "
    "abstraction error bounds, epsilon-Nash, exploitability). Honest cost/benefit; distinguish high-leverage from "
    "intellectually-appealing-but-low-ROI. Serve THIS bot + the measured -160, not a literature review."
)

O3_Q = BRIEF + """

REASON RIGOROUSLY:
1. WHY frequency-match != EV-match (formalize the -160). A strategy is a distribution PER INFO-SET; our advisor
   matches MARGINAL action-frequencies over a COARSE feature partition. Make precise why matching bucket-marginal
   frequencies does NOT bound EV loss: decompose the loss into (within-bucket strategy heterogeneity) x
   (EV-sensitivity / how non-indifferent the spots are), and the role of SIZING + facing-ranges that the partition
   omits entirely. What does the "more solutions" intuition correspond to formally (finer info-set partition /
   lower abstraction error / a per-info-set strategy)?
2. REAL-TIME DEPTH-LIMITED RESOLVING theory: safe vs unsafe re-solving (CFR-D, re-solve gadgets), depth-limited
   solving with LEAF VALUE FUNCTIONS (Brown/Sandholm/Moravcik), and what it PROVABLY buys over a supervised
   blueprint (exploitability bound, the value-net error -> exploitability relation). What is tractable for HU with
   a local CPU solver vs what needs a trained value net? For 6-max: PPAD-hardness, CCE vs Nash -- does real-time
   solving even have the same guarantee?
3. ML-PROCESS: is supervised-imitation-of-solver-FREQUENCIES fundamentally limited (it learns marginals, loses the
   joint per-info-set strategy + sizing + defense)? The right learning target for a value/CFV net (counterfactual
   values), the compute/data trade-off, and whether our cache (frequencies only, no per-action EVs) is even the
   right training signal -- do we need to RE-SOLVE dumping EVs / CFVs? RANK by EV/effort. Flag any fabricated
   specifics (we will verify against the actual literature + our solver).
"""


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 45000) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap},
               {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"({model} empty, finish={r.choices[0].finish_reason}, kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"({model} err kw={list(kw)}: {type(e).__name__}: {str(e)[:140]})", flush=True)
    return ""


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT_POKER} (poker / per-situation architecture) ...", flush=True)
    poker = ask_openai(GPT_POKER, POKER_SYSTEM, POKER_Q)
    (out / "situational_poker_gpt55.md").write_text(f"# Per-situation solutions — poker ({GPT_POKER})\n\n{poker}\n", encoding="utf-8")
    print(f"  saved docs/situational_poker_gpt55.md ({len(poker)} chars)", flush=True)

    print(f"=== {O3} (theory / ML-process) ...", flush=True)
    reason = ask_openai(O3, O3_SYSTEM, O3_Q)
    (out / "situational_reason_o3.md").write_text(f"# Per-situation solutions — theory ({O3})\n\n{reason}\n", encoding="utf-8")
    print(f"  saved docs/situational_reason_o3.md ({len(reason)} chars)", flush=True)
    print("DONE -- Claude (in-session) vets + synthesizes the technical path.", flush=True)


if __name__ == "__main__":
    main()
