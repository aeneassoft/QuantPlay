"""HEUTE-ABEND-SIM — das 60er-Freezeout mit 50k-Start, 10er-Tischen und limpigem Feld.

Struktur (vom Veranstalter): Freezeout NLH, 60 Spieler, 10 pro Tisch, Start-Stack 50.000,
Blinds 50/100 mit BIG BLIND ANTE, Level 20min (die ersten vier) danach 15min, Pause alle
4 Level, 10% bezahlt = 6 Plaetze. Start-Tiefe: 500 bb — aussergewoehnlich tief.

Feld = KNEIPEN-FELD (Beobachtung des Auftraggebers): viele steigen preflop ein, gecallt wird
auch gegen Erhoehungen; postflop klebrig (Fit-or-Fold mit weitem Call). Bewusst als
Frequenz-Agent modelliert wie alle unsere Oekologie-Felder — die ARM-VERGLEICHE (gepaarte
Seeds) sind das belastbare Signal, die absolute Platzierung eine optimistische Schranke.

BIG BLIND ANTE wird oekonomisch aequivalent abgebildet: der BB zahlt 1 bb fuer den Tisch,
also je Sitz bb/n — dieselbe tote Menge im Pot wie in der Realitaet.

Arme (identische Deck-Seeds je Tisch/Hand):
  turnier : tag-Kern + exakte ICM-Brille ab <=12 + Bubble-Druckfenster  (unser Turnier-Bot)
  chipEV  : derselbe Kern ohne jede ICM-Schicht
  weit    : lag-Kern (die hoehere Amplitude — der natuerliche Stil)
  eng     : nit-Kern (das reine Ueberleben)

  python -m research.tonight_sim --tourneys 300 --paired --out data/tonight.json
"""
from __future__ import annotations

import argparse
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table
from pokerbot.strategy import preflop_strength as ps
from pokerbot.engine.cards import hand_class
from pokerbot.engine.evaluator import made_class
from pokerbot.strategy.tournament import icm_pressure_mult

N_PLAYERS = 60
SEATS_PER_TABLE = 10
START_STACK = 50_000
PAID = 6                       # 10% des Feldes
FT_SIZE = 10                   # Finaltisch
BUYIN = 20.0
POOL = N_PLAYERS * BUYIN
PAYOUT_SHARES = [0.30, 0.20, 0.15, 0.13, 0.11, 0.11]
PAYOUTS = [POOL * x for x in PAYOUT_SHARES]
EXACT_ICM_AT = 12
BUBBLE_WINDOW = 2.0            # Druckfenster: 6 < left <= 12
PRESSURE_CAP, PRESSURE_SLOPE = 1.5, 0.6
MAX_ROUNDS = 4000

# Blind-Leiter eines 20-Euro-Live-Events mit 50k-Start; steigt bis das Spiel enden MUSS.
_LADDER = [(50, 100), (100, 200), (150, 300), (200, 400), (300, 600), (400, 800),
           (500, 1000), (600, 1200), (800, 1600), (1000, 2000), (1500, 3000), (2000, 4000),
           (3000, 6000), (4000, 8000), (5000, 10_000), (6000, 12_000), (8000, 16_000),
           (10_000, 20_000), (15_000, 30_000), (20_000, 40_000), (30_000, 60_000),
           (40_000, 80_000), (60_000, 120_000), (80_000, 160_000)]
# Live 10-handed: ~25 Haende/Stunde -> 20-min-Level ~8 Haende, 15-min-Level ~6.
HANDS_PER_LEVEL = [8, 8, 8, 8] + [6] * (len(_LADDER) - 4)
_CUM = []
_acc = 0
for h in HANDS_PER_LEVEL:
    _acc += h
    _CUM.append(_acc)


def level_for_round(rnd: int) -> tuple[int, int, int]:
    """(sb, bb, level_index) fuer eine Runde (= eine Hand an jedem Tisch)."""
    for i, c in enumerate(_CUM):
        if rnd < c:
            return _LADDER[i][0], _LADDER[i][1], i
    return _LADDER[-1][0], _LADDER[-1][1], len(_LADDER) - 1


def _hc(hole):
    return hand_class(hole[0], hole[1]) if len(hole) == 2 else "72o"


