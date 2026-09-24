"""Kaggle Game Arena "Heads Up Poker" — die LOKALE Bruecke (2026-09-10).

WARUM: das Leaderboard https://www.kaggle.com/benchmarks/kaggle/poker-heads-up misst **Mean BB/100**
in einem All-play-all von Frontier-LLMs (Stand v1: Spitze +34,9, Schluss -49,3). Die Umgebung ist
OPEN SOURCE und laeuft hier auf dem PC — anders als GTOW kostet eine Hand also weder Zeitfenster noch
Hand-Budget. Das macht sie zum billigen Volumen-Kanal; ein GTO-Anker ist sie NICHT (das Feld sind LLMs,
kein Re-Solver — siehe docs/reports/KAGGLE_ARENA.md).

Spielkonfiguration EXAKT wie Kaggle (Default aus kaggle_environments/envs/open_spiel_env):
    python_repeated_pokerkit(max_num_hands=100, reset_stacks=True, rotate_dealer=True,
        pokerkit_game_params=python_pokerkit_wrapper(blinds=1 2, num_players=2,
                                                     stack_sizes=200 200, variant=NoLimitTexasHoldem))
= HUNL, Blinds 1/2, Stacks 200 Einheiten = **100 bb**, Stacks je Hand zurueckgesetzt, Dealer rotiert.
100 bb ist exakt unsere Hausgroesse — der Champion spielt hier ohne Umrechnung seiner Tiefe.

EINHEITEN: Kaggle rechnet in Einheiten (BB = 2), unsere Engine in Chips (BB = 100) -> Faktor 50.

MESSUNG (Doktrin): gepaarte Decks — jedes Deck wird ZWEIMAL gespielt, mit getauschten Sitzen; die Summe
beider Haelften loescht das Kartenglueck. A/A (derselbe Agent auf beiden Seiten) muss EXAKT 0 ergeben.

Run:
    python -m pokerbot.benchmark.kaggle_arena --aa --decks 100          # Nulltest
    python -m pokerbot.benchmark.kaggle_arena --gegner basis --decks 500
"""
from __future__ import annotations

import argparse
import random
import re
import time

CHIPS_JE_EINHEIT = 50          # Kaggle-BB 2 Einheiten == unsere 100 Chips
# Basisrate planfaehiger River-Wurzeln (gpt-5.6-sol nannte sie als die #1 fehlende Zahl): wie oft steht
# ueberhaupt eine River-Entscheidung mit Pot >= 15 bb an? Unabhaengig von v10 gezaehlt, rein aus dem Spiel.
PLAN_POT_CHIPS = 1500
_ZAEHLER = {"entscheidungen": 0, "river": 0, "river_planfaehig": 0, "haende": 0}
# v10-Instrumentierung: NUR Zaehler, keine Strategie-Aenderung. Der River-Plan meldet sonst nirgends nach
# aussen, ob er gespielt hat — ohne das ist ein v10-Lauf nicht interpretierbar (gemessen 2026-09-10: ohne
# deal-Marke im Adapter spielte er 0-mal und der Lauf sah wie "identisch zum Champion" aus).
_PLAN = {"aktivierungen": 0, "gespielt": 0, "fallback": {}}


def instrumentiere_plan() -> None:
    """Haengt Zaehler an river_plan (idempotent). Aendert keine Entscheidung."""
    from pokerbot.autogym import river_plan as rp
    if getattr(rp, "_kaggle_instrumentiert", False):
        return
    orig_akt, orig_fb = rp.ist_aktiviert, rp.RiverPlanFabrik._fallback

    def akt(st, min_pot_chips=rp.DEFAULT_MIN_POT_CHIPS):
        aktiv, pot = orig_akt(st, min_pot_chips)
        _PLAN["aktivierungen"] += int(aktiv)
        return aktiv, pot

    def fb(self, z, st, status, *a, **kw):
        _PLAN["fallback"][status] = _PLAN["fallback"].get(status, 0) + 1
        return orig_fb(self, z, st, status, *a, **kw)

    rp.ist_aktiviert, rp.RiverPlanFabrik._fallback = akt, fb
    rp._kaggle_instrumentiert = True
BB_CHIPS = 100
STRASSEN = ("preflop", "flop", "turn", "river")

# Der Default-Spielstring der Kaggle-Umgebung (nicht abgeschrieben: importiert, siehe spiel()).
_SPIEL: dict = {}


