"""Sprachschicht des Trainers: der eingefrorene coach.v1-Vertrag + austauschbare Render-Backends.

WHY: Die Sprachschicht ENTSCHEIDET NICHTS und RECHNET NICHTS (TRAINER_DESIGN.md §3) — sie formt
bereits berechnete Zahlen in warmes Deutsch. Der Vertrag ist hier gepinnt, damit Grader (P0),
Templates (P1) und Backends (P3) dieselbe Sprache sprechen; jede Zahl im gerenderten Text MUSS
aus dem Payload stammen (die GLM-Lektion: LLM-Output wird gegatet, nie vertraut).

BINDING Enum-Pin (TRAINER_PLAN.md Must-Fix "GRADE/GRADE_TYP VOCABULARY DRIFT"):
  grade     in {ok, teuer, leak}                                  — KEIN 'none'
  grade_typ in {pot_odds, mdf, sizing, advisor_freq, oracle_diff} — das P0-4-Vokabular

Payload-Schema coach.v1 (make_payload baut es, validate_payload erzwingt es):
  {schema:'coach.v1', mode:'gto'|'exploit', hand_id, street, hero_pos,
   grade, grade_typ, confidence:'hart'|'bot_einschaetzung',
   human_action:{action, amount_bb?}, oracle_action:{action, amount_bb?}|None,
   numbers:{equity_pct?, required_equity_pct?, mdf_pct?, pot_bb?, to_call_bb?, bet_frac_pot?,
            snapped_frac_pot?, advisor_bet_pct?, advisor_fold_pct?, advisor_call_pct?,
            advisor_raise_pct?, spr?, ev_diff_bb?},   # 1 Dezimale, fehlende Werte WEGLASSEN (nie 0)
   strategic:{...}|None, mixed:{is_mixed, dist:{aktion: pct}}|None, glossar_terms:[str]}

Run: python -m pokerbot.coach.language   (Selbsttest, kein Server noetig)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Protocol

SCHEMA = "coach.v1"
GRADES = frozenset({"ok", "teuer", "leak"})
GRADE_TYPES = frozenset({"pot_odds", "mdf", "sizing", "advisor_freq", "oracle_diff"})
CONFIDENCES = frozenset({"hart", "bot_einschaetzung"})
MODES = frozenset({"gto", "exploit"})

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_DEFAULT_MODEL = "qwen3:8b"
OLLAMA_TIMEOUT_S = 2.0          # harte Latenz-Grenze (TRAINER_DESIGN.md §3: < 2 s oder Templates)

# Zaehlt jeden Rueckfall vom LLM auf Templates (Timeout/leer/halluzinierte Zahl) — Mess-Artefakt
# fuer research/language_backend_test.py (die frac_bad-Disziplin aus den GLM-Lektionen).
FALLBACKS = 0

_NUM_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?")
# "3-Bet"/"4-Bet" sind Vokabeln, keine Zahlen — vor der Token-Extraktion entfernen.
_LEXICAL_NUM_RE = re.compile(r"[34]-?[Bb]et\w*")
# Board-Kartenzahlen (3 Flop / 4 Turn / 5 River) sind strukturell erlaubt, wenn vom Board die Rede ist.
_BOARD_COUNT_WHITELIST = frozenset({"3", "4", "5"})
_BOARD_WORDS = ("Flop", "Turn", "River", "Board", "Karte")

_ACTION_DE = {"fold": "Fold", "check": "Check", "call": "Call", "bet": "Bet",
              "raise": "Raise", "allin": "All-in"}


# ---------------------------------------------------------------- Vertrag: bauen + validieren
def validate_payload(payload: dict) -> dict:
    """Erzwingt den coach.v1-Vertrag. ValueError bei falschem Schema/Enum — nie still durchwinken."""
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"kein {SCHEMA}-Payload: schema={payload.get('schema')!r}")
    if payload.get("mode") not in MODES:
        raise ValueError(f"mode {payload.get('mode')!r} nicht in {sorted(MODES)}")
    if payload.get("grade") not in GRADES:
        raise ValueError(f"grade {payload.get('grade')!r} nicht in {sorted(GRADES)}")
    if payload.get("grade_typ") not in GRADE_TYPES:
        raise ValueError(f"grade_typ {payload.get('grade_typ')!r} nicht in {sorted(GRADE_TYPES)}")
    if payload.get("confidence") not in CONFIDENCES:
        raise ValueError(f"confidence {payload.get('confidence')!r} nicht in {sorted(CONFIDENCES)}")
    ha = payload.get("human_action")
    if not isinstance(ha, dict) or "action" not in ha:
        raise ValueError("human_action fehlt oder hat keine 'action'")
    if not isinstance(payload.get("numbers"), dict):
        raise ValueError("numbers fehlt (dict mit vorberechneten Zahlen)")
    return payload


def make_payload(*, mode: str, hand_id, street: str, grade: str, grade_typ: str,
                 human_action: dict, numbers: dict, hero_pos: str = "?",
                 confidence: str = "bot_einschaetzung", oracle_action: dict | None = None,
                 strategic: dict | None = None, mixed: dict | None = None,
                 glossar_terms: list[str] | None = None) -> dict:
    """Baut ein valides coach.v1-Payload. Zahlen werden auf 1 Dezimale gerundet,
    None-Werte WEGGELASSEN (Advisor None darf nie zu 0 werden — Recon-Gotcha)."""
    clean_numbers = {k: round(float(v), 1) for k, v in numbers.items() if v is not None}
    payload = {"schema": SCHEMA, "mode": mode, "hand_id": hand_id, "street": street,
               "hero_pos": hero_pos, "grade": grade, "grade_typ": grade_typ,
               "confidence": confidence, "human_action": dict(human_action),
               "oracle_action": dict(oracle_action) if oracle_action else None,
               "numbers": clean_numbers, "strategic": strategic, "mixed": mixed,
               "glossar_terms": list(glossar_terms or [])}
    return validate_payload(payload)


# ---------------------------------------------------------------- Zahlen-Grounding (frac_bad-Gate)
def _numeric_leaves(obj) -> list[float]:
    """Alle Zahl-Blaetter eines Payload-Teilbaums (dict/list rekursiv, bool ausgenommen)."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [x for v in obj.values() for x in _numeric_leaves(v)]
    if isinstance(obj, list):
        return [x for v in obj for x in _numeric_leaves(v)]
    return []


