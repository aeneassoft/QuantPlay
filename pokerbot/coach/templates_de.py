"""Deterministische Feedback-Templates fuer den Trainer (P1-B, docs/plans/TRAINER_PLAN.md) — Spielertext auf Englisch.

WHY: die Sprachschicht ENTSCHEIDET nichts und RECHNET nichts (docs/doctrine/TRAINER_DESIGN.md par.3) — sie uebersetzt die vom
Grader (P0) gefuellten Decision-Records in warme, konkrete Saetze nach der Fairness-Doktrin par.1:
nie Ergebnisse graden, gute Zuege EXPLIZIT feiern, ein Leak heisst "costly" (teurer Kauf), jede Kritik traegt die
Alternative + den Ein-Satz-Grund, gemischter Support wird GESAGT ("... both fine"). Zahlen erscheinen einmal
als Zahl und dann als Vergleich ("needed 1-in-3, had 1-in-4").

INPUT-KONTRAKT (docs/doctrine/TRAINER_DESIGN.md par.4, BINDEND — jeder Zugriff via .get() mit Fallback):
    record = {hand_id, ts, street, spot_fp, state_kompakt, human_action: {action, amount}|str,
              oracle_action: str|{action,...}, advisor_dist: {aktion: p}, equity, pot_odds, mdf,
              grade: 'ok'|'teuer'|'leak' (PINNED — unbekannter Grade -> ValueError),
              grade_typ: 'pot_odds'|'mdf'|'sizing'|'advisor_freq'|'oracle_diff' (fehlend -> generischer Zweig),
              erklaerung_kurz, confidence, checks: {pot_odds|mdf|sizing|advisor: {...}}, mode, rationale}
Pot-Konventionen der Zahlen im Record folgen understanding.py:76-81 (required_equity nutzt den Pot AS-FACED;
MDF den PRE-bet Pot) — hier wird NUR gerendert, nie nachgerechnet.

Public API (BINDING P1-B): render_decision_feedback(rec) / render_hand_feedback(records, hand_result, mode)
— beide geben {'text', 'html', 'terms'} zurueck; html via glossar_de.markup (guarded, Fallback html=text);
TERMS_USED (exakt dieser Name) = frozenset aller Glossar-Term-Ids, die diese Templates emittieren koennen.

Run: python -m pokerbot.coach.templates_de   (Selftest: Branch-Abdeckung, Determinismus, TERMS_USED-Abdeckung)
"""
from __future__ import annotations

import re

# Shared thresholds — grader math and UI text must agree (recon reuse mandate). understanding._in_position/
# _effective_stack_bb need the Spot DATACLASS; records carry asdict()-dicts, so geometry sentences are re-rendered
# from the record's numeric fields instead (plan P1-B step 8) and the helpers are deliberately NOT imported.
try:
    from pokerbot.brain.understanding import MEDIUM_MADE, STRONG_MADE
except Exception:                                     # noqa: BLE001 — standalone fallback mirrors understanding.py:25-26
    STRONG_MADE, MEDIUM_MADE = 0.62, 0.40

try:                                                  # P1-A wird parallel gebaut — Import strikt optional
    from pokerbot.coach import glossar_de as _G
except Exception:                                     # noqa: BLE001
    _G = None

GRADE_ICON = {"ok": "✓", "teuer": "～", "leak": "✗"}
GRADE_TYPEN = ("pot_odds", "mdf", "sizing", "advisor_freq", "oracle_diff")
MIX_SUPPORT_MIN = 0.15        # Fairness-Doktrin par.1.2: Aktion im gemischten Support ab ~15% Advisor-Frequenz
MIN_HAND_LINES, MAX_HAND_LINES = 3, 5                 # docs/doctrine/TRAINER_DESIGN.md par.6: 3-5 Zeilen Feedback pro Hand
EINS_VON_MAX = 20             # "1-in-N"-Vergleich wird jenseits davon unlesbar -> Wortband stattdessen

ACTION_DE = {"fold": "Fold", "check": "Check", "call": "Call", "bet": "Bet", "raise": "Raise", "allin": "All-in"}
STREET_DE = {"preflop": "preflop", "flop": "on the flop", "turn": "on the turn", "river": "on the river"}
_STREET_BIS = {"preflop": "ended preflop", "flop": "went to the flop", "turn": "went to the turn",
               "river": "went to the river"}
_STREET_ORDER = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
# Unsicherheits-Hierarchie par.1.3: sichtbares Konfidenz-Label. Der Kern-String ist der Marker, auf den
# render_decision_feedback prueft (Label nie doppelt anhaengen); grader.CONF_ORACLE traegt 'Bot' im Namen.
BOT_LABEL_CORE = "bot estimate"
BOT_LABEL = f"({BOT_LABEL_CORE})"

