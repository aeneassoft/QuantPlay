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
    """'du brauchtest 1-von-3 (33%), hattest etwa 1-von-4 (25%)' — Zahl einmal, dann Vergleich.
    QA-Fix (50-Hand-Probe): wenn beide Werte auf DASSELBE 1-von-N runden (38% und 33% -> beide '1-von-3'),
    las sich der Satz als Widerspruch ('brauchtest 1-von-3, hattest 1-von-3 — zu wenig'). Dann nur Prozente."""
    if isinstance(req, (int, float)) and isinstance(eq, (int, float)):
        a, b = eins_von(req), eins_von(eq)
        if a == b:
            return f"du brauchtest {req * 100:.0f}% Equity, hattest nur {eq * 100:.0f}%"
        return f"du brauchtest {a} ({req * 100:.0f}% Equity), hattest etwa {b} ({eq * 100:.0f}%)"
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
    orc = rec.get("oracle") or {}
    oa = rec.get("oracle_action") or orc.get("oracle_action") or orc.get("action")   # P0-3 nistet 'oracle_action'
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


def _sizing_worte(rec: dict, hf, sf) -> tuple[str, str]:
    """Preflop misst man in BIG BLINDS, nicht in Pot-Vielfachen — 'Overbet (29.2x Pot)' für einen
    Preflop-Raise war technisch richtig und praktisch unbrauchbar (User-QA 2026-08-02)."""
    if str(rec.get("street", "")).lower() != "preflop":
        return pot_frac_de(hf), pot_frac_de(sf)
    obs = rec.get("obs") or {}
    bb = _num(obs.get("bb")) or 100
    ha = rec.get("human_action") or {}
    amt = _num(ha.get("amount")) if isinstance(ha, dict) else None
    gespielt = f"Raise auf {amt / bb:.1f}bb" if amt else "diese Raise-Größe"
    return gespielt, "eine Standard-Open-Größe (2–3bb, gegen einen Raise ~3x)"


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
    """'→ wähle die Bet ~45 % kleiner' — die konkrete Prozent-Korrektur (User-QA 2026-08-02: gut
    sichtbar zeigen, um wie viel die Bet höher/niedriger gehört; ab 2x als Faktor, Prozente >100 lügen)."""
    if ratio is None or (1 - SIZING_TOLERANZ) <= ratio <= (1 + SIZING_TOLERANZ):
        return ""
    if ratio >= 2:
        return f" → wähle die Bet ~{ratio:.1f}-mal so groß."
    if ratio > 1:
        return f" → wähle die Bet ~{(ratio - 1) * 100:.0f} % größer."
    return f" → wähle die Bet ~{(1 - ratio) * 100:.0f} % kleiner."


def _fb_sizing(rec: dict, grade: str) -> str:
    sz = _check(rec, "sizing")
    hf, sf = _num(sz.get("human_frac")), _num(sz.get("snapped_frac"))
    gespielt, plan = _sizing_worte(rec, hf, sf)
    if grade == "ok":
        return f"Sauberes Sizing: {gespielt} passt hier — so bleibt deine Value-Bet glaubwürdig."
    # Plan-Größe nur EINMAL nennen — die preflop-Variante ist lang ('Standard-Open-Größe (2–3bb …)') und
    # las sich doppelt genannt wie ein Stottern (User-QA 2026-08-02).
    korrektur = _sizing_korrektur(_sizing_ratio(rec, hf, sf))
    if grade == "teuer":
        return (f"Dein Sizing war etwas daneben: gespielt {gespielt}, der Plan sieht {plan} vor — "
                f"die Größe erzählt die stimmigere Geschichte.{korrektur}")
    return (f"Teurer Kauf beim Sizing: {gespielt}, der Plan sieht {plan} vor — "
            f"die Geometrie gibt die Größe vor, nicht das Bauchgefühl.{korrektur}")


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
    # QA-Fix (50-Hand-Probe): erklaerung_kurz beginnt selbst mit 'Teurer Kauf: der Referenz-Bot spielt hier X'
    # — im Rahmensatz wiederholt ergab das 'Etwas teuer: … — Teurer Kauf: … spielt hier Call …' (doppelt,
    # verschachtelt). Wir übernehmen nur den BEGRÜNDUNGS-Schwanz nach dem Gedankenstrich.
    grund = rec.get("erklaerung_kurz") or "seine Linie hält die Range besser zusammen"
    grund = re.sub(r"^(Teurer Kauf|Etwas teuer|Sauber)\s*:\s*", "", grund).strip()
    if f"spielt hier {alt}" in grund and "—" in grund:
        grund = grund.split("—", 1)[1].strip().rstrip(".")
    grund = grund.rstrip(".")
    if grade == "teuer":
        return f"Etwas teuer: dein {ha}, der Bot wählt {alt} — {grund} ({quelle})."
    return f"Teurer Kauf: {ha} statt {alt} — {grund} ({quelle})."


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


