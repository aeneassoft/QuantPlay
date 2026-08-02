"""Deterministische deutsche Feedback-Templates fuer den Trainer (P1-B, docs/TRAINER_PLAN.md).

WHY: die Sprachschicht ENTSCHEIDET nichts und RECHNET nichts (TRAINER_DESIGN.md par.3) — sie uebersetzt die vom
Grader (P0) gefuellten Decision-Records in warme, konkrete deutsche Saetze nach der Fairness-Doktrin par.1:
nie Ergebnisse graden, gute Zuege EXPLIZIT feiern, ein Leak heisst "teurer Kauf", jede Kritik traegt die
Alternative + den Ein-Satz-Grund, gemischter Support wird GESAGT ("... beides gut"). Zahlen erscheinen einmal
als Zahl und dann als Vergleich ("brauchte 1-von-3, hatte 1-von-4").

INPUT-KONTRAKT (TRAINER_DESIGN.md par.4, BINDEND — jeder Zugriff via .get() mit deutschem Fallback):
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
MIN_HAND_LINES, MAX_HAND_LINES = 3, 5                 # TRAINER_DESIGN.md par.6: 3-5 Zeilen Feedback pro Hand
EINS_VON_MAX = 20             # "1-von-N"-Vergleich wird jenseits davon unlesbar -> Wortband stattdessen

ACTION_DE = {"fold": "Fold", "check": "Check", "call": "Call", "bet": "Bet", "raise": "Raise", "allin": "All-in"}
STREET_DE = {"preflop": "Preflop", "flop": "am Flop", "turn": "am Turn", "river": "am River"}
_STREET_BIS = {"preflop": "Preflop", "flop": "zum Flop", "turn": "zum Turn", "river": "zum River"}
_STREET_ORDER = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
BOT_LABEL = "(Bot-Einschätzung)"                 # Unsicherheits-Hierarchie par.1.3: sichtbares Konfidenz-Label

# Term-Ids (P1-A Glossar) -> Oberflaechenformen, wie sie in den Template-Strings vorkommen. Grundlage fuer die
# 'terms'-Liste jeder Rueckgabe UND fuer TERMS_USED (der statische Vollstaendigkeits-Check liest dieses Symbol).
TERM_SURFACES: dict[str, tuple[str, ...]] = {
    "equity": ("Equity",),
    "pot_odds": ("Pot Odds", "Pot-Odds"),
    "mdf": ("MDF",),
    "sizing": ("Sizing",),
    "mixing": ("mischt", "gemischte Strategie"),
    "gto": ("GTO",),
    "bluff": ("Bluff",),
    "value_bet": ("Value-Bet",),
    "range": ("Range",),
    "advisor_frequenz": ("Advisor-Frequenz",),
    "resolver": ("Resolver",),
    "overbet": ("Overbet",),
}
TERMS_USED: frozenset[str] = frozenset(TERM_SURFACES)          # BINDING: exakt dieser Symbolname (P2-2 prueft)

_TERM_RE = {tid: re.compile(r"\b(?:" + "|".join(re.escape(s) for s in surfs) + r")\b")
            for tid, surfs in TERM_SURFACES.items()}


# ---------------------------------------------------------------- Zahlen -> Vergleiche (Doktrin: nie nackte Zahlenwand)
def eins_von(p) -> str:
    """0.33 -> '1-von-3'. Der Kern des 'brauchte 1-von-3, hatte 1-von-4'-Vergleichs."""
    if not isinstance(p, (int, float)) or p <= 0:
        return "praktisch nie"
    if p >= 0.999:
        return "praktisch immer"
    n = max(2, round(1 / p))
    return f"1-von-{n}" if n <= EINS_VON_MAX else "praktisch nie"


def freq_vergleich(p: float) -> str:
    """Banded Haeufigkeits-Wort fuer Advisor-Frequenzen — deterministisch, keine Prozentwand."""
    if p <= 0.02:
        return "praktisch nie"
    if p <= 0.15:
        return "selten (etwa 1 von 10)"
    if p <= 0.29:
        return "etwa jede vierte"
    if p <= 0.40:
        return "etwa jede dritte"
    if p <= 0.60:
        return "etwa jede zweite"
    if p <= 0.85:
        return "meistens"
    return "fast immer"


def pot_frac_de(frac) -> str:
    """Bet-Groesse als deutscher Pot-Bruch ('halber Pot', 'Overbet (1.6x Pot)')."""
    if not isinstance(frac, (int, float)) or frac <= 0:
        return "eine kleine Bet"
    if frac <= 0.29:
        return "ein Viertel Pot"
    if frac <= 0.415:
        return "ein Drittel Pot"
    if frac <= 0.59:
        return "halber Pot"
    if frac <= 0.79:
        return "zwei Drittel Pot"
    if frac <= 1.25:
        return "Pot-Größe"
    return f"Overbet ({frac:.1f}x Pot)"


def equity_satz(eq, req) -> str:
    """'du brauchtest 1-von-3 (33% Equity), hattest etwa 1-von-4' — Zahl einmal, dann Vergleich."""
    if isinstance(req, (int, float)) and isinstance(eq, (int, float)):
        return f"du brauchtest {eins_von(req)} ({req * 100:.0f}% Equity), hattest etwa {eins_von(eq)}"
    if isinstance(req, (int, float)):
        return f"du brauchtest {eins_von(req)} ({req * 100:.0f}% Equity)"
    return "der genaue Preis ließ sich hier nicht rekonstruieren"


def _anteil_wort(p: float) -> str:
    if p >= 0.75:
        return "drei von vier Händen"
    if p >= 0.60:
        return "zwei von drei Händen"
    if p >= 0.45:
        return "gut die Hälfte deiner Hände"
    return "einen guten Teil deiner Hände"


# ---------------------------------------------------------------- tolerante Record-Zugriffe (P0-Drift-Panzer)
def _action_de(x) -> str:
    a = (x or {}).get("action") if isinstance(x, dict) else x
    return ACTION_DE.get(str(a or "").lower(), str(a) if a else "dein Zug")


def _human(rec: dict) -> str:
    return _action_de(rec.get("human_action"))


def _alternative(rec: dict, default: str = "die ruhigere Linie") -> str:
    oa = rec.get("oracle_action") or (rec.get("oracle") or {}).get("action")
    return _action_de(oa) if oa else default


def _street_de(rec: dict) -> str:
    return STREET_DE.get(str(rec.get("street", "")).lower(), "in diesem Spot")


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
    """Advisor-Mix normalisiert zu [(deutsche Aktion, p)], deterministisch sortiert (-p, Name). Leer = kein Advisor."""
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
    """Doktrin par.1.2: mehrere Aktionen im Support werden GESAGT — 'GTO mischt hier: ... — beides gut.'"""
    sup = [(a, p) for a, p in dist if p >= MIX_SUPPORT_MIN]
    if len(sup) < 2:
        return None
    teile = " / ".join(f"{p * 100:.0f}% {a}" for a, p in sup)
    schluss = "beides gut" if len(sup) == 2 else "alles spielbar"
    return f"GTO mischt hier: {teile} — {schluss}."


# ---------------------------------------------------------------- die fuenf grade_typ-Zweige (x ok/teuer/leak)
def _fb_pot_odds(rec: dict, grade: str) -> str:
    po = _check(rec, "pot_odds")
    req = _num(po.get("req"), rec.get("pot_odds"), (rec.get("rationale") or {}).get("required_equity"))
    eq = _num(po.get("eq_max"), rec.get("equity"), (rec.get("rationale") or {}).get("equity"))
    satz, ha, alt = equity_satz(eq, req), _human(rec), _alternative(rec, "Fold")
    if grade == "ok":
        return f"Guter {ha}: der Preis stimmte — {satz}. Genau so rechnet man Pot Odds."
    if grade == "teuer":
        return (f"Dein {ha} war etwas teuer eingekauft: {satz}. Besser {alt} — "
                f"die Pot Odds geben den Preis vor, und der passte hier nicht ganz.")
    return (f"Teurer Kauf: {satz} — selbst gegen jede Hand zu wenig. Besser {alt}, "
            f"denn ohne den richtigen Preis lohnt sich der Call auf Dauer nie.")


def _fb_mdf(rec: dict, grade: str) -> str:
    md = _check(rec, "mdf")
    m = _num(md.get("mdf"), rec.get("mdf"), (rec.get("rationale") or {}).get("mdf"))
    m_satz = (f"MDF sagt: mindestens {m * 100:.0f}% verteidigen ({_anteil_wort(m)})"
              if m is not None else "MDF sagt: genug verteidigen")
    ha, alt, stark = _human(rec), _alternative(rec, "Call"), _num(md.get("strength"))
    if grade == "ok":
        return f"Gut verteidigt {_street_de(rec)}: {m_satz} — dein {ha} hält deine Range zusammen."
    hand_wort = "eine starke Hand" if (stark is not None and stark >= STRONG_MADE) else \
        "eine brauchbare Hand" if (stark is not None and stark >= MEDIUM_MADE) else "diese Hand"
    if grade == "teuer":
        return (f"Dieser {ha} war etwas teuer: {m_satz}. {alt} wäre die robustere Wahl — "
                f"wer zu oft aufgibt, wird zu leicht vom Pot geschoben.")
    return (f"Teurer Kauf: {hand_wort} gegen eine kleine Bet aufgegeben. {m_satz} — besser {alt}, "
            f"sonst kann dich jeder Bluff vom Pot schieben.")


def _fb_sizing(rec: dict, grade: str) -> str:
    sz = _check(rec, "sizing")
    hf, sf = _num(sz.get("human_frac")), _num(sz.get("snapped_frac"))
    gespielt, plan = pot_frac_de(hf), pot_frac_de(sf)
    if grade == "ok":
        return f"Sauberes Sizing: {gespielt} passt hier — so bleibt deine Value-Bet glaubwürdig."
    if grade == "teuer":
        return (f"Dein Sizing war etwas daneben: gespielt {gespielt}, der Plan kennt hier {plan}. "
                f"Nimm {plan} — die Größe erzählt die stimmigere Geschichte.")
    return (f"Teurer Kauf beim Sizing: {gespielt} statt {plan}. Besser {plan} — "
            f"die Geometrie des Pots gibt die Größe vor, nicht das Bauchgefühl.")


def _fb_advisor_freq(rec: dict, grade: str) -> str:
    dist, ha = _support_dist(rec), _human(rec)
    mix = _mix_satz(dist)
    p_chosen = next((p for a, p in dist if a == ha), None)
    if grade == "ok":
        if mix:
            return f"{mix} Dein {ha} liegt voll im Mix."
        return f"Voll im Plan: die Advisor-Frequenz spielt deinen {ha} hier {freq_vergleich(p_chosen or 1.0)}."
    alt = _alternative(rec, dist[0][0] if dist else "die häufigere Linie")
    grund = (f"die Advisor-Frequenz sieht deinen {ha} {freq_vergleich(p_chosen)}"
             if p_chosen is not None else "die Advisor-Frequenz trägt deinen Zug hier kaum")
    if grade == "teuer":
        return f"Dein {ha} war die teure Seite des Mixes: {grund}. Besser {alt} — gegen eine vernünftige Range ist das die häufigere Wahl."
    return f"Teurer Kauf: {grund}. Besser {alt} — gegen eine vernünftige Range ist das klar die bessere Seite."


def _fb_oracle_diff(rec: dict, grade: str) -> str:
    ha, alt = _human(rec), _alternative(rec)
    resolver = bool((rec.get("rationale") or {}).get("resolver"))
    quelle = "River-Urteil vom Resolver (harte Referenz)" if resolver else "Bot-Einschätzung"
    if grade == "ok":
        return f"Gute Wahl: der Bot spielt hier genauso {ha} — zwei Wege, gleiche Logik ({quelle})."
    grund = rec.get("erklaerung_kurz") or "seine Linie hält die Range besser zusammen"
    if grade == "teuer":
        return f"Etwas teuer: du hast {ha} gespielt, der Bot wählt {alt} — {grund} ({quelle})."
    return f"Teurer Kauf: {ha} statt {alt}. Der Bot geht den anderen Weg, weil {grund} ({quelle})."


def _fb_generic(rec: dict, grade: str) -> str:
    """Missing-Check-Fallback: grade_typ fehlt/unbekannt — warm bleiben, nichts erfinden."""
    ha, street = _human(rec), _street_de(rec)
    if grade == "ok":
        return f"Guter Zug: dein {ha} {street} passt — weiter so."
    alt = _alternative(rec)
    grund = rec.get("erklaerung_kurz") or "die einfachere Linie kostet hier weniger"
    if grade == "teuer":
        return f"Dein {ha} {street} war vermutlich etwas teuer: besser {alt} — {grund}."
    return f"Teurer Kauf {street}: {ha} statt {alt} — {grund}."


_TYP_RENDERER = {"pot_odds": _fb_pot_odds, "mdf": _fb_mdf, "sizing": _fb_sizing,
                 "advisor_freq": _fb_advisor_freq, "oracle_diff": _fb_oracle_diff}

MERKSATZ = {                                                     # optionale L5 der Hand-Zusammenfassung
    "pot_odds": "Merksatz: Pot Odds zuerst — zähle, wie oft du gewinnen musst, bevor du zahlst.",
    "mdf": "Merksatz: MDF schützt dich — wer zu oft foldet, lädt jeden Bluff ein.",
    "sizing": "Merksatz: Sizing folgt dem Plan — die Bet-Größe erzählt deine Geschichte.",
    "advisor_freq": "Merksatz: GTO mischt — es gibt oft mehr als einen guten Zug.",
    "oracle_diff": "Merksatz: gleiche Spots, gleiche Logik — der Bot ist nur eine zweite Meinung.",
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
        raise ValueError(f"Unbekannter Grade: {grade!r} (erlaubt: {sorted(GRADE_ICON)})")
    return grade


def render_decision_feedback(rec: dict) -> dict:
    """EINE benotete Entscheidung -> 1-2 warme deutsche Saetze -> {'text','html','terms'}."""
    grade = _validate_grade(rec)
    renderer = _TYP_RENDERER.get(rec.get("grade_typ"), _fb_generic)
    text = renderer(rec, grade)
    conf = str(rec.get("confidence") or "")
    if "Bot" in conf and "Bot-Einschätzung" not in text:     # Konfidenz-Label sichtbar (Doktrin par.1.3)
        text += f" {BOT_LABEL}"
    return _finish(text)


def _grade_rang(rec: dict) -> int:
    return {"leak": 0, "teuer": 1, "ok": 2}[rec["grade"]]


def _hand_rahmen(records: list[dict], hand_result) -> str:
    """L1: neutraler Rahmen — Street + Umfang, NIE Ergebnis-Woerter (Anti-Resultorientierung, Doktrin par.1.1)."""
    letzte = max(records, key=lambda r: _STREET_ORDER.get(str(r.get("street", "")).lower(), 0))
    street = _STREET_BIS.get(str(letzte.get("street", "")).lower(), "zum Ende")
    n = len(records)
    zusatz = ""
    pot = (hand_result or {}).get("pot") if isinstance(hand_result, dict) else None
    if isinstance(pot, (int, float)) and pot > 0:
        zusatz = f", Pot am Ende {pot / 100:.0f} bb"
    return f"Hand-Rückblick: {n} Entscheidung{'en' if n != 1 else ''}, gespielt bis {street}{zusatz}."


def render_hand_feedback(records: list[dict], hand_result: dict | None = None, mode: str = "gto") -> dict:
    """3-5 Zeilen pro Hand: Rahmen, bestes Moment (explizit gefeiert), teuerstes Moment (+ Alternative + Grund),
    optional Mixing-Hinweis und Merksatz. Leere records -> eine warme Zeile."""
    records = [r for r in (records or []) if isinstance(r, dict)]
    if not records:
        return _finish("Keine Hero-Entscheidung zu bewerten — Fold preflop ist oft der beste Kauf.")
    for r in records:
        _validate_grade(r)

    lines = [_hand_rahmen(records, hand_result)]
    beste = next((r for r in records if r["grade"] == "ok"), None)
    if beste is not None:                                        # L2: gute Zuege EXPLIZIT feiern (Doktrin par.1.5)
        lines.append(f"{GRADE_ICON['ok']} Stark: dein {_human(beste)} {_street_de(beste)} — sauber gewählt, genau im Plan.")
    schlecht = min(records, key=_grade_rang)
    if schlecht["grade"] != "ok":                                # L3: teuerstes Moment via Entscheidungs-Atom
        lines.append(f"{GRADE_ICON[schlecht['grade']]} {render_decision_feedback(schlecht)['text']}")
    else:
        lines.append("Kein teurer Kauf in dieser Hand — jede Entscheidung saß.")
    if len(lines) < MAX_HAND_LINES:                              # L4: Mixing wird GESAGT, wenn vorhanden
        mix = next((m for m in (_mix_satz(_support_dist(r)) for r in records) if m), None)
        if mix:
            lines.append(mix)
    if len(lines) < MAX_HAND_LINES:                              # L5: Merksatz zum teuersten Typ
        merk = MERKSATZ.get(schlecht.get("grade_typ") or "", "Merksatz: Entscheidungen zählen, nicht einzelne Resultate.")
        lines.append(merk)
    while len(lines) < MIN_HAND_LINES:
        lines.append("Weiter so — Entscheidungen zählen, nicht einzelne Resultate.")
    lines = lines[:MAX_HAND_LINES]
    assert MIN_HAND_LINES <= len(lines) <= MAX_HAND_LINES
    return _finish("\n".join(lines))


# ---------------------------------------------------------------- Selftest (synthetische Fixtures, kein Server noetig)
def _rec(typ, grade, **kw) -> dict:
    base = {"hand_id": "selftest-1", "street": kw.pop("street", "turn"), "grade": grade, "grade_typ": typ,
            "human_action": {"action": kw.pop("ha", "call"), "amount": kw.pop("amount", None)},
            "oracle_action": kw.pop("oa", "fold"), "confidence": kw.pop("conf", "Mathe (unanfechtbar)"),
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
             conf="Solver-Frequenz (HU-trainiert, Näherung)"),
        _rec("advisor_freq", "ok", ha="call", advisor_dist={"call": 0.95, "fold": 0.04, "raise": 0.01}),
        _rec("advisor_freq", "teuer", ha="call", oa="fold", advisor_dist={"fold": 0.9, "call": 0.02, "raise": 0.08}),
        _rec("advisor_freq", "leak", ha="raise", oa="fold", advisor_dist={"fold": 0.97, "call": 0.02, "raise": 0.01}),
        # oracle_diff x 3, ok = sparse Resolver-Shape OHNE equity/mdf-Keys (Resolver-Oberflaeche)
        _rec("oracle_diff", "ok", ha="call", oa="call", street="river", conf="Bot-Einschätzung",
             rationale={"phase": "postflop", "street": "river", "made_hand": "two pair", "resolver": True, "range_conf": 0.8}),
        _rec("oracle_diff", "teuer", ha="bet", oa="check", conf="Bot-Einschätzung",
             erklaerung_kurz="der Check hält die schwachen Hände in seiner Range"),
        _rec("oracle_diff", "leak", ha="allin", oa="fold", conf="Bot-Einschätzung"),
        # Missing-Check-Fallbacks: unbekannter/fehlender grade_typ + leere checks bei gesetztem typ
        _rec(None, "ok"), _rec(None, "teuer", conf="Bot-Einschätzung"), _rec("nonsense_typ", "leak"),
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
    # 2) Kritik traegt Alternative: teuer/leak-Texte nennen 'Besser'/'wählt'/'statt' (Alternative + Grund)
    for rec, out in zip(fixtures, outs):
        if rec["grade"] in ("teuer", "leak"):
            assert any(w in out["text"] for w in ("Besser", "besser", "wählt", "statt", "wäre", "Nimm")), out["text"]
    # 3) Bot-Einschaetzung sichtbar gelabelt
    bot_out = render_decision_feedback(_rec(None, "teuer", conf="Bot-Einschätzung"))
    assert "Bot-Einschätzung" in bot_out["text"]
    # 4) Hand-Feedback: 3-5 Zeilen, Feier-Zeile bei ok, Mixing gesagt, Anti-Result-Woerter abwesend
    hand = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    zeilen = hand["text"].split("\n")
    assert MIN_HAND_LINES <= len(zeilen) <= MAX_HAND_LINES, zeilen
    assert GRADE_ICON["ok"] in hand["text"] and "Stark" in hand["text"], hand["text"]
    assert "mischt" in hand["text"], hand["text"]
    for verboten in ("gewonnen", "verloren", "leider", "Fehler"):
        assert verboten not in hand["text"], (verboten, hand["text"])
    hand2 = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    assert hand["text"] == hand2["text"], "Hand-Feedback nicht deterministisch"
    outs.append(hand)
    all_ok = render_hand_feedback([fixtures[0], fixtures[3]], None, "gto")
    assert MIN_HAND_LINES <= len(all_ok["text"].split("\n")) <= MAX_HAND_LINES
    outs.append(all_ok)
    leer = render_hand_feedback([], None, "gto")
    assert "Keine Hero-Entscheidung" in leer["text"] and leer["html"]
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
    assert "Resolver" in res["text"], res["text"]
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