# Term-Ids (P1-A Glossar) -> Oberflaechenformen, wie sie in den Template-Strings vorkommen. Grundlage fuer die
# 'terms'-Liste jeder Rueckgabe UND fuer TERMS_USED (der statische Vollstaendigkeits-Check liest dieses Symbol).
TERM_SURFACES: dict[str, tuple[str, ...]] = {
    "equity": ("Equity", "equity"),
    "pot_odds": ("Pot Odds", "Pot-Odds", "pot odds"),
    "mdf": ("MDF",),
    "sizing": ("Sizing", "sizing"),
    "mixing": ("mixes", "mixed strategy", "mix"),
    "gto": ("GTO",),
    "bluff": ("Bluff", "bluff"),
    "value_bet": ("Value-Bet", "value bet", "value-bet"),
    "range": ("Range", "range"),
    "advisor_frequenz": ("Advisor-Frequenz", "advisor frequency"),
    "resolver": ("Resolver", "resolver"),
    "overbet": ("Overbet", "overbet"),
}
TERMS_USED: frozenset[str] = frozenset(TERM_SURFACES)          # BINDING: exakt dieser Symbolname (P2-2 prueft)

_TERM_RE = {tid: re.compile(r"\b(?:" + "|".join(re.escape(s) for s in surfs) + r")\b")
            for tid, surfs in TERM_SURFACES.items()}


# ---------------------------------------------------------------- Zahlen -> Vergleiche (Doktrin: nie nackte Zahlenwand)
def eins_von(p) -> str:
    """0.33 -> '1-in-3'. Der Kern des 'needed 1-in-3, had 1-in-4'-Vergleichs."""
    if not isinstance(p, (int, float)) or p <= 0:
        return "practically never"
    if p >= 0.999:
        return "practically always"
    n = max(2, round(1 / p))
    return f"1-in-{n}" if n <= EINS_VON_MAX else "practically never"


def freq_vergleich(p: float) -> str:
    """Banded Haeufigkeits-Wort fuer Advisor-Frequenzen — deterministisch, keine Prozentwand."""
    if p <= 0.02:
        return "practically never"
    if p <= 0.15:
        return "rarely (about one time in ten)"
    if p <= 0.29:
        return "about one time in four"
    if p <= 0.40:
        return "about one time in three"
    if p <= 0.60:
        return "about every other time"
    if p <= 0.85:
        return "most of the time"
    return "almost always"


def pot_frac_de(frac) -> str:
    """Bet-Groesse als Pot-Bruch ('half pot', 'overbet (1.6x pot)')."""
    if not isinstance(frac, (int, float)) or frac <= 0:
        return "a small bet"
    if frac <= 0.29:
        return "a quarter pot"
    if frac <= 0.415:
        return "a third pot"
    if frac <= 0.59:
        return "half pot"
    if frac <= 0.79:
        return "two-thirds pot"
    if frac <= 1.25:
        return "pot-sized"
    return f"an overbet ({frac:.1f}x pot)"


def equity_satz(eq, req) -> str:
    """'you needed 1-in-3 (33%), had about 1-in-4 (25%)' — Zahl einmal, dann Vergleich.
    QA-Fix (50-Hand-Probe): wenn beide Werte auf DASSELBE 1-in-N runden (38% und 33% -> beide '1-in-3'),
    las sich der Satz als Widerspruch ('needed 1-in-3, had 1-in-3 — too little'). Dann nur Prozente."""
    if isinstance(req, (int, float)) and isinstance(eq, (int, float)):
        a, b = eins_von(req), eins_von(eq)
        if a == b:
            return f"you needed {req * 100:.0f}% equity, had only {eq * 100:.0f}%"
        return f"you needed {a} ({req * 100:.0f}% equity), had about {b} ({eq * 100:.0f}%)"
    if isinstance(req, (int, float)):
        return f"you needed {eins_von(req)} ({req * 100:.0f}% equity)"
    return "the exact price could not be reconstructed here"


def _anteil_wort(p: float) -> str:
    if p >= 0.75:
        return "three out of four hands"
    if p >= 0.60:
        return "two out of three hands"
    if p >= 0.45:
        return "a good half of your hands"
    return "a good share of your hands"


# ---------------------------------------------------------------- tolerante Record-Zugriffe (P0-Drift-Panzer)
def _action_de(x) -> str:
    a = (x or {}).get("action") if isinstance(x, dict) else x
    return ACTION_DE.get(str(a or "").lower(), str(a) if a else "your move")


def _human(rec: dict) -> str:
    return _action_de(rec.get("human_action"))


def _alternative(rec: dict, default: str = "the quieter line") -> str:
    orc = rec.get("oracle") or {}
    oa = rec.get("oracle_action") or orc.get("oracle_action") or orc.get("action")   # P0-3 nistet 'oracle_action'
    return _action_de(oa) if oa else default


def _street_de(rec: dict) -> str:
    return STREET_DE.get(str(rec.get("street", "")).lower(), "in this spot")


def _check(rec: dict, name: str) -> dict:
    c = rec.get("checks") or {}
    sub = c.get(name)
    return sub if isinstance(sub, dict) else {}


def _num(*vals):
    """Erster numerischer Kandidat (Records liefern Zahlen wahlweise flach, im Check oder im rationale)."""
    for v in vals:
        if isinstance(v, (int, float)) and v == v:                    # NaN-Guard
            return v
    return None