def spiel(stack_einheiten: int = 200):
    """Laedt (einmalig) das Kaggle-Poker-Spiel in der gewuenschten Stacktiefe.
    stack_einheiten=200 -> 100 bb (Kaggles eigene Konfiguration);
    stack_einheiten=400 -> 200 bb (die Tiefe des GTOW-Wettbewerbs, siehe docs/reports/KAGGLE_ARENA.md). Der String kommt aus kaggle_environments selbst,
    damit eine Aenderung dort hier auffaellt statt still zu divergieren."""
    global _SPIEL
    if stack_einheiten not in _SPIEL:
        import pyspiel
        from kaggle_environments.envs.open_spiel_env.open_spiel_env import (
            DEFAULT_REPEATED_POKERKIT_GAME_STRING as S,
        )
        from kaggle_environments.envs.open_spiel_env.open_spiel_env import (
            _ensure_python_game_registered as reg,
        )
        # EIN-HAND-Variante: der repeated-Wrapper spielt 100 Haende am Stueck und laesst uns die
        # Deck-Paarung nicht steuern. Da reset_stacks=True gilt, ist eine Einzelhand oekonomisch
        # identisch — und nur so bekommen wir den gepaarten Kanal (Mess-Doktrin).
        innen = re.search(r"pokerkit_game_params=([^)]*\))", S).group(1)
        if stack_einheiten != 200:
            innen = innen.replace("stack_sizes=200 200", f"stack_sizes={stack_einheiten} {stack_einheiten}")
        reg(S)
        _SPIEL[stack_einheiten] = pyspiel.load_game(innen)
    return _SPIEL[stack_einheiten]


# ----------------------------------------------------------------- Beobachtung -> unser Zustand
_FELD = re.compile(r"\|\|([^:]+): (.*)")
_KARTE = re.compile("([2-9TJQKA][shdc])")


def parse_beobachtung(obs: str) -> dict:
    """Die observation_string des pokerkit-Wrappers in ein dict. Beispielzeilen:
    ||Current Street: 0 | ||Bets: [2, 1] | ||Board Cards: [] |
    ||Player's Private Hole Cards: [Jd, 3c] | ||Per-player Current Stacks: [198, 199]"""
    d = {}
    for schluessel, wert in _FELD.findall(obs):
        d[schluessel.strip()] = wert.strip()

    def zahlen(name):
        roh = d.get(name, "").strip().strip("()[]")
        return [int(t) for t in roh.replace("(", " ").replace(")", " ").split(",") if t.strip().lstrip("-").isdigit()]

    def karten(name):
        # WHY Regex statt split: der Wrapper klammert je Strasse ("[[8d], [Qs], [Td]]") — ein
        # naiver Split lieferte Tokens wie "8d]" und liess treys mit KeyError '[' abstuerzen.
        return _KARTE.findall(d.get(name, ""))

    stacks = zahlen("Per-player Current Stacks")
    start = zahlen("Per-player Starting Stacks")
    return {
        "strasse": int(d.get("Current Street", "0")),
        "bets": zahlen("Bets"),
        "stacks": stacks,
        "start": start,
        "board": karten("Board Cards"),
        "hole": karten("Player's Private Hole Cards"),
        # Pot AUS DEN STACKS: alles, was nicht mehr hinter den Spielern liegt, steht in der Mitte
        # (die "Pot(s)"-Zeile druckt Objekte, keine Zahlen — nicht robust parsebar).
        "pot_gesamt": sum(start) - sum(stacks),
    }


