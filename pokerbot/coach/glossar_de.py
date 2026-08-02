"""P1-A: Deutsches Poker-Glossar — die EINZIGE Quelle der Wahrheit fuer jeden Begriff des Coaching-Layers.

WHY: Das Trainingsprogramm (TRAINER_PLAN.md P1-A, BINDING) erklaert JEDEN Fachbegriff, den Templates,
Feedback oder Session-Report ausspucken koennen, in warmem Alltagsdeutsch — ein Nicht-Pokerspieler muss
es verstehen. Es gibt genau EINE Registry (dieses GLOSSAR) und EINEN Markup-Mechanismus (markup()/term());
P2-2 serviert as_json() ueber GET /api/glossary, P1-B rendert Begriffe ausschliesslich via term().
Kein zweites glossar.json, keine zweite Liste — sonst driften Erklaerung und Anzeige auseinander.

Schema pro Eintrag: {begriff, synonyme: [...], erklaerung (1-3 Saetze, eine Zeile, <=220 Zeichen),
formel?: str, quelle?: str}. Formeln/Quellen der Mathe-Begriffe stammen aus den auditierten Docstrings
in knowledge_base/math/formulas.py — nie erfunden.

Run: python -m pokerbot.coach.glossar_de   (Selbsttest, exit 1 bei FAIL)
"""
from __future__ import annotations

import html
import json
import re

# Fairness-Doktrin (TRAINER_DESIGN.md §1.5): warm, konkret, nie eiskalt; jede Erklaerung Alltagsdeutsch.
MAX_ERKLAERUNG_CHARS = 220   # eine Zeile Klartext — laenger = Textwall, kuerzer erzwingt Einfachheit
MIN_ENTRIES = 50             # Paket-Akzeptanz P1-A: das Glossar deckt den kompletten Coaching-Wortschatz

_FORMULAS = "knowledge_base/math/formulas.py"  # Quelle-Praefix der auditierten Mathe-Docstrings

