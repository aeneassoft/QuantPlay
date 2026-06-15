"""Deep theory collaboration with gpt-5.5: can we mathematically PROVE 6-max NLHE is "solvable"? Define
"solvable" rigorously (existence vs tractable computation vs uniqueness/value vs the unexploitability
guarantee), give the formal status with REAL theorems, say whether ANY restricted sense is tractably solvable,
and -- most important -- extract the CONCRETE insights that sharpen OUR bot + its next steps. The user's point:
asking the question rigorously advances the direction. Vet all output (esp. citations) for hallucination.
Run: python -m extraction.solvability_proof_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_MODEL = "gpt-5.5"

SYSTEM = (
    "You are a rigorous game theorist + complexity theorist who is ALSO a working poker-AI engineer and brutally "
    "honest. Use REAL theorems and name them correctly (Nash existence 1950; PPAD-completeness of Nash = "
    "Daskalakis-Goldberg-Papadimitriou 2009 + Chen-Deng; von Neumann minimax 1928; CCE via no-regret = "
    "Hart-Mas-Colell 2000; folk theorems; team-game / zero-sum reductions). Do NOT fabricate citations or "
    "numbers -- if unsure, say so. Distinguish EXISTENCE vs TRACTABILITY vs UNIQUENESS vs the UNEXPLOITABILITY "
    "guarantee. Every theoretical point must end in a concrete consequence for THIS bot."
)

BRIEF = """\
OUR BOT + THESIS: HU + 6-max NLHE. HU floor = solver-imitation advisor (flop/turn) + analytic river + CFR
push/fold, with an ONLINE adaptive exploit overlay (confidence-gated fallback). 6-max currently = each seat
decides INDEPENDENTLY from its own cards (per-position ranges), no joint/opponent-coupled model. Our stated edge
= a robust low-exploitability blueprint + an adaptive exploiter of each opponent's gap to GTO. We measure with
solver EV-gap + a (currently weak) LBR; HU vs near-GTO is ~break-even, we crush the field.

PRIOR FINDING (gpt-5.1, to confirm or sharpen): 6-max NLHE is NOT "solvable" the way HU is -- multiplayer
general-sum => computing Nash is PPAD-hard and non-unique, no-regret/CFR reaches a CCE not a Nash, and
exploitability is not a clean scalar. So a bounded-exploitability blueprint + adaptive exploiter is the only
sound target.
"""

QUESTION = BRIEF + """

THE QUESTION (collaborate, be rigorous, then make it USEFUL):

1. CAN WE MATHEMATICALLY PROVE 6-MAX NLHE IS "SOLVABLE"? Split "solvable" into the distinct claims and give the
   precise formal status of EACH, with the correct theorem:
   (a) EXISTENCE of an equilibrium;
   (b) TRACTABLE computation of one (complexity class; what a proof of efficient solvability would imply);
   (c) UNIQUENESS / a well-defined game VALUE;
   (d) the UNEXPLOITABILITY / maximin guarantee that makes "solving" 2p-zero-sum worth it -- does it transfer?
   Be explicit about WHICH of these 6-max passes and which it provably fails, and why the HU "solve =>
   unexploitable" property is a zero-sum artifact.

2. IS THERE ANY SENSE IN WHICH IT IS (TRACTABLY) SOLVABLE? Honestly assess: epsilon-equilibria; correlated/
   coarse-correlated equilibria via no-regret (what they give up vs Nash, and whether a correlation device is
   needed); symmetric / potential-game structure; small-game or heavy-abstraction solves; team-game or
   zero-sum reductions (e.g. 1-vs-the-field); blueprint + depth-limited search a la Pluribus (what it actually
   guarantees, which is NOT a Nash/unexploitability proof). What would a genuine "proof of solvability" require,
   and exactly why does established theory make the meaningful version unattainable?

3. THE PAYOFF (MOST IMPORTANT) -- what CONCRETE insights does the rigorous answer give to improve OUR bot and
   pick the next steps? Reframe "GTO for 6-max" into the mathematically SOUND objective. Specifically:
   - what should we MEASURE for 6-max (per-seat realized EV? regret? a per-opponent best-response gap?) given
     no scalar exploitability exists;
   - what should we BUILD vs NOT build (is the independent-seat model defensible, or is joint-range / opponent-
     coupling mathematically necessary, and to what minimal degree?);
   - does the CCE/no-regret target suggest a concrete, low-complexity algorithm or invariant we can exploit;
   - how does the safe-exploit Pareto frontier (exploit EV vs own exploitability) generalize to 6-max, and what
     is the right per-seat deviation-safety condition;
   - any non-obvious, RIGOROUS edge the impossibility result hands us that other bots ignore.

Be brutally honest: where the answer is "you can't and here's the proof," say so AND turn it into direction.
Rank the bot-relevant insights by (edge or clarity gained / effort), on a consolidation/pruning phase.
"""


def ask_gpt(effort: str = "high", cap: int = 45000) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": QUESTION}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap},
               {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=GPT_MODEL, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"(empty, finish={r.choices[0].finish_reason}, kw={list(kw)})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"(gpt err kw={list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT_MODEL} (6-max solvability proof-status + bot insights, effort=high) ...", flush=True)
    txt = ask_gpt()
    (out / "solvability_proof_gpt55.md").write_text(
        f"# Can we prove 6-max NLHE is solvable? — {GPT_MODEL}\n\n{txt}\n", encoding="utf-8")
    print(f"  saved docs/solvability_proof_gpt55.md ({len(txt)} chars)", flush=True)


if __name__ == "__main__":
    main()
