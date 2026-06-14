"""Grand synthesis (uses BOTH APIs systematically):
  OpenAI gpt-5.1 (MATH)  -> Does GTO 'exist'? (Nash existence vs computability vs true-GTO for NLHE);
                            the math of beating near-GTO pros (off-tree sizing, safe 2*eps exploit).
  Claude opus  (THEORY)  -> concrete strategies to beat the pros with a real edge; the future of
                            poker; how the Goldbach research methods transfer to our exploiter.

Grounded in OUR measured results + the Goldbach methodology. Saves knowledge_base/theory/grand_synthesis.md
Run: python -m extraction.grand_synthesis
"""
from __future__ import annotations

import anthropic
from openai import OpenAI

from pokerbot import config

client = OpenAI(api_key=config.OPENAI_API_KEY)
OUT = config.KNOWLEDGE_DIR / "theory" / "grand_synthesis.md"

CONTEXT = (
    "OUR MEASURED RESULTS (real):\n"
    "- A universal ADAPTIVE EXPLOITER (robust baseline + online opponent-fold-curve model + safe, "
    "confidence-gated exploit overlay) beats a diverse suite AND 120/120 random unknown opponents.\n"
    "- Cross-source leak check on the PHH dataset: 'over-folds to small/pot bets postflop heads-up' is "
    "NEARLY UNIVERSAL — online cash population +9.5pp over n=38,453, Pluribus +10-12pp; BUT WSOP "
    "final-table ELITE PROS do NOT over-fold (gap -4pp, small n). Multiway high-folding is an MDF "
    "artifact everywhere (tight-correct, not a leak).\n"
    "- We added BOUNDED PROBING (occasional unorthodox test-moves), gated by a prior prediction of a "
    "weakness, with a hard session risk budget (worst-case reserved per probe) — provably cannot run "
    "away. And boolean control knobs an AI co-pilot (Claude Haiku) flips per opponent read.\n\n"
    "GOLDBACH RESEARCH METHODS we want to transfer (from the user's math project):\n"
    "- BLIND PREDICTION: predict structure BEFORE seeing data, then test (= our probe-gating).\n"
    "- PREDATOR-PREY: two INDEPENDENT models converging (rho=0.93) = truth; dominant factors (first 2 "
    "small primes) carry most of the signal.\n"
    "- EXACT VERIFICATION over curve-fitting; counterexample hunting; honesty about empirics vs proof."
)


def openai_math() -> str:
    r = client.chat.completions.create(
        model=config.OPENAI_MODEL or "gpt-5.1", max_completion_tokens=5500,
        messages=[
            {"role": "system", "content": "Rigorous game-theory mathematician. Quantitative, honest, "
             "willing to say 'unknown'. Answer in German."},
            {"role": "user", "content": CONTEXT + "\n\nAUFGABE (Mathematik):\n"
             "1) EXISTIERT GTO? Streng: Nash-Existenzsatz (endliche Spiele -> Gleichgewicht existiert) "
             "vs. EINDEUTIGKEIT/Berechenbarkeit in >2 Spielern vs. die Frage, ob 'wahres GTO' für "
             "volles NLHE überhaupt definierbar/erreichbar ist (Abstraktion, epsilon-Gleichgewicht). "
             "Gib eine klare, begründete Antwort mit Fallunterscheidung HU-Zero-Sum vs. Multiway.\n"
             "2) Wenn Profis das Over-fold-Leck NICHT haben — wo ist mathematisch dann noch ein Edge? "
             "Quantifiziere: Off-Tree-Bet-Sizing-Ausbeutung (Abstraktionslücken), safe-exploitation "
             "(~2*epsilon) gegen near-GTO, und die realistische Größenordnung des Edges vs. Elite.\n"
             "3) Wie groß ist epsilon für Top-Profis grob, und was heißt das für unser bb/100-Ziel?"}])
    return (r.choices[0].message.content or "").strip()


def claude_theory() -> str:
    a = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = a.messages.create(
        model=config.CLAUDE_MODEL, max_tokens=4500,
        system="Scharfer Poker-Theoretiker & Stratege. Konkret, ehrlich, keine Plattitüden. Deutsch.",
        messages=[{"role": "user", "content": CONTEXT + "\n\nAUFGABE (Theorie/Strategie):\n"
                   "1) KONKRETE Strategien, um ECHTE Profis mit echtem Edge zu schlagen — gegeben, dass "
                   "sie das Over-fold-Leck nicht haben. (Population-/Sizing-Reads, Off-Tree-Sizes, "
                   "Multi-Street-Druck, Müdigkeit/Tilt, dynamische Anpassung, unser bounded Probing + "
                   "die adaptive Engine angewandt auf Elite-Menschen.) Sei spezifisch.\n"
                   "2) ZUKUNFT des Spiels: Solver-Sättigung, exploitative Renaissance, AI-Co-Piloten, "
                   "der Arms-Race — wie sieht Poker in 3-5 Jahren aus?\n"
                   "3) Wie übertragen wir die GOLDBACH-Methoden (Predator-Prey-Konvergenz, "
                   "Blind-Prediction, exakte Verifikation, dominante Faktoren) konkret auf unseren Bot?\n"
                   "4) Dein ehrliches Urteil: Existiert GTO praktisch — und ist 'die Profis schlagen' "
                   "realistisch?"}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def main() -> None:
    print("=== OpenAI gpt-5.1 — MATHEMATIK (Existiert GTO? + Profi-Edge) ===\n")
    m = openai_math()
    print(m)
    print("\n\n=== Claude opus — THEORIE (Profi-Strategien, Zukunft, Goldbach-Transfer) ===\n")
    t = claude_theory()
    print(t)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"# Grand synthesis\n\n## Math (OpenAI)\n\n{m}\n\n## Theory (Claude)\n\n{t}\n", encoding="utf-8")
    print(f"\n\nSaved -> {OUT}")


if __name__ == "__main__":
    main()