def _allowed_forms(value: float) -> set[str]:
    """Erlaubte Text-Formen einer Payload-Zahl: exakt, 1 Dezimale (Punkt+Komma), int-gerundet —
    plus die Vergleichsform der Doktrin ('Zahlen -> Vergleiche'): ein Prozentwert p darf als
    '1-von-N' mit N=round(100/p) erscheinen (templates_de.eins_von emittiert genau das)."""
    forms = {f"{value:g}", f"{value:.1f}", f"{value:.1f}".replace(".", ","),
             str(int(round(value)))}
    if value == int(value):
        forms.add(str(int(value)))
    if 1.0 <= value <= 100.0:
        forms |= {"1", str(int(round(100.0 / value)))}
    return forms


def validate_numbers(text: str, payload: dict) -> list[str]:
    """Liefert jede Zahl im Text, die NICHT aus dem Payload stammt (leer = sauber).

    Grounding-Quelle: numbers + human_action/oracle_action (amount_bb) + mixed.dist —
    alles Payload, nichts Erfundenes. Struktur-Whitelist: Board-Kartenzahlen 3/4/5 nur
    wenn vom Board die Rede ist; '3-Bet'/'4-Bet' zaehlen als Vokabel, nicht als Zahl."""
    allowed: set[str] = set()
    for section in (payload.get("numbers"), payload.get("human_action"),
                    payload.get("oracle_action"), payload.get("mixed")):
        for v in _numeric_leaves(section):
            allowed |= _allowed_forms(v)
    board_ok = any(w in text for w in _BOARD_WORDS)
    bad: list[str] = []
    for token in _NUM_TOKEN_RE.findall(_LEXICAL_NUM_RE.sub("", text)):
        normalized = token.replace(",", ".")
        if normalized in allowed or f"{float(normalized):g}" in allowed:
            continue
        if token in _BOARD_COUNT_WHITELIST and board_ok:
            continue
        bad.append(token)
    return bad


# ---------------------------------------------------------------- Backends
class LanguageBackend(Protocol):
    """Vertrag jedes Sprach-Backends: strukturiertes JSON rein -> kurzer deutscher Text raus."""
    name: str

    def render_short(self, payload: dict) -> str: ...