# ---------------------------------------------------------------------------
# GLOSSAR — kanonische id -> Eintrag. ids sind snake_case und wandern als
# data-term Attribut in die UI (P2-2 Klappfeld springt per id zum Eintrag).
# ---------------------------------------------------------------------------
GLOSSAR: dict[str, dict] = {
    # ---- MATHE ----
    "equity": {
        "begriff": "Equity",
        "synonyme": ["Gewinnwahrscheinlichkeit", "Equities"],
        "erklaerung": "Dein Anteil am Pot, wenn die Hand jetzt bis zum Ende durchgespielt wuerde. 40 % Equity heisst: Von 100 solcher Situationen gewinnst du ungefaehr 40.",
    },
    "pot_odds": {
        "begriff": "Pot Odds",
        "synonyme": ["Pott-Odds", "Pot-Odds", "Potodds"],
        "erklaerung": "Der Preis, den dir der Pot fuer einen Call bietet: Du zahlst den Call und kannst dafuer den ganzen Pot gewinnen. Je groesser der Pot im Verhaeltnis zum Call, desto seltener musst du gewinnen.",
        "formel": "benoetigte Equity = C / (P + B + C)  (C = Call, P = Pot vor dem Einsatz, B = Einsatz)",
        "quelle": _FORMULAS + "::compute_pot_odds",
    },
    "required_equity": {
        "begriff": "Required Equity",
        "synonyme": ["benoetigte Equity", "Break-even-Equity", "Mindest-Equity"],
        "erklaerung": "Wie oft du mindestens gewinnen musst, damit sich ein Call rechnet. Liegt deine echte Gewinnchance darueber, verdient der Call auf Dauer Geld — darunter zahlst du drauf.",
        "formel": "req = to_call / (Pot + to_call)  (Pot enthaelt den gegnerischen Einsatz bereits)",
        "quelle": _FORMULAS + "::compute_pot_odds",
    },
    "mdf": {
        "begriff": "MDF",
        "synonyme": ["Minimum Defense Frequency", "Mindest-Verteidigungsfrequenz"],
        "erklaerung": "Wie oft du gegen einen Einsatz mindestens dranbleiben solltest (Call oder Raise), damit dich der Gegner nicht einfach mit jedem Blatt wegbetten kann.",
        "formel": "MDF = Pot / (Pot + Bet)  (Pot = Pot VOR dem Einsatz)",
        "quelle": _FORMULAS + "::minimum_defense_frequency",
    },
    "spr": {
        "begriff": "SPR",
        "synonyme": ["Stack-to-Pot Ratio", "Stack-Pot-Verhaeltnis"],
        "erklaerung": "Das Verhaeltnis vom kleinsten verbleibenden Stack zum Pot. Kleiner SPR: es geht schnell um alles; grosser SPR: viel Spielraum, mehr Planung noetig.",
        "formel": "SPR = effektiver Stack / Pot",
        "quelle": _FORMULAS + "::compute_spr",
    },
    "outs": {
        "begriff": "Outs",
        "synonyme": ["Out"],
        "erklaerung": "Die Karten im Deck, die deine Hand zur (sehr wahrscheinlich) besten machen. Beispiel: Ein Flush-Draw hat 9 Outs — neun Karten, die dir den Flush bringen.",
    },
    "rule_2_4": {
        "begriff": "Regel von 2 und 4",
        "synonyme": ["Rule of 2 and 4", "2-4-Regel"],
        "erklaerung": "Faustregel zum Kopfrechnen: Outs mal 4 ist deine Trefferchance in Prozent, wenn noch zwei Karten kommen — Outs mal 2, wenn nur noch eine kommt.",
        "formel": "Equity ≈ Outs × 4 % (2 Karten kommen) bzw. Outs × 2 % (1 Karte)",
        "quelle": _FORMULAS + "::outs_to_equity_rule_2_and_4",
    },
    "implied_odds": {
        "begriff": "Implied Odds",
        "synonyme": ["implizite Odds"],
        "erklaerung": "Rechnet zu den Pot Odds das Geld dazu, das du spaeter noch gewinnst, wenn dein Draw ankommt. Deshalb darf ein guter Draw manchmal callen, obwohl der Pot allein es nicht rechtfertigt.",
        "formel": "hit × (Pot + F) = (1 − hit) × Call  (F = noetige zukuenftige Gewinne)",
        "quelle": _FORMULAS + "::required_future_winnings_for_implied_odds",
    },
    "fold_equity": {
        "begriff": "Fold Equity",
        "synonyme": ["Fold-Equity"],
        "erklaerung": "Der Gewinn, der daraus entsteht, dass der Gegner auf deinen Einsatz aufgibt. Auch eine schwache Hand druckt Geld, wenn der Gegner oft genug foldet.",
        "formel": "purer Bluff: noetige Fold-Haeufigkeit = Risiko / (Pot + Risiko)",
        "quelle": _FORMULAS + "::required_fold_equity",
    },
    "alpha_breakeven_bluff": {
        "begriff": "Alpha",
        "synonyme": ["Breakeven-Bluff-Prozent", "Bluff-Breakeven"],
        "erklaerung": "Wie oft der Gegner mindestens folden muss, damit ein reiner Bluff kein Verlustgeschaeft ist. Bei halbem Pot als Einsatz reicht es, wenn er jedes dritte Mal aufgibt.",
        "formel": "Alpha = Bet / (Bet + Pot)",
        "quelle": _FORMULAS + "::breakeven_bluff_percentage",
    },
    "blocker": {
        "begriff": "Blocker",
        "synonyme": ["Blockern", "Card Removal"],
        "erklaerung": "Eine Karte in deiner Hand, die der Gegner dadurch nicht mehr haben kann. Haeltst du das Ass einer Farbe, kann er den besten Flush nicht halten — das macht Bluffs und Calls planbarer.",
        "quelle": _FORMULAS + "::count_hand_combos_with_blockers",
    },
    "combos": {
        "begriff": "Combos",
        "synonyme": ["Kombos", "Kombinationen", "Combo"],
        "erklaerung": "Die Anzahl konkreter Kartenpaare, mit denen eine Hand gebildet werden kann: AK gibt es 16-mal, ein Pocket-Paar nur 6-mal. Damit zaehlt man, wie viel einer Range wirklich existiert.",
        "quelle": _FORMULAS + "::count_hand_combos_with_blockers",
    },
    "equity_realization": {
        "begriff": "Equity-Realisierung",
        "synonyme": ["Equity Realization", "Realization"],
        "erklaerung": "Wie viel deiner theoretischen Gewinnchance du am Tisch wirklich zu Geld machst. In Position holst du meist mehr heraus, aus schlechter Position oft weniger.",
        "formel": "EV = R × Equity × Pot − Kosten",
        "quelle": _FORMULAS + "::equity_realization",
    },
    "ev": {
        "begriff": "EV",
        "synonyme": ["Erwartungswert", "Expected Value"],
        "erklaerung": "Der Durchschnittsgewinn einer Entscheidung, wenn du sie sehr oft wiederholen wuerdest. Gute Entscheidung = positiver EV — auch wenn die einzelne Hand mal verloren geht.",
    },
    "varianz": {
        "begriff": "Varianz",
        "synonyme": ["Variance", "Downswing", "Upswing"],
        "erklaerung": "Das normale Auf und Ab des Gluecks im Poker. Auch perfekt gespielte Haende verlieren mal — deshalb bewerten wir Entscheidungen, nie einzelne Ergebnisse.",
    },
    "bluff_to_value": {
        "begriff": "Bluff-to-Value-Ratio",
        "synonyme": ["Bluff-Value-Verhaeltnis"],
        "erklaerung": "Das gesunde Mischverhaeltnis aus Bluffs und starken Haenden beim Betten. Nur Value ist zu leicht zu folden, nur Bluffs sind zu leicht zu callen — erst die Mischung macht dich unlesbar.",
        "formel": "Bluff-Anteil q = B / (P + 2B)",
        "quelle": _FORMULAS + "::bluff_to_value_and_frequencies",
    },
    # ---- AKTIONEN / LINES ----
    "cbet": {
        "begriff": "C-Bet",
        "synonyme": ["Continuation Bet", "Conti-Bet", "Cbet", "C-Bets"],
        "erklaerung": "Der Einsatz des Spielers, der schon vor dem Flop erhoeht hat und nun weitermacht. Er erzaehlt die Geschichte: Ich hatte die staerkste Hand — und habe sie immer noch.",
    },
    "donk_bet": {
        "begriff": "Donk Bet",
        "synonyme": ["Donk-Bet", "Donken"],
        "erklaerung": "Ein Einsatz aus schlechter Position hinein in den Spieler, der eigentlich die Initiative hatte. Selten die beste Wahl — meist ueberlaesst man dem Aggressor das Betten.",
    },
    "barrel": {
        "begriff": "Barrel",
        "synonyme": ["Second Barrel", "Double Barrel", "Triple Barrel", "barreln"],
        "erklaerung": "Nach einem Einsatz auf der einen Strasse gleich der naechste auf der folgenden. Wer weiterfeuert, erhoeht den Druck — braucht dafuer aber einen Plan fuer die ganze Hand.",
    },
    "probe_bet": {
        "begriff": "Probe Bet",
        "synonyme": ["Probe-Bet"],
        "erklaerung": "Ein Einsatz auf Turn oder River, nachdem der Preflop-Aggressor auf dem Flop nur gecheckt hat. Du fuehlst vor, ob er seine Hand wirklich mag — und nimmst dir den Pot, wenn nicht.",
    },
    "check_raise": {
        "begriff": "Check-Raise",
        "synonyme": ["Checkraise", "Check Raise"],
        "erklaerung": "Erst checken, dann die Bet des Gegners erhoehen. Eine Falle: Du wirkst schwach, lockst einen Einsatz heraus und schlaegst dann zu.",
    },
    "threebet": {
        "begriff": "3-Bet",
        "synonyme": ["3bet", "Threebet", "3-Bets"],
        "erklaerung": "Die zweite Erhoehung: Jemand raist, du erhoehst noch einmal darueber. Ein starkes Signal — diese Range sollte deutlich enger sein als beim normalen Eroeffnen.",
    },
    "fourbet": {
        "begriff": "4-Bet",
        "synonyme": ["4bet", "Fourbet", "4-Bets"],
        "erklaerung": "Die Erhoehung ueber eine 3-Bet — die dritte Eskalationsstufe vor dem Flop. Hier reden meist nur noch sehr starke Haende und ein paar gut gewaehlte Bluffs mit.",
    },
    "squeeze": {
        "begriff": "Squeeze",
        "synonyme": ["Squeeze Play", "Squeezen"],
        "erklaerung": "Eine 3-Bet, nachdem einer erhoeht und mindestens einer gecallt hat. Du quetschst beide: Der Erhoeher fuerchtet dich, der Caller ist dazwischen gefangen.",
    },
    "open_raise": {
        "begriff": "Open Raise",
        "synonyme": ["Open", "Opening Raise", "Eroeffnungsraise"],
        "erklaerung": "Die erste Erhoehung in einer noch unberuehrten Runde — dein Standard-Einstieg in den Pot. Wer zuerst erhoeht, hat die Initiative und oft schon den halben Pot.",
    },
    "limp": {
        "begriff": "Limp",
        "synonyme": ["Limpen", "Open-Limp"],
        "erklaerung": "Nur den Big Blind mitgehen statt zu erhoehen. Gilt meist als zu passiv: Man baut keinen Druck auf und verraet, dass die Hand eher mittelmaessig ist.",
    },
    "overbet": {
        "begriff": "Overbet",
        "synonyme": ["Over-Bet", "Overbets"],
        "erklaerung": "Ein Einsatz groesser als der Pot. Ein Polarisierungs-Werkzeug: Entweder du hast es richtig stark — oder gar nichts. Fuer den Gegner wird jeder Call teuer.",
    },
    "value_bet": {
        "begriff": "Value Bet",
        "synonyme": ["Value-Bet", "Valuebet"],
        "erklaerung": "Ein Einsatz mit einer starken Hand, damit schlechtere Haende bezahlen. Die Kernfrage lautet immer: Callt mich hier wirklich etwas Schlechteres?",
    },
    "thin_value": {
        "begriff": "Thin Value",
        "synonyme": ["duenne Value", "Thin-Value-Bet"],
        "erklaerung": "Eine Value Bet mit einer nur leicht besseren Hand — der Vorsprung ist duenn, aber vorhanden. Wer diese kleinen Einsaetze weglaesst, verschenkt auf Dauer viel Geld.",
    },
    "bluff": {
        "begriff": "Bluff",
        "synonyme": ["Bluffen", "Bluffs"],
        "erklaerung": "Ein Einsatz mit einer Hand, die beim Aufdecken nicht gewinnen wuerde — der Gewinn kommt daraus, dass der Gegner Besseres wegwirft. Gehoert in gesunder Dosis in jede Strategie.",
    },
    "bluffcatcher": {
        "begriff": "Bluffcatcher",
        "synonyme": ["Bluff-Catcher"],
        "erklaerung": "Eine Hand, die nur gegen Bluffs gewinnt: Sie schlaegt keine Value-Hand des Gegners, aber alle seine Bluffs. Der Call lohnt genau dann, wenn er oft genug blufft.",
    },
    "slowplay": {
        "begriff": "Slowplay",
        "synonyme": ["Slow Play", "Slowplayen"],
        "erklaerung": "Eine sehr starke Hand absichtlich schwach spielen (checken/callen statt betten), damit der Gegner Fehler macht oder selbst blufft. Vorsicht auf Boards mit vielen Draws.",
    },
    "allin_jam": {
        "begriff": "All-in",
        "synonyme": ["Allin", "Jam", "Shove", "Push"],
        "erklaerung": "Alles setzen, was du hast. Der maximale Druck: Der Gegner spielt um seinen ganzen Stack — und weitere Entscheidungen gibt es danach nicht mehr.",
    },
    "pot_control": {
        "begriff": "Pot Control",
        "synonyme": ["Pot-Kontrolle"],
        "erklaerung": "Den Pot bewusst klein halten (checken statt betten), wenn deine Hand gut, aber nicht grossartig ist. Kleine Hand, kleiner Pot — grosse Hand, grosser Pot.",
    },
    "side_pot": {
        "begriff": "Side Pot",
        "synonyme": ["Nebenpot", "Side-Pot"],
        "erklaerung": "Entsteht, wenn ein Spieler all-in ist und andere weiterbieten: Das zusaetzliche Geld landet in einem Nebentopf, um den nur die Spieler mit verbliebenen Chips spielen.",
    },
    # ---- KONZEPTE ----
    "range": {
        "begriff": "Range",
        "synonyme": ["Ranges", "Hand-Range"],
        "erklaerung": "Nicht EINE Hand, sondern die ganze Sammlung von Haenden, die jemand in dieser Situation haben kann. Gute Spieler denken in Ranges, nie in einzelnen Karten.",
    },
    "position_ip_oop": {
        "begriff": "Position",
        "synonyme": ["IP", "OOP", "In Position", "Out of Position"],
        "erklaerung": "Wer zuletzt handeln darf, ist 'in Position' (IP) — er sieht erst, was alle anderen tun. Einer der groessten Vorteile am Tisch; 'OOP' heisst entsprechend ausser Position.",
    },
    "initiative": {
        "begriff": "Initiative",
        "synonyme": ["Aggressor"],
        "erklaerung": "Wer zuletzt erhoeht hat, fuehrt die Hand an: Von ihm erwarten alle den naechsten Einsatz. Mit Initiative darfst du Geschichten erzaehlen — ohne sie musst du meist reagieren.",
    },
    "board_textur": {
        "begriff": "Board-Textur",
        "synonyme": ["Board Texture", "Textur"],
        "erklaerung": "Der Charakter der Gemeinschaftskarten: trocken (kaum Draws, etwa K-7-2 bunt) oder nass (viele Draws, etwa 9-8-7 zweifarbig). Sie bestimmt, wie viel Schutz und Druck eine Hand braucht.",
    },
    "draw": {
        "begriff": "Draw",
        "synonyme": ["Draws", "Flushdraw", "Straightdraw"],
        "erklaerung": "Eine noch unfertige Hand, der eine Karte zum starken Blatt fehlt — etwa vier Karten einer Farbe. Ihr Wert steckt in der Zukunft: in den Outs.",
    },
    "made_hand": {
        "begriff": "Made Hand",
        "synonyme": ["fertige Hand", "Made-Hand"],
        "erklaerung": "Eine bereits fertige Hand — Paar, Two Pair, Strasse und besser. Das Gegenstueck zum Draw: Sie muss nichts mehr treffen, sondern will ihren Wert verteidigen oder ausbauen.",
    },
    "kicker": {
        "begriff": "Kicker",
        "synonyme": [],
        "erklaerung": "Die Beikarte neben deinem Paar, die bei gleichem Paar entscheidet. A-K schlaegt A-Q auf einem Ass-Board — allein wegen des besseren Kickers.",
    },
    "mixing": {
        "begriff": "Mischen",
        "synonyme": ["Mixed Strategy", "gemischte Strategie", "Mixing", "mischt"],
        "erklaerung": "Dieselbe Situation absichtlich mal so, mal so spielen (z. B. 60 % betten, 40 % checken). Genau dieses Mischen macht dich unberechenbar — oft sind mehrere Aktionen gleichzeitig richtig.",
    },
    "gto": {
        "begriff": "GTO",
        "synonyme": ["Game Theory Optimal", "spieltheoretisch optimal"],
        "erklaerung": "Die ausbalancierte Spielweise, gegen die es langfristig keinen Trick gibt. Unser Massstab beim Bewerten — nicht weil sie maximal gewinnt, sondern weil sie nicht ausbeutbar ist.",
    },
    "exploit": {
        "begriff": "Exploit",
        "synonyme": ["Exploiten", "exploitativ"],
        "erklaerung": "Gezieltes Abweichen von der Standardlinie, um Schwaechen eines konkreten Gegners auszunutzen — etwa mehr bluffen gegen jemanden, der zu oft foldet. Bringt Gewinn, macht aber selbst angreifbar.",
    },
    "sizing": {
        "begriff": "Sizing",
        "synonyme": ["Bet-Sizing", "Einsatzgroesse", "Sizings"],
        "erklaerung": "Wie gross du deinen Einsatz waehlst, meist als Anteil vom Pot. Das Sizing erzaehlt eine Geschichte und bestimmt den Preis, den Draws und Bluffcatcher zahlen muessen.",
    },
    "hand_class_percentile": {
        "begriff": "Hand-Klasse",
        "synonyme": ["Hand Class", "Percentile", "Perzentil"],
        "erklaerung": "Deine Starthand als Kuerzel (z. B. AKs = Ass-Koenig in gleicher Farbe) plus ihre Einordnung: Zu welchen besten X Prozent aller Starthaende gehoert sie?",
    },
    "showdown": {
        "begriff": "Showdown",
        "synonyme": ["Show-down"],
        "erklaerung": "Der Moment am Ende der Hand, in dem die verbliebenen Spieler ihre Karten aufdecken und die beste Hand den Pot bekommt.",
    },
    "effective_stack": {
        "begriff": "Effektiver Stack",
        "synonyme": ["Effective Stack", "effektive Stacks"],
        "erklaerung": "Der kleinere der beteiligten Stacks — mehr kann in dieser Hand nicht gewonnen oder verloren werden. Alle Planung (SPR, Implied Odds) rechnet mit diesem Wert.",
    },
    "advisor_frequenz": {
        "begriff": "Advisor-Frequenz",
        "synonyme": ["Advisor", "Solver-Frequenz"],
        "erklaerung": "Unsere trainierte Solver-Schaetzung, wie oft GTO an diesem Punkt bettet, callt oder foldet. Liegt deine Aktion in dieser Mischung, war sie gut vertretbar — eine Naeherung, kein hartes Urteil.",
    },
    "solver": {
        "begriff": "Solver",
        "synonyme": [],
        "erklaerung": "Ein Programm, das Poker-Situationen mathematisch durchrechnet und die ausbalancierte GTO-Strategie ausgibt. Unser Schiedsrichter im Hintergrund.",
    },
    "resolver": {
        "begriff": "Resolver",
        "synonyme": ["Re-Solver", "Echtzeit-Solver"],
        "erklaerung": "Ein Rechenwerkzeug, das eine konkrete Situation (vor allem den River) live durchrechnet, statt auf gespeicherte Muster zu vertrauen. Wo es laeuft, sind die Urteile am haertesten.",
    },
    "blueprint": {
        "begriff": "Blueprint",
        "synonyme": ["Preflop-Blueprint"],
        "erklaerung": "Unsere vorberechnete Preflop-Strategie: Fuer jede Starthand und Position steht fest, wie oft geraist, gecallt und gefoldet wird. Preflop ist damit fast geloest — die Kunst beginnt am Flop.",
    },
    "ergebnis_orientierung": {
        "begriff": "Ergebnis-Orientierung",
        "synonyme": ["Ergebnisorientierung", "Results-Oriented"],
        "erklaerung": "Der klassische Denkfehler, eine Entscheidung danach zu bewerten, wie die Hand ausging. Wir bewerten nur die Entscheidung — ein guter Call bleibt gut, auch wenn der River boese war.",
    },
    "grade_band": {
        "begriff": "Grade-Band",
        "synonyme": ["Bewertungsband", "Grade-Baender"],
        "erklaerung": "Unsere drei Stufen pro Entscheidung: OK (gut vertretbar, oft sind mehrere Aktionen OK), Teuer (eine klar bessere Linie existierte) und Leak (harter Rechenfehler).",
    },
    "leak": {
        "begriff": "Leak",
        "synonyme": ["Leaks", "teurer Kauf"],
        "erklaerung": "Ein wiederkehrendes Loch im Spiel, durch das auf Dauer Geld abfliesst — bei uns nur vergeben, wenn die Mathematik klar verletzt wurde. Jedes gefundene Leak ist eine Chance, Geld zu behalten.",
    },
    # ---- STATS ----
    "vpip": {
        "begriff": "VPIP",
        "synonyme": ["Voluntarily Put In Pot"],
        "erklaerung": "Wie oft du freiwillig Geld in den Pot steckst (Call oder Raise vor dem Flop), in Prozent aller Haende. Misst, wie locker oder eng du startest.",
    },
    "pfr": {
        "begriff": "PFR",
        "synonyme": ["Preflop-Raise-Quote"],
        "erklaerung": "Wie oft du vor dem Flop selbst erhoehst, in Prozent aller Haende. Zusammen mit VPIP zeigt es deinen Stil: nah beieinander = aggressiv, weit auseinander = viel passives Callen.",
    },
    "wtsd": {
        "begriff": "WTSD",
        "synonyme": ["Went to Showdown"],
        "erklaerung": "Wie oft du nach dem Flop bis zum Showdown mitgehst. Sehr hohe Werte deuten auf zu viele Calls hin, sehr niedrige darauf, dass du dich zu oft wegbetten laesst.",
    },
    "aggression_factor": {
        "begriff": "Aggression Factor",
        "synonyme": ["Aggressionsfaktor", "AF"],
        "erklaerung": "Das Verhaeltnis deiner aggressiven Aktionen (Bet und Raise) zu deinen Calls nach dem Flop. Zeigt, ob du das Geschehen anfuehrst oder eher hinterherlaeufst.",
    },
    "bb100": {
        "begriff": "bb/100",
        "synonyme": ["bb pro 100 Haende", "Winrate"],
        "erklaerung": "Deine Gewinnrate: wie viele Big Blinds du pro 100 gespielte Haende gewinnst oder verlierst. Die ehrlichste Waehrung im Poker.",
    },
}


