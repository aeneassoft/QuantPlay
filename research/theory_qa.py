"""Two deep gpt-5.1 analyses the user asked for:
  Q1 — game theory of poker + a CRITICAL examination of mainstream poker theory (ranges, GTO,
       solvability, exploitation/arms-race, and the user's 'bet on strategy-fit, not outcomes' idea).
  Q2 — what the user's own notes + session data reveal about their playstyle / poker understanding.

Run:  python -m extraction.theory_qa
Saves to knowledge_base/theory/.
"""
from __future__ import annotations

from openai import OpenAI

from pokerbot import config
from pokerbot.analysis.session_analysis import compute_stats
from pokerbot.analysis.session_deep import fmt_hand, hnet, user_sessions

client = OpenAI(api_key=config.OPENAI_API_KEY)
NOTES_FILE = r"C:\Users\hampe\Desktop\Textdokument (neu).txt"


def _resolve_model() -> str:
    if config.OPENAI_MODEL:
        return config.OPENAI_MODEL
    try:
        available = {m.id for m in client.models.list()}
        for cand in config.OPENAI_MODEL_PREFERENCE:
            if cand in available:
                return cand
    except Exception:  # noqa: BLE001
        pass
    return "gpt-5.1"


MODEL = _resolve_model()


def ask(system: str, user: str, max_tokens: int) -> str:
    r = client.chat.completions.create(
        model=MODEL, max_completion_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return (r.choices[0].message.content or "").strip()


def q1_game_theory() -> str:
    system = (
        "Du bist Spieltheoretiker UND Poker-KI-Forscher (CFR, Nash, Exploitability, Bayes'sche "
        "Gegnermodellierung, No-Regret-Learning). Sei rigoros, KRITISCH und bereit, Mainstream-"
        "Poker-Dogmen zu hinterfragen. Der Leser ist anspruchsvoll und will LERNEN, nicht beruhigt "
        "werden. Antworte auf Deutsch, klar strukturiert, mit konkreten Konzepten — keine Plattitüden."
    )
    user = (
        "Beantworte rigoros und kritisch:\n\n"
        "1) WARUM hat ein HEURISTISCHER Bot (Equity-vs-Range + Fold-Equity-Sizing + Exploit-Layer) "
        "ausbeutbare Lecks (foldet zu viel gegen Raises, ignoriert Board-Textur), die ein CFR-Bot wie "
        "PLURIBUS NICHT hat? Was ist der fundamentale algorithmische Unterschied (Blueprint via "
        "MCCFR-Selfplay + Echtzeit-Depth-Limited-Search vs. lokale Heuristik)? Warum macht CFR eine "
        "Strategie schwer ausbeutbar?\n\n"
        "2) MACHT das Konzept 'RANGES' überhaupt Sinn? Man kennt nie die exakte aktuelle Range des "
        "Gegners; selbst 'er spielt nie 23o' hat bei einem Menschen keine Garantie, er kann dynamisch "
        "abweichen. Untersuche kritisch Gültigkeit UND Grenzen des Range-Denkens. Was bedeutet eine "
        "Range epistemisch (Verteilung/Glaubensgrad vs. Fakt)? Wie geht GTO damit um, wie exploitatives "
        "Spiel (Bayes-Update)?\n\n"
        "3) Hinterfrage die MAINSTREAM-Poker-Theorie / GTO-Orthodoxie kritisch: Ist GTO als ZIEL "
        "richtig? Blind spots? Wann ist Abweichen klar besser?\n\n"
        "4) KANN man Poker 'lösen'? Was heißt 'gelöst' (HU-Zero-Sum-Nash vs. Mehrspieler/adaptive "
        "Gegner)? Gewinnt am Ende der mit der breitesten Strategie-Bandbreite + Anpassungsfähigkeit? "
        "Wie verhält sich 'Exploit-Arms-Race' zu Nash (jeder Exploit ist selbst ausbeutbar)?\n\n"
        "5) PLURIBUS & Hand-Histories: Ein Profi sagte 'Spieltheorie kennt keine Hand-History'. "
        "Pluribus nutzte KEINE menschlichen Daten (reines Selfplay) — aber seine Echtzeit-Suche nutzt "
        "die AKTIONS-History der laufenden Hand. Kläre diese Verwechslung. Schlägt das Einrechnen von "
        "Gegner-History (Exploitation) reines Equilibrium?\n\n"
        "6) Bewerte diese IDEE des Lesers rigoros: ein System, das nicht auf OUTCOMES wettet, sondern "
        "auf die 'Angebrachtheit/Passung' einer Strategie — z.B. 'mit 30% Wahrscheinlichkeit passt "
        "DIESE Strategie'. Wie verhält sich das zu Bayes'scher Gegnermodellierung, Thompson-Sampling, "
        "einer Verteilung über Gegner-Modelle/Meta-Strategien, robusten/regret-basierten Ansätzen? "
        "Ist es tragfähig? Was sind Fallstricke?"
    )
    return ask(system, user, 9000)


def q2_playstyle() -> str:
    try:
        notes = open(NOTES_FILE, encoding="utf-8").read()
    except OSError:
        notes = "(Notizen nicht lesbar)"
    all_recs = [r for _, recs in user_sessions() for r in recs]
    stats = compute_stats(all_recs) if all_recs else {}
    ranked = sorted(all_recs, key=hnet)
    sample = "\n".join(fmt_hand(r) for r in ranked[:3] + ranked[-3:][::-1])
    system = (
        "Du bist ein scharfsinniger Poker- und Meta-Game-Analyst. Beurteile, was die EIGENEN Notizen "
        "eines Spielers (während er gegen unseren Bot spielte) über sein Poker-Verständnis und sein "
        "META-Denken verraten. Er behauptet, den Bot 'verstanden' zu haben — prüfe das ehrlich. "
        "Antworte auf Deutsch, konkret, mit Bezug auf seine einzelnen Beobachtungen."
    )
    user = (
        f"SPIELER-NOTIZEN (während des Spiels gegen den Bot):\n{notes}\n\n"
        f"AGGREGAT-STATISTIK seiner Sessions: {stats}\n\n"
        f"BEISPIELHÄNDE:\n{sample}\n\n"
        "Beurteile: (a) Auf welchem Niveau denkt dieser Spieler (Level-1/2/3-Denken, Exploitation, "
        "Meta-Game)? (b) Hat er den Bot wirklich verstanden — welche echten Lecks hat er korrekt "
        "identifiziert? (c) Was ist stark, was naiv/falsch in seinen Schlüssen? (d) Was sollte er als "
        "Nächstes lernen, um vom 'Bot-Exploiter' zum starken Spieler zu werden?"
    )
    return ask(system, user, 6000)


def main() -> None:
    out_dir = config.KNOWLEDGE_DIR / "theory"
    out_dir.mkdir(parents=True, exist_ok=True)
    print("=== gpt-5.1 — Q1: SPIELTHEORIE & KRITIK DER MAINSTREAM-THEORIE ===\n")
    a1 = q1_game_theory()
    print(a1)
    (out_dir / "game_theory_critique.md").write_text(a1, encoding="utf-8")
    print("\n\n=== gpt-5.1 — Q2: DEIN PLAYSTYLE (aus deinen Notizen) ===\n")
    a2 = q2_playstyle()
    print(a2)
    (out_dir / "playstyle_analysis.md").write_text(a2, encoding="utf-8")


if __name__ == "__main__":
    main()
