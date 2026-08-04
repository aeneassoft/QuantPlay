"""PS-$1050-DUELL — unsere Turnier-Arme gegen das phasenkalibrierte High-Stakes-Feld.

Feld = Frequenz-Agenten mit den GEMESSENEN Phasen-Frequenzen der echten $1050-6-max-Regs
(data/ps_tourney_field.json: deep VPIP32/FvR54 → short FvR62/Jam13% — deren ICM-Verhalten steckt
in den Zahlen, User-These). Struktur = die echte PS-Blind-Leiter aus den HHs, 50k-Start, Antes.

Drei Hero-Arme, gepaarte Seeds (identische Decks/Felder je Turnier):
  chipEV   = tag-Kern pur (kein icm-Key)
  icm      = tag-Kern + ICM-Brille (anteiliges Risiko-Premium + exakte All-in-Schwelle)
  icm+druck= dazu der Coverstack-Druckhebel (Doktrin 9) + Live-Reads AN (Exploit-Layer)

Zwei Payout-Regime: sng65_35 (Single-Table-Proxy) und winner_take_all (des Users 'Platz 1 ist
das Ziel' — unter WTA ist ICM=chipEV per Definition, dort zeigt der DRUCK-Arm den reinen
Exploit-Wert der gegnerischen ICM-Tightness).

  python -m research.ps_tourney_duel --tourneys 300 --payout sng
"""
from __future__ import annotations

import argparse
import json
import random

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy.tournament import BlindLevel, Director, Structure

FIELD = json.load(open("data/ps_tourney_field.json", encoding="utf-8"))["phasen"]

# Die echte PS-Leiter (aus den HHs; Ante ~= 0.13*bb wie beobachtet, 12 Haende je Level bei 6-max)
PS_LEVELS = tuple(BlindLevel(int(bb / 2), int(bb), int(round(bb * 0.13)), 12)
                  for bb in (250, 300, 350, 400, 500, 600, 700, 800, 1000, 1200, 1600, 2000, 2500))
PS6_SNG = Structure("ps6_sng", PS_LEVELS, (0.65, 0.35), start_stack=50_000, buyin=1050.0)
PS6_WTA = Structure("ps6_wta", PS_LEVELS, (1.0,), start_stack=50_000, buyin=1050.0)


_RANKS = "23456789TJQKA"


def _hand_class(hole: list[str]) -> str:
    """['9h','Th'] -> 'T9s'; Paare ohne Suffix — die Notation, die preflop_strength kennt.
    Erste Fassung sortierte lexikografisch ('9To') und gab Paaren ein Suffix: strength kannte die
    Klasse nicht, das Feld foldete fast alles (Smoke: Hero gewann 3/3 in jedem Arm)."""
    a, b = sorted((h[0] for h in hole), key=_RANKS.index, reverse=True)
    if a == b:
        return a + b
    return a + b + ("s" if hole[0][1] == hole[1][1] else "o")


def _phase(eff_bb: float) -> str:
    return "deep" if eff_bb >= 40 else ("mid" if eff_bb >= 15 else "short")


class PSFieldAgent:
    """Frequenz-Agent mit den gemessenen Phasen-Frequenzen des $1050-Pools.

    Preflop-Frequenzen exakt aus der Messung (open ~ PFR, defend = 1−FoldVsRaise, 3bet, Jam-Rate
    im Short-Regime); postflop bewusst schlicht (Fit-or-Fold auf Staerke) — dieselbe Modellklasse
    wie alle Oekologie-Felder, damit die Arm-VERGLEICHE sauber bleiben.
    """

    def __init__(self, rng: random.Random):
        self.rng = rng

    def decide(self, obs):
        st = FIELD[_phase((obs.get("my_stack") or 0) / max(1, obs.get("bb") or 100))]
        r = self.rng
        hole = [c for c in (obs.get("hole") or []) if c]
        strength = ps.strength(_hand_class(hole)) if len(hole) == 2 else 0.3
        bb = obs.get("bb") or 100
        eff = (obs.get("my_stack") or 0) / bb
        if obs.get("street") == "preflop":
            if obs.get("preflop_raises", 0) == 0:
                if eff <= 15 and r.random() < st["jam_rate"] * 4 and strength > 0.45 and obs.get("can_raise"):
                    return {"action": "raise", "amount": obs.get("raise_max"), "rationale": {}}
                if r.random() < st["pfr"] * 2.2 and strength > 0.50 and obs.get("can_raise"):
                    return {"action": "raise", "amount": min(obs.get("raise_max") or 250, int(2.3 * bb)),
                            "rationale": {}}
                if obs.get("can_check"):
                    return {"action": "check", "amount": None, "rationale": {}}
                if r.random() < (st["vpip"] - st["pfr"]) * 2 and obs.get("can_call"):
                    return {"action": "call", "amount": None, "rationale": {}}
                return {"action": "fold", "amount": None, "rationale": {}}
            if r.random() < st["threebet"] and strength > 0.72 and obs.get("can_raise"):
                return {"action": "raise", "amount": obs.get("raise_min"), "rationale": {}}
            if r.random() > st["fold_vs_raise"] and strength > 0.42 and obs.get("can_call"):
                return {"action": "call", "amount": None, "rationale": {}}
            return {"action": "check" if obs.get("can_check") else "fold", "amount": None, "rationale": {}}
        # postflop: Fit-or-Fold auf Handstaerke-Proxy
        if obs.get("to_call", 0) == 0:
            if strength > 0.62 and obs.get("can_raise") and r.random() < 0.5:
                return {"action": "raise", "amount": obs.get("raise_min"), "rationale": {}}
            return {"action": "check", "amount": None, "rationale": {}}
        if strength > 0.55 and obs.get("can_call"):
            return {"action": "call", "amount": None, "rationale": {}}
        return {"action": "fold", "amount": None, "rationale": {}}