def zustand(state, spieler: int, historie: list, hand_id) -> dict:
    """OpenSpiel-Zustand -> unser Engine-Zustand (Held IMMER Index 0, wie im GTOW-Adapter).
    Alle Betraege in Chips; der Held ist `spieler`, der Gegner 1-spieler."""
    b = parse_beobachtung(state.observation_string(spieler))
    geg = 1 - spieler
    c_h, c_v = b["bets"][spieler], b["bets"][geg]                 # Einsatz DIESER Strasse
    stack_h, stack_v = b["stacks"][spieler], b["stacks"][geg]
    pot = b["pot_gesamt"]                                          # enthaelt die laufenden Einsaetze bereits
    to_call = max(0, c_v - c_h)
    # Button = wer preflop den kleinen Blind zahlt; im HU ist das der Button (SB=1, BB=2).
    # Nach dem Preflop steht das nicht mehr in den Bets -> aus der Historie gemerkt.
    button = historie[0]["button"] if historie else (0 if c_h < c_v else 1)
    legale = state.legal_actions(spieler)
    kann_erhoehen = any(a > 1 for a in legale)
    return {
        "street": STRASSEN[min(b["strasse"], 3)],
        "board": b["board"],
        "pot": pot * CHIPS_JE_EINHEIT,
        "bb": BB_CHIPS,
        "current_bet": max(c_h, c_v) * CHIPS_JE_EINHEIT if to_call > 0 else 0,
        "button": 0 if button == spieler else 1,
        "hand_id": hand_id,
        "hand_no": 0,
        "history": [h for h in historie if "button" not in h],
        "to_act": 0,
        "hand_over": False,
        "players": [
            {"idx": 0, "hole": b["hole"], "stack": stack_h * CHIPS_JE_EINHEIT,
             "committed_street": c_h * CHIPS_JE_EINHEIT,
             "committed_total": (b["start"][spieler] - stack_h) * CHIPS_JE_EINHEIT,
             "folded": False, "all_in": stack_h == 0, "is_button": button == spieler},
            {"idx": 1, "hole": ["??", "??"], "stack": stack_v * CHIPS_JE_EINHEIT,
             "committed_street": c_v * CHIPS_JE_EINHEIT,
             "committed_total": (b["start"][geg] - stack_v) * CHIPS_JE_EINHEIT,
             "folded": False, "all_in": stack_v == 0, "is_button": button == geg},
        ],
        "legal": {
            "to_act": 0, "to_call": to_call * CHIPS_JE_EINHEIT, "pot": pot * CHIPS_JE_EINHEIT,
            "can_fold": 0 in legale, "can_check": to_call == 0 and 1 in legale,
            "can_call": to_call > 0 and 1 in legale, "call_amount": to_call * CHIPS_JE_EINHEIT,
            "can_raise": kann_erhoehen, "is_bet": to_call == 0,
            "raise_min": (min(a for a in legale if a > 1) * CHIPS_JE_EINHEIT) if kann_erhoehen else None,
            "raise_max": (max(legale) * CHIPS_JE_EINHEIT) if kann_erhoehen else None,
        },
    }


def spiel_aktion(entscheidung: dict, state, spieler: int) -> int:
    """Unser {action, amount} -> OpenSpiel-Aktion. amount ist ein commit-TO in Chips.
    LEGALITAETS-GARANTIE: was nicht angeboten wird, faellt auf check/call/fold zurueck (nie illegal)."""
    legale = set(state.legal_actions(spieler))
    akt, betrag = entscheidung.get("action"), entscheidung.get("amount")
    if akt == "fold":
        return 0 if 0 in legale else 1
    if akt in ("check", "call"):
        return 1 if 1 in legale else (0 if 0 in legale else max(legale))
    erhoehungen = [a for a in legale if a > 1]
    if not erhoehungen:                                  # kein Raise moeglich -> naechstbeste Linie
        return 1 if 1 in legale else 0
    if akt == "allin" or betrag is None:
        return max(erhoehungen)
    ziel = int(round(betrag / CHIPS_JE_EINHEIT))
    return min(max(ziel, min(erhoehungen)), max(erhoehungen))


# ----------------------------------------------------------------- Agenten
class PrinceAgent:
    """Der Champion (Trainer-Konfig, docs/reports/TRAINER_WIRING.md): PRINCE-Profil, exploit AUS,
    Resolver AN, AUSLESE-Kette FINAL_STACK. `stack=None` = nackter Bot (Basis-Arm)."""

    def __init__(self, stack: str | None = "final", seed: int = 7, kanal: str = "gym"):
        import os

        os.environ.setdefault("POKERB_PRINCE", "1")
        from pokerbot.strategy.bot import PokerBot
        self.bot = PokerBot(0, seed=seed, exploit=False)
        self.bot.use_resolver = True
        self.bot.use_turn_resolver = True
        self.name = f"prince[{stack or 'basis'}]"
        if stack:
            from pokerbot.strategy.auslese import FINAL_STACK, wickle_decide
            self._decide = wickle_decide(self.bot, FINAL_STACK if stack == "final" else stack, kanal=kanal)
        else:
            self._decide = self.bot.decide

    def neue_hand(self):
        if hasattr(self.bot, "new_hand"):
            self.bot.new_hand([0, 1])

    def __call__(self, state, spieler, historie, hand_id):
        return spiel_aktion(self._decide(zustand(state, spieler, historie, hand_id)), state, spieler)