def _support_dist(rec: dict) -> list[tuple[str, float]]:
    """Advisor-Mix normalisiert zu [(Aktionswort, p)], deterministisch sortiert (-p, Name). Leer = kein Advisor."""
    dist = rec.get("advisor_dist")
    if not isinstance(dist, dict):
        adv = _check(rec, "advisor")
        rat = rec.get("rationale") or {}
        if isinstance(adv.get("dist"), dict):
            dist = adv["dist"]
        elif isinstance(adv.get("p_defense"), (list, tuple)) and len(adv["p_defense"]) == 3:
            dist = dict(zip(("fold", "call", "raise"), adv["p_defense"]))
        elif isinstance(rat.get("defense_advisor"), (list, tuple)) and len(rat["defense_advisor"]) == 3:
            dist = dict(zip(("fold", "call", "raise"), rat["defense_advisor"]))
        else:
            pb = _num(adv.get("p_bet"), rat.get("advisor_pbet"), rat.get("advisor_pbet_turn"),
                      rat.get("advisor_pbet_river"))
            dist = {"bet": pb, "check": 1 - pb} if pb is not None else None
    if not isinstance(dist, dict):
        return []
    pairs = [(_action_de(a), float(p)) for a, p in dist.items() if isinstance(p, (int, float))]
    return sorted(pairs, key=lambda ap: (-ap[1], ap[0]))


def _mix_satz(dist: list[tuple[str, float]]) -> str | None:
    """Doktrin par.1.2: mehrere Aktionen im Support werden GESAGT — 'GTO mixes here: ... — both fine.'"""
    sup = [(a, p) for a, p in dist if p >= MIX_SUPPORT_MIN]
    if len(sup) < 2:
        return None
    teile = " / ".join(f"{p * 100:.0f}% {a}" for a, p in sup)
    schluss = "both fine" if len(sup) == 2 else "all playable"
    return f"GTO mixes here: {teile} — {schluss}."


# ---------------------------------------------------------------- die fuenf grade_typ-Zweige (x ok/teuer/leak)
def _fb_pot_odds(rec: dict, grade: str) -> str:
    po = _check(rec, "pot_odds")
    req = _num(po.get("req"), rec.get("pot_odds"), (rec.get("rationale") or {}).get("required_equity"))
    eq = _num(po.get("eq_max"), rec.get("equity"), (rec.get("rationale") or {}).get("equity"))
    satz, ha, alt = equity_satz(eq, req), _human(rec), _alternative(rec, "Fold")
    if grade == "ok":
        return f"Good {ha}: the price was right — {satz}. That is exactly how pot odds work."
    if grade == "teuer":
        return (f"Your {ha} was a bit pricey: {satz}. Better {alt} — "
                f"pot odds set the price, and it did not quite fit here.")
    return (f"Costly: {satz} — not enough even against any two cards. Better {alt}, "
            f"because without the right price the call never pays off in the long run.")


def _fb_mdf(rec: dict, grade: str) -> str:
    md = _check(rec, "mdf")
    m = _num(md.get("mdf"), rec.get("mdf"), (rec.get("rationale") or {}).get("mdf"))
    m_satz = (f"MDF says: defend at least {m * 100:.0f}% ({_anteil_wort(m)})"
              if m is not None else "MDF says: defend enough")
    ha, alt, stark = _human(rec), _alternative(rec, "Call"), _num(md.get("strength"))
    if grade == "ok":
        return f"Well defended {_street_de(rec)}: {m_satz} — your {ha} keeps your range intact."
    hand_wort = "a strong hand" if (stark is not None and stark >= STRONG_MADE) else \
        "a playable hand" if (stark is not None and stark >= MEDIUM_MADE) else "this hand"
    if grade == "teuer":
        return (f"That {ha} was a bit costly: {m_satz}. {alt} would be the sturdier choice — "
                f"give up too often and you get pushed off the pot too easily.")
    return (f"Costly: {hand_wort} folded to a small bet. {m_satz} — better {alt}, "
            f"otherwise any bluff can push you off the pot.")


def _sizing_worte(rec: dict, hf, sf) -> tuple[str, str]:
    """Preflop misst man in BIG BLINDS, nicht in Pot-Vielfachen — 'overbet (29.2x pot)' für einen
    Preflop-Raise war technisch richtig und praktisch unbrauchbar (User-QA 2026-08-02)."""
    if str(rec.get("street", "")).lower() != "preflop":
        return pot_frac_de(hf), pot_frac_de(sf)
    obs = rec.get("obs") or {}
    bb = _num(obs.get("bb")) or 100
    ha = rec.get("human_action") or {}
    amt = _num(ha.get("amount")) if isinstance(ha, dict) else None
    gespielt = f"a raise to {amt / bb:.1f}bb" if amt else "this raise size"
    return gespielt, "a standard open size (2–3bb, ~3x when facing a raise)"


def _sizing_ratio(rec: dict, hf, sf):
    """Plan/gespielt als Faktor (>1 = größer wählen): postflop aus den Pot-Fraktionen des Sizing-Checks,
    preflop in bb (Open-Plan 2.5bb; gegen einen Raise ~3x dessen Höhe). None = nicht rekonstruierbar."""
    if str(rec.get("street", "")).lower() == "preflop":
        bbv = _num((rec.get("obs") or {}).get("bb")) or 100
        ha = rec.get("human_action") or {}
        amt = _num(ha.get("amount")) if isinstance(ha, dict) else None
        if not amt or amt <= 0:
            return None
        pre = [h for h in (rec.get("history") or []) if str(h.get("street")) == "preflop"
               and h.get("action") in ("bet", "raise", "allin")]
        plan = 3.0 * (_num(pre[-1].get("to"), pre[-1].get("amount")) or 0) if pre else 2.5 * bbv
        return (plan / amt) if plan > 0 else None
    if isinstance(hf, (int, float)) and isinstance(sf, (int, float)) and hf > 0 and sf > 0:
        return sf / hf
    return None