# Formel-Monotonie-Bremse (49/50 identische Openings gemessen). DETERMINISTISCH: der Opener hängt an der
# hand_id, nicht an einem Zähler — gleicher Input ergibt exakt denselben Text (P1-B-Vertrag), verschiedene
# Hände variieren trotzdem.
_OPENER = ("Hand-Rückblick", "Kurz zur Hand", "Rückblick")


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
    street = _STREET_BIS.get(str(letzte.get("street", "")).lower(), "zum Ende")
    n = len(records)
    opener = _opener_for(records)
    zusatz = ""
    net = (hand_result or {}).get("hero_net_bb") if isinstance(hand_result, dict) else None
    if isinstance(net, (int, float)) and abs(net) >= 1:
        zusatz = f" — Ergebnis {net:+.0f} bb"
        grades = {r["grade"] for r in records}
        if net <= -5 and grades == {"ok"}:
            zusatz += " (sauber gespielt und trotzdem verloren — genau so verliert man richtig)"
        elif net >= 5 and "leak" in grades:
            zusatz += " (gewonnen, aber der teure Kauf bleibt teuer — das Ergebnis adelt ihn nicht)"
    return f"{opener}: {n} Entscheidung{'en' if n != 1 else ''}, gespielt bis {street}{zusatz}."


def _dist_str(rec: dict) -> str:
    """'[Bot: 68% Fold / 29% Call]' — die Advisor-Frequenzen als direkter Lern-Impuls (User-Wunsch)."""
    dist = _support_dist(rec)
    parts = [f"{p * 100:.0f}% {_action_de(a)}" for a, p in dist
             if isinstance(p, (int, float)) and p >= 0.02][:3]
    return ("  [Bot: " + " / ".join(parts) + "]") if parts else ""


_STREET_TAG = {"preflop": "PREFLOP", "flop": "FLOP", "turn": "TURN", "river": "RIVER"}
_HERO_SEAT = 0                       # six_server.HUMAN — der Trainer setzt den Menschen immer auf Sitz 0
_RANGE_WORT = {1: "etwa die besten 20% der Hände", 2: "etwa die besten 8% (3-Bet-Range)",
               3: "nur die absolute Spitze (~4%, 4-Bet-Range)"}


def _kurz(txt: str) -> str:
    """Grade-Präfixe raus — Icon + Straßen-Tag tragen das schon; der Satz startet direkt mit dem Grund."""
    return re.sub(r"^(Teurer Kauf|Etwas teuer|Dein Sizing war etwas daneben)\s*[:—-]\s*", "", txt).strip()


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
        wer = "Du repräsentierst" if pre_raises[-1].get("player") == _HERO_SEAT else "Der Gegner repräsentiert"
        out.append(f"Preflop: {wer} {_RANGE_WORT.get(min(len(pre_raises), 3), _RANGE_WORT[3])}.")
    else:
        out.append("Preflop: nur Limps/Calls — alle Ranges bleiben breit und unsortiert.")
    for st in ("river", "turn", "flop"):
        agg = [e for e in hist if str(e.get("street")) == st and e.get("player") != _HERO_SEAT
               and e.get("action") in ("bet", "raise", "allin")]
        if agg:
            verb = "Raise" if agg[-1].get("action") == "raise" else "Bet"
            out.append(f"{_STREET_TAG[st].capitalize()}: seine {verb} erzählt einen Treffer — Top-Paar oder besser.")
            break
    hole, board = obs.get("hole") or [], obs.get("board") or []
    halt = None
    try:
        from pokerbot.brain import api as _api
        if board:
            _name, st_val = _api.hand_rank(hole, board)
            halt = ("eine starke Made Hand" if st_val >= STRONG_MADE
                    else "eine mittlere Hand" if st_val >= MEDIUM_MADE else "wenig Substanz")
    except Exception:  # noqa: BLE001 — Strategie ist Zusatz, nie Blocker
        pass
    fd = ""
    if 3 <= len(board) <= 4 and hole:
        for suit in "shdc":
            tot = sum(1 for c in hole + board if len(c) > 1 and c[1] == suit)
            if tot == 4 and any(len(c) > 1 and c[1] == suit for c in hole):
                fd = " plus Flush-Draw"
                break
    aggro = any(str(r.get("street")) != "preflop"
                and str(((r.get("human_action") or {}).get("action") if isinstance(r.get("human_action"), dict)
                         else r.get("human_action"))) in ("bet", "raise", "allin") for r in records)
    linie = "Stärke — du repräsentierst den Treffer" if aggro else "Zurückhaltung — Marginales oder Draws"
    if halt:
        out.append(f"Du hältst {halt}{fd}; deine Linie erzählt {linie}.")
    return out[:3]


