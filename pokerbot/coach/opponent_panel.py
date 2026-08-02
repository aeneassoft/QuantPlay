"""Exploit-Panel „Was der Bot ueber dich gelernt hat": sixmax-OppModel -> deutscher Klartext.

WHY: Das Killer-Feature des Exploit-Modus (TRAINER_DESIGN.md §2) — die live gelernten
Tendenzen des Trainierenden als Leak-Detektor in Klartext („Sitz 3 hat bemerkt: du foldest
oft auf River-Bets — er blufft dich oefter"). Die Trigger-Schwellen SPIEGELN exakt
SixMaxBot._read (pokerbot/arena/sixmax.py:290-318): das Panel zeigt genau die Reads, auf die
die Bots wirklich reagieren — nichts Erfundenes. Jede Zahl stammt aus den Zaehlern des
OppModel; unterhalb der Sample-Gates rendert der ehrliche Leerstand („noch nicht genug Daten").

Run: python -m pokerbot.coach.opponent_panel   (Selbsttest mit synthetischem OppModel-Fixture)
"""
from __future__ import annotations

HUMAN_SEAT = 0
MAX_OBSERVATIONS = 4            # 2-4 Beobachtungen: Panel bleibt lesbar, kein Textwall
MIN_OBSERVATIONS = 2

# Schwellen 1:1 aus SixMaxBot._read. Falls der P3-C-Refactor (paralleler Builder) die Literale
# als READ_*-Konstanten hoisted, importieren wir sie — das Panel kann dann nie driften.
try:
    from pokerbot.arena.sixmax import (READ_AGGRO_HI, READ_AGGRO_LO, READ_OVERFOLD,
                                       READ_STATION, READ_THREEBET_HAPPY)
    _MIRRORED_THRESHOLDS = False    # Konstanten kommen aus sixmax — Drift unmoeglich
except ImportError:
    _MIRRORED_THRESHOLDS = True     # noch Literale — die Drift-Wache im Selbsttest greift
    READ_THREEBET_HAPPY = 0.11  # _read: tb > 0.11 -> cont_bonus (3bet-Bluffer breiter continuen)
    READ_AGGRO_HI = 0.55        # _read: aggression > 0.55 -> call_delta -0.07 (bluff-catchen)
    READ_AGGRO_LO = 0.30        # _read: aggression < 0.30 -> call_delta +0.07 (nur Value glauben)
    READ_OVERFOLD = 0.55        # _read: fold_to_bet > 0.55 -> bluff_mult bis 2.2 (oefter bluffen)
    READ_STATION = 0.30         # _read: fold_to_bet < 0.30 -> bluff_mult 0.4 (kaum noch bluffen)

# Sample-Gates der OppModel-Methoden (sixmax.py:219-226): darunter liefern sie None.
MIN_FACED_BET = 8
MIN_TB_OPP = 6
MIN_AGG_OPP = 8


def _markup(text: str) -> str:
    """Glossar-Verlinkung (P1-A, paralleler Builder) — bewacht: ohne glossar_de bleibt Klartext."""
    try:
        from pokerbot.coach import glossar_de
        return glossar_de.markup(text)
    except Exception:  # noqa: BLE001 — Modul darf fehlen/abweichen, das Panel traegt trotzdem
        return text


def _pct(rate: float) -> int:
    return int(round(rate * 100))


def _stat(model, method: str):
    """None-sicherer Zugriff auf die gegateten OppModel-Raten (fold_to_bet/threebet/aggression)."""
    fn = getattr(model, method, None)
    try:
        return fn() if callable(fn) else None
    except Exception:  # noqa: BLE001 — kaputtes Fixture darf das Panel nicht reissen
        return None


def _observation(model) -> tuple[str, str] | None:
    """(trigger_key, deutscher Satz) fuer den staerksten aktiven _read-Trigger, sonst None.
    Prioritaet wie die Spielwirkung: Overfold/Station (Bluff-Dial) > Aggro (Call-Dial) > 3bet."""
    f = _stat(model, "fold_to_bet")
    if f is not None and f > READ_OVERFOLD:
        return ("overfold", f"du foldest oft auf Bets ({_pct(f)} % bei n={model.faced_bet}) "
                            "— er blufft dich oefter.")
    if f is not None and f < READ_STATION:
        return ("station", f"du foldest fast nie auf Bets ({_pct(f)} % bei n={model.faced_bet}) "
                           "— er blufft dich kaum noch und bettet nur Value.")
    ag = _stat(model, "aggression")
    if ag is not None and ag > READ_AGGRO_HI:
        return ("aggro_bluffcatch", f"du bettest und raist sehr oft ({_pct(ag)} % bei "
                                    f"n={model.agg_opp}) — er callt dich breiter runter.")
    if ag is not None and ag < READ_AGGRO_LO:
        return ("passive_valueonly", f"du bettest fast nur mit starken Haenden ({_pct(ag)} % bei "
                                     f"n={model.agg_opp}) — er glaubt deinen Bets und foldet mehr.")
    tb = _stat(model, "threebet")
    if tb is not None and tb > READ_THREEBET_HAPPY:
        return ("threebet_happy", f"du 3-bettest auffaellig oft ({_pct(tb)} % bei n={model.tb_opp}) "
                                  "— er spielt gegen deine 3-Bets breiter weiter.")
    return None


def _progress(model) -> str:
    """Ehrlicher Leerstand: die Sample-Gates als n/min-Fortschritt (Recon-Gotcha: None != 0)."""
    faced = getattr(model, "faced_bet", 0)
    return f"noch nicht genug Daten (Bets gegen dich: {min(faced, MIN_FACED_BET)}/{MIN_FACED_BET})."


