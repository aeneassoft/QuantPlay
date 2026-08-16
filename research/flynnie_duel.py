"""FLYNNIE-DUELL — Prince gegen die beiden konkurrierenden Gegner-Bilder.

Aus dem Abend gibt es ZWEI unvereinbare Beschreibungen des Ranglisten-Besten:

  A) "MINED"     — das Frequenzprofil aus den online gefundenen Handhistorien
                   (VPIP 58 / PFR 28 / AF 3.3, Showdown-Median 0.58) = loose-aggressiv.
  B) "SURVIVOR"  — die Beobachtung am Tisch ("spielt nicht auf Platz eins, sondern um
                   lange drin zu bleiben; hatte nicht geblufft") = eng, passiv, callt aus
                   Neugier.

Beide werden gegen denselben Prince gespielt, GEPAART (jedes Deck zweimal, Sitze
getauscht) — so faellt das Kartenglueck heraus und der Unterschied ist der Gegner.
Weil offen ist, welches Bild stimmt, ist das Ergebnis zweigeteilt: die Antwort auf
"wie schlage ich ihn" haengt davon ab, WER er ist.

  python -m research.flynnie_duel --hands 3000
"""
from __future__ import annotations

import argparse
import random
import statistics
from collections import Counter

from pokerbot.arena.sixmax import PROFILES, Knobs, SixMaxBot
from pokerbot.engine.cards import hand_class
from pokerbot.engine.evaluator import made_class
from pokerbot.engine.table import Table
from pokerbot.strategy import preflop_strength as ps

BB = 100
START_BB = 100                    # Cash-Tiefe; das Live-Bild war tief, s. Auswertung unten
HANDS_DEFAULT = 3000

# Gemessene Zielwerte aus den 165 6-max-Cash-Haenden der Handhistorien.
TARGET = {"vpip": 0.582, "pfr": 0.279, "af": 3.27}


def _hc(hole):
    return hand_class(hole[0], hole[1]) if len(hole) == 2 else "72o"


def _tier(obs) -> str:
    """Blatt-Klasse; faellt vor dem Flop auf die Preflop-Staerke zurueck."""
    hole = [c for c in (obs.get("hole") or []) if c]
    board = list(obs.get("board") or [])
    if len(board) < 3 or len(hole) != 2:
        return "preflop"
    try:
        return made_class(board, hole)
    except Exception:                                   # noqa: BLE001
        return "air"


class FrequencyAgent:
    """Ein Gegner, der auf BEOBACHTETE Frequenzen gestellt wird statt auf Spielstaerke.

    Unsere Profil-Bibliothek (nit..maniac) deckt den gemessenen Spieler nicht ab — sie
    endet bei VPIP ~35 % / AF ~1.7 am 6-max-Tisch, er liegt bei 58 % / 3.3. Darum hier
    ein direkt frequenz-gestellter Agent: die Schwellen sind Knoepfe, die
    `measure_6max` gegen die Zielwerte kalibriert.
    """

    def __init__(self, k: dict, rng: random.Random):
        self.k, self.rng = k, rng
        self.seat = 0
        self.barrels = 0

    def new_hand(self, seats):
        self.barrels = 0

    def observe(self, *a, **kw):
        pass

    def decide(self, obs):
        return (self._preflop if obs.get("street") == "preflop" else self._postflop)(obs)

    # ---- preflop ----------------------------------------------------------------
    def _preflop(self, obs):
        k, r = self.k, self.rng
        hole = [c for c in (obs.get("hole") or []) if c]
        s = ps.strength(_hc(hole)) if len(hole) == 2 else 0.30
        if obs.get("preflop_raises", 0) == 0:
            if s >= k["open"] and obs.get("can_raise"):
                bb = obs.get("bb") or BB
                return {"action": "raise",
                        "amount": min(obs.get("raise_max") or 3 * bb, int(k["open_bb"] * bb))}
            if s >= k["enter"] and obs.get("can_call"):
                return {"action": "call", "amount": None}
            return {"action": "check" if obs.get("can_check") else "fold", "amount": None}
        if s >= k["threebet"] and obs.get("can_raise"):
            return {"action": "raise", "amount": obs.get("raise_min")}
        price = obs.get("to_call", 0) / max(1, obs.get("pot") or 1)
        if s >= k["defend"] and price <= k["price_cap"] and obs.get("can_call"):
            return {"action": "call", "amount": None}
        return {"action": "check" if obs.get("can_check") else "fold", "amount": None}

    # ---- postflop ---------------------------------------------------------------
    def _postflop(self, obs):
        k, r = self.k, self.rng
        tier = _tier(obs)
        strong = tier in ("two-pair+", "monster")
        medium = tier in ("pair", "top-pair")
        pot = max(1, obs.get("pot") or 1)
        if obs.get("to_call", 0) == 0:
            p = k["bet_strong"] if strong else k["bet_medium"] if medium else k["bet_air"]
            if r.random() < p and obs.get("can_raise"):
                self.barrels += 1
                return {"action": "raise",
                        "amount": min(obs.get("raise_max") or pot, int(k["bet_frac"] * pot))}
            return {"action": "check", "amount": None}
        price = obs.get("to_call", 0) / pot
        if strong and obs.get("can_raise") and r.random() < k["raise_strong"]:
            return {"action": "raise", "amount": obs.get("raise_min")}
        thr = k["call_strong"] if strong else k["call_medium"] if medium else k["call_air"]
        if price <= thr and obs.get("can_call"):
            return {"action": "call", "amount": None}
        return {"action": "fold", "amount": None}


