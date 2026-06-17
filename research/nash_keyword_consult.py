"""Keyword-reframed consult: query the LLMs about "Nash equilibrium in poker" SPECIFICALLY (not "GTO") — the user's
hypothesis is that the Nash-equilibrium framing tickles DIFFERENT knowledge (algorithms, published near-Nash
solutions, distance-to-Nash measurement) than the saturated "GTO" keyword. Tie it to our live build: a near-Nash HU
200bb bot + a cheap way to MEASURE distance-to-Nash locally (we are building a preflop best-response/exploitability
metric right now). Routing: poker-practice -> gpt-5.5 ; theory/algorithms -> o3. Claude vets in-session.
Run: python -m extraction.nash_keyword_consult
"""
from __future__ import annotations

from pokerbot import config

GPT = "gpt-5.5"
O3 = "o3"

CONTEXT = """OUR LIVE SITUATION: a HU NLHE 200bb bot, ~-72 bb/100 vs GTO Wizard AI (AIVAT). We just built a from-scratch
EXACT preflop CFR+ blueprint (real size menu: limp/2.5/3bet-10/4bet-24/5bet-60/jam, a 169x169 all-in equity matrix, a
checkdown+realization continuation). Goal (the user's explicit framing): do NOT chase opponent-specific EXPLOITS;
instead get CLOSER to a true Nash equilibrium and then MEASURE where we stand. We are building a local preflop
best-response / exploitability metric as the grounded distance-to-Nash gauge (the GTO Wizard API is slow + flaky)."""

POKER_SYS = ("You are a poker AI RESEARCHER (CFR/Pluribus/ReBeL/Supremus lineage) AND a literature scout. Answer with "
             "SPECIFIC, checkable facts — algorithm names, papers, published solutions, numbers. No hand-waving. Flag "
             "anything you are not sure of as such.")
POKER_Q = CONTEXT + """

Search your knowledge under the keyword "NASH EQUILIBRIUM IN POKER" (NOT "GTO" — deliberately the other phrasing, to
surface different material). Be concrete:
1. What NEAR-NASH HU NLHE solutions are actually PUBLISHED or known (preflop range charts at common depths, Slumbot's
   approach, the Libratus/Pluribus blueprints, any open solver outputs)? Cite specifics we could cross-check against.
2. What are the CHEAPEST RELIABLE ways to MEASURE a strategy's distance to Nash WITHOUT a full re-solve — exact
   best-response, local best response (LBR), exploitability descent, AIVAT? Their failure modes (when does LBR read
   ~0 for a leaky strategy)? This is exactly the metric we are coding now — what makes it trustworthy vs vacuous?
3. Is the HU 200bb preflop Nash equilibrium STRUCTURE documented (limp frequencies, multiple open sizes, 4bet/5bet
   mixing, the indifference/blocker logic)? Where would real Nash differ from a simple equity-solved preflop with a
   checkdown continuation (i.e. what is our blueprint most likely getting WRONG)?
4. Anything important about Nash equilibria in poker that the "GTO" framing tends to OBSCURE."""

O3_SYS = ("You are a game theorist (zero-sum extensive games, equilibrium computation, online learning). Cite ACTUAL "
          "theorems/algorithms; separate provable from heuristic; flag fabrication. Serve THIS bot's measured -72.")
O3_Q = CONTEXT + """

Reason under "NASH EQUILIBRIUM" specifically:
1. To MEASURE distance-to-Nash for our preflop strategy in a SMALL solved tree (9 betting nodes, 169 hand classes,
   an all-in equity matrix): formalize the exact best-response / exploitability computation and what it guarantees.
   We compute expl = delta_SB + delta_BB (each = BR_value - strategy_value). Is that the correct exploitability, and
   what does "expl(heuristic) >> expl(blueprint)~0 in the SIMPLIFIED game" actually prove about the REAL game? Where
   is the inference circular, and how do we make a NON-circular distance-to-Nash claim?
2. Exact best-response vs Local Best Response (LBR): why can LBR report ~0 exploitability for a genuinely leaky
   strategy (our LBR was "vacuous")? What is the minimal fix to make a best-response-based metric trustworthy?
3. Distance-to-Nash vs EV-vs-a-specific-opponent: re-state precisely why minimizing exploitability is the right
   target if the goal is "get closer to 100% GTO and see where we stand" (not exploit a specific opponent), and what
   the achievable HU 200bb game value tells us about the BEST we could measure.
4. Cheapest rigorous algorithm to compute (or tightly bound) the exploitability of a FIXED strategy in HU NLHE."""


def ask(model, system, user, cap=42000):
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": "high", "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap}, {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            t = r.choices[0].message.content or ""
            if t.strip():
                return t
            print(f"  ({model} empty finish={r.choices[0].finish_reason})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main():
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT} (Nash-equilibrium-in-poker, keyword-reframed) ...", flush=True)
    a = ask(GPT, POKER_SYS, POKER_Q)
    (out / "nash_keyword_gpt55.md").write_text(f"# Nash equilibrium in poker — keyword consult ({GPT})\n\n{a}\n", encoding="utf-8")
    print(f"  saved docs/nash_keyword_gpt55.md ({len(a)} chars)", flush=True)
    print(f"=== {O3} (distance-to-Nash measurement theory) ...", flush=True)
    b = ask(O3, O3_SYS, O3_Q)
    (out / "nash_keyword_o3.md").write_text(f"# Distance-to-Nash measurement ({O3})\n\n{b}\n", encoding="utf-8")
    print(f"  saved docs/nash_keyword_o3.md ({len(b)} chars)", flush=True)
    print("DONE — Claude vets + folds into the exploitability metric.", flush=True)


if __name__ == "__main__":
    main()