def _fmt(value: float) -> str:
    """Deutsche Zahldarstellung, deckungsgleich mit den _allowed_forms von validate_numbers."""
    v = float(value)
    return str(int(v)) if v == int(v) else f"{v:.1f}".replace(".", ",")


def _action_de(act: dict | None) -> str:
    if not act:
        return "?"
    verb = _ACTION_DE.get(act.get("action", "?"), str(act.get("action")))
    amount = act.get("amount_bb")
    return f"{verb} auf {_fmt(amount)} bb" if amount is not None else verb


def _grade_sentence(payload: dict) -> str:
    """Der Ein-Satz-Grund, gekeyt nach grade_typ — Zahlen NUR aus payload['numbers']."""
    n = payload["numbers"]
    typ = payload["grade_typ"]
    if typ == "pot_odds" and "required_equity_pct" in n:
        eq = f", du hattest etwa {_fmt(n['equity_pct'])} %" if "equity_pct" in n else ""
        return f"Der Call brauchte {_fmt(n['required_equity_pct'])} % Equity{eq}."
    if typ == "mdf" and "mdf_pct" in n:
        return f"MDF sagt: mindestens {_fmt(n['mdf_pct'])} % der Range verteidigen."
    if typ == "sizing" and "bet_frac_pot" in n:
        snap = f", die Baum-Groesse waere {_fmt(n['snapped_frac_pot'])}" if "snapped_frac_pot" in n else ""
        return f"Dein Sizing lag bei {_fmt(n['bet_frac_pot'])}x Pot{snap}."
    if typ == "advisor_freq" and "advisor_bet_pct" in n:
        return f"Der Solver-Advisor spielt das etwa {_fmt(n['advisor_bet_pct'])} % der Zeit."
    if payload.get("oracle_action"):
        return f"Der Bot haette {_action_de(payload['oracle_action'])} gespielt."
    return "Die Referenz war hier knapp — Entscheidung im Rahmen."


def _fallback_render(payload: dict) -> str:
    """Deterministischer deutscher Mini-Renderer: Rueckgrat, wenn templates_de (P1-B, paralleler
    Builder) noch fehlt oder wirft. Warmer Ton per Fairness-Doktrin §1.5 (nie 'Fehler')."""
    grade = payload["grade"]
    lead = {"ok": "Gut gespielt", "teuer": "Ein teurer Kauf", "leak": "Ein klarer teurer Kauf"}[grade]
    text = f"{payload['street'].capitalize()}: {_action_de(payload['human_action'])} — {lead}. "
    text += _grade_sentence(payload)
    mixed = payload.get("mixed") or {}
    if grade == "ok" and mixed.get("is_mixed") and mixed.get("dist"):
        parts = " / ".join(f"{_fmt(p)} % {a.capitalize()}" for a, p in sorted(mixed["dist"].items()))
        text += f" GTO mischt hier: {parts} — beides gut."
    if payload["confidence"] == "bot_einschaetzung":
        text += " (Bot-Einschaetzung)"
    return text


def _frac(pct) -> float | None:
    """coach.v1 fuehrt Prozente (33.3), der P0-Record/templates_de fuehren Brueche (0.333)."""
    return None if pct is None else float(pct) / 100.0


def _payload_to_record(payload: dict) -> dict:
    """coach.v1 -> Decision-Record-Form (TRAINER_DESIGN.md §4), die templates_de konsumiert.
    Einheiten-Konversion Prozent->Bruch fuer equity/pot_odds/mdf und den Advisor-Mix."""
    n = payload["numbers"]
    dist = (payload.get("mixed") or {}).get("dist")
    conf = {"hart": "hart", "bot_einschaetzung": "Bot-Einschätzung"}[payload["confidence"]]
    return {"hand_id": payload.get("hand_id"), "street": payload.get("street"),
            "mode": payload.get("mode"), "grade": payload.get("grade"),
            "grade_typ": payload.get("grade_typ"), "human_action": payload.get("human_action"),
            "oracle_action": payload.get("oracle_action"), "confidence": conf,
            "advisor_dist": {a: _frac(p) for a, p in dist.items()} if dist else None,
            "equity": _frac(n.get("equity_pct")), "pot_odds": _frac(n.get("required_equity_pct")),
            "mdf": _frac(n.get("mdf_pct")), "erklaerung_kurz": "", "rationale": {}}


