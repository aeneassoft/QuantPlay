"""Konsult gpt-5.6-sol (das im Kaggle-Feld staerkste Poker-LLM, Mean BB/100 +34,9) zu drei Fragen:
Flaggschiff-Verbesserung, v10.1-Potenzial, "Zwitter" aus allen gebauten Bauteilen.

Der Schluessel wird AUS DER DATEI gelesen (nie hartkodiert, CLAUDE.md-Regel).
Run:  python -m research.konsult_sol --briefing <pfad.md> --out "KONSULT_GPT56_SOL_2026-09-10.md"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MODELL = "gpt-5.6-sol"
SCHLUESSEL_DATEI = Path(r"C:\Users\hampe\Desktop\Secret keys\AI\OpenAI - API key - Goldbach.txt")

ROLLE = """Du bist ein erfahrener Forscher fuer Poker-KI (CFR/Deep-CFR, Re-Solving, Subgame-Safety,
Exploitability-Messung) UND ein starker Heads-Up-Spieler. Du berätst ein reales, praezise vermessenes
Einzelprojekt, das seit Monaten laeuft. Deine Antwort wird direkt in Bau-Entscheidungen umgesetzt.

Halte dich an folgende Regeln:
- Sei KONKRET. Nenne Module, Datenstrukturen, Schwellen, Reihenfolgen, Abbruchkriterien.
- Trenne strikt: WAS ICH WEISS (Theorie/Literatur), WAS ICH VERMUTE (mit Begruendung), WAS GEMESSEN WERDEN MUSS.
- Gib zu jeder Empfehlung: erwartete Wirkung (Groessenordnung in bb/100 gegen GTO Wizard), Kosten
  (Rechenzeit/Bauzeit), Risiko und den billigsten Test, der sie widerlegen wuerde.
- Sage ausdruecklich, was das Team NICHT tun sollte, und warum.
- Widersprich dem Team, wo seine Doktrin falsch oder ueberdehnt ist. Hoeflichkeit ist zweitrangig, Genauigkeit
  ist alles. Erfinde KEINE Zahlen ueber das Projekt; wenn dir eine Angabe fehlt, sage welche.
- Antworte auf DEUTSCH, in Markdown, ohne Einleitungsfloskeln."""

FRAGEN = """
# DEINE AUFGABE

Drei Fragen. **FRAGE 1 (der "Zwitter") ist die HAUPTFRAGE** — sie soll den GROESSTEN Teil deiner Antwort
bekommen, mindestens die Haelfte. Die Fragen 2 und 3 sind nachgeordnet.

## FRAGE 1 (HAUPTFRAGE) — Der ZWITTER: ein Bot aus ALLEM, was wir gebaut haben

Das Projekt hat ueber Monate viele Bauteile erzeugt, die heute NEBENEINANDER liegen und einzeln vermessen
sind (siehe Inventar im Briefing): Preflop-Blueprint, Range-Tracker, Advisor-MLPs (Solver-Frequenzen),
TexasSolver-Re-Solver, GPU-CFR, river_gpu_guard, oeffentlicher River-Plan (K2), Hero-Likelihood-Replay (K1),
exakter Best-Response-Pruefstand (K3), Fingerprint/Ledger (K4), die AUSLESE-Guard-Kette (v1..v5), das
v9-Ernte-Paket, ICM/Turnier-Schicht, die 6-max-Liga, LLM-Brain-Reste — dazu mehrere ausdruecklich
REFUTIERTE Teile.

Die Kernfrage: **Kann man daraus EINEN Bot bauen — einen Zwitter, der je Entscheidung das jeweils beste
Bauteil einsetzt — und wenn ja, wie genau?**

Beantworte bitte einzeln und ausfuehrlich:

(a) **Ist die Idee tragfaehig oder ein Denkfehler?** Antworte ehrlich, auch wenn die Antwort "nein" oder
    "nur in stark eingeschraenkter Form" lautet. Begruende spieltheoretisch, nicht nur ingenieurmaessig.
    Beruecksichtige dabei ausdruecklich: eine Mischung aus mehreren Politiken ist selbst eine Politik, und
    ihre Ausbeutbarkeit ist NICHT das Minimum der Ausbeutbarkeiten ihrer Teile. Unter welchen Bedingungen
    ist ein Mischer besser als sein bestes Einzelteil, und unter welchen ist er nachweislich schlechter?

