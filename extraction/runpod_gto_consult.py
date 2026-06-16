"""Design a $140 multi-CPU RunPod run to get our HUNL bot CLOSER TO GTO (currently -33 bb/100 AIVAT vs GTO
Wizard, behind Opus 4.6 -20.4). Routing (per the user): DESIGN/poker-architecture -> gpt-5.5 ; POKER-STRATEGY
insight -> Claude Opus 4.6 (it scored well on the GTO Wizard leaderboard). Claude (in-session) synthesizes + the
launch script. Vet for hallucination. Run: python -m extraction.runpod_gto_consult
"""
from __future__ import annotations

from pokerbot import config

GPT = "gpt-5.5"
OPUS46 = "claude-opus-4-6"

BRIEF = """\
OUR BOT + STATE (heads-up NLHE; honest, MEASURED):
- MVP#1 floor = supervised "advisor" MLPs imitating TexasSolver bet/check FREQUENCIES (flop/turn/river) + analytic
  defense/sizing. It MATCHES solver frequencies (GTO-gap ~30%) but LOSES big in bb/100 = a CONTEXT-COLLAPSE /
  abstraction-error problem (it averages over info-sets differing by line/SPR/ranges/size-faced).
- MEASURED vs GTO Wizard AI (AIVAT, the #1 benchmark): **-32.6 +/- 11 bb/100** (n=30 prelim) -> behind Opus 4.6
  (-20.4), ~Gemini level; better than Grok (-60). vs Slumbot we are +31 (Slumbot is exploitable). So: we crush the
  exploitable field, we LOSE to true near-GTO. Goal: close the GTO gap (beat Opus 4.6 -20.4, toward best ~-3).
- MVP#2 (in progress): a HYBRID = supervised blueprint + targeted REAL-TIME sub-game RE-SOLVING (TexasSolver) at
  high-leverage nodes + a range tracker. RIVER resolver is built (solves the actual river public state live, to
  terminal, samples our hand) -- testing vs GTO Wizard now. Turn resolver + a CFV value net are next.
- The GTO Wizard Benchmark paper (arXiv 2603.23660) confirms the direction: GTO Wizard AI = equilibrium-finding +
  deep learning, REAL-TIME computation (not precomputed), self-play RL over 100s of millions of hands, balanced
  unexploitable ranges; the LLMs' failure = FREQUENCY/MIXING mistakes + unbalanced ranges. (We are an LLM-built
  classical bot, not an LLM agent.)
- RESOURCES: TexasSolver (open-source CPU solver; ~ms-to-seconds per postflop spot; we have a RAM-adaptive
  parallel mass-solve harness `extraction/mass_solve.py` + a flop/turn/river GTO cache). Caches store STRATEGY
  FREQUENCIES ONLY (no per-action EVs / CFVs). An optional GPU (RunPod) used before for Deep-CFR/distill.
- NEW: **$140 of RunPod credit** for a MULTI-CPU run to materially close the GTO gap.
"""

GPT_SYSTEM = (
    "You are a world-class HUNL solver/ML systems architect. Design a concrete, budget-bounded compute plan for "
    "THIS bot. Quantify (cores, hours, #solves, $); ground every choice in the measured -33 + the MVP#2 resolver. "
    "No hype; flag what is overkill or won't move EV."
)