class KneipenAgent:
    """Limpiges Live-Feld: steigt oft ein, foldet ungern gegen Erhoehungen, klebt postflop.

    Frequenzen sind die Beobachtung des Auftraggebers in Zahlen: VPIP hoch, PFR niedrig,
    Fold-vs-Raise niedrig. Kurzstack-Regime jammt breiter (typisch fuer Live-Turniere).
    """
    VPIP, PFR, FOLD_VS_RAISE, THREEBET = 0.62, 0.10, 0.38, 0.030

    def __init__(self, rng: random.Random):
        self.rng = rng

    def decide(self, obs):
        r = self.rng
        hole = [c for c in (obs.get("hole") or []) if c]
        strength = ps.strength(_hc(hole)) if len(hole) == 2 else 0.3
        bb = obs.get("bb") or 100
        eff = (obs.get("my_stack") or 0) / max(1, bb)
        if obs.get("street") == "preflop":
            if obs.get("preflop_raises", 0) == 0:
                if eff <= 12 and strength > 0.55 and obs.get("can_raise") and r.random() < 0.55:
                    return {"action": "raise", "amount": obs.get("raise_max")}
                if r.random() < self.PFR * 2.0 and strength > 0.62 and obs.get("can_raise"):
                    return {"action": "raise", "amount": min(obs.get("raise_max") or 300,
                                                             int(3.0 * bb))}
                if obs.get("can_check"):
                    return {"action": "check", "amount": None}
                # der Kern des Feldes: der billige Einstieg
                if r.random() < self.VPIP and strength > 0.20 and obs.get("can_call"):
                    return {"action": "call", "amount": None}
                return {"action": "fold", "amount": None}
            if r.random() < self.THREEBET and strength > 0.80 and obs.get("can_raise"):
                return {"action": "raise", "amount": obs.get("raise_min")}
            # callt auch gegen Erhoehungen, solange der Preis relativ zum Stack traegt
            price = obs.get("to_call", 0) / max(1, obs.get("my_stack") or 1)
            if r.random() > self.FOLD_VS_RAISE and strength > 0.28 and price < 0.35 \
                    and obs.get("can_call"):
                return {"action": "call", "amount": None}
            if eff <= 12 and strength > 0.60 and obs.get("can_call"):
                return {"action": "call", "amount": None}
            return {"action": "check" if obs.get("can_check") else "fold", "amount": None}
        # postflop: klebrig — setzt nur mit echtem Blatt, callt aber weit
        if obs.get("to_call", 0) == 0:
            if strength > 0.66 and obs.get("can_raise") and r.random() < 0.45:
                return {"action": "raise", "amount": obs.get("raise_min")}
            return {"action": "check", "amount": None}
        pot = max(1, obs.get("pot") or 1)
        if strength > 0.40 and obs.get("can_call") and obs.get("to_call", 0) / pot < 0.9:
            return {"action": "call", "amount": None}
        if strength > 0.70 and obs.get("can_call"):
            return {"action": "call", "amount": None}
        return {"action": "fold", "amount": None}



