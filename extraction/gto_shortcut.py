"""Ask OpenAI (gpt-5.1) the deep question: is there a MATHEMATICAL SHORTCUT to (near-)GTO for NLHE
WITHOUT astronomical brute force? Feed it our extracted book math (Mathematics of Poker etc.) and make
it reason rigorously + honestly. Saves knowledge_base/theory/gto_shortcut.md.

Run: python -m extraction.gto_shortcut
"""
from __future__ import annotations

import glob
import json
import os

from openai import OpenAI

from pokerbot import config

client = OpenAI(api_key=config.OPENAI_API_KEY)
OUT = config.KNOWLEDGE_DIR / "theory" / "gto_shortcut.md"


def load_book(budget: int = 18000) -> str:
    chunks = []
    for f in sorted(glob.glob(str(config.MATH_DIR / "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        chunks.append(f"### math/{os.path.basename(f)}\n{json.dumps(d, ensure_ascii=False)[:9000]}")
    for f in sorted(glob.glob(str(config.CONCEPTS_DIR / "*.json")))[:4]:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        chunks.append(f"### concepts/{os.path.basename(f)}\n{json.dumps(d, ensure_ascii=False)[:3500]}")
    return ("\n\n".join(chunks))[:budget] or "(no extracted book math found)"


QUESTION = """
THE QUESTION: Is there a MATHEMATICAL SHORTCUT to (near-)GTO for No-Limit Hold'em that does NOT require
astronomical brute force (no supercomputer-scale CFR over the full game tree)? Reason rigorously and
HONESTLY (no hype). Use the extracted book math above where relevant (cite which formula/idea).

Cover precisely:
1) COMPLEXITY floor: how astronomically large is full NLHE (info sets, with 100-200bb continuous-ish
   bet sizing)? Is there any known polynomial/structural result, or is large-scale computation provably
   unavoidable for EXACT GTO? Where exactly does the cost come from?
2) CLOSED-FORM / ANALYTIC solutions via the INDIFFERENCE PRINCIPLE: how far do exact analytic solutions
   extend (Kuhn, AKQ, [0,1] clairvoyance/half-street/full-street games, polarized vs bluff-catcher,
   alpha = s/(1+s), MDF = P/(P+B))? Can analytic subgame solutions be STITCHED into a near-GTO whole, or
   does card removal / range interaction break that? Be concrete about the boundary.
3) SUBGAME DECOMPOSITION + DEPTH-LIMITED SOLVING (DeepStack/Libratus-style continual re-solving with a
   learned value function at a depth limit): is THIS the real practical shortcut that avoids full-tree
   compute? What does it cost on MODEST hardware (a single workstation / one cheap GPU pod), and what is
   the residual exploitability?
4) ACCELERATION of the iterative solve itself: CFR+ vs Linear/Discounted CFR vs predictive/optimistic
   regret matching vs exploitability-descent — concrete convergence-rate improvements (iterations to
   reach a given exploitability). Do they change the asymptotics or just constants?
5) ABSTRACTION theory: how much do card+action abstraction shrink the problem for a bounded
   exploitability budget? Rule-of-thumb sizes.
6) STACK-DEPTH / SPR STRUCTURE (a user hypothesis to evaluate): "the space of viable strategies shrinks
   as the stack gets shorter (low SPR), collapsing toward solved push/fold; this holds even in cash at
   fixed blinds." Is the strategy-space dimensionality effectively a function of SPR? Does that give a
   tractable decomposition or a principled shortcut (solve deep-stack rarely, short-stack cheaply)?

Finally: given MODEST hardware (one GPU pod + many CPU cores, plus a local TexasSolver postflop oracle
and an analytic Chen/MDF baseline), what is the MOST COMPUTE-EFFICIENT concrete path to a strong
near-GTO NLHE strategy — i.e. the actual shortcut we should implement? Name the single highest-leverage
technique.
"""


def main() -> None:
    om = config.OPENAI_MODEL or "gpt-5.1"
    book = load_book()
    print(f"=== OpenAI {om} — math shortcut to GTO (book math: {len(book)} chars) ===\n")
    r = client.chat.completions.create(
        model=om, max_completion_tokens=7000,
        messages=[{"role": "system", "content": "You are a rigorous game-theory + computational "
                   "complexity mathematician specialising in imperfect-information game solving (CFR, "
                   "Deep CFR, subgame/depth-limited solving, abstraction, exploitability). Be precise, "
                   "cite concrete results, flag hype, give numbers. Answer in German."},
                  {"role": "user", "content": "EXTRACTED BOOK MATH:\n" + book + "\n\n" + QUESTION}])
    out = (r.choices[0].message.content or "").strip()
    print(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"# Mathematical shortcut to GTO? (OpenAI {om})\n\n{out}\n", encoding="utf-8")
    print(f"\n\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
