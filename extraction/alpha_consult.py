"""Comprehensive 'where is our ALPHA' consult to pressure-test + operationalize the EXPLOIT-PRIMARY concept and
review the WHOLE pipeline/architecture, against real targets (Slumbot crush; Supremus + GTO Wizard overtake).
Routing: gpt-5.5 = poker (concept test, per-target crush, alpha); o3 = architecture/algorithm (pipeline
coherence, exploit-primary objective, opponent-model learning, minimal inversion). I (Claude) vet + synthesize.
Keep it REAL: honest per-target ceilings, no hype. Run: python -m extraction.alpha_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_POKER = "gpt-5.5"
O3 = "o3"

BRIEF = """\
FULL SYSTEM (review the whole pipeline + architecture for coherence + where it LEAKS ALPHA):
- DATA: 5 poker books -> knowledge_base (concepts/ranges/math). TexasSolver -> flop cache (1340) + a turn solve
  (1825 boards, since deleted with the pod). PokerBench -> preflop GTO lookup (88.6% action match).
- FLOOR (history-free, HU): CFR push/fold (verified Nash); strength-model ranges deeper; a supervised "advisor"
  MLP predicting the solver's P(bet) per hand from blocker/potential features, confidence-gated -> flop (+43% vs
  a frequency-only baseline, held out) + turn (+20%); river is blocker-aware analytic. Equity = Monte-Carlo +
  exact river enumeration. Defense = pot-odds/MDF shaded by villain bluffiness. Sizing = "fold-equity-optimal".
- EXPLOIT LAYER (online): an adaptive exploiter + a 62-rule book overlay that NUDGES bluff/value/foldcatch from
  live-measured opponent stats (vpip, fold-to-bet, aggression-freq), with a confidence-gated fallback to the
  floor. Per-opponent models exist for Slumbot (a learned fold-curve) + Pluribus.
- EVAL: solver EV-gap (the cache has NO per-action EVs -> EVs must be derived); a PAIRED/DUPLICATE A/B harness
  (low-variance change-gate); and an LBR that is PROVEN VACUOUS (blind to range-composition leaks + under-
  exploits via passive-after-move).
- MEASURED (honest): vs Slumbot (HU, near-GTO) ~break-even (floor -14.6, exploit +2.2 bb/100 over 500h, noisy);
  crushes weak/exploitable bots +300-700 bb/100. 6-max = each seat decides independently (no joint belief).

ESTABLISHED (do NOT relitigate; build on it): you CANNOT beat true GTO -- break-even is the minimax ceiling.
6-max GTO is undefined (PPAD-hard, non-unique, no scalar exploitability). GTO is a CEILING, not the goal.

THE NEW CONCEPT to pressure-test + operationalize -- "EXPLOIT-PRIMARY": demote GTO from goal to INSURANCE; make
MAXIMAL SAFE EXPLOITATION the engine. Invert the architecture: by default play the max-EV best-response to a fast
online OPPONENT MODEL; fall back to the GTO floor ONLY when the model is too uncertain to beat it. Add ACTIVE
leak-probing (information-gain bets to map the opponent's fold/call curves early). Objective = MAXIMIZE the
opponent's EV-loss (their regret), bounded ONLY by the safe-exploit frontier (~irrelevant vs STATIC opponents
-> exploit to the max; bound only vs adaptive ones).

TARGETS (be BRUTALLY honest about each ceiling -- the user explicitly wants NO HYPE, real bb/100):
- SLUMBOT (HU, static CFR + card/action abstraction, public API + a learned fold-curve): the realistic CRUSH
  target. Where exactly are its abstraction/structural leaks to probe + hammer (fold-curve by size/texture,
  blocker classes, suit-isomorphism breaks, thin-value thresholds, paired/monotone/4-flush rivers, off-tree
  bet sizes, turn/river abstraction)? Honest bb/100 a STRONG TAILORED exploit can realistically extract.
- SUPREMUS AI (a strong HUNL agent; CFVnet/search lineage). If you do NOT know its exact architecture, SAY SO --
  do not fabricate. Assess honestly whether/how it can be overtaken and the realistic ceiling.
- GTO WIZARD AI (plays solved/near-GTO; its public AIVAT benchmark/leaderboard where every agent LOSES, best
  ~-3 bb/100). The user notes it "hides behind its restriction to solving". Honest: is the only attainable goal
  LEAST-LOSS on its board, or is there any exploitable STATIC abstraction leak? No hype.