class BasisAgent(PrinceAgent):
    """Unser Bot OHNE die AUSLESE-Kette — der interne Referenz-Arm."""

    def __init__(self, seed: int = 7):
        super().__init__(stack=None, seed=seed)


class RufAgent:
    """Call-Station: checkt/callt immer. Nur Verdrahtungs-Smoke, nie ein Verdikt."""

    name = "station"

    def neue_hand(self):
        pass

    def __call__(self, state, spieler, historie, hand_id):
        legale = state.legal_actions(spieler)
        return 1 if 1 in legale else legale[0]


# ----------------------------------------------------------------- Spiel-Schleife
def spiele_hand(agenten, deck_seed: int, hand_id: str, stack_einheiten: int = 200) -> float:
    """EINE Hand. agenten[i] spielt Sitz i. -> Netto von Sitz 0 in Einheiten."""
    g = spiel(stack_einheiten)
    s = g.new_initial_state()
    rng = random.Random(deck_seed)
    historie: list = [{"button": 1}]            # HU: Sitz 1 zahlt den kleinen Blind? -> unten korrigiert
    button_gesetzt = False
    letzte_strasse = "preflop"
    _ZAEHLER["haende"] += 1
    for a in agenten:
        a.neue_hand()
    while not s.is_terminal():
        if s.is_chance_node():
            aus = s.chance_outcomes()
            r, kum = rng.random(), 0.0
            for aktion, p in aus:
                kum += p
                if r <= kum:
                    s.apply_action(aktion)
                    break
            else:
                s.apply_action(aus[-1][0])
            continue
        p = s.current_player()
        _b = parse_beobachtung(s.observation_string(p))
        _ZAEHLER["entscheidungen"] += 1
        if _b["strasse"] >= 3:
            _ZAEHLER["river"] += 1
            # Planfaehig = Pot am RIVER-BEGINN (river_plan.pot_river_aus_state: Pot minus laufende
            # Strasseneinsaetze). Die erste Fassung zaehlte den Pot INKLUSIVE Einsatz und ueberschaetzte
            # die Basisrate deutlich (84 statt des korrekten Werts je 100 Haende).
            pot_river = (_b["pot_gesamt"] - sum(_b["bets"])) * CHIPS_JE_EINHEIT
            if pot_river >= PLAN_POT_CHIPS:
                _ZAEHLER["river_planfaehig"] += 1
        if not button_gesetzt:                  # Button = kleiner Blind = kleinerer Preflop-Einsatz
            b = parse_beobachtung(s.observation_string(p))
            historie[0]["button"] = 0 if b["bets"][0] < b["bets"][1] else 1
            button_gesetzt = True
        vor = parse_beobachtung(s.observation_string(p))
        strasse = STRASSEN[min(vor["strasse"], 3)]
        if strasse != letzte_strasse:
            # DEAL-MARKE wie im GTOW-Adapter (_parse_history): river_plan.state_am_river_beginn schneidet
            # die Historie daran. Ohne sie meldete v10 'fehler:root_nicht_rekonstruierbar' und spielte NIE
            # (gemessen 2026-09-10: 30 Haende, 1 Aktivierung, 0 Plaene).
            historie.append({"action": "deal", "street": strasse})
            letzte_strasse = strasse
        aktion = agenten[p](s, p, historie, hand_id)
        if aktion == 0:
            name = "fold"
        elif aktion == 1:
            name = "check" if vor["bets"][p] == vor["bets"][1 - p] else "call"
        else:
            name = "bet" if vor["bets"][1 - p] == 0 else "raise"
        historie.append({"player": p, "action": name, "street": strasse,
                         "amount": aktion * CHIPS_JE_EINHEIT if aktion > 1 else None})
        s.apply_action(aktion)
    return s.returns()[0]