SIZING_TOLERANZ = 0.15        # <15% Abweichung: keine Prozent-Korrektur — das wäre Präzisions-Theater


def _sizing_korrektur(ratio) -> str:
    """'→ size the bet ~45% smaller' — die konkrete Prozent-Korrektur (User-QA 2026-08-02: gut
    sichtbar zeigen, um wie viel die Bet höher/niedriger gehört; ab 2x als Faktor, Prozente >100 lügen)."""
    if ratio is None or (1 - SIZING_TOLERANZ) <= ratio <= (1 + SIZING_TOLERANZ):
        return ""
    if ratio >= 2:
        return f" → size the bet ~{ratio:.1f}x as large."
    if ratio > 1:
        return f" → size the bet ~{(ratio - 1) * 100:.0f}% larger."
    return f" → size the bet ~{(1 - ratio) * 100:.0f}% smaller."


def _fb_sizing(rec: dict, grade: str) -> str:
    sz = _check(rec, "sizing")
    hf, sf = _num(sz.get("human_frac")), _num(sz.get("snapped_frac"))
    gespielt, plan = _sizing_worte(rec, hf, sf)
    if grade == "ok":
        return f"Clean sizing: {gespielt} fits here — that keeps your value bet credible."
    # Plan-Größe nur EINMAL nennen — die preflop-Variante ist lang ('a standard open size (2–3bb …)') und
    # las sich doppelt genannt wie ein Stottern (User-QA 2026-08-02).
    korrektur = _sizing_korrektur(_sizing_ratio(rec, hf, sf))
    if grade == "teuer":
        return (f"Your sizing was a bit off: you played {gespielt}, the plan calls for {plan} — "
                f"the size tells the more coherent story.{korrektur}")
    return (f"Costly sizing: {gespielt}, the plan calls for {plan} — "
            f"geometry sets the size, not gut feeling.{korrektur}")


def _fb_advisor_freq(rec: dict, grade: str) -> str:
    dist, ha = _support_dist(rec), _human(rec)
    mix = _mix_satz(dist)
    p_chosen = next((p for a, p in dist if a == ha), None)
    if grade == "ok":
        if mix:
            return f"{mix} Your {ha} is squarely in the mix."
        return f"Right on plan: the advisor frequency plays your {ha} here {freq_vergleich(p_chosen or 1.0)}."
    alt = _alternative(rec, dist[0][0] if dist else "the more common line")
    grund = (f"the advisor frequency has your {ha} {freq_vergleich(p_chosen)}"
             if p_chosen is not None else "the advisor frequency barely supports your move here")
    if grade == "teuer":
        return f"Your {ha} was the costly side of the mix: {grund}. Better {alt} — against a reasonable range that is the more common choice."
    return f"Costly: {grund}. Better {alt} — against a reasonable range that is clearly the better side."


def _fb_oracle_diff(rec: dict, grade: str) -> str:
    ha, alt = _human(rec), _alternative(rec)
    resolver = bool((rec.get("rationale") or {}).get("resolver"))
    quelle = "river verdict from the resolver (hard reference)" if resolver else BOT_LABEL_CORE
    if grade == "ok":
        return f"Good choice: the bot plays {ha} here as well — two roads, same logic ({quelle})."
    # QA-Fix (50-Hand-Probe): erklaerung_kurz beginnt selbst mit 'Costly: the reference bot plays X here'
    # — im Rahmensatz wiederholt ergab das 'A bit costly: … — Costly: … plays Call here …' (doppelt,
    # verschachtelt). Wir übernehmen nur den BEGRÜNDUNGS-Schwanz nach dem Gedankenstrich.
    grund = rec.get("erklaerung_kurz") or "its line keeps the range together better"
    grund = re.sub(r"^(Costly|A bit costly|Clean)\s*:\s*", "", grund).strip()
    if f"plays {alt} here" in grund and "—" in grund:
        grund = grund.split("—", 1)[1].strip().rstrip(".")
    grund = grund.rstrip(".")
    if grade == "teuer":
        return f"A bit costly: your {ha}, the bot picks {alt} — {grund} ({quelle})."
    return f"Costly: {ha} instead of {alt} — {grund} ({quelle})."


def _fb_generic(rec: dict, grade: str) -> str:
    """Missing-Check-Fallback: grade_typ fehlt/unbekannt — warm bleiben, nichts erfinden."""
    ha, street = _human(rec), _street_de(rec)
    if grade == "ok":
        return f"Good move: your {ha} {street} fits — keep it up."
    alt = _alternative(rec)
    grund = rec.get("erklaerung_kurz") or "the simpler line costs less here"
    if grade == "teuer":
        return f"Your {ha} {street} was probably a bit costly: better {alt} — {grund}."
    return f"Costly {street}: {ha} instead of {alt} — {grund}."