class TemplateBackend:
    """Default-Backend: deterministische deutsche Templates (P1-B), $0, sub-ms, nie halluzinierend.
    render_short ist das EIN-Entscheidungs-Atom -> templates_de.render_decision_feedback (Anhang V
    sanktioniert beide Symbole; render_hand_feedback emittiert Struktur-Zahlen wie '1 Entscheidung'
    und ist das Hand-Level-Werkzeug von P1-C, nicht der Kurz-Renderer). templates_de wird parallel
    gebaut — der Import ist bewacht, der eingebaute Fallback traegt bis dahin."""
    name = "templates"

    def render_short(self, payload: dict) -> str:
        payload = validate_payload(payload)
        try:  # P1-B liefert {text, html, terms} — render_short extrahiert ['text'] (Anhang V)
            from pokerbot.coach import templates_de
            rendered = templates_de.render_decision_feedback(_payload_to_record(payload))
            if rendered.get("text"):
                return rendered["text"]
        except Exception:  # noqa: BLE001 — parallel gebautes Modul darf fehlen/abweichen
            pass
        return _fallback_render(payload)


_OLLAMA_PROMPT = (
    "Du bist ein warmer, konkreter Poker-Coach. Formuliere aus dem folgenden JSON genau 1-2 "
    "deutsche Saetze Feedback zur Entscheidung. HARTE REGEL: Uebernimm Zahlen AUSSCHLIESSLICH "
    "woertlich aus dem JSON-Feld 'numbers' (und amount_bb). NIE rechnen, NIE runden, NIE neue "
    "Zahlen erfinden. Nie Ergebnisse bewerten, nur die Entscheidung. Leaks heissen 'teurer "
    "Kauf', gute Zuege werden explizit gelobt.\n\nJSON:\n"
)


class OllamaBackend:
    """Optionales LLM-Backend (lokal, Ollama). STRIKT gegatet: Timeout 2 s, und jede Zahl im
    Output, die nicht im Payload steht, verwirft die Antwort -> TemplateBackend uebernimmt."""
    name = "ollama"

    def __init__(self, model: str | None = None, url: str = OLLAMA_URL,
                 timeout_s: float = OLLAMA_TIMEOUT_S):
        self.model = model or os.environ.get("POKERB_OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
        self.url = url
        self.timeout_s = timeout_s
        self._fallback = TemplateBackend()

    def _generate(self, prompt: str) -> str:
        """Ein POST /api/generate (stream=False). Getrennt gehalten, damit der Selbsttest die
        Netz-Schicht monkeypatchen kann."""
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "").strip()

    def render_short(self, payload: dict) -> str:
        global FALLBACKS
        payload = validate_payload(payload)
        try:
            text = self._generate(_OLLAMA_PROMPT + json.dumps(payload, ensure_ascii=False))
        except Exception:  # noqa: BLE001 — offline/timeout: der Trainer muss ohne Ollama laufen
            FALLBACKS += 1
            return self._fallback.render_short(payload)
        if not text or validate_numbers(text, payload):
            FALLBACKS += 1  # leere oder zahlen-halluzinierende Antwort -> verwerfen
            return self._fallback.render_short(payload)
        return text


def get_backend(name: str = "templates") -> LanguageBackend:
    """Backend-Fabrik. Templates sind der DEFAULT; beim Default-Aufruf darf die Env-Variable
    POKERB_COACH_BACKEND umschalten (explizite name-Argumente gewinnen immer). Unbekannte
    Namen fallen mit Warnung auf Templates zurueck — nie crashen."""
    if name in (None, "", "templates") and os.environ.get("POKERB_COACH_BACKEND"):
        name = os.environ["POKERB_COACH_BACKEND"]
    chosen = (name or "templates").lower()
    if chosen in ("templates", "template"):
        return TemplateBackend()
    if chosen == "ollama":
        return OllamaBackend()
    print(f"[language] unbekanntes Backend {chosen!r} — Templates bleiben Default", file=sys.stderr)
    return TemplateBackend()


