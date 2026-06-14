"""How do we play (near-)GTO with everything we have, and STAY adaptive (know when to exploit vs
play GTO)? Uses BOTH APIs + our extracted books (Modern Poker Theory + Bill Chen's Mathematics of
Poker).

  OpenAI gpt-5.1 (MATH) -> how to determine/approximate GTO with our assets; Chen indifference /
    optimal bluff & call frequencies / MDF; and the REGIME-SWITCH decision math (when does exploiting
    beat playing GTO — quantified via the safe-exploit bound).
  Claude opus (THEORY)  -> the complete hybrid architecture (GTO baseline + adaptive exploit overlay +
    a regime detector), how MPT + Chen concretely inform a near-GTO baseline, why it fixes the Slumbot
    loss, and concrete build steps.

Saves knowledge_base/theory/gto_hybrid.md.  Run: python -m extraction.gto_hybrid
"""
from __future__ import annotations

import json

import anthropic
from openai import OpenAI

from pokerbot import config

client = OpenAI(api_key=config.OPENAI_API_KEY)
OUT = config.KNOWLEDGE_DIR / "theory" / "gto_hybrid.md"


def book_excerpts(limit: int = 16) -> str:
    kws = ("equilibrium", "optimal", "indiffer", "balance", "minimum defense", "mdf", "bluff",
           "unexploit", "frequency", "gto", "alpha", "range", "chen")
    hits: list[str] = []
    for fn in ("math/mathematics_of_poker.json", "concepts/concepts.json",
               "ranges/range_captions.json", "postflop/openai_strategy.json"):
        fp = config.KNOWLEDGE_DIR / fn
        if not fp.exists():
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        items = data.values() if isinstance(data, dict) else data
        for it in items:
            s = it if isinstance(it, str) else json.dumps(it, ensure_ascii=False)
            if any(k in s.lower() for k in kws):
                hits.append(f"[{fn.split('/')[0]}] {s[:500]}")
            if len(hits) >= limit:
                break
        if len(hits) >= limit:
            break
    return "\n---\n".join(hits) if hits else "(no book excerpts found)"


CONTEXT = (
    "WHERE WE ARE (real, measured):\n"
    "- Our adaptive EXPLOITER crushes the field (beats 200/200 random opponents; +127..+848 bb/100 vs "
    "opponents calibrated to real Pluribus/online-cash/WSOP fold-curves) BUT just LOST to Slumbot "
    "(near-GTO, card-aware) at -207 bb/100 — because its baseline plays VPIP 0.75 (way too loose) and "
    "is itself exploitable. Lesson: vs strong/balanced play we must play GTO, not exploit.\n"
    "- We VALIDATED a real neural Deep CFR (OpenSpiel, PyTorch) on a GPU pod: it converged on Leduc "
    "(nash_conv 2.33 -> 0.33). This is our path to an actual near-GTO baseline (scale to NLHE).\n"
    "- We also have: a verified MCCFR push/fold Nash solver; extracted book knowledge from *Modern "
    "Poker Theory* (Acevedo, GTO ranges/principles) and *The Mathematics of Poker* (Bill Chen & "
    "Ankenman: indifference, optimal frequencies, the [0,1] toy games).\n"
    "GOAL: a HYBRID that plays near-GTO by default (unexploitable, fixes the Slumbot loss) AND switches "
    "to exploitation when it detects exploitable opponents — and knows WHICH regime to use."
)


def main() -> None:
    books = book_excerpts()
    om = config.OPENAI_MODEL or "gpt-5.1"
    print(f"=== OpenAI {om} — MATH: determining GTO + Chen + regime-switch ===\n")
    r = client.chat.completions.create(model=om, max_completion_tokens=5000, messages=[
        {"role": "system", "content": "Rigorous poker game-theory mathematician. Quantitative, honest, "
         "concrete. Answer in German."},
        {"role": "user", "content": CONTEXT + f"\n\nBUCH-AUSZÜGE:\n{books}\n\nAUFGABE (Mathematik):\n"
         "1) Wie bestimmen/approximieren wir GTO mit dem, was wir HABEN (neuronales Deep CFR + CFR "
         "Push/Fold + Buch-Ranges)? Wie nah an echtem GTO ist realistisch erreichbar?\n"
         "2) Bill Chens Mathematik konkret: Indifferenz-Prinzip, optimale Bluff-Frequenz (alpha=s/(1+s)), "
         "optimale Call-/Bluff-Catch-Frequenz (MDF), [0,1]-Toy-Games — gib die nutzbaren Formeln und "
         "wie sie eine near-GTO-Baseline OHNE Solver definieren.\n"
         "3) REGIME-SWITCH-MATHEMATIK: Wann schlägt Exploiten das GTO-Spiel? Formuliere die "
         "Entscheidung quantitativ (exploite nur, wenn der geschätzte Gegner-Leak-EV den eigenen "
         "Exploitability-Anstieg übersteigt; safe-exploit-Bound ~2·epsilon). Wie schätzt man das live?"}])
    math_out = (r.choices[0].message.content or "").strip()
    print(math_out)

    print(f"\n\n=== Claude {config.CLAUDE_MODEL} — THEORY: hybrid architecture + books ===\n")
    a = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = a.messages.create(model=config.CLAUDE_MODEL, max_tokens=4000,
        system="Scharfer Poker-Stratege & KI-Architekt. Konkret, ehrlich, umsetzbar. Deutsch.",
        messages=[{"role": "user", "content": CONTEXT + f"\n\nBUCH-AUSZÜGE:\n{books}\n\nAUFGABE:\n"
                   "1) Entwirf die komplette HYBRID-Architektur: GTO-Baseline (neuronales Deep CFR / "
                   "Buch-Ranges) + adaptive Exploit-Schicht + ein REGIME-DETEKTOR, der live erkennt, ob "
                   "wir GTO spielen (tougher/balancierter Gegner, kein Read) oder exploiten (klare "
                   "Lecks). Konkret: welche Signale, welche Schwellen, wie schalten wir um?\n"
                   "2) Wie informieren *Modern Poker Theory* und *Bill Chen* konkret unsere "
                   "near-GTO-Baseline (Ranges, Frequenzen, Sizings)?\n"
                   "3) Warum behebt das die Slumbot-Niederlage (-207, VPIP 0.75)?\n"
                   "4) Konkrete Bau-Schritte für unseren Bot (was zuerst)."}])
    theory_out = "".join(b.text for b in msg.content if b.type == "text").strip()
    print(theory_out)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"# GTO hybrid (near-GTO baseline + adaptive regime switch)\n\n"
                   f"## Math (OpenAI {om})\n\n{math_out}\n\n## Theory (Claude)\n\n{theory_out}\n",
                   encoding="utf-8")
    print(f"\n\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