"""

POKER_SYSTEM = (
    "You are the world's strongest exploitative-NLHE strategist AND a brutally honest analyst who refuses hype. "
    "You know Slumbot, Pluribus, Supremus, GTO Wizard. Give REAL, attainable bb/100 ceilings per opponent; if you "
    "are unsure about a system, say so rather than fabricate. Every claim must be actionable for THIS bot."
)

POKER_Q = BRIEF + """

ANSWER (ranked by attainable edge / effort, brutally honest, flag any hype):
1. PRESSURE-TEST exploit-primary. Is "max-EV best-response to the opponent model, GTO floor only as the
   uncertainty-fallback" sound? How do we capture the BIG EV (not a timid nudge) WITHOUT being counter-exploited
   -- exactly when is max-exploit safe (static opponents) vs when must it be bounded? What breaks this concept?
2. PER-TARGET crush plan with HONEST ceilings: SLUMBOT (the concrete exploitable structure to probe + hammer, and
   the realistic bb/100 a tailored exploit gets vs its ~break-even near-GTO baseline); SUPREMUS (honest, say if
   unknown); GTO WIZARD (honest least-loss reality + any static leak). Rank the three by attainable edge.
3. WHERE IS OUR REAL ALPHA -- the edge no other bot has (opponent model? active probing? safety-bounded max-
   exploit? the beat-them-all breadth?)? What are we MISSING that would actually move the crush?
4. THE OPPONENT MODEL: what to model (per-node fold/call/raise curves, sizing tells, type, drift/tilt) and how to
   learn it FAST + robustly online (few-hand priors, Bayesian shrinkage, active probing). The cheapest version
   that already crushes the field.
"""

O3_SYSTEM = (
    "You are a rigorous ML/algorithms + game-theory researcher and an honest systems architect. Reason precisely, "
    "give concrete algorithms + decision rules, distinguish high-leverage from intellectually-appealing-but-low-"
    "ROI, and do NOT fabricate empirical numbers. It must serve THIS bot on a consolidation phase (mesh existing "
    "parts, don't add complexity)."
)

O3_Q = BRIEF + """

REASON RIGOROUSLY:
1. PIPELINE/ARCHITECTURE COHERENCE: review the whole system above. Where does it LEAK ALPHA -- parts that don't
   mesh, redundancy, signal thrown away (e.g. an exploit overlay that only NUDGES instead of best-responding;
   an opponent model under-used; the vacuous LBR)? The frame: make the conceived engine RUN coherently, fit the
   parts, do NOT add complexity. What is incoherent or wasted TODAY, and the minimal fix?
2. FORMALIZE the exploit-primary objective: best-response-to-model vs maximize-opponent-regret -- which, and the
   precise SAFE-EXPLOIT bound (restricted Nash response / data-biased response / LCB-gated deviation under an
   exploitability budget). Give the concrete per-node DECISION RULE the bot runs.
3. OPPONENT-MODEL LEARNING as a concrete LOW-complexity algorithm: an online Bayesian per-node action model +
   information-gain "leak-probing" (bandit/active exploration), with the few-hand cold-start and shrinkage-to-
   floor when data is thin. What is the right exploration-vs-exploitation tradeoff, and is probing worth its EV
   cost vs just observing?
4. The MINIMAL architecture change to invert to exploit-primary (decide() default = model best-response, GTO as
   fallback) using parts that ALREADY exist (opponent model, overlay, paired-eval gate) -- smallest-first, no
   rebuild. Rank by leverage; be honest about ROI.
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
            print(f"({model} err kw={list(kw)}: {type(e).__name__}: {str(e)[:130]})", flush=True)
    return ""


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT_POKER} (exploit-primary + per-target crush + alpha) ...", flush=True)
    poker = ask_openai(GPT_POKER, POKER_SYSTEM, POKER_Q)
    (out / "alpha_poker_gpt55.md").write_text(f"# Alpha consult — poker/exploit ({GPT_POKER})\n\n{poker}\n", encoding="utf-8")
    print(f"  saved docs/alpha_poker_gpt55.md ({len(poker)} chars)", flush=True)
    print(f"=== {O3} (pipeline coherence + objective + opponent-model algorithm + inversion) ...", flush=True)
    arch = ask_openai(O3, O3_SYSTEM, O3_Q)
    (out / "alpha_arch_o3.md").write_text(f"# Alpha consult — architecture/algorithm ({O3})\n\n{arch}\n", encoding="utf-8")
    print(f"  saved docs/alpha_arch_o3.md ({len(arch)} chars)", flush=True)


if __name__ == "__main__":
    main()