# ---------------------------------------------------------------------------
# Lookup + Markup — genau EIN Mechanismus (BINDING P1-A)
# ---------------------------------------------------------------------------
def _build_lookup() -> dict[str, str]:
    """Lowercased Oberflaechenform (begriff + jedes Synonym) -> kanonische id. Kollision = Datenfehler."""
    lookup: dict[str, str] = {}
    for tid, entry in GLOSSAR.items():
        for surface in [entry["begriff"], *entry["synonyme"]]:
            key = surface.lower()
            claimed = lookup.get(key)
            if claimed is not None and claimed != tid:
                raise AssertionError(f"Glossar-Kollision: {surface!r} gehoert zu {claimed!r} UND {tid!r}")
            lookup[key] = tid
    return lookup


_LOOKUP: dict[str, str] = _build_lookup()

# Alternation longest-first: Python probiert Alternativen in Reihenfolge, so gewinnt 'Pot Odds' vor 'Pot'.
# Lookarounds statt \b: Begriffe wie '3-Bet' oder 'bb/100' starten/enden nicht auf Wortzeichen.
_TERM_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(s) for s in sorted(_LOOKUP, key=len, reverse=True)) + r")(?!\w)",
    re.IGNORECASE,
)
# Von markup()/term() erzeugte Spans — bei erneutem markup() unangetastet (Idempotenz).
_SPAN_RE = re.compile(r'<span class="term" data-term="[\w-]+">[^<]*</span>')


