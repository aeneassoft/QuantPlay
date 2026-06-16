"""Consult GPT-5.5: (1) which HUNL spots are hardest + most VALUABLE for a from-scratch GTO net to get right (so we
prioritize abstraction/features/validation there); (2) VET whether we can use PokerBench (solver-labeled spots) +
Pluribus (6-max histories) WITHOUT contaminating pure self-play; (3) which OpenSpiel METHODOLOGY to apply to our net.
Routing: poker+architecture -> gpt-5.5. Vet all output for hallucination in-session. Run: python -m extraction.hard_spots_consult
"""
from __future__ import annotations

from pokerbot import config

BRIEF = """OUR NET (ground every answer here; honest, not hyped):
A from-scratch neural Deep CFR self-play GTO core for HEADS-UP NLHE (deep_cfr_hunl.py): self-contained cloneable
HUNL game + external-sampling MCCFR + dual nets (advantage per player + policy/avg-strategy), DCFR+ update (validated
on Leduc: neural exploitability 445->338). Currently fcpa betting (fold/call/POT/all-in) + 20-dim strength-bucketed
features; a first fcpa net beats call-station/always-fold/random but is compute-limited. Target: beat a -72 bb/100
solver-IMITATION floor vs GTO Wizard AI (the loss is BROAD postflop quality; run-to-run noise +/-8 bb/100 @ n=2500).
NEXT RUN (already decided, 4 sources converge): FINER bet abstraction (0.33/0.5/0.75/1/1.25/2/allin) + RICHER features
(card occupancy + hand-class/draw/blocker/texture) + DCFR+; gated by a paired A/B vs GTO Wizard. The PURE self-play
GTO core must NOT be trained on imitation data (that is exactly the -72 ceiling we are escaping).

DATA WE HOLD: PokerBench (solver-labeled HUNL spots; we fine-tuned Qwen to 88.6% action-match on it). 10k Pluribus
6-max hand histories. ~1340 flop + 1308 river + turn-subset TexasSolver caches (frequencies only, no per-action EVs).
A local RTX 3080 Ti + optional RunPod. We also have deep_cfr_nlhe.py = OpenSpiel universal_poker Deep CFR (pod-only;
OpenSpiel is NOT installable locally on Windows)."""

SYS = (
    "You are the world's strongest No-Limit Hold'em GTO architect AND a brutally honest ML engineer. Ground EVERY "
    "claim in THIS build. Rank by EV-gained/effort. No hype; flag overkill and self-deception; flag any value you are "
    "not certain of. Respect the stated constraint: the pure self-play GTO core must not be trained on imitation data."
)

Q = BRIEF + """

ANSWER CONCRETELY, ranked, brutally honest:

1. HARDEST + MOST VALUABLE HUNL SPOTS. Rank the postflop (and key preflop) situations by (difficulty for a
   from-scratch self-play net) x (EV-leverage / how much bb/100 is won or lost there vs GTO Wizard). Be specific:
   river bluff-catching, turn barreling / double-barrel give-up, polarized vs condensed (overbet) spots, 3-bet pots
   / low-SPR, blocker-driven bluff selection, check-raise lines, draw-heavy turns, etc. For the TOP spots, say WHY
   they are hard for OUR architecture (fcpa + strength buckets) and WHAT in the next-run upgrade (which bet sizes,
   which features) each spot needs. Which 3-4 spots should drive our abstraction + feature + validation priorities?

2. USING POKERBENCH + PLURIBUS DATA WITHOUT CONTAMINATION. Vet our plan honestly: we will NOT use them as training
   labels for the self-play core. Instead (a) PokerBench = a VALIDATION set — measure our trained net's action-match
   vs the solver labels on held-out HUNL spots (a real-HUNL "GTO match %", richer than toy games); (b) Pluribus 6-max
   histories = an evaluation spot-distribution + opponent-model data for the EXPLOIT overlay (separate from the GTO
   core). Is this the right, non-contaminating use? Is there a BETTER sensible use we're missing (e.g. PokerBench to
   pick the hardest spots to validate; or a warm-start that you would or would NOT recommend, and why)? Be explicit
   about what would and would NOT poison the equilibrium.

3. OPENSPIEL METHODOLOGY TO APPLY. Which parts of OpenSpiel's methodology should we mirror in our OWN from-scratch
   net (without needing OpenSpiel installed locally)? Specifically: the universal_poker INFORMATION-STATE TENSOR as
   our feature representation (vs our hand-crafted 20-dim); reservoir-sampling + external-sampling patterns; the
   exploitability/nash_conv tooling; their Deep CFR / DeepPDCFR reference implementation; and whether RNaD / NFSP /
   PSRO offer anything over Deep CFR for HUNL. Rank by EV/effort; flag what is NOT worth porting. Also: is the
   OpenSpiel C++ traverse (deep_cfr_nlhe.py on a pod) the right answer to our Python-traverse speed bottleneck, or
   should we vectorize our own?"""


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 32000) -> str:
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
            print(f"  ({model} empty, finish={r.choices[0].finish_reason})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main() -> None:
    docs = config.ROOT / "docs"
    docs.mkdir(exist_ok=True)
    print("=== GPT-5.5: hardest/most-valuable spots + data-use + OpenSpiel methodology ...", flush=True)
    out = ask_openai("gpt-5.5", SYS, Q)
    (docs / "hard_spots_gpt55.md").write_text(f"# Hard/valuable spots + data + OpenSpiel — GPT-5.5\n\n{out}\n", encoding="utf-8")
    print(f"saved docs/hard_spots_gpt55.md ({len(out)} chars)\nDONE — Claude (in-session) vets + folds into NEXT_RUN_TODO.", flush=True)


if __name__ == "__main__":
    main()