def make_hero(arm: str):
    def factory(rng):
        bot = SixMaxBot(0, PROFILES["tag"])
        if arm != "icm+druck":
            bot._read = lambda obs: {}          # Reads nur im Exploit-Arm
        return bot
    return factory


BOT_FIELD = ("tag", "tag", "lag", "nit", "tag")   # kompetentes 6-max-Feld (der harte Modus)


def run_one(structure: Structure, arm: str, seed: int, field_kind: str = "freq") -> dict:
    rng = random.Random(seed)
    names = ["hero"] + [f"reg_{i}" for i in range(5)]
    rng.shuffle(names)
    d = Director(structure, names, seed=seed)
    agents = {}
    for nm in names:
        if nm == "hero":
            agents[nm] = make_hero(arm)(random.Random(rng.randrange(1 << 30)))
        elif field_kind == "bots":
            bot = SixMaxBot(0, PROFILES[BOT_FIELD[int(nm.split("_")[1]) % len(BOT_FIELD)]])
            bot._read = lambda obs: {}
            agents[nm] = bot
        else:
            agents[nm] = PSFieldAgent(random.Random(rng.randrange(1 << 30)))
    guard_hands = 0
    while not d.over() and guard_hands < 4000:
        guard_hands += 1
        t = d.next_table()
        for a in agents.values():
            if hasattr(a, "bind_table"):
                a.bind_table(t)
        aggressor = None
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 300:
            guard += 1
            seat = t.to_act
            obs = t.obs_for(seat)
            nm_seat = t.seats[seat].name
            if arm != "chipEV" and nm_seat == "hero":
                obs["icm"] = d.icm_ctx(t, seat, aggressor)
                if arm == "icm+druck":
                    obs["icm"]["pressure"] = True
            elif field_kind == "bots" and nm_seat != "hero":
                # DAS FELD SPIELT SELBST ICM (User-These; die PS-Messung belegt genau dieses
                # Tightening: FoldVsRaise 54->62 unter Druck). Erst gegen ICM-tightende Gegner
                # hat der Druck-Arm etwas zu ernten - und chipEV einen echten Kontrast.
                obs["icm"] = d.icm_ctx(t, seat, aggressor)
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = agents[t.seats[seat].name].decide(obs)
                action, amount = (dec["action"], dec["amount"]) if isinstance(dec, dict) else dec
                t.act(action, amount)
            except Exception:  # noqa: BLE001
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
            if action in ("bet", "raise", "allin"):
                aggressor = seat
            for a in agents.values():
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        d.after_hand(t)
    res = next(r for r in d.results() if r["name"] == "hero")
    return {"place": res["place"], "payout": res["payout"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tourneys", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42000)
    ap.add_argument("--payout", choices=("sng", "wta"), default="sng")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--field", choices=("freq", "bots"), default="freq")
    a = ap.parse_args()
    structure = PS6_SNG if a.payout == "sng" else PS6_WTA
    arms = ("chipEV", "icm", "icm+druck")
    raw = {arm: [] for arm in arms}
    for k in range(a.tourneys):
        for arm in arms:
            r = run_one(structure, arm, a.seed + k, field_kind=a.field)
            raw[arm].append(r)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(raw))
        print(f"fertig -> {a.out}")
        return
    for arm in arms:
        nets = [r["payout"] - structure.buyin for r in raw[arm]]
        m = sum(nets) / len(nets)
        se = (sum((x - m) ** 2 for x in nets) / max(1, len(nets) - 1)) ** 0.5 / len(nets) ** 0.5
        pl = [r["place"] for r in raw[arm]]
        p1 = pl.count(1) / len(pl)
        print(f"[{arm:9s}] ROI {100*m/structure.buyin:+6.1f}% ± {100*se/structure.buyin:.1f} | "
              f"P(1.) {p1*100:.1f}% | Plätze {{1..6}}: {[pl.count(i) for i in range(1,7)]}")


if __name__ == "__main__":
    main()