def render_hand_feedback(records: list[dict], hand_result: dict | None = None, mode: str = "gto") -> dict:
    """Lern-Impuls-Struktur (User-QA 2026-08-02): NUR die suboptimalen Entscheidungen, je eine Zeile mit
    Straßen-Tag + Grund + Bot-Frequenzen; kein Lob-Ballast, kein Ergebnis-Text (steht schon im UI); danach
    der Strategie-Abschnitt (Range-Erzählung). Alles ok -> ein Satz + der knappste Spot als Frequenz-Fenster."""
    records = [r for r in (records or []) if isinstance(r, dict)]
    if not records:
        return _finish("Keine Hero-Entscheidung zu bewerten — Fold preflop ist oft der beste Kauf.")
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
        mehr = f" (+{n_st - 1} weitere {_STREET_TAG.get(st, '')}-Spots)" if n_st > 1 else ""
        txt = _kurz(render_decision_feedback(r)["text"])
        lines.append(f"{GRADE_ICON[r['grade']]} {_STREET_TAG.get(st, '?')} · {_human(r)}: {txt}{_dist_str(r)}{mehr}")
    if not bad:
        lines.append(f"✓ Alle {len(records)} Entscheidungen im Plan — nichts zu verbessern.")
        mit_dist = [r for r in records if _support_dist(r)]
        if mit_dist:
            knapp = min(mit_dist, key=lambda r: max((p for _, p in _support_dist(r)), default=1.0))
            tag = _STREET_TAG.get(str(knapp.get("street", "")).lower(), "?")
            lines.append(f"Knappster Spot — {tag} · {_human(knapp)}:{_dist_str(knapp)}")
    strat = _strategie(records, hand_result)
    if strat:
        lines.append("— Strategie (Bot-Lesart) —")
        lines.extend(strat)
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
            assert any(w in out["text"] for w in ("Besser", "besser", "wählt", "statt", "wäre", "Nimm",
                                                  "sieht", "Plan")), out["text"]
    # 3) Bot-Einschaetzung sichtbar gelabelt
    bot_out = render_decision_feedback(_rec(None, "teuer", conf="Bot-Einschätzung"))
    assert "Bot-Einschätzung" in bot_out["text"]
    # 3b) Sizing-Korrektur in Prozent (User-QA 2026-08-02): 1.6x Pot statt 0.75 -> '~53 % kleiner';
    #     0.1 statt 0.75 -> Faktor-Wortlaut; Preflop 12bb-Open vs 2.5bb-Plan -> '% kleiner' in bb-Logik
    assert "% kleiner" in render_decision_feedback(fixtures[7])["text"], fixtures[7]
    assert "-mal so groß" in render_decision_feedback(fixtures[8])["text"], fixtures[8]
    pre_sz = _rec("sizing", "leak", ha="raise", amount=1200, street="preflop",
                  obs={"bb": 100}, history=[], checks={"sizing": {"human_frac": 8.0, "snapped_frac": 1.0}})
    assert "% kleiner" in render_decision_feedback(pre_sz)["text"], render_decision_feedback(pre_sz)["text"]
    # 4) Hand-Feedback (Lern-Impuls-Struktur, User-QA 2026-08-02): NUR suboptimale Entscheidungen, je eine
    #    Zeile mit STRASSEN-TAG + Bot-Frequenzen, danach der Strategie-Abschnitt; KEIN Lob, KEIN Ergebnis-Text.
    hand = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    assert any(t in hand["text"] for t in ("PREFLOP", "FLOP", "TURN", "RIVER")), hand["text"]
    assert "Strategie (Bot-Lesart)" in hand["text"], hand["text"]
    assert "Stark:" not in hand["text"], "Lob-Zeile gehoert nicht mehr ins Hand-Feedback"
    assert "Ergebnis" not in hand["text"], "Ergebnis-Text ist Sache des UI, nicht des Coach-Textes"
    for verboten in ("gewonnen", "verloren", "leider", "Fehler"):
        assert verboten not in hand["text"], (verboten, hand["text"])
    hand2 = render_hand_feedback([fixtures[0], fixtures[7], fixtures[9]], {"pot": 2400}, "gto")
    assert hand["text"] == hand2["text"], "Hand-Feedback nicht deterministisch"
    outs.append(hand)
    all_ok = render_hand_feedback([fixtures[0], fixtures[3]], None, "gto")
    assert "im Plan" in all_ok["text"], all_ok["text"]        # Alles-ok-Zweig bleibt knapp und ehrlich
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
