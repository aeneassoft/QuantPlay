"""P1-A: Poker-Glossar (Spielertexte Englisch) — die EINZIGE Quelle der Wahrheit fuer jeden Begriff des Coaching-Layers.

WHY: Das Trainingsprogramm (docs/plans/TRAINER_PLAN.md P1-A, BINDING) erklaert JEDEN Fachbegriff, den Templates,
Feedback oder Session-Report ausspucken koennen, in warmer Alltagssprache — ein Nicht-Pokerspieler muss
es verstehen. Es gibt genau EINE Registry (dieses GLOSSAR) und EINEN Markup-Mechanismus (markup()/term());
P2-2 serviert as_json() ueber GET /api/glossary, P1-B rendert Begriffe ausschliesslich via term().
Kein zweites glossar.json, keine zweite Liste — sonst driften Erklaerung und Anzeige auseinander.

Seit 2026-09-24 (quantplay.io) sind begriff/erklaerung/formel Englisch; die deutschen Begriffe bleiben als
Synonyme erhalten, damit Suche und markup() deutsche Oberflaechenformen weiterhin finden.

Schema pro Eintrag: {begriff, synonyme: [...], erklaerung (1-3 Saetze, eine Zeile, <=220 Zeichen),
formel?: str, quelle?: str}. Formeln/Quellen der Mathe-Begriffe stammen aus den auditierten Docstrings
in knowledge_base/math/formulas.py — nie erfunden.

Run: python -m pokerbot.coach.glossar_de   (Selbsttest, exit 1 bei FAIL)
"""
from __future__ import annotations

import html
import json
import re