# --- Die beiden Gegner-Bilder --------------------------------------------------------
# Die Schwellen sind QUANTILE der combo-gewichteten Preflop-Staerke, per Gittersuche
# gegen die drei Zielwerte gestellt. MINED trifft sie praktisch exakt:
#   VPIP 58.0 % (Ziel 58.2) · PFR 29.3 % (Ziel 27.9) · AF 3.28 (Ziel 3.27).
# MINED: das Frequenzprofil der gefundenen Handhistorien — breit drin, oft aggressiv,
# mehrfach gefeuert (die gezeigten 52s/Q3s/J4s sind Drei-Strassen-Bluffs).
MINED = {"open": 0.470, "open_bb": 2.8, "enter": 0.430, "threebet": 0.660, "defend": 0.400,
         "price_cap": 0.55, "bet_strong": 0.86, "bet_medium": 0.62, "bet_air": 0.24,
         "bet_frac": 0.66, "raise_strong": 0.45,
         "call_strong": 3.0, "call_medium": 0.70, "call_air": 0.20}
# SURVIVOR: die Tischbeobachtung — eng eroeffnend, praktisch bluff-frei, aber callt
# breit bis zum Showdown ("wollte die Karten sehen"). Gemessen 33/15 bei AF 0.98.
SURVIVOR = {"open": 0.545, "open_bb": 2.5, "enter": 0.500, "threebet": 0.800, "defend": 0.520,
            "price_cap": 0.50, "bet_strong": 0.80, "bet_medium": 0.34, "bet_air": 0.05,
            "bet_frac": 0.55, "raise_strong": 0.35,
            "call_strong": 3.0, "call_medium": 0.90, "call_air": 0.34}

OPPONENTS = {"mined": MINED, "survivor": SURVIVOR}
LEAGUE = {"lag": PROFILES["lag"], "station": PROFILES["station"], "nit": PROFILES["nit"]}


def _agent(spec, seat: int, seed: int):
    """Baut den passenden Agenten — Knobs -> unser Kern, dict -> Frequenz-Agent."""
    if isinstance(spec, dict):
        a = FrequencyAgent(spec, random.Random(seed))
        a.seat = seat
        return a
    b = SixMaxBot(seat, spec)
    b._read = lambda obs: {}          # kein Gegner-Modell: wir messen den STIL, nicht die Anpassung
    b.rng = random.Random(seed)
    return b