_TYP_RENDERER = {"pot_odds": _fb_pot_odds, "mdf": _fb_mdf, "sizing": _fb_sizing,
                 "advisor_freq": _fb_advisor_freq, "oracle_diff": _fb_oracle_diff}

MERKSATZ = {                                                     # optionale L5 der Hand-Zusammenfassung
    "pot_odds": "Takeaway: pot odds first — count how often you need to win before you pay.",
    "mdf": "Takeaway: MDF protects you — fold too often and you invite every bluff.",
    "sizing": "Takeaway: sizing follows the plan — the bet size tells your story.",
    "advisor_freq": "Takeaway: GTO mixes — there is often more than one good move.",
    "oracle_diff": "Takeaway: same spots, same logic — the bot is just a second opinion.",
}


# ---------------------------------------------------------------- Public API (BINDING: {text, html, terms})
def _finish(text: str) -> dict:
    if _G is not None:
        try:
            html = _G.markup(text)
        except Exception:                                        # noqa: BLE001 — Renderfehler nie in den Spielfluss
            html = text
    else:
        html = text
    terms = sorted(tid for tid, rx in _TERM_RE.items() if rx.search(text))
    return {"text": text, "html": html, "terms": terms}


def _validate_grade(rec: dict) -> str:
    grade = (rec or {}).get("grade")
    if grade not in GRADE_ICON:
        raise ValueError(f"Unknown grade: {grade!r} (allowed: {sorted(GRADE_ICON)})")
    return grade


def render_decision_feedback(rec: dict) -> dict:
    """EINE benotete Entscheidung -> 1-2 warme Saetze -> {'text','html','terms'}."""
    grade = _validate_grade(rec)
    renderer = _TYP_RENDERER.get(rec.get("grade_typ"), _fb_generic)
    text = renderer(rec, grade)
    conf = str(rec.get("confidence") or "")
    if "Bot" in conf and BOT_LABEL_CORE not in text:      # Konfidenz-Label sichtbar (Doktrin par.1.3)
        text += f" {BOT_LABEL}"
    return _finish(text)


def _grade_rang(rec: dict) -> int:
    return {"leak": 0, "teuer": 1, "ok": 2}[rec["grade"]]


# Formel-Monotonie-Bremse (49/50 identische Openings gemessen). DETERMINISTISCH: der Opener hängt an der
# hand_id, nicht an einem Zähler — gleicher Input ergibt exakt denselben Text (P1-B-Vertrag), verschiedene
# Hände variieren trotzdem.
_OPENER = ("Hand review", "Quick recap", "Recap")


def _opener_for(records: list[dict]) -> str:
    hid = str((records[0] or {}).get("hand_id", ""))
    tail = "".join(ch for ch in hid if ch.isdigit())[-4:] or "0"
    return _OPENER[int(tail) % len(_OPENER)]


def _hand_rahmen(records: list[dict], hand_result) -> str:
    """L1: Rahmen + EHRLICHES Ergebnis. Das Ergebnis wird GENANNT, nie BENOTET (Doktrin par.1.1) — gerade
    die Divergenz (sauber gespielt & verloren / Leak & gewonnen) ist die Anti-Tilt-Lektion schlechthin.
    QA-Fix: die alte Zeile nannte den End-Pot des TISCHES ('Pot am Ende 200 bb' nach Hero-Fold preflop —
    zwei Bots stackten off), was als Hero-Zahl gelesen wurde. Jetzt zählt nur Heros eigenes Ergebnis."""
    letzte = max(records, key=lambda r: _STREET_ORDER.get(str(r.get("street", "")).lower(), 0))
    street = _STREET_BIS.get(str(letzte.get("street", "")).lower(), "played to the end")
    n = len(records)
    opener = _opener_for(records)
    zusatz = ""
    net = (hand_result or {}).get("hero_net_bb") if isinstance(hand_result, dict) else None
    if isinstance(net, (int, float)) and abs(net) >= 1:
        zusatz = f" — result {net:+.0f} bb"
        grades = {r["grade"] for r in records}
        if net <= -5 and grades == {"ok"}:
            zusatz += " (played clean and still lost — that is exactly how you lose the right way)"
        elif net >= 5 and "leak" in grades:
            zusatz += " (won, but the costly call stays costly — the result does not redeem it)"
    return f"{opener}: {n} decision{'s' if n != 1 else ''}, {street}{zusatz}."


def _dist_str(rec: dict) -> str:
    """'[Bot: 68% Fold / 29% Call]' — die Advisor-Frequenzen als direkter Lern-Impuls (User-Wunsch)."""
    dist = _support_dist(rec)
    parts = [f"{p * 100:.0f}% {_action_de(a)}" for a, p in dist
             if isinstance(p, (int, float)) and p >= 0.02][:3]
    return ("  [Bot: " + " / ".join(parts) + "]") if parts else ""


