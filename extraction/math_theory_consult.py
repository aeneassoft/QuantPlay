"""Connect our from-scratch HUNL Deep CFR net to the MATHEMATICAL POKER THEORY we hold (knowledge_base/math/), via
the Claude API. The theory must NOT be a training input — that would contaminate pure self-play exactly like
imitating the bot/LLM (AlphaGo-Zero lesson). It connects in three SOUND ways:
  (1) VALIDATION — the toy games (AKQ, [0,1] half/full-street, clairvoyance) have EXACT analytical GTO, so the net
      should REDISCOVER them (bet size, value:bluff ratio, bluff freq alpha, defend freq, indifference, game value);
  (2) DESIGN — which bet sizes / features / bounds the theory says matter, for our abstraction + feature set;
  (3) INTERPRETATION — read the trained net's strategy in theory terms (alpha, MDF, polarization).
Output = a concrete, numeric validation suite + design notes. Vet for hallucination in-session.
Run: python -m extraction.math_theory_consult
"""
from __future__ import annotations

from pokerbot import config

OUR_NET = """OUR NET (ground every answer here):
A from-scratch neural Deep CFR self-play GTO core for HEADS-UP NLHE (deep_cfr_hunl.py): a self-contained cloneable
HUNL game (fcpa betting: fold/call/POT/all-in; treys showdown; SB50/BB100/20000=200bb) + external-sampling MCCFR +
dual nets (advantage net per player + a policy/average-strategy net), DCFR+ update (discount+clip+bootstrap of
cumulative advantages). 20-dim strength-bucketed features. Validated by EXACT exploitability on Leduc (correctness)
and head-to-head on HUNL; target = beat a -72 bb/100 solver-IMITATION floor vs GTO Wizard. The net learns GTO from
self-play with NO external knowledge — so theory is the CHECK + SCAFFOLD, never a training label."""

SYS = (
    "You are a game-theory-optimal poker theorist at the level of Chen & Ankenman's 'The Mathematics of Poker', AND "
    "a rigorous ML engineer. The user is building a from-scratch neural Deep CFR self-play GTO net for HEADS-UP NLHE. "
    "CRITICAL CONSTRAINT: the analytical theory must NOT be injected into the net's training (pure self-play is the "
    "source of strength; imitation contaminates it). Your job is to CONNECT theory to the net WITHOUT contaminating "
    "it — validation, design, interpretation. Give EXACT NUMBERS wherever the theory provides them (these become unit "
    "tests). Be brutally honest; explicitly flag any value you are not certain is exactly correct so we can verify it."
)


def _read_math() -> str:
    parts = []
    for fn in ("mathematics_of_poker.md", "mathematics_of_poker.json", "math.jsonl"):
        p = config.KNOWLEDGE_DIR / "math" / fn
        if p.exists():
            parts.append(f"--- {fn} ---\n{p.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)[:70000]


def ask_claude(system: str, user: str, max_tokens: int = 8000) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    m = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system,
                               messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in m.content if getattr(b, "type", None) == "text")


def main() -> None:
    docs = config.ROOT / "docs"
    docs.mkdir(exist_ok=True)
    math = _read_math()
    print(f"=== Claude: connecting math theory ({len(math)} chars) to the Deep CFR net ...", flush=True)
    q = OUR_NET + "\n\nMATHEMATICAL POKER THEORY WE HAVE EXTRACTED:\n" + math + """

Produce THREE sections — concrete and NUMERIC:

A. VALIDATION SUITE — the analytically-solved toy games our net must REDISCOVER. For EACH of: the AKQ game; the
   [0,1] half-street game; the [0,1] full-street (both-can-bet) game; the clairvoyance / nuts-or-air vs bluff-catcher
   game; a polarized-range-vs-condensed spot — give the EXACT GTO: optimal bet size (as pot fraction), value:bluff
   ratio, bluffing frequency alpha, the defender's calling/defending frequency, the indifference equations, and the
   game value (to the aggressor). State exact numbers so we can write an assertion that the net matches. Where a value
   depends on stack/pot params, give the closed-form. FLAG any number you are not 100% sure of.

B. DESIGN (theory -> our net, no contamination) — (1) which BET SIZES matter and why (geometric sizing, polarization,
   over-betting the nuts) -> the exact pot-fraction menu we should give the net's action abstraction; (2) which
   FEATURES the net needs to be ABLE to express GTO (range polarity, nut-advantage, SPR, blockers, board texture);
   (3) the BOUNDS the net's output must respect on any single bet: alpha = s/(1+s) bluff ratio, MDF = 1/(1+s) ... give
   the exact formulas in terms of bet-size s (fraction of pot) so we can sanity-check the net's frequencies.

C. INTERPRETATION + HONEST LIMITS — how to read the trained net's strategy in theory terms (is it bluffing at alpha?
   defending at MDF? polarizing?), and explicitly what the theory CANNOT give (multi-street range-vs-range HUNL GTO
   is the net's job; the theory is the unit-test + the scaffold). Be honest about where toy-game intuitions break in
   real multi-street NLHE.
"""
    out = ask_claude(SYS, q)
    (docs / "math_theory_net_connection.md").write_text(
        f"# Connecting the Deep CFR net to Mathematical Poker Theory (Claude)\n\n{out}\n", encoding="utf-8")
    print(f"saved docs/math_theory_net_connection.md ({len(out)} chars)\n"
          f"DONE — these become the net's GTO validation suite + design bounds (in-session vetting next).", flush=True)


if __name__ == "__main__":
    main()