class DepthGuard:
    """Kappt Commitments in der TIEFEN Phase (der Befund dieser Sim).

    Unser Turnier-Kern ist bei ~100 bb validiert. Bei 500 bb Start setzt er dieselben
    Pot-Anteile — und weil das Feld klebt, wachsen die Poette bis zum ganzen Markenstand.
    Gemessen: Hero verdoppelt in Runde 7 (+490 bb) und verliert in Runde 9 den ganzen
    Stack in EINER Hand. Der Guard erzwingt, was ein guter Live-Spieler bei 500 bb ohnehin
    tut: ohne starkes Blatt geht nie mehr als ein Bruchteil der Marken in die Mitte.

    Er greift NUR oberhalb von DEEP_BB effektiver Tiefe; ab Turnier-Normaltiefe ist der
    Kern unveraendert.
    """
    DEEP_BB = 60          # ab hier gilt "tief"
    CAP = 0.28            # hoechstens 28 % des eigenen Markenstands ohne starkes Blatt
    PRE_STRONG = 0.65     # kalibriert: AKo .655 / TT .758 / AA .845 -> ~TT+/AK
    # ZWEITER Befund dieser Sim: der Kern ist ein 6-max-Kern. An einem 10er-Tisch sitzen vor
    # dem Button fuenf zusaetzliche Spieler — eine 6-max-EP-Range ist dort viel zu weit, und
    # gegen klebende Caller blutet sie dauerhaft. EARLY_10 fordert in frueher Position ein
    # deutlich staerkeres Blatt.
    EARLY_10 = {"UTG", "UTG+1", "UTG+2", "UTG+3", "LJ"}
    EARLY_MIN = 0.62      # kalibriert: ~ATo/KJo/66+/QJs+ = 12-15 % (10-max-EP)

    def __init__(self, bot, tighten10: bool = False):
        self.bot = bot
        self.tighten10 = tighten10

    def __getattr__(self, item):          # seat / new_hand / observe / rng durchreichen
        return getattr(self.bot, item)

    def _strong(self, obs) -> bool:
        hole = [c for c in (obs.get("hole") or []) if c]
        board = list(obs.get("board") or [])
        if len(board) < 3:
            return len(hole) == 2 and ps.strength(_hc(hole)) >= self.PRE_STRONG
        try:
            return made_class(board, hole) in ("two-pair+", "monster")
        except Exception:  # noqa: BLE001
            return False

    def decide(self, obs):
        d = self.bot.decide(obs)
        if not isinstance(d, dict):
            return d
        # 10-max-Positionsdisziplin: in frueher Position nur mit echtem Blatt eroeffnen
        if (self.tighten10 and obs.get("street") == "preflop"
                and obs.get("preflop_raises", 0) == 0
                and (obs.get("n_active") or 0) >= 7
                and obs.get("position") in self.EARLY_10
                and d.get("action") in ("raise", "call")):
            hole = [c for c in (obs.get("hole") or []) if c]
            if len(hole) != 2 or ps.strength(_hc(hole)) < self.EARLY_MIN:
                return {"action": "check", "amount": None} if obs.get("can_check") else                        {"action": "fold", "amount": None}
        stack = obs.get("my_stack") or 0
        bb = obs.get("bb") or 100
        if stack / max(1, bb) <= self.DEEP_BB or self._strong(obs):
            return d
        cap = int(stack * self.CAP)
        act, amt = d.get("action"), d.get("amount")
        if act in ("raise", "bet") and amt and amt > cap and obs.get("can_raise"):
            lo, hi = obs.get("raise_min") or 0, obs.get("raise_max") or 0
            if lo and cap >= lo:
                return {"action": "raise", "amount": max(lo, min(cap, hi))}
            return {"action": "check", "amount": None} if obs.get("can_check") else \
                   {"action": "call", "amount": None} if obs.get("can_call") else d
        if act == "call" and (obs.get("to_call") or 0) > cap:
            return {"action": "check", "amount": None} if obs.get("can_check") else \
                   {"action": "fold", "amount": None}
        return d


class _Host:
    __slots__ = ("uid", "names", "button_name", "hand_no")

    def __init__(self, uid, names):
        self.uid, self.names = uid, list(names)
        self.button_name, self.hand_no = names[0], 0


ARM_PROFILE = {"turnier": "tag", "chipEV": "tag", "weit": "lag", "eng": "nit",
               "tief": "tag", "tief_weit": "lag", "live": "tag", "live_weit": "lag"}
DEEP_ARMS = {"tief", "tief_weit", "live", "live_weit"}   # mit Tiefen-Disziplin
TEN_ARMS = {"live", "live_weit"}                        # zusaetzlich 10-max-Position
# Heros Tisch im Modus "bots": echte Entscheidungskerne statt Frequenz-Agenten — die
# KONSERVATIVE Schranke. Mischung nach der Beobachtung: viele Caller, wenige Solide.
LIVE_MIX = ["station", "whale", "station", "lag", "tag", "station",
            "whale", "nit", "station", "lag"]