_STREET_TAG = {"preflop": "PREFLOP", "flop": "FLOP", "turn": "TURN", "river": "RIVER"}
_HERO_SEAT = 0                       # six_server.HUMAN — der Trainer setzt den Menschen immer auf Sitz 0
_RANGE_WORT = {1: "roughly the top 20% of hands", 2: "roughly the top 8% (3-bet range)",
               3: "only the very top (~4%, 4-bet range)"}


def _kurz(txt: str) -> str:
    """Grade-Präfixe raus — Icon + Straßen-Tag tragen das schon; der Satz startet direkt mit dem Grund."""
    return re.sub(r"^(Costly sizing|Costly|A bit costly|Your sizing was a bit off)\s*[:—-]\s*", "", txt).strip()


def _strategie(records: list[dict], hand_result: dict | None = None) -> list[str]:
    """Range-Erzählung (Bot-Lesart): ECHT gerechnet via range_story (Bayes-Tracker + Equity + made_class,
    User-Auftrag 2026-08-02); die statische Heuristik darunter bleibt als Fail-soft-Fallback stehen."""
    try:
        from pokerbot.coach import range_story as _rs
        echt = _rs.build_story(records, hand_result)
        if echt:
            return echt
    except Exception:  # noqa: BLE001 — Strategie ist Zusatz, nie Blocker
        pass
    out: list[str] = []
    last = records[-1]
    hist = last.get("history") or []
    obs = last.get("obs") or {}
    pre_raises = [e for e in hist if str(e.get("street")) == "preflop" and e.get("action") in ("raise", "bet", "allin")]
    if pre_raises:
        wer = "You represent" if pre_raises[-1].get("player") == _HERO_SEAT else "Villain represents"
        out.append(f"Preflop: {wer} {_RANGE_WORT.get(min(len(pre_raises), 3), _RANGE_WORT[3])}.")
    else:
        out.append("Preflop: only limps/calls — every range stays wide and unsorted.")
    for st in ("river", "turn", "flop"):
        agg = [e for e in hist if str(e.get("street")) == st and e.get("player") != _HERO_SEAT
               and e.get("action") in ("bet", "raise", "allin")]
        if agg:
            verb = "raise" if agg[-1].get("action") == "raise" else "bet"
            out.append(f"{_STREET_TAG[st].capitalize()}: his {verb} says he connected — top pair or better.")
            break
    hole, board = obs.get("hole") or [], obs.get("board") or []
    halt = None
    try:
        from pokerbot.brain import api as _api
        if board:
            _name, st_val = _api.hand_rank(hole, board)
            halt = ("a strong made hand" if st_val >= STRONG_MADE
                    else "a medium-strength hand" if st_val >= MEDIUM_MADE else "little substance")
    except Exception:  # noqa: BLE001 — Strategie ist Zusatz, nie Blocker
        pass
    fd = ""
    if 3 <= len(board) <= 4 and hole:
        for suit in "shdc":
            tot = sum(1 for c in hole + board if len(c) > 1 and c[1] == suit)
            if tot == 4 and any(len(c) > 1 and c[1] == suit for c in hole):
                fd = " plus a flush draw"
                break
    aggro = any(str(r.get("street")) != "preflop"
                and str(((r.get("human_action") or {}).get("action") if isinstance(r.get("human_action"), dict)
                         else r.get("human_action"))) in ("bet", "raise", "allin") for r in records)
    linie = "strength — you represent the hit" if aggro else "restraint — marginal hands or draws"
    if halt:
        out.append(f"You hold {halt}{fd}; your line tells {linie}.")
    return out[:3]


def render_hand_feedback(records: list[dict], hand_result: dict | None = None, mode: str = "gto") -> dict:
    """Lern-Impuls-Struktur (User-QA 2026-08-02): NUR die suboptimalen Entscheidungen, je eine Zeile mit
    Straßen-Tag + Grund + Bot-Frequenzen; kein Lob-Ballast, kein Ergebnis-Text (steht schon im UI); danach
    der Strategie-Abschnitt (Range-Erzählung). Alles ok -> ein Satz + der knappste Spot als Frequenz-Fenster."""
    records = [r for r in (records or []) if isinstance(r, dict)]
    if not records:
        return _finish("No hero decision to grade — folding preflop is often the best move.")
    for r in records:
        _validate_grade(r)
    lines: list[str] = []
    bad = [r for r in records if r["grade"] != "ok"]
    # EINE Zeile pro Straße, in Spielreihenfolge — die Struktur muss auf einen Blick erkennbar sein
    # (User-QA: vier identische PREFLOP-Zeilen in einer Hand waren Rauschen, kein Lern-Impuls).
    pro_street: dict[str, dict] = {}
    for r in bad:
        st = str(r.get("street", "")).lower()
        if st not in pro_street or _grade_rang(r) < _grade_rang(pro_street[st]):
            pro_street[st] = r
    for st in ("preflop", "flop", "turn", "river"):
        r = pro_street.get(st)
        if r is None:
            continue
        n_st = sum(1 for x in bad if str(x.get("street", "")).lower() == st)
        mehr = f" (+{n_st - 1} more {_STREET_TAG.get(st, '')} spot{'s' if n_st > 2 else ''})" if n_st > 1 else ""
        txt = _kurz(render_decision_feedback(r)["text"])
        lines.append(f"{GRADE_ICON[r['grade']]} {_STREET_TAG.get(st, '?')} · {_human(r)}: {txt}{_dist_str(r)}{mehr}")
    if not bad:
        n = len(records)
        lines.append(f"✓ All {n} decision{'s' if n != 1 else ''} on plan — nothing to improve.")
        mit_dist = [r for r in records if _support_dist(r)]
        if mit_dist:
            knapp = min(mit_dist, key=lambda r: max((p for _, p in _support_dist(r)), default=1.0))
            tag = _STREET_TAG.get(str(knapp.get("street", "")).lower(), "?")
            lines.append(f"Closest spot — {tag} · {_human(knapp)}:{_dist_str(knapp)}")
    strat = _strategie(records, hand_result)
    if strat:
        lines.append("— Strategy (bot read) —")
        lines.extend(strat)
    return _finish("\n".join(lines))