def was_bot_gelernt(bots: dict) -> list[dict]:
    """[{seat, name, beobachtung_de}] — was die Liga-Bots ueber den Menschen (Sitz 0) gelernt haben.

    `bots` = die six_server-Session-Belegung {seat: SixMaxBot}. Jeder Bot lernt nur aus
    oeffentlichen Aktionen (INTEGRITY-Doktrin), also konvergieren die Reads — pro Trigger-Art
    wird EIN Sitz gezeigt (Dedupe), maximal 4 Beobachtungen, mit Leerstand auf mindestens 2
    aufgefuellt, sofern ueberhaupt Bots am Tisch sitzen."""
    entries: list[dict] = []
    seen_triggers: set[str] = set()
    fallback: list[dict] = []
    for seat in sorted(bots):
        bot = bots[seat]
        name = getattr(getattr(bot, "k", None), "name", None) or getattr(bot, "name", "bot")
        model = getattr(bot, "opp", {}).get(HUMAN_SEAT) if hasattr(bot, "opp") else None
        if model is None:
            continue
        obs = _observation(model)
        if obs is None:
            fallback.append({"seat": seat, "name": name,
                             "beobachtung_de": _markup(f"Sitz {seat} ({name}): {_progress(model)}")})
            continue
        trigger, satz = obs
        if trigger in seen_triggers:        # konvergente Beobachtung: einmal zeigen reicht
            continue
        seen_triggers.add(trigger)
        entries.append({"seat": seat, "name": name,
                        "beobachtung_de": _markup(f"Sitz {seat} ({name}) hat bemerkt: {satz}")})
    while len(entries) < MIN_OBSERVATIONS and fallback:
        entries.append(fallback.pop(0))
    return entries[:MAX_OBSERVATIONS]


# ---------------------------------------------------------------- Selbsttest (synthetisch)
def _selftest():
    from pokerbot.arena.sixmax import Knobs, OppModel   # das ECHTE Modell — Attribute verifiziert

    class _FakeBot:
        def __init__(self, profile: str, model: OppModel):
            self.k = Knobs(profile)
            self.opp = {HUMAN_SEAT: model}

    # 1) Over-Threshold-Trigger: fold_to_bet 9/12 = 0.75 > 0.55 -> Overfold-Beobachtung
    bots = {1: _FakeBot("tag", OppModel(hands=20, faced_bet=12, fold_bet=9)),
            2: _FakeBot("lag", OppModel(hands=20, faced_bet=12, fold_bet=9)),      # konvergent
            3: _FakeBot("nit", OppModel(hands=20, agg=8, agg_opp=10)),             # aggro 0.8
            4: _FakeBot("station", OppModel(hands=20, tb=2, tb_opp=8)),            # 3bet 0.25
            5: _FakeBot("maniac", OppModel(hands=2, faced_bet=3))}                 # unter Gate
    out = was_bot_gelernt(bots)
    assert 2 <= len(out) <= MAX_OBSERVATIONS, out
    for e in out:
        assert set(e) == {"seat", "name", "beobachtung_de"} and e["beobachtung_de"], e
    texts = [e["beobachtung_de"] for e in out]
    assert any("foldest oft" in t and "75" in t and "n=12" in t for t in texts), texts
    assert any("raist sehr oft" in t and "80" in t for t in texts), texts
    assert any("3-bettest" in t and "25" in t for t in texts), texts
    # Konvergenz-Dedupe: der Overfold-Read erscheint genau EINMAL (Sitz 1, nicht auch Sitz 2)
    assert sum("foldest oft" in t for t in texts) == 1
    assert out[0]["seat"] == 1 and out[0]["name"] == "tag"

    # 2) Unter dem Sample-Gate: kein falscher Trigger, ehrlicher n/min-Leerstand
    gated = was_bot_gelernt({1: _FakeBot("tag", OppModel(hands=3, faced_bet=3, fold_bet=3)),
                             2: _FakeBot("lag", OppModel(hands=3))})
    assert len(gated) == 2 and all("noch nicht genug Daten" in e["beobachtung_de"] for e in gated)
    assert any("3/8" in e["beobachtung_de"] for e in gated), gated

    # 3) Station-Read (fold_to_bet 2/12 < 0.30) + Passiv-Read (aggression 1/10 < 0.30)
    low = was_bot_gelernt({1: _FakeBot("tag", OppModel(hands=20, faced_bet=12, fold_bet=2)),
                           2: _FakeBot("lag", OppModel(hands=20, agg=1, agg_opp=10))})
    lt = [e["beobachtung_de"] for e in low]
    assert any("blufft dich kaum" in t and "17" in t for t in lt), lt
    assert any("starken Haenden" in t and "10" in t for t in lt), lt

    # 4) Determinismus + leere Tische
    assert was_bot_gelernt(bots) == out
    assert was_bot_gelernt({}) == []

    # 5) Drift-Wache: solange die Schwellen hier gespiegelte Literale sind, muessen sie
    #    woertlich in _read stehen (nach dem READ_*-Hoist entfaellt der Check — Import deckt ab)
    if _MIRRORED_THRESHOLDS:
        import inspect
        from pokerbot.arena import sixmax
        src = inspect.getsource(sixmax.SixMaxBot._read)
        for literal in ("0.11", "0.55", "0.30"):
            assert literal in src, f"Schwelle {literal} nicht mehr in _read — Panel driftet!"

    print("OK - Panel rendert 2-4 deutsche Beobachtungen aus echten OppModel-Zaehlern, "
          "Trigger spiegeln _read, Sample-Gates rendern ehrlichen Leerstand.")


if __name__ == "__main__":
    _selftest()