# ---------------------------------------------------------------- Selbsttest (synthetisch, offline)
def _fixture_payload(**overrides) -> dict:
    base = dict(mode="gto", hand_id="s1-7", street="river", grade="teuer", grade_typ="pot_odds",
                human_action={"action": "call"}, oracle_action={"action": "fold"},
                numbers={"equity_pct": 24.0, "required_equity_pct": 33.3,
                         "pot_bb": 12.5, "to_call_bb": 6.2},
                confidence="hart")
    base.update(overrides)
    return make_payload(**base)


def _selftest():
    # 1) Vertrag: falsche Enums werden abgelehnt, gutes Payload validiert
    for bad_kwargs in ({"grade": "super"}, {"grade_typ": "ev"}, {"grade_typ": "none"},
                       {"mode": "turbo"}, {"confidence": "sicher"}):
        try:
            _fixture_payload(**bad_kwargs)
            raise AssertionError(f"bad enum accepted: {bad_kwargs}")
        except ValueError:
            pass
    payload = _fixture_payload()
    assert validate_payload(payload) is payload

    # 2) TemplateBackend: nicht-leer, deterministisch, zahlen-sauber
    tb = TemplateBackend()
    text = tb.render_short(payload)
    assert text and isinstance(text, str), text
    assert text == tb.render_short(payload), "TemplateBackend nicht deterministisch"
    assert validate_numbers(text, payload) == [], (text, validate_numbers(text, payload))

    # 3) Validator: injizierte Fremdzahl wird gefangen; Payload-Zahlen (auch '33,3') passieren
    assert validate_numbers("Du brauchtest 73 % Equity.", payload) == ["73"]
    assert validate_numbers("Der Call brauchte 33,3 % bei 24 % Equity.", payload) == []
    assert validate_numbers("Am Flop liegen 3 Karten.", payload) == []      # Struktur-Whitelist
    assert validate_numbers("Nimm 7 mehr.", payload) == ["7"]               # nicht ableitbar -> flag
    assert validate_numbers("du brauchtest 1-von-3 (33% Equity)", payload) == []  # Vergleichsform
    assert validate_numbers("Gegen die 3-Bet weiterspielen.", payload) == []  # Vokabel, keine Zahl

    # 4) Mixing-Support rendert beide Frequenzen (Doktrin §1.2)
    mixed = _fixture_payload(grade="ok", grade_typ="advisor_freq",
                             human_action={"action": "check"},
                             numbers={"advisor_bet_pct": 60.0},
                             mixed={"is_mixed": True, "dist": {"bet": 60.0, "check": 40.0}},
                             confidence="bot_einschaetzung")
    mtext = tb.render_short(mixed)
    assert validate_numbers(mtext, mixed) == [], mtext

    # 5) Ollama offline (Port 9 = discard, sofortiger Refuse) -> sauberer Template-Fallback
    global FALLBACKS
    before = FALLBACKS
    ob = OllamaBackend(url="http://127.0.0.1:9/api/generate", timeout_s=0.5)
    assert ob.render_short(payload) == text, "Offline-Fallback muss den Template-Text liefern"
    assert FALLBACKS == before + 1

    # 6) Halluzinations-Gate: LLM-Antwort mit Fremdzahl wird verworfen -> Template-Text
    ob2 = OllamaBackend(url="http://127.0.0.1:9/api/generate")
    ob2._generate = lambda prompt: "Du brauchtest 73 % Equity fuer den Call."  # type: ignore
    assert ob2.render_short(payload) == text
    assert FALLBACKS == before + 2

    # 7) Fabrik: Templates default, Env nur beim Default-Aufruf, Unbekanntes faellt zurueck
    os.environ.pop("POKERB_COACH_BACKEND", None)
    assert get_backend().name == "templates"
    assert get_backend("ollama").name == "ollama"
    assert get_backend("quatsch").name == "templates"
    os.environ["POKERB_COACH_BACKEND"] = "ollama"
    try:
        assert get_backend().name == "ollama"
        assert get_backend("ollama").name == "ollama"
    finally:
        os.environ.pop("POKERB_COACH_BACKEND", None)

    print("OK - coach.v1 Vertrag gepinnt (ok/teuer/leak x 5 grade_typ), Templates default, "
          f"Ollama-Gate faellt sauber zurueck (FALLBACKS={FALLBACKS}).")


if __name__ == "__main__":
    _selftest()