(b) **Wie sieht die spieltheoretisch KORREKTE Formulierung aus?** Wir vermuten, dass es hier um
    Politik-Abschluss (jede Umschaltung braucht eine definierte Fortsetzung), Range-Konsistenz (die Ranges
    muessen den tatsaechlich ausgefuehrten Aktionswahrscheinlichkeiten folgen) und Subgame-Sicherheit geht.
    Ist das die richtige Begriffsmenge? Was fehlt? Wie formuliert man den Zwitter sauber — als eine einzige
    Strategie in einem erweiterten Spiel, als Meta-Strategie ueber Experten, als Ensemble mit
    Sicherheitsschranke, oder anders? Nenne die Literatur, die du fuer einschlaegig haeltst.

(c) **Wovon darf die Auswahl abhaengen?** Unsere bisherige Doktrin sagt: oeffentliches Gating ist Standard,
    handabhaengige Auswahl nur als vollstaendig modellierte Strategie. Stimmt das? Was genau geht kaputt,
    wenn die Auswahl von den privaten Karten abhaengt — und gibt es eine saubere Konstruktion, die
    handabhaengige Auswahl doch erlaubt (z. B. als gemischte Strategie mit korrekt fortgeschriebenen Ranges)?

(d) **Konkrete Architektur.** Beschreibe den Zwitter so, dass ein Ingenieur ihn bauen kann:
    - Der Auswahl-Mechanismus: worauf konditioniert er, wie wird er kalibriert, wie wird er GEMESSEN?
    - Zustandsfuehrung: was muss ueber Strassen und Haende hinweg konsistent gehalten werden?
    - Die Nahtstellen: was passiert genau beim Wechsel zwischen zwei Bauteilen mitten in einer Hand,
      und was passiert bei einem Wechsel zwischen zwei Haenden?
    - Die Fallback-Kette: was tut der Zwitter, wenn ein Bauteil ausfaellt, zu langsam ist oder die Hand
      ausserhalb seines Definitionsbereichs liegt? (Unser bisheriger Off-Tree-Fallback landete auf der
      NACKTEN Basis ohne die spaeteren Verbesserungen — genau das hat v10 zerlegt.)
    - Latenz-Budget: wie verteilt man eine feste Rechenzeit je Entscheidung auf die Bauteile?

(e) **Reihenfolge des Baus.** In welcher Reihenfolge wuerdest du die Bauteile integrieren, damit nach jedem
    Schritt ein messbarer, versionierbarer Bot existiert? Nenne je Schritt das Gate, das ihn freigibt.

(f) **Welche Bauteile gehoeren AUSDRUECKLICH NICHT hinein** und warum? Gehe dabei auch auf die refutierten
    Teile ein: ist "refutiert im Spiegel" ein ausreichender Grund zum Ausschluss, oder koennte ein im
    Selbstspiel refutiertes Bauteil in einem Zwitter trotzdem Wert haben?

(g) **Wie misst man den Zwitter?** Unsere Instrumente sind gepaarte Selbstspiel-Kanaele (billig, aber
    stille Kanaele und nur eine Nichtverschlechterungs-Schranke), ein exakter Best-Response-Pruefstand
    gegen feste Politiken, und der teure GTOW-Anker. Wie wuerdest du einen Mischer messen, dessen Wert
    gerade in der Auswahl liegt — und wie verhinderst du, dass die Auswahl auf den Messkanal
    ueberangepasst wird?

(h) **4-Wochen-Bauskizze** mit Meilensteinen, Gates und Abbruchkriterien.