def _span(term_id: str, anzeige: str) -> str:
    return '<span class="term" data-term="' + term_id + '">' + html.escape(anzeige) + "</span>"


def term(name: str, text: str | None = None) -> dict | str | None:
    """Zwei Nutzungsarten (deckt Paket-API UND den P1-B-Template-Vertrag ab):

    term(name) -> Eintrag-dict (mit 'id') oder None — Lookup ueber id/begriff/Synonym, case-insensitiv.
    term(name, anzeige_text) -> '<span class="term" data-term="ID">…</span>' — KeyError bei unbekanntem
    Begriff, damit Templates nie einen unregistrierten Term ausliefern (Vollstaendigkeits-Gate P1-A).
    """
    tid = name if name in GLOSSAR else _LOOKUP.get(str(name).lower())
    if text is None:
        return {"id": tid, **GLOSSAR[tid]} if tid is not None else None
    if tid is None:
        raise KeyError(f"Unbekannter Glossar-Begriff: {name!r}")
    return _span(tid, text)


def get(term_id: str) -> dict:
    """Eintrag zur kanonischen id; KeyError bei unbekannter id (Plan P1-A Schritt 3)."""
    return {"id": term_id, **GLOSSAR[term_id]}


def markup(text: str) -> str:
    """Freitext HTML-sicher machen und JEDES bekannte Begriff-/Synonym-Vorkommen in einen Term-Span wickeln.

    Idempotent: bereits erzeugte Spans bleiben unangetastet; Textsegmente werden ueber
    unescape->escape kanonisiert, damit markup(markup(x)) == markup(x) gilt.
    """
    out: list[str] = []
    pos = 0
    for m in _SPAN_RE.finditer(text):
        out.append(_mark_segment(text[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_mark_segment(text[pos:]))
    return "".join(out)


def _mark_segment(segment: str) -> str:
    escaped = html.escape(html.unescape(segment))
    return _TERM_RE.sub(lambda m: _span(_LOOKUP[m.group(0).lower()], m.group(0)), escaped)


def as_json() -> list[dict]:
    """Alle Eintraege fuer GET /api/glossary (P2-2), alphabetisch nach begriff, JSON-serialisierbar."""
    return [
        {"id": tid, "begriff": e["begriff"], "synonyme": list(e["synonyme"]),
         "erklaerung": e["erklaerung"], "formel": e.get("formel"), "quelle": e.get("quelle")}
        for tid, e in sorted(GLOSSAR.items(), key=lambda kv: kv[1]["begriff"].lower())
    ]


def all_terms() -> set[str]:
    """Die Menge aller kanonischen Term-ids (Coverage-Checks der Templates pruefen dagegen)."""
    return set(GLOSSAR)


# ---------------------------------------------------------------------------
# Selbsttest (Idiom: gtowizard._selftest) — synthetisch, kein Server, keine anderen Coach-Module
# ---------------------------------------------------------------------------
def _selftest() -> None:
    # >=50 eindeutige Begriffe, saubere Erklaerungen (eine Zeile, <=220 Zeichen, echtes Deutsch statt Formel)
    assert len(GLOSSAR) >= MIN_ENTRIES, f"nur {len(GLOSSAR)} Eintraege"
    begriffe = [e["begriff"] for e in GLOSSAR.values()]
    assert len({b.lower() for b in begriffe}) == len(begriffe), "doppelter begriff"
    for tid, e in GLOSSAR.items():
        assert e["begriff"].strip() and e["erklaerung"].strip(), tid
        assert "\n" not in e["erklaerung"], f"{tid}: erklaerung mehrzeilig"
        assert len(e["erklaerung"]) <= MAX_ERKLAERUNG_CHARS, f"{tid}: {len(e['erklaerung'])} Zeichen"
        assert len(e["erklaerung"].split()) >= 8, f"{tid}: erklaerung zu duerr (formelartig?)"
        assert isinstance(e["synonyme"], list), tid

    # Kein Synonym kollidiert mit einem anderen begriff/Synonym (der Build wirft sonst schon beim Import)
    _build_lookup()

    # markup: zwei Terme -> zwei Spans mit korrekter data-term-id
    marked = markup("Pot Odds und MDF")
    assert marked.count('<span class="term"') == 2, marked
    assert 'data-term="pot_odds"' in marked and 'data-term="mdf"' in marked, marked
    assert ">Pot Odds</span>" in marked and ">MDF</span>" in marked, marked

    # markup: HTML-Escaping ist sicher, Terme werden trotzdem markiert
    hostile = markup("<script>alert(1)</script> Equity")
    assert "<script>" not in hostile and "&lt;script&gt;" in hostile, hostile
    assert 'data-term="equity"' in hostile, hostile

    # markup: Idempotenz + jedes Vorkommen + Wortgrenzen (Bluffcatcher enthaelt 'Bluff', bleibt EIN Span)
    samples = ["Pot Odds und MDF", "Equity, equity, EQUITY!", "Der Bluffcatcher callt den Bluff.",
               "<b>3-Bet</b> & bb/100", "kein Fachbegriff hier"]
    for s in samples:
        once = markup(s)
        assert markup(once) == once, s
    assert markup("Equity, equity").count('data-term="equity"') == 2
    bc = markup("Der Bluffcatcher callt.")
    assert 'data-term="bluffcatcher"' in bc and 'data-term="bluff"' not in bc, bc

    # term(): Synonym- und case-insensitiver Lookup; Span-Modus; KeyError-Gate
    e = term("pott-odds")
    assert e is not None and e["id"] == "pot_odds" and e["begriff"] == "Pot Odds", e
    assert term("POT ODDS")["id"] == "pot_odds"
    assert term("mdf")["id"] == "mdf" and term("voellig_unbekannt_xyz") is None
    span = term("mdf", "MDF")
    assert span == '<span class="term" data-term="mdf">MDF</span>', span
    try:
        term("voellig_unbekannt_xyz", "x")
        raise AssertionError("term() mit Text muss bei unbekannter id KeyError werfen")
    except KeyError:
        pass
    assert get("spr")["id"] == "spr"
    try:
        get("voellig_unbekannt_xyz")
        raise AssertionError("get() muss KeyError werfen")
    except KeyError:
        pass

    # as_json(): vollstaendig, sortiert, unicode-fest serialisierbar; all_terms() = Menge der ids
    data = as_json()
    assert len(data) == len(GLOSSAR)
    assert [d["begriff"].lower() for d in data] == sorted(d["begriff"].lower() for d in data)
    assert all(set(d) == {"id", "begriff", "synonyme", "erklaerung", "formel", "quelle"} for d in data)
    json.dumps(data, ensure_ascii=False)
    assert all_terms() == set(GLOSSAR) and isinstance(all_terms(), set)

    # Mindest-Inventar des Plans (P2-2 Kern-Terme muessen als begriff oder Synonym aufloesbar sein)
    for need in ["Pot Odds", "MDF", "Equity", "EV", "SPR", "C-Bet", "3-Bet", "Blocker", "Fold Equity",
                 "VPIP", "PFR", "GTO", "Exploit", "Bluffcatcher", "Outs"]:
        assert term(need) is not None, f"Kern-Term fehlt: {need}"

    print(f"OK - Glossar: {len(GLOSSAR)} Begriffe, {len(_LOOKUP)} Oberflaechenformen, "
          f"markup idempotent + escaped, term() synonym-/case-insensitiv.")


if __name__ == "__main__":
    _selftest()
