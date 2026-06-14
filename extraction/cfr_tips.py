"""One-off: ask OpenAI (auto-resolves to gpt-5.1) for concrete, VETTABLE tips to improve our Deep-CFR /
GTO-floor net on local hardware. We critically vet the output before applying anything.
Run: python -m extraction.cfr_tips
"""
from __future__ import annotations

from openai import OpenAI

from pokerbot import config


def _resolve_model(client) -> str:
    if config.OPENAI_MODEL:
        return config.OPENAI_MODEL
    try:
        ids = {m.id for m in client.models.list().data}
    except Exception:  # noqa: BLE001
        ids = set()
    for m in config.OPENAI_MODEL_PREFERENCE:
        if m in ids:
            return m
    return config.OPENAI_MODEL_PREFERENCE[0]


CONTEXT = """We are building a No-Limit Hold'em bot. GOAL NOW: a LOW-EXPLOITABILITY GTO "floor" policy net to
sit UNDER an online exploit layer (the exploit layer already exists). Assets / constraints:

- Local GPU: NVIDIA RTX 3080 Ti, 12 GB VRAM; torch 2.11+cu128; Windows; single GPU; no pod right now.
- Engine A (self-contained, validated): PyTorch external-sampling Deep-CFR (Brown 2019) on LEDUC hold'em,
  measured by EXACT exploitability (mbb/hand -> 0). Advantage net 2x128 MLP, regret-matching, reinit-per-iter,
  linear-weighted average. Conceptually scales to NLHE.
- Engine B: OpenSpiel Deep-CFR on universal_poker (FCPA HUNL), now pip-installable on Windows.
- Engine C (we have the data): DISTILLATION from a local TexasSolver GTO cache of ~1340 solved flops
  (single-raised-pot ~100bb, BB vs BTN). Features = 13 fast features (treys made-hand strength, made-hand
  tier, board-texture flags, role IP/OOP, SPR, street). Targets = 5 action buckets
  (fold/check, call, bet-small, bet-big, allin). 2x128 MLP, cross-entropy to the GTO distribution.
  Selector = mean total-variation gap vs GTO on held-out spots. Our earlier DETERMINISTIC analytic baseline
  topped out ~15% gap because it cannot MIX; a stochastic net should beat that.
- Cache facts: IP c-bet strongly texture-conditioned (~77% dry/high vs ~58% wet/connected); GTO puts ~98%
  of c-bet mass on a single ~2/3-pot size; OOP donk ~22% but the ranges may be untuned (suspect).

Give CONCRETE, RANKED, actionable tips (each 1-3 sentences). Cover:
(1) which engine(s) to prioritize on THIS hardware and why;
(2) distillation upgrades: features, targets/bucketing, loss, calibration, and DATA COVERAGE beyond SRP flops
    (turns/rivers, other preflop lines, stack depths) — what matters most;
(3) Deep-CFR self-play upgrades feasible on 12 GB (variance reduction, CFR+/linear weighting, sampling,
    network size, abstraction) and whether self-play or distillation is the better use of this GPU;
(4) how to MEASURE NLHE exploitability HONESTLY when exact best-response is intractable (LBR, local best
    response, depth-limited resolving) — what to actually implement;
(5) the top pitfalls that would make our "floor" SECRETLY exploitable despite a low training loss.
Be specific and honest about trade-offs; flag anything in our setup that is a mistake."""


def main() -> None:
    if not config.OPENAI_API_KEY:
        print("no OpenAI key found")
        return
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    model = _resolve_model(client)
    print(f"== OpenAI model: {model} ==\n", flush=True)
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": "You are a world-class computational game-theory and "
                   "poker-AI engineer (CFR, Deep-CFR, ReBeL, exploitability). Be concrete and honest."},
                  {"role": "user", "content": CONTEXT}],
    )
    print(r.choices[0].message.content)


if __name__ == "__main__":
    main()