## FRAGE 2 — Die Flaggschiff-Versionen verbessern
Der heutige Champion liegt beim einzigen belastbaren Anker bei rund −21 bb/100 gegen GTO Wizard. Die
Top-5-Schwelle des GTOW-Leaderboards liegt bei einer 95-%-UNTERGRENZE von etwa −14,8, d. h. wir brauchen
einen Mittelwert um −11 bei ~10.000 Haenden oder um −13 bei ~50.000 Haenden.
(a) Woran liegt der Rest-Verlust STRUKTURELL, gegeben unsere Zerlegung (Flop ≈ −8,3, River ≈ −8,6,
    Turn ≈ −1,6, Preflop ≈ −1,6)?
(b) Priorisierte Liste konkreter Eingriffe an der bestehenden Architektur (keine Neubauten), je mit
    erwarteter Wirkung, Aufwand und Falsifikationstest, sortiert nach Wirkung pro Aufwand.
(c) Wo verschwendet das Team Aufwand? Was sollte es einstellen?
(d) Das Ranking nutzt die Intervall-UNTERGRENZE. Was ist die optimale Kombination aus Spielstaerke und
    Handvolumen, um die Top 5 zu erreichen?

## FRAGE 3 — Potenzial von v10.1 (H0 → H1)
v10 ist gebaut, aber ein Gate ist verfehlt (Hero-Likelihood zu ungenau, Hero faellt in 21 von 64 Faellen aus
dem Support; der Off-Tree-Fallback landet auf der nackten Basis). v10.1 soll daraus einen geschlossenen
Hybrid machen: H0 = Plan, sonst unveraendertes produktives v5 je Entscheidung; H1 = Plan plus
range-konsistente Fortsetzung aus der wirklich ausgefuehrten Hybridpolitik.
(a) Realistisches Potenzial in bb/100 gegen GTOW, mit Unsicherheit, begruendet ueber den Mechanismus.
(b) Ist v10.1 der richtige naechste Build oder eine Sackgasse? Wenn Sackgasse: was stattdessen?
(c) Welche Konstruktionsfehler siehst du im H0/H1-Entwurf?
(d) Welche Messung wuerde v10.1 am billigsten widerlegen, BEVOR wir es bauen?
(e) Verhaelt sich v10.1 zum Zwitter aus Frage 1 wie ein Spezialfall — oder sind es zwei verschiedene Dinge?

## FORM
Schreibe eine UMFANGREICHE, technische Antwort auf Deutsch, in Markdown, mit Ueberschriften je Frage.
Mindestens die Haelfte des Umfangs gehoert Frage 1. Am Ende:
- "DIE DREI DINGE, DIE ICH ZUERST TUN WUERDE" (nummeriert, je ein Satz Begruendung)
- "WORIN SICH DAS TEAM MEINER EINSCHAETZUNG NACH IRRT"
- "WAS MIR AN INFORMATION GEFEHLT HAT"
"""


def schluessel() -> str:
    return SCHLUESSEL_DATEI.read_text(encoding="utf-8").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefing", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modell", default=MODELL)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=40000)
    args = ap.parse_args()

    from openai import OpenAI
    kunde = OpenAI(api_key=schluessel())
    briefing = Path(args.briefing).read_text(encoding="utf-8")
    eingabe = f"{ROLLE}\n\n# BRIEFING (Projektstand, alle Zahlen sind gemessen, Quellen als datei:zeile)\n\n{briefing}\n\n{FRAGEN}"
    print(f"Modell {args.modell} | Briefing {len(briefing)} Zeichen | effort {args.effort}", flush=True)

    antwort = kunde.responses.create(
        model=args.modell,
        input=eingabe,
        reasoning={"effort": args.effort},
        max_output_tokens=args.max_tokens,
    )
    text = antwort.output_text
    Path(args.out).write_text(text, encoding="utf-8")
    roh = Path(args.out).with_suffix(".raw.json")
    roh.write_text(json.dumps(antwort.model_dump(), ensure_ascii=False, indent=1), encoding="utf-8")
    u = getattr(antwort, "usage", None)
    print(f"OK: {len(text)} Zeichen -> {args.out} (roh: {roh.name})")
    if u is not None:
        print(f"Tokens: in {getattr(u, 'input_tokens', '?')} / out {getattr(u, 'output_tokens', '?')}")


if __name__ == "__main__":
    main()