class Stats:
    """Zaehlt genau die Kennzahlen, die wir aus den Handhistorien haben — damit der
    simulierte Gegner an derselben Elle gemessen wird wie der echte."""

    __slots__ = ("hands", "vpip", "pfr", "bets", "raises", "calls")

    def __init__(self):
        self.hands = self.vpip = self.pfr = self.bets = self.raises = self.calls = 0

    def note(self, street: str, action: str, first_pre: bool):
        if street == "preflop":
            if action in ("call", "raise") and first_pre:
                self.vpip += 1
            if action == "raise" and first_pre:
                self.pfr += 1
        else:
            if action == "bet":
                self.bets += 1
            elif action == "raise":
                self.raises += 1
            elif action == "call":
                self.calls += 1

    def as_dict(self) -> dict:
        n = max(1, self.hands)
        return {"n": self.hands, "vpip": self.vpip / n, "pfr": self.pfr / n,
                "af": (self.bets + self.raises) / max(1, self.calls)}


def play_hand(names: list[str], agents: dict, seed: int, stats: dict) -> dict[str, float]:
    """Spielt EINE Hand und gibt die Netto-Veraenderung je Name in Chips zurueck."""
    t = Table(names, starting_stack=START_BB * BB, sb=BB // 2, bb=BB, seed=seed, rebuy=False)
    t.start_hand()
    start = {s.name: s.stack + s.committed_total for s in t.seats}
    for nm, a in agents.items():
        a.seat = names.index(nm)
        a.new_hand(list(range(len(names))))
    seen_pre = {nm: False for nm in names}
    for st in stats.values():
        st.hands += 1
    guard = 0
    while not t.hand_over and t.to_act is not None and guard < 300:
        guard += 1
        seat = t.to_act
        nm = t.seats[seat].name
        obs = t.obs_for(seat)
        street = t.street
        try:
            d = agents[nm].decide(obs)
            action, amount = (d["action"], d.get("amount")) if isinstance(d, dict) else d
            t.act(action, amount)
        except Exception:                                   # noqa: BLE001
            la = t.legal_actions()
            action = "check" if "check" in la else "fold"
            amount = None
            t.act(action, amount)
        if nm in stats:
            stats[nm].note(street, action, not seen_pre[nm])
            if street == "preflop":
                seen_pre[nm] = True
    return {s.name: (s.stack - start[s.name]) / BB for s in t.seats}


def duel(opp_key: str, hands: int, prince: str = "tag", seed0: int = 20260808) -> dict:
    """Gepaartes Duell: jedes Deck zweimal, Prince einmal auf jedem Platz."""
    knobs = {**OPPONENTS, **LEAGUE}[opp_key]
    hero = PROFILES[prince]
    diffs, prince_bb, opp_stats = [], [], Stats()
    for i in range(hands // 2):
        seed = seed0 + i * 7919
        pair = []
        for swap in (0, 1):
            names = ["prince", "opp"] if swap == 0 else ["opp", "prince"]
            agents = {"prince": _agent(hero, names.index("prince"), seed * 3 + 1),
                      "opp": _agent(knobs, names.index("opp"), seed * 5 + 2)}
            res = play_hand(names, agents, seed, {"opp": opp_stats})
            pair.append(res["prince"])
        # gepaarte Differenz: dasselbe Deck, beide Sitzhaelften -> Kartenglueck kuerzt sich
        diffs.append(sum(pair))
        prince_bb.extend(pair)
    n = len(prince_bb)
    mean = sum(prince_bb) / n * 100
    # SE aus den GEPAARTEN Summen (die unabhaengige Einheit), auf bb/100 je Hand skaliert
    sd = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
    se = sd / (len(diffs) ** 0.5) / 2 * 100
    return {"gegner": opp_key, "haende": n, "bb100": mean, "se": se,
            "gegner_stil": opp_stats.as_dict()}


def measure_6max(knobs, hands: int, seed0: int = 4242) -> dict:
    """Misst VPIP/PFR/AF eines Knopf-Satzes AM 6-MAX-TISCH — dieselbe Elle wie die
    Zielwerte, die aus 165 6-max-Cash-Haenden stammen. Heads-up spielt jedes Profil
    deutlich breiter; dort zu kalibrieren waere ein Massstabsfehler."""
    st = Stats()
    names = ["opp"] + [f"f{i}" for i in range(5)]
    for i in range(hands):
        seed = seed0 + i * 6151
        rot = names[i % 6:] + names[:i % 6]          # Position rotiert wie am echten Tisch
        agents = {nm: _agent(knobs if nm == "opp" else PROFILES["tag"],
                             rot.index(nm), seed * 7 + rot.index(nm)) for nm in rot}
        play_hand(rot, agents, seed, {"opp": st})
    return st.as_dict()


def calibrate(hands: int = 1500) -> None:
    """Zeigt, wie nah jedes Knopf-Set an den GEMESSENEN Frequenzen liegt."""
    print(f"KALIBRIERUNG am 6-max-Tisch — Ziel aus den Handhistorien: "
          f"VPIP {TARGET['vpip']:.1%} / PFR {TARGET['pfr']:.1%} / AF {TARGET['af']:.2f}\n")
    print(f"{'Profil':<10} {'VPIP':>7} {'PFR':>7} {'AF':>6}   Abweichung")
    for key, spec in {**OPPONENTS, **LEAGUE}.items():
        d = measure_6max(spec, hands)
        err = (abs(d["vpip"] - TARGET["vpip"]) + abs(d["pfr"] - TARGET["pfr"])
               + abs(d["af"] - TARGET["af"]) / 10)
        print(f"{key:<10} {d['vpip']:>6.1%} {d['pfr']:>6.1%} {d['af']:>6.2f}   {err:.3f}")


# Kandidaten fuer die Gegen-Einstellung. Die Frage ist nicht "welcher Bot ist besser",
# sondern welche STIL-DREHUNG gegen genau diesen Gegner am meisten erntet.
PRINCE_ARMS = ["tag", "nit", "lag", "station"]


def counter_matrix(hands: int) -> None:
    """Welche Prince-Einstellung erntet gegen welches Gegner-Bild am meisten?"""
    print(f"GEGEN-MATRIX — Prince-Einstellung x Gegner-Bild, {hands} Haende je Zelle, "
          f"gepaart\n")
    print(f"{'Prince':<10}" + "".join(f"{k:>20}" for k in OPPONENTS))
    best = {k: (None, -1e9) for k in OPPONENTS}
    for arm in PRINCE_ARMS:
        cells = []
        for opp in OPPONENTS:
            r = duel(opp, hands, prince=arm)
            cells.append(f"{r['bb100']:>+13.1f} ±{r['se']:<5.1f}")
            if r["bb100"] > best[opp][1]:
                best[opp] = (arm, r["bb100"])
        print(f"{arm:<10}" + "".join(cells))
    print()
    for opp, (arm, v) in best.items():
        print(f"  bestes Gegenmittel gegen '{opp}': {arm}  ({v:+.1f} bb/100)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=HANDS_DEFAULT)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--counter", action="store_true",
                    help="Matrix: welche Prince-Einstellung erntet gegen welches Gegner-Bild")
    ap.add_argument("--opps", default="mined,survivor,lag,station,nit")
    a = ap.parse_args()
    if a.calibrate:
        calibrate()
        return
    if a.counter:
        counter_matrix(a.hands)
        return
    print(f"GEPAARTES DUELL — Prince (Turnier-Kern 'tag') vs. Gegner-Bilder, "
          f"{a.hands} Haende je Arm, {START_BB} bb tief\n")
    print(f"{'Gegner':<10} {'Haende':>7} {'Prince bb/100':>15} {'±SE':>7}   "
          f"{'VPIP':>6} {'PFR':>6} {'AF':>5}")
    for key in a.opps.split(","):
        r = duel(key.strip(), a.hands)
        g = r["gegner_stil"]
        print(f"{r['gegner']:<10} {r['haende']:>7} {r['bb100']:>+15.1f} {r['se']:>7.1f}   "
              f"{g['vpip']:>5.1%} {g['pfr']:>5.1%} {g['af']:>5.2f}")


if __name__ == "__main__":
    main()