class Tonight:
    def __init__(self, seed: int, arm: str = "turnier", feld: str = "bots"):
        self.seed, self.arm, self.feld = seed, arm, feld
        self.rng = random.Random(seed * 7919 + 13)
        names = ["hero"] + [f"p{i}" for i in range(N_PLAYERS - 1)]
        self.rng.shuffle(names)
        self.stacks = {nm: START_STACK for nm in names}
        self.alive = list(names)
        self.next_place = N_PLAYERS
        self.hero_place = None
        self.round_no = 0
        self._uid = 0
        self.tables = [_Host(self._nu(), names[i:i + SEATS_PER_TABLE])
                       for i in range(0, len(names), SEATS_PER_TABLE)]
        self.hero_bot = SixMaxBot(0, PROFILES[ARM_PROFILE[arm]])
        self.hero_bot._read = lambda obs: {}
        self.hero_bot.rng = random.Random(seed * 31 + 7)
        if arm in DEEP_ARMS:
            self.hero_bot = DepthGuard(self.hero_bot, tighten10=arm in TEN_ARMS)
        self.field = {nm: KneipenAgent(random.Random(self.rng.randrange(1 << 30)))
                      for nm in names if nm != "hero"}
        self._local: dict[str, SixMaxBot] = {}
        self.ck = {"itm": False, "ft": False}
        self.trace = []          # (level, left, hero_bb) — nur solange Hero lebt
        self.knockouts = 0       # Bounties

    def _local_bot(self, nm: str) -> SixMaxBot:
        b = self._local.get(nm)
        if b is None:
            idx = int(nm[1:])
            b = SixMaxBot(0, PROFILES[LIVE_MIX[idx % len(LIVE_MIX)]])
            b._read = lambda obs: {}
            b.rng = random.Random(self.seed * 104729 + idx)
            self._local[nm] = b
        return b

    def _nu(self):
        self._uid += 1
        return self._uid

    def _play_hand(self, host: _Host):
        sb, bb, lvl = level_for_round(self.round_no)
        names = [nm for nm in host.names if self.stacks[nm] > 0]
        if len(names) < 2:
            return []
        ante = max(1, bb // len(names))          # Big Blind Ante, oekonomisch aequivalent
        btn = (names.index(host.button_name) + 1) % len(names) if host.button_name in names else 0
        t = Table(names, starting_stack=START_STACK, sb=sb, bb=bb,
                  seed=self.seed * 1_000_003 + host.uid * 10_007 + host.hand_no,
                  stacks=[self.stacks[nm] for nm in names], ante=ante, rebuy=False)
        t.button = btn - 1
        t.start_hand()
        host.button_name = t.seats[t.button].name
        host.hand_no += 1
        start = {s.name: s.stack + s.committed_total for s in t.seats}

        hero_here = "hero" in names
        dec_of = {}
        for nm in names:
            if nm == "hero":
                dec_of[nm] = self.hero_bot
            elif self.feld == "bots" and hero_here:
                dec_of[nm] = self._local_bot(nm)
            else:
                dec_of[nm] = self.field[nm]
        for nm, a in dec_of.items():
            if hasattr(a, "seat"):
                a.seat = names.index(nm)
            if hasattr(a, "new_hand"):
                a.new_hand(list(range(len(names))))
        pressure = None
        icm_base = None
        aggressor = None
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 400:
            guard += 1
            seat = t.to_act
            nm = t.seats[seat].name
            obs = t.obs_for(seat)
            left = len(self.alive)
            if nm == "hero" and self.arm != "chipEV":
                if left <= EXACT_ICM_AT:
                    if icm_base is None:
                        icm_base = [float(self.stacks[o]) for o in self.alive if o not in start]
                    ctx = {"stacks": [float(start[s.name]) for s in t.seats] + icm_base,
                           "payouts": PAYOUTS[:left] if left <= len(PAYOUTS) else list(PAYOUTS),
                           "seat": seat, "aggressor": aggressor,
                           "invested": {i: float(s.committed_total) for i, s in enumerate(t.seats)}}
                    if pressure is None:
                        tv = [i for i in range(len(t.seats)) if i != seat]
                        pressure = icm_pressure_mult({"icm": ctx}, villains=tv)
                    ctx["pressure"], ctx["pressure_mult"] = True, pressure
                    obs["icm"] = ctx
                elif PAID < left <= int(PAID * BUBBLE_WINDOW):
                    if pressure is None:
                        my = start.get("hero", 0)
                        opp = [v for k, v in start.items() if k != "hero"]
                        cov = sum(1 for v in opp if v < my) / max(1, len(opp))
                        pressure = min(PRESSURE_CAP, 1.0 + PRESSURE_SLOPE * cov)
                    obs["icm"] = {"pressure": True, "pressure_mult": pressure}
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                d = dec_of[nm].decide(obs)
                action, amount = (d["action"], d.get("amount")) if isinstance(d, dict) else d
                t.act(action, amount)
            except Exception:  # noqa: BLE001
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
            if action in ("bet", "raise", "allin"):
                aggressor = seat
            for a in dec_of.values():
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        if not t.hand_over:
            for s in t.seats:
                s.stack += s.committed_total
        busts = []
        hero_won = "hero" in names and t.seats[names.index("hero")].stack > start["hero"]
        for s in t.seats:
            self.stacks[s.name] = s.stack
            if s.stack <= 0:
                busts.append((s.name, start[s.name]))
                if hero_won and s.name != "hero":
                    self.knockouts += 1
        return busts

    def _rebalance(self):
        live = set(self.alive)
        for h in self.tables:
            h.names = [nm for nm in h.names if nm in live]
        self.tables = [h for h in self.tables if h.names]
        target = max(1, -(-len(self.alive) // SEATS_PER_TABLE))
        while len(self.tables) > target:
            self.tables.sort(key=lambda h: len(h.names))
            dead = self.tables.pop(0)
            movers = list(dead.names)
            self.rng.shuffle(movers)
            for nm in movers:
                min(self.tables, key=lambda h: len(h.names)).names.append(nm)
        while len(self.tables) > 1:
            big = max(self.tables, key=lambda h: len(h.names))
            small = min(self.tables, key=lambda h: len(h.names))
            if len(big.names) - len(small.names) <= 1:
                break
            small.names.append(big.names.pop(self.rng.randrange(len(big.names))))

    def _apply(self, busts):
        busts.sort(key=lambda x: x[1])
        for nm, _ in busts:
            self.alive.remove(nm)
            if nm == "hero":
                self.hero_place = self.next_place
            self.next_place -= 1

    def run(self):
        while len(self.alive) > 1 and self.round_no < MAX_ROUNDS and self.hero_place is None:
            bs = []
            for host in list(self.tables):
                bs.extend(self._play_hand(host))
            self._apply(bs)
            self._rebalance()
            self.round_no += 1
            left = len(self.alive)
            if "hero" in self.alive:
                _, bb, lvl = level_for_round(self.round_no)
                self.trace.append((lvl + 1, left, round(self.stacks["hero"] / bb, 1)))
                if left <= PAID:
                    self.ck["itm"] = True
                if left <= FT_SIZE:
                    self.ck["ft"] = True
        if self.hero_place is None:
            if len(self.alive) == 1:
                self.hero_place = 1
            else:
                self.hero_place = sorted(self.alive,
                                         key=lambda n: -self.stacks[n]).index("hero") + 1
        payout = PAYOUTS[self.hero_place - 1] if self.hero_place <= PAID else 0.0
        deep = [x for x in self.trace if x[1] <= 20]
        return {"place": self.hero_place, "payout": payout, "ko": self.knockouts,
                "itm": self.ck["itm"] or self.hero_place <= PAID,
                "ft": self.ck["ft"] or self.hero_place <= FT_SIZE,
                "rounds": self.round_no,
                "bust_level": self.trace[-1][0] if self.trace else 1,
                "bb_at_ft": deep[0][2] if deep else None}


def run_one(args):
    seed, arm, feld = args
    return Tonight(seed, arm, feld).run()


def summarize(recs):
    n = len(recs)
    nets = [r["payout"] + 5.0 * r["ko"] - (BUYIN + 5.0) for r in recs]
    m = sum(nets) / n
    se = (sum((x - m) ** 2 for x in nets) / max(1, n - 1)) ** 0.5 / n ** 0.5
    places = sorted(r["place"] for r in recs)
    return {"n": n,
            "p_win": round(sum(r["place"] == 1 for r in recs) / n, 4),
            "p_top3": round(sum(r["place"] <= 3 for r in recs) / n, 4),
            "p_itm": round(sum(r["itm"] for r in recs) / n, 4),
            "p_ft": round(sum(r["ft"] for r in recs) / n, 4),
            "median_place": places[n // 2],
            "mean_place": round(sum(places) / n, 1),
            "mean_ko": round(sum(r["ko"] for r in recs) / n, 2),
            "roi_pct": round(100 * m / (BUYIN + 5.0), 1),
            "roi_se_pct": round(100 * se / (BUYIN + 5.0), 1),
            "mean_bust_level": round(sum(r["bust_level"] for r in recs) / n, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tourneys", type=int, default=200)
    ap.add_argument("--arms", default="turnier,chipEV,weit,eng")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--feld", default="bots", choices=["bots", "kneipe"])
    ap.add_argument("--out", default="data/tonight.json")
    a = ap.parse_args()
    arms = a.arms.split(",")
    out = {"struktur": {"spieler": N_PLAYERS, "sitze": SEATS_PER_TABLE,
                        "start_stack": START_STACK, "start_bb": START_STACK // 100,
                        "bezahlt": PAID, "finaltisch": FT_SIZE, "feld": a.feld}}
    for arm in arms:
        jobs = [(1000 + s, arm, a.feld) for s in range(a.tourneys)]
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            recs = list(ex.map(run_one, jobs, chunksize=4))
        out[arm] = summarize(recs)
        out[arm]["platz_verteilung"] = {
            "1": sum(r["place"] == 1 for r in recs),
            "2-3": sum(2 <= r["place"] <= 3 for r in recs),
            "4-6": sum(4 <= r["place"] <= 6 for r in recs),
            "7-10": sum(7 <= r["place"] <= 10 for r in recs),
            "11-20": sum(11 <= r["place"] <= 20 for r in recs),
            "21-60": sum(r["place"] > 20 for r in recs)}
        print(f"[{arm}] {json.dumps(out[arm], ensure_ascii=False)}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("->", a.out)


if __name__ == "__main__":
    main()