# ---------------------------------------------------------------- Selftest (synthetische Fixtures, kein Server noetig)
def _rec(typ, grade, **kw) -> dict:
    base = {"hand_id": "selftest-1", "street": kw.pop("street", "turn"), "grade": grade, "grade_typ": typ,
            "human_action": {"action": kw.pop("ha", "call"), "amount": kw.pop("amount", None)},
            "oracle_action": kw.pop("oa", "fold"), "confidence": kw.pop("conf", "Math (indisputable)"),
            "checks": kw.pop("checks", {}), "rationale": kw.pop("rationale", {})}
    base.update(kw)
    return base


def _selftest_fixtures() -> list[dict]:
    f = [
        # pot_odds x 3 (equity/pot_odds-Oberflaechen)
        _rec("pot_odds", "ok", checks={"pot_odds": {"req": 0.25, "eq_max": 0.45, "violated": False}}),
        _rec("pot_odds", "teuer", checks={"pot_odds": {"req": 0.33, "eq_max": 0.28, "violated": False}}),
        _rec("pot_odds", "leak", checks={"pot_odds": {"req": 0.33, "eq_max": 0.24, "violated": True}}),
        # mdf x 3 (mdf/bluff-Oberflaechen)
        _rec("mdf", "ok", ha="call", oa="call", checks={"mdf": {"mdf": 0.62, "strength": 0.5, "violated": False}}),
        _rec("mdf", "teuer", ha="fold", oa="call", checks={"mdf": {"mdf": 0.55, "strength": 0.45, "violated": False}}),
        _rec("mdf", "leak", ha="fold", oa="call", checks={"mdf": {"mdf": 0.67, "strength": 0.70, "violated": True}}),
        # sizing x 3 (sizing/value_bet/overbet-Oberflaechen)
        _rec("sizing", "ok", ha="bet", checks={"sizing": {"human_frac": 0.5, "snapped_frac": 0.5, "err": 0.0}}),
        _rec("sizing", "teuer", ha="bet", checks={"sizing": {"human_frac": 1.6, "snapped_frac": 0.75, "err": 0.85}}),
        _rec("sizing", "leak", ha="raise", checks={"sizing": {"human_frac": 0.1, "snapped_frac": 0.75, "err": 0.65}}),
        # advisor_freq x 3 (+ single-support ok) (gto/mixing/range/advisor_frequenz-Oberflaechen)
        _rec("advisor_freq", "ok", ha="check", advisor_dist={"bet": 0.6, "check": 0.4},
             conf="Solver frequency (HU-trained, approximation)"),
        _rec("advisor_freq", "ok", ha="call", advisor_dist={"call": 0.95, "fold": 0.04, "raise": 0.01}),
        _rec("advisor_freq", "teuer", ha="call", oa="fold", advisor_dist={"fold": 0.9, "call": 0.02, "raise": 0.08}),
        _rec("advisor_freq", "leak", ha="raise", oa="fold", advisor_dist={"fold": 0.97, "call": 0.02, "raise": 0.01}),
        # oracle_diff x 3, ok = sparse Resolver-Shape OHNE equity/mdf-Keys (Resolver-Oberflaeche)
        _rec("oracle_diff", "ok", ha="call", oa="call", street="river", conf="Bot estimate",
             rationale={"phase": "postflop", "street": "river", "made_hand": "two pair", "resolver": True, "range_conf": 0.8}),
        _rec("oracle_diff", "teuer", ha="bet", oa="check", conf="Bot estimate",
             erklaerung_kurz="the check keeps the weak hands in his range"),
        _rec("oracle_diff", "leak", ha="allin", oa="fold", conf="Bot estimate"),
        # Missing-Check-Fallbacks: unbekannter/fehlender grade_typ + leere checks bei gesetztem typ
        _rec(None, "ok"), _rec(None, "teuer", conf="Bot estimate"), _rec("nonsense_typ", "leak"),
        _rec("pot_odds", "teuer", checks={}),
    ]
    return f