GPT_Q = BRIEF + """

DESIGN THE $140 MULTI-CPU RUNPOD RUN to get us materially closer to GTO. Be concrete + budget-bounded:
1. WHAT TO SOLVE for max GTO-closeness/$. Our leak is CONTEXT-COLLAPSE, so we need solved PUBLIC STATES (not just
   boards), across node types our floor is blind to: facing-bet defense PER SIZE, OOP check-raise, probes, turn-
   after-betting lines, river value/bluff sizing, varied SPRs. Specify the sampling: board coverage, range pairs
   (which preflop lines), SPR/stack grid, bet-size abstraction (how many sizes), street priority. What dump do we
   need -- strategy frequencies AND/OR counterfactual values (CFVs) -- to train (a) a richer public-state BLUEPRINT
   net and (b) a CFV/value net for depth-limited flop resolving? (Our cache lacks CFVs -> does TexasSolver dump
   them, or must we compute/modify?)
2. THE BOX + SCALE. Recommend a RunPod CPU instance (vCPU count, $/hr spot/community) and how to spend $140: how
   many parallel TexasSolver processes, expected #solved-public-states in the budget, and whether to also reserve
   some $ for a short GPU training run (CFV net). Quantify (e.g., "64 vCPU @ $X/hr * Y hrs -> Z solves").
3. THE DATA -> MODEL pipeline. What schema to dump; how it trains the blueprint (multi-action, public-state-
   conditioned) + the CFV net (L1 on CFVs). What is the realistic bb/100 gain vs GTO Wizard from (a) the richer
   blueprint alone, (b) + real-time river/turn resolving, (c) + CFV-net flop resolving?
4. HONEST: is a big MASS-SOLVE the right use of $140, or is the compute better spent training a CFV net from a
   SMALLER solve set, or self-play? What's the single highest-leverage $140 plan? Give the concrete launch recipe
   (extend our mass_solve.py: what params, what to dump) + the "do NOT do this" list.
"""

OPUS_SYSTEM = (
    "You are an elite No-Limit Hold'em theorist and player (you score well on the GTO Wizard AI benchmark). Give "
    "sharp, concrete poker-STRATEGY guidance for closing a bot's gap to GTO. Be specific about spots, ranges, "
    "sizing, and balance -- not generic. No hype."
)

OPUS_Q = BRIEF + """

POKER-STRATEGY INSIGHT (you reason about poker better than most -- help us beat your own benchmark score):
1. We lose -33 bb/100 to GTO Wizard AI while MATCHING its bet/check frequencies. From a POKER standpoint, where
   does a frequency-matching-but-context-blind bot bleed the most EV in HUNL 200bb? Rank the spots/concepts
   (facing-bet defense, sizing, turn/river barreling lines, check-raising, blockers, polarization, range
   protection, overbets) by EV impact.
2. If we can RE-SOLVE specific spots in real time, which SPOTS/NODES should we prioritize to claw back the most
   bb/100 fastest, and why (poker reasoning, not just engineering)?
3. What BALANCE / mixing / range-construction principles must the bot get right to stop being exploitable by a
   near-GTO opponent? Concrete examples (e.g., river bluff-to-value ratios, turn barrel ranges, c-bet sizing by
   board texture, defending vs overbets).
4. Any specific, high-EV HUNL spots or heuristics you'd hard-check our bot against (where bots commonly err)?
"""


def ask_openai(model, system, user, effort="high", cap=45000):
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap}, {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"({model} empty finish={r.choices[0].finish_reason} kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"({model} err kw={list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def ask_anthropic(model, system, user, cap=12000):
    from anthropic import Anthropic
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    for m in (model, "claude-opus-4-6-20250115", "claude-opus-4-5"):
        try:
            r = client.messages.create(model=m, max_tokens=cap, system=system,
                                        messages=[{"role": "user", "content": user}])
            txt = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
            if txt.strip():
                return f"[model={m}]\n\n{txt}"
        except Exception as e:  # noqa: BLE001
            print(f"(anthropic {m} err: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main():
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT} (RunPod multi-CPU design) ...", flush=True)
    g = ask_openai(GPT, GPT_SYSTEM, GPT_Q)
    (out / "runpod_gto_gpt55.md").write_text(f"# $140 RunPod multi-CPU run -> closer to GTO ({GPT})\n\n{g}\n", encoding="utf-8")
    print(f"  saved docs/runpod_gto_gpt55.md ({len(g)} chars)", flush=True)
    print(f"=== {OPUS46} (poker-strategy insight) ...", flush=True)
    o = ask_anthropic(OPUS46, OPUS_SYSTEM, OPUS_Q)
    (out / "runpod_gto_opus46.md").write_text(f"# Closing the GTO gap — poker insight ({OPUS46})\n\n{o}\n", encoding="utf-8")
    print(f"  saved docs/runpod_gto_opus46.md ({len(o)} chars)", flush=True)
    print("DONE -- Claude (in-session) vets + designs the launch recipe.", flush=True)


if __name__ == "__main__":
    main()