# Fairness-Doktrin (docs/doctrine/TRAINER_DESIGN.md §1.5): warm, konkret, nie eiskalt; jede Erklaerung Alltagssprache.
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
        "synonyme": ["Gewinnwahrscheinlichkeit", "Equities", "win probability"],
        "erklaerung": "Your share of the pot if the hand were played out to the end right now. 40% equity means: out of 100 such situations you win roughly 40.",
    },
    "pot_odds": {
        "begriff": "Pot Odds",
        "synonyme": ["Pott-Odds", "Pot-Odds", "Potodds"],
        "erklaerung": "The price the pot offers you for a call: you pay the call and can win the whole pot in return. The bigger the pot relative to the call, the less often you need to win.",
        "formel": "required equity = C / (P + B + C)  (C = call, P = pot before the bet, B = bet)",
        "quelle": _FORMULAS + "::compute_pot_odds",
    },
    "required_equity": {
        "begriff": "Required Equity",
        "synonyme": ["benoetigte Equity", "Break-even-Equity", "Mindest-Equity", "break-even equity", "minimum equity"],
        "erklaerung": "How often you need to win, at minimum, for a call to be profitable. If your real chance of winning is above that, the call makes money in the long run — below it, you pay extra.",
        "formel": "req = to_call / (pot + to_call)  (pot already includes the opponent's bet)",
        "quelle": _FORMULAS + "::compute_pot_odds",
    },
    "mdf": {
        "begriff": "MDF",
        "synonyme": ["Minimum Defense Frequency", "Mindest-Verteidigungsfrequenz"],
        "erklaerung": "How often you should at least continue against a bet (call or raise) so your opponent cannot simply bet you off the pot with any two cards.",
        "formel": "MDF = pot / (pot + bet)  (pot = pot BEFORE the bet)",
        "quelle": _FORMULAS + "::minimum_defense_frequency",
    },
    "spr": {
        "begriff": "SPR",
        "synonyme": ["Stack-to-Pot Ratio", "Stack-Pot-Verhaeltnis"],
        "erklaerung": "The ratio of the smallest remaining stack to the pot. Low SPR: it is quickly all or nothing; high SPR: lots of room to play, more planning needed.",
        "formel": "SPR = effective stack / pot",
        "quelle": _FORMULAS + "::compute_spr",
    },
    "outs": {
        "begriff": "Outs",
        "synonyme": ["Out"],
        "erklaerung": "The cards left in the deck that turn your hand into the (very likely) best one. Example: a flush draw has 9 outs — nine cards that complete your flush.",
    },
    "rule_2_4": {
        "begriff": "Rule of 2 and 4",
        "synonyme": ["Regel von 2 und 4", "2-4-Regel", "Rule of 4 and 2"],
        "erklaerung": "A rule of thumb for mental math: outs times 4 is your chance to hit in percent with two cards to come — outs times 2 with only one card to come.",
        "formel": "equity ≈ outs × 4% (two cards to come) or outs × 2% (one card)",
        "quelle": _FORMULAS + "::outs_to_equity_rule_2_and_4",
    },
    "implied_odds": {
        "begriff": "Implied Odds",
        "synonyme": ["implizite Odds"],
        "erklaerung": "Adds to the pot odds the money you can still win later when your draw gets there. That is why a good draw may sometimes call even though the pot alone does not justify it.",
        "formel": "hit × (pot + F) = (1 − hit) × call  (F = future winnings needed)",
        "quelle": _FORMULAS + "::required_future_winnings_for_implied_odds",
    },
    "fold_equity": {
        "begriff": "Fold Equity",
        "synonyme": ["Fold-Equity"],
        "erklaerung": "The profit that comes from your opponent giving up against your bet. Even a weak hand prints money if the opponent folds often enough.",
        "formel": "pure bluff: required fold frequency = risk / (pot + risk)",
        "quelle": _FORMULAS + "::required_fold_equity",
    },
    "alpha_breakeven_bluff": {
        "begriff": "Alpha",
        "synonyme": ["Breakeven-Bluff-Prozent", "Bluff-Breakeven", "break-even bluff percentage"],
        "erklaerung": "How often your opponent has to fold, at minimum, for a pure bluff not to lose money. With a half-pot bet it is enough if they give up every third time.",
        "formel": "alpha = bet / (bet + pot)",
        "quelle": _FORMULAS + "::breakeven_bluff_percentage",
    },
    "blocker": {
        "begriff": "Blocker",
        "synonyme": ["Blockern", "Card Removal", "Blockers"],
        "erklaerung": "A card in your hand that your opponent therefore cannot hold. Holding the ace of a suit means they cannot have the nut flush — that makes bluffs and calls easier to plan.",
        "quelle": _FORMULAS + "::count_hand_combos_with_blockers",
    },
    "combos": {
        "begriff": "Combos",
        "synonyme": ["Kombos", "Kombinationen", "Combo", "Combinations"],
        "erklaerung": "The number of concrete two-card holdings that make up a hand: AK comes in 16 combos, a pocket pair in only 6. That is how you count how much of a range really exists.",
        "quelle": _FORMULAS + "::count_hand_combos_with_blockers",
    },
    "equity_realization": {
        "begriff": "Equity Realization",
        "synonyme": ["Equity-Realisierung", "Realization"],
        "erklaerung": "How much of your theoretical equity you actually turn into money at the table. In position you usually realize more, out of position often less.",
        "formel": "EV = R × equity × pot − cost",
        "quelle": _FORMULAS + "::equity_realization",
    },
    "ev": {
        "begriff": "EV",
        "synonyme": ["Erwartungswert", "Expected Value"],
        "erklaerung": "The average profit of a decision if you repeated it many times. Good decision = positive EV — even if the individual hand is sometimes lost.",
    },
    "varianz": {
        "begriff": "Variance",
        "synonyme": ["Varianz", "Downswing", "Upswing"],
        "erklaerung": "The normal ups and downs of luck in poker. Even perfectly played hands lose sometimes — that is why we grade decisions, never individual results.",
    },
    "bluff_to_value": {
        "begriff": "Bluff-to-Value Ratio",
        "synonyme": ["Bluff-Value-Verhaeltnis", "Bluff-to-Value-Ratio", "bluff ratio"],
        "erklaerung": "The healthy mix of bluffs and strong hands when betting. Only value is too easy to fold against, only bluffs too easy to call — the mix is what makes you unreadable.",
        "formel": "bluff share q = B / (P + 2B)",
        "quelle": _FORMULAS + "::bluff_to_value_and_frequencies",
    },
    # ---- AKTIONEN / LINES ----
    "cbet": {
        "begriff": "C-Bet",
        "synonyme": ["Continuation Bet", "Conti-Bet", "Cbet", "C-Bets"],
        "erklaerung": "The bet by the player who raised before the flop and now keeps going. It tells the story: I had the strongest hand — and I still do.",
    },
    "donk_bet": {
        "begriff": "Donk Bet",
        "synonyme": ["Donk-Bet", "Donken", "Donk"],
        "erklaerung": "A bet from out of position into the player who actually had the initiative. Rarely the best choice — usually you leave the betting to the aggressor.",
    },
    "barrel": {
        "begriff": "Barrel",
        "synonyme": ["Second Barrel", "Double Barrel", "Triple Barrel", "barreln", "barreling"],
        "erklaerung": "Betting one street and then betting again on the next. Firing on raises the pressure — but it needs a plan for the whole hand.",
    },
    "probe_bet": {
        "begriff": "Probe Bet",
        "synonyme": ["Probe-Bet"],
        "erklaerung": "A bet on the turn or river after the preflop aggressor only checked the flop. You probe whether they really like their hand — and take the pot if they do not.",
    },
    "check_raise": {
        "begriff": "Check-Raise",
        "synonyme": ["Checkraise", "Check Raise"],
        "erklaerung": "Check first, then raise your opponent's bet. A trap: you look weak, invite a bet and then strike.",
    },
    "threebet": {
        "begriff": "3-Bet",
        "synonyme": ["3bet", "Threebet", "3-Bets", "Three-Bet"],
        "erklaerung": "The second raise: someone raises, you re-raise on top. A strong signal — this range should be much tighter than a normal open.",
    },
    "fourbet": {
        "begriff": "4-Bet",
        "synonyme": ["4bet", "Fourbet", "4-Bets", "Four-Bet"],
        "erklaerung": "The raise over a 3-bet — the third level of preflop escalation. Usually only very strong hands and a few well-chosen bluffs are still involved here.",
    },
    "squeeze": {
        "begriff": "Squeeze",
        "synonyme": ["Squeeze Play", "Squeezen"],
        "erklaerung": "A 3-bet after one player raised and at least one called. You squeeze both: the raiser fears you, the caller is trapped in between.",
    },
    "open_raise": {
        "begriff": "Open Raise",
        "synonyme": ["Open", "Opening Raise", "Eroeffnungsraise", "Open-Raise"],
        "erklaerung": "The first raise in an untouched pot — your standard way into the hand. Whoever raises first has the initiative and often half the pot already.",
    },
    "limp": {
        "begriff": "Limp",
        "synonyme": ["Limpen", "Open-Limp", "Limping"],
        "erklaerung": "Just calling the big blind instead of raising. Usually considered too passive: you build no pressure and reveal that the hand is rather mediocre.",
    },
    "overbet": {
        "begriff": "Overbet",
        "synonyme": ["Over-Bet", "Overbets"],
        "erklaerung": "A bet bigger than the pot. A polarizing tool: either you have it very strong — or nothing at all. Every call gets expensive for your opponent.",
    },
    "value_bet": {
        "begriff": "Value Bet",
        "synonyme": ["Value-Bet", "Valuebet", "Value Bets"],
        "erklaerung": "A bet with a strong hand so that worse hands pay you off. The core question is always: does anything worse really call me here?",
    },
    "thin_value": {
        "begriff": "Thin Value",
        "synonyme": ["duenne Value", "Thin-Value-Bet", "thin value bet"],
        "erklaerung": "A value bet with a hand that is only slightly better — the edge is thin but real. Skipping these small bets gives away a lot of money over time.",
    },
    "bluff": {
        "begriff": "Bluff",
        "synonyme": ["Bluffen", "Bluffs", "Bluffing"],
        "erklaerung": "A bet with a hand that would not win at showdown — the profit comes from your opponent folding something better. Belongs in every strategy in a healthy dose.",
    },
    "bluffcatcher": {
        "begriff": "Bluffcatcher",
        "synonyme": ["Bluff-Catcher", "Bluff Catcher"],
        "erklaerung": "A hand that only beats bluffs: it loses to every value hand your opponent has but beats all their bluffs. The call is worth it exactly when they bluff often enough.",
    },
    "slowplay": {
        "begriff": "Slowplay",
        "synonyme": ["Slow Play", "Slowplayen", "Slowplaying"],
        "erklaerung": "Deliberately playing a very strong hand weak (check/call instead of bet) so your opponent makes mistakes or bluffs. Careful on boards with lots of draws.",
    },
    "allin_jam": {
        "begriff": "All-in",
        "synonyme": ["Allin", "Jam", "Shove", "Push", "All in"],
        "erklaerung": "Betting everything you have. Maximum pressure: your opponent plays for their whole stack — and there are no more decisions afterwards.",
    },
    "pot_control": {
        "begriff": "Pot Control",
        "synonyme": ["Pot-Kontrolle", "Pot-Control"],
        "erklaerung": "Deliberately keeping the pot small (checking instead of betting) when your hand is good but not great. Small hand, small pot — big hand, big pot.",
    },
    "side_pot": {
        "begriff": "Side Pot",
        "synonyme": ["Nebenpot", "Side-Pot"],
        "erklaerung": "Arises when one player is all-in and others keep betting: the extra money goes into a separate pot that only the players with chips left compete for.",
    },
    # ---- KONZEPTE ----
    "range": {
        "begriff": "Range",
        "synonyme": ["Ranges", "Hand-Range", "hand range"],
        "erklaerung": "Not ONE hand, but the whole collection of hands someone can have in this spot. Good players think in ranges, never in single holdings.",
    },
    "position_ip_oop": {
        "begriff": "Position",
        "synonyme": ["IP", "OOP", "In Position", "Out of Position"],
        "erklaerung": "Whoever acts last is 'in position' (IP) — they see what everyone else does first. One of the biggest edges at the table; 'OOP' means out of position.",
    },
    "initiative": {
        "begriff": "Initiative",
        "synonyme": ["Aggressor"],
        "erklaerung": "Whoever made the last raise leads the hand: everyone expects the next bet from them. With initiative you get to tell stories — without it you mostly have to react.",
    },
    "board_textur": {
        "begriff": "Board Texture",
        "synonyme": ["Board-Textur", "Textur", "Texture"],
        "erklaerung": "The character of the community cards: dry (few draws, e.g. K-7-2 rainbow) or wet (many draws, e.g. 9-8-7 two-tone). It decides how much protection and pressure a hand needs.",
    },
    "draw": {
        "begriff": "Draw",
        "synonyme": ["Draws", "Flushdraw", "Straightdraw", "flush draw", "straight draw"],
        "erklaerung": "An unfinished hand that is one card short of a strong holding — four cards of one suit, say. Its value lies in the future: in the outs.",
    },
    "made_hand": {
        "begriff": "Made Hand",
        "synonyme": ["fertige Hand", "Made-Hand"],
        "erklaerung": "A hand that is already complete — a pair, two pair, a straight or better. The counterpart of a draw: it needs to hit nothing more, it wants to defend or grow its value.",
    },
    "kicker": {
        "begriff": "Kicker",
        "synonyme": [],
        "erklaerung": "The side card next to your pair that decides when the pairs are equal. A-K beats A-Q on an ace-high board — purely because of the better kicker.",
    },
    "mixing": {
        "begriff": "Mixing",
        "synonyme": ["Mischen", "Mixed Strategy", "gemischte Strategie", "mischt"],
        "erklaerung": "Deliberately playing the same spot sometimes one way, sometimes another (e.g. bet 60%, check 40%). This mixing is what makes you unpredictable — often several actions are right at once.",
    },
    "gto": {
        "begriff": "GTO",
        "synonyme": ["Game Theory Optimal", "spieltheoretisch optimal"],
        "erklaerung": "The balanced way of playing that no trick can beat in the long run. Our yardstick for grading — not because it wins the most, but because it cannot be exploited.",
    },
    "exploit": {
        "begriff": "Exploit",
        "synonyme": ["Exploiten", "exploitativ", "exploitative"],
        "erklaerung": "Deliberately deviating from the standard line to attack a specific opponent's weakness — e.g. bluffing more against someone who folds too much. Wins money, but leaves you open to attack.",
    },
    "sizing": {
        "begriff": "Sizing",
        "synonyme": ["Bet-Sizing", "Einsatzgroesse", "Sizings", "bet size"],
        "erklaerung": "How big you make your bet, usually as a fraction of the pot. Sizing tells a story and sets the price that draws and bluffcatchers have to pay.",
    },
    "hand_class_percentile": {
        "begriff": "Hand Class",
        "synonyme": ["Hand-Klasse", "Percentile", "Perzentil"],
        "erklaerung": "Your starting hand as shorthand (e.g. AKs = ace-king suited) plus its ranking: which top X percent of all starting hands does it belong to?",
    },
    "showdown": {
        "begriff": "Showdown",
        "synonyme": ["Show-down"],
        "erklaerung": "The moment at the end of the hand when the remaining players turn over their cards and the best hand takes the pot.",
    },
    "effective_stack": {
        "begriff": "Effective Stack",
        "synonyme": ["Effektiver Stack", "effektive Stacks", "effective stacks"],
        "erklaerung": "The smaller of the stacks involved — no more than that can be won or lost in this hand. All planning (SPR, implied odds) works with this number.",
    },
    "advisor_frequenz": {
        "begriff": "Advisor Frequency",
        "synonyme": ["Advisor-Frequenz", "Advisor", "Solver-Frequenz", "solver frequency"],
        "erklaerung": "Our trained solver estimate of how often GTO bets, calls or folds at this point. If your action sits inside that mix, it was well defensible — an approximation, not a hard verdict.",
    },
    "solver": {
        "begriff": "Solver",
        "synonyme": [],
        "erklaerung": "A program that calculates poker spots mathematically and outputs the balanced GTO strategy. Our referee in the background.",
    },
    "resolver": {
        "begriff": "Resolver",
        "synonyme": ["Re-Solver", "Echtzeit-Solver", "real-time solver"],
        "erklaerung": "A tool that calculates a concrete spot (above all the river) live instead of relying on stored patterns. Where it runs, the verdicts are the strictest.",
    },
    "blueprint": {
        "begriff": "Blueprint",
        "synonyme": ["Preflop-Blueprint", "preflop blueprint"],
        "erklaerung": "Our precomputed preflop strategy: for every starting hand and position it fixes how often to raise, call and fold. Preflop is nearly solved with it — the art begins on the flop.",
    },
    "ergebnis_orientierung": {
        "begriff": "Results-Oriented Thinking",
        "synonyme": ["Ergebnis-Orientierung", "Ergebnisorientierung", "Results-Oriented", "results orientation"],
        "erklaerung": "The classic thinking error of judging a decision by how the hand turned out. We grade only the decision — a good call stays good even if the river was cruel.",
    },
    "grade_band": {
        "begriff": "Grade Band",
        "synonyme": ["Grade-Band", "Bewertungsband", "Grade-Baender", "grade bands"],
        "erklaerung": "Our three levels per decision: OK (well defensible — often several actions are OK), Costly (a clearly better line existed) and Leak (a hard math error).",
    },
    "leak": {
        "begriff": "Leak",
        "synonyme": ["Leaks", "teurer Kauf"],
        "erklaerung": "A recurring hole in your game that money drains through over time — we only flag it when the math was clearly violated. Every leak found is a chance to keep more money.",
    },
    # ---- STATS ----
    "vpip": {
        "begriff": "VPIP",
        "synonyme": ["Voluntarily Put In Pot"],
        "erklaerung": "How often you voluntarily put money into the pot (call or raise before the flop), as a percent of all hands. Measures how loose or tight you start.",
    },
    "pfr": {
        "begriff": "PFR",
        "synonyme": ["Preflop-Raise-Quote", "Preflop Raise"],
        "erklaerung": "How often you raise before the flop yourself, as a percent of all hands. Together with VPIP it shows your style: close together = aggressive, far apart = a lot of passive calling.",
    },
    "wtsd": {
        "begriff": "WTSD",
        "synonyme": ["Went to Showdown"],
        "erklaerung": "How often you go all the way to showdown after seeing a flop. Very high values suggest too many calls, very low ones that you let yourself get bet off too often.",
    },
    "aggression_factor": {
        "begriff": "Aggression Factor",
        "synonyme": ["Aggressionsfaktor", "AF"],
        "erklaerung": "The ratio of your aggressive actions (bets and raises) to your calls after the flop. Shows whether you drive the action or mostly tag along.",
    },
    "bb100": {
        "begriff": "bb/100",
        "synonyme": ["bb pro 100 Haende", "Winrate", "win rate", "bb per 100 hands"],
        "erklaerung": "Your win rate: how many big blinds you win or lose per 100 hands played. The most honest currency in poker.",
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
    # >=50 eindeutige Begriffe, saubere Erklaerungen (eine Zeile, <=220 Zeichen, echte Prosa statt Formel)
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

    # term(): Synonym- und case-insensitiver Lookup (deutsche UND englische Oberflaechen); Span-Modus; KeyError-Gate
    e = term("pott-odds")
    assert e is not None and e["id"] == "pot_odds" and e["begriff"] == "Pot Odds", e
    assert term("POT ODDS")["id"] == "pot_odds"
    assert term("mdf")["id"] == "mdf" and term("voellig_unbekannt_xyz") is None
    assert term("Varianz")["id"] == "varianz" and term("Mischen")["id"] == "mixing"   # deutsche Synonyme bleiben
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