def duell(a_fabrik, b_fabrik, decks: int, seed0: int = 90000, stack_einheiten: int = 200) -> dict:
    """Gepaarter Kanal: jedes Deck zweimal, Sitze getauscht. -> robust_stats ueber die Deck-Kanten."""
    from pokerbot.autogym import stats
    # FRISCHE Instanzen je Haelfte: unser Bot MISCHT (Seesaw-Doktrin) aus einem RNG-STROM, der mit der
    # Zahl/Reihenfolge der Entscheidungen fortschreitet. Ueber Haende hinweg wiederverwendet, laufen die
    # beiden Spiegelhaelften auseinander -> A/A war -37,5 statt 0 (gemessen 2026-09-10, 8 Decks). Mit je
    # frischen Instanzen ist jede Haelfte ein deterministischer Wiederholungslauf -> A/A EXAKT 0.
    kanten, t0 = [], time.perf_counter()
    instrumentiere_plan()
    for k in _ZAEHLER:
        _ZAEHLER[k] = 0
    _PLAN.update(aktivierungen=0, gespielt=0, fallback={})
    name_a, name_b = a_fabrik().name, b_fabrik().name
    for i in range(decks):
        ds = seed0 + i
        # hand_id IDENTISCH je Deck (nicht je Haelfte): sie keyt die private Randomisierung des
        # Bots — verschiedene IDs zerstoerten in v10 den A/A-Nulltest (-9,4 statt 0, docs/reports/V10_GATES_REPORT.md).
        hid = str(ds)
        hin = spiele_hand([a_fabrik(), b_fabrik()], ds, hid, stack_einheiten)      # A auf Sitz 0
        rueck = spiele_hand([b_fabrik(), a_fabrik()], ds, hid, stack_einheiten)    # A auf Sitz 1
        kanten.append((hin - rueck) * CHIPS_JE_EINHEIT)   # A-Netto beider Haelften, in Chips
        if (i + 1) % 50 == 0:
            m = sum(kanten) / len(kanten) / 2 / BB_CHIPS * 100
            print(f"  [{i+1}/{decks}] Zwischenstand {m:+.1f} bb/100 "
                  f"({(time.perf_counter()-t0)/(i+1):.2f} s/Deck)", flush=True)
    st = stats.robust_stats(kanten, bb=BB_CHIPS, haende_je_deck=2)
    st.update(stats.bootstrap_ci(kanten, bb=BB_CHIPS, haende_je_deck=2))
    z = dict(_ZAEHLER)
    _PLAN["gespielt"] = _PLAN["aktivierungen"] - sum(_PLAN["fallback"].values())
    st.update({"plan": dict(_PLAN)})
    st.update({"basisrate": {**z,
                             "planfaehig_je_100_haende": round(100 * z["river_planfaehig"] / max(1, z["haende"]), 1)}})
    st.update({"kandidat": name_a, "gegner": name_b, "n_decks": decks,
               "stack_bb": stack_einheiten / 2,
               "kanal": "kaggle_arena", "sekunden": round(time.perf_counter() - t0, 1)})
    st["verdict"] = stats.verdikt(st)
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decks", type=int, default=100)
    # --kandidat: Name einer AUSLESE-Kette aus pargate (z.B. r10_ernte = v9-River-Ernte);
    # "final" = der Champion (FINAL_STACK/r8_stack), "basis" = nackter Bot ohne Kette.
    ap.add_argument("--kandidat", default="final")
    ap.add_argument("--gegner", default="basis",
                    help="basis | station | prince | ein Kettenname (z.B. r8_stack)")
    ap.add_argument("--aa", action="store_true", help="A/A-Nulltest (muss EXAKT 0 sein)")
    ap.add_argument("--seed0", type=int, default=90000)
    # WHY: Kaggle spielt 100 bb, der GTOW-Wettbewerb 200 bb — und unser Preflop-Blueprint feuert erst ab
    # 140 bb effektiv (bot.py:200). Bei 100 bb misst man deshalb einen ANDEREN Bot (Heuristik-Kaskade
    # statt near-Nash-Blueprint). Befund von gpt-5.6-sol, am Code bestaetigt.
    ap.add_argument("--stack-bb", type=int, default=100, choices=(100, 200),
                    help="100 = Kaggles Konfiguration, 200 = Tiefe des GTOW-Wettbewerbs")
    args = ap.parse_args()

    def fabrik(name):
        if name == "station":
            return RufAgent
        if name == "basis":
            return BasisAgent
        return lambda: PrinceAgent(stack=("final" if name in ("final", "prince") else name))

    kandidat = fabrik(args.kandidat)
    gegner = kandidat if args.aa else fabrik(args.gegner)
    st = duell(kandidat, gegner, args.decks, args.seed0, stack_einheiten=args.stack_bb * 2)
    print(st)
    if args.aa and abs(st["bb100"]) > 1e-9:
        raise SystemExit(f"A/A NICHT null: {st['bb100']} bb/100 -> STOPP (Mess-Doktrin)")


if __name__ == "__main__":
    main()