def _selftest() -> None:
    import json
    import sys

    fixtures = _selftest_fixtures()
    # 1) jeder Zweig rendert nicht-leer + Determinismus (zwei Laeufe byte-identisch)
    outs = []
    for rec in fixtures:
        a, b = render_decision_feedback(rec), render_decision_feedback(dict(rec))
        assert a["text"] and a["html"] and isinstance(a["terms"], list), rec
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), ("nicht deterministisch", rec)
        outs.append(a)
    # 2) Kritik traegt Alternative: teuer/leak-Texte nennen 'Better'/'picks'/'instead of' (Alternative + Grund)
    for rec, out in zip(fixtures, outs):
        if rec["grade"] in ("teuer", "leak"):
            assert any(w in out["text"] for w in ("Better", "better", "picks", "instead of", "would be",
                                                  "calls for", "plan")), out["text"]
    # 3) Bot-Einschaetzung sichtbar gelabelt
    bot_out = render_decision_feedback(_rec(None, "teuer", conf="Bot estimate"))
    assert BOT_LABEL_CORE in bot_out["text"]
    # 3b) Sizing-Korrektur in Prozent (User-QA 2026-08-02): 1.6x Pot statt 0.75 -> '~53% smaller';
    #     0.1 statt 0.75 -> Faktor-Wortlaut; Preflop 12bb-Open vs 2.5bb-Plan -> '% smaller' in bb-Logik
    assert "% smaller" in render_decision_feedback(fixtures[7])["text"], fixtures[7]
    assert "x as large" in render_decision_feedback(fixtures[8])["text"], fixtures[8]
    pre_sz = _rec("sizing", "leak", ha="raise", amount=1200, street="preflop",
                  obs={"bb": 100}, history=[], checks={"sizing": {"human_frac": 8.0, "snapped_frac": 1.0}})
    assert "% smaller" in render_decision_feedback(pre_sz)["text"], render_decision_feedback(pre_sz)["text"]
    # 4) Hand-Feedback (Lern-Impuls-Struktur, User-QA 2026-08-02): NUR suboptimale Entscheidungen, je eine
    #    Zeile mit STRASSEN-TAG + Bot-Frequenzen, danach der Strategie-Abschnitt; KEIN Lob, KEIN Ergebnis-Text.
    hand = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    assert any(t in hand["text"] for t in ("PREFLOP", "FLOP", "TURN", "RIVER")), hand["text"]
    assert "Strategy (bot read)" in hand["text"], hand["text"]
    assert "Strong:" not in hand["text"], "Lob-Zeile gehoert nicht mehr ins Hand-Feedback"
    assert "result" not in hand["text"].lower(), "Ergebnis-Text ist Sache des UI, nicht des Coach-Textes"
    for verboten in ("won", "lost", "unfortunately", "mistake"):
        assert verboten not in hand["text"], (verboten, hand["text"])
    hand2 = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    assert hand["text"] == hand2["text"], "Hand-Feedback nicht deterministisch"
    outs.append(hand)
    all_ok = render_hand_feedback([fixtures[0], fixtures[3]], None, "gto")
    assert "on plan" in all_ok["text"], all_ok["text"]        # Alles-ok-Zweig bleibt knapp und ehrlich
    outs.append(all_ok)
    leer = render_hand_feedback([], None, "gto")
    assert "No hero decision" in leer["text"] and leer["html"]
    # 5) TERMS_USED: nicht-leer, und JEDER Eintrag kommt in mindestens einem gerenderten Template vor
    assert TERMS_USED and TERMS_USED == frozenset(TERM_SURFACES)
    alle_texte = "\n".join(o["text"] for o in outs) + "\n" + "\n".join(MERKSATZ.values())
    fehlend = [tid for tid in sorted(TERMS_USED) if not _TERM_RE[tid].search(alle_texte)]
    assert not fehlend, f"TERMS_USED ohne Template-Vorkommen: {fehlend}"
    # 6) 'terms' der Rueckgabe entspricht den tatsaechlich emittierten Oberflaechenformen
    po = render_decision_feedback(fixtures[0])
    assert "pot_odds" in po["terms"] and "equity" in po["terms"], po["terms"]
    # 7) unbekannter Grade -> ValueError (PINNED Vokabular)
    for bad in ("super", None, "OK"):
        try:
            render_decision_feedback(_rec("pot_odds", bad))
            raise AssertionError(f"Grade {bad!r} haette ValueError werfen muessen")
        except ValueError:
            pass
    # 8) sparse Resolver-Record (keine equity/mdf-Keys) rendert ohne KeyError, nennt den Resolver
    res = render_decision_feedback(fixtures[13])
    assert "resolver" in res["text"], res["text"]
    # 9) Render-Pfad laedt kein torch (Advisor bleibt draussen — Plan P1-B Schritt 1)
    assert "torch" not in sys.modules, "templates_de darf torch nicht laden"
    # 10) Glossar-Fallback: ohne glossar_de ist html == text (guarded import)
    global _G
    g_alt, _G = _G, None
    try:
        fb = render_decision_feedback(fixtures[0])
        assert fb["html"] == fb["text"]
    finally:
        _G = g_alt
    print(f"OK - templates_de: {len(fixtures)} Entscheidungs-Fixtures ({len(GRADE_TYPEN)} Typen x 3 Grades "
          f"+ Fallbacks), Hand-Feedback 3-5 Zeilen, deterministisch, TERMS_USED={len(TERMS_USED)} Terme abgedeckt, "
          f"glossar_de {'aktiv' if _G is not None else 'Fallback (html=text)'}.")


if __name__ == "__main__":
    _selftest()
