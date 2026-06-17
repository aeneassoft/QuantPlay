"""Consult GPT-5.5 on the SHORT-DECK (6+ Hold'em) opportunity surfaced + VERIFIED this session: TexasSolver
v0.2.0 (bundled) solves short-deck postflop natively (`--mode shortdeck`), and our gto_oracle.solve now wires it.
Strategic question: is short-deck a smarter path to "a bot that is actually near-GTO" than the NLHE least-loss
grind? Honest scope. Run: python -m extraction.shortdeck_consult
"""
from __future__ import annotations

from pokerbot import config

GPT = "gpt-5.5"

BRIEF = """\
CONTEXT (all MEASURED/VERIFIED this session, be skeptical + honest):
- Our project = a HU + 6-max NLHE bot. vs GTO Wizard AI (the #1 benchmark, AIVAT, n=2500, DECISION-GRADE) we are
  stuck at ~-66 to -71 bb/100 — WORSE than always-fold (-64.6). A solver-grounded facing-bet DEFENSE advisor
  (trained on TexasSolver caches, +67% MSE vs the heuristic) moved the floor -70.7 -> -66.4 = only +4.3 bb/100
  (NOT significant). The pattern is clear: vs a balanced near-GTO opponent the gains are tiny = LEAST-LOSS; you
  cannot beat near-GTO. Our real +EV is vs the exploitable field (Slumbot +31). NLHE-vs-GTO-Wizard is a hard grind.
- NEW + VERIFIED BY US (re-ran the falsification, not assumed): TexasSolver v0.2.0 (already bundled) supports
  SHORT-DECK (6+, 36-card, ranks 6-A) NATIVELY via `--mode shortdeck` + a correct C(36,5)=376,992-row hand-rank
  dict (flush>full house, A-6-7-8-9 wheel). We ran a short-deck flop solve: converged ~0.5% exploitability in ~5s,
  the per-combo strategy dump parses through our existing parser, ranks are 6-A only. `gto_oracle.solve(mode=
  "shortdeck")` is wired (default holdem, no NLHE regression). Short-deck = ~630 combos / 81 hand-classes (vs
  1326/169 for NLHE) = a much SMALLER game.
- Honest scope (a frontier consult already flagged): HU short-deck postflop = 2-player zero-sum -> unique value,
  approximable to epsilon. 6-max short-deck (the popular Triton ANTE format) = still PPAD-hard, CCE != Nash, no
  clean exploitability scalar (the smaller deck shrinks the tree but changes ZERO complexity results). GTO Wizard
  does short-deck "Planning only" (no AI benchmark). Critical rule fork: trips-vs-straight order differs by room.
- Our pipeline (deck-agnostic Bayesian range tracker + a real-time TexasSolver resolver + solver-imitation
  advisors) is claimed to PORT to short-deck by editing cards.py RANKS + retraining the advisor on short-deck caches.
"""

Q = BRIEF + """

Be a skeptical poker-AI strategist. Decision-useful, no hype:

1. STRATEGIC VALUE: We're at -66 vs GTO Wizard in NLHE (a least-loss grind; +4 from a defense advisor). Is pivoting
   effort to SHORT-DECK a smarter path to "a bot that is actually near-GTO / that we can WIN with", given short-deck
   is smaller + our solver does it natively? Or is it a distraction from the NLHE goal? Where EXACTLY is the value
   (HU postflop near-GTO demonstration? a sellable short-deck product? a smaller game to prove the pipeline?) vs the
   marketing trap ("we solved 6+").

2. THE MEASUREMENT PROBLEM: in NLHE, GTO Wizard AIVAT is our sharp gate. For short-deck there is NO equivalent
   AI benchmark (GTO Wizard = planning only). So how do we MEASURE "near-GTO" for a HU short-deck bot — solver-gap
   vs our own TexasSolver caches? LBR/exploitability? self-play convergence? Without a sharp external gate, do we
   just repeat the unmeasurable-near-GTO problem? Be concrete about what's actually checkable.

3. MINIMAL EXECUTION PATH (in-repo, cheap, parallel-CPU-capable): given the solver is wired, what is the LEANEST
   path to a MEASURED HU short-deck postflop bot? Rank the steps (rule-lock trips-vs-straight; short-deck cache via
   mode=shortdeck mass-solve; cards.py RANKS=6789TJQKA -> 81 classes; re-derive equity bands; retrain the advisor;
   HU resolver). What's the realistic compute (it's smaller — quantify vs NLHE)? Biggest pitfalls (the rule fork,
   the ante PREFLOP format which our blueprint doesn't cover).

3. HONEST RECOMMENDATION: with finite effort, what % on (a) finishing the NLHE defense advisor (flop+river, the
   +4-and-counting path) vs (b) a HU short-deck near-GTO demonstration vs (c) the exploit-vs-field edge? One ranked
   call. What would make short-deck clearly WORTH it vs clearly a distraction?
"""


def ask_openai(model, user, effort="high", cap=42000):
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    sysmsg = ("You are a skeptical, world-class poker-AI + solver strategist. Ground every claim in the measured "
              "facts given; separate what's checkable from what's hype; give one ranked recommendation. No fluff.")
    msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap}, {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"({model} empty finish={r.choices[0].finish_reason})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"({model} err kw={list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main():
    print(f"=== {GPT} (short-deck strategy consult) ...", flush=True)
    out = ask_openai(GPT, Q)
    p = config.ROOT / "docs" / "shortdeck_consult_gpt55.md"
    p.write_text(f"# Short-deck (6+) strategy consult ({GPT})\n\n{out}\n", encoding="utf-8")
    print(f"saved {p} ({len(out)} chars)", flush=True)


if __name__ == "__main__":
    main()
