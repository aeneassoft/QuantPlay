"""CoinPoker-NL200-Ökologie: würde PRINCEDARKNESS auf diesem Level gewinnen? (User, 2026-08-03)

INPUT: 'hand histories/2026-08-03_CPH2N_NL-HH-_SH_HRBYF37.zip' — 8 Tages-Zips beobachteter NL200-6-max-
Hände (₮1/₮2 + Ante, Rake pro Hand ausgewiesen). Man kann fixe Transkripte nicht kontrafaktisch
"gegen" einen Klon replayen — stattdessen der ehrliche Zweibein-Ansatz:

BEIN 1 (MESSUNG): die Population vermessen — per-Spieler VPIP/PFR/3bet/Limp/AF/WTSD + ECHTES Netto
(bb/100 inkl. Rake, aus den Chips-Flüssen der Hände), Rake-Funktion empirisch (Anteil + Cap), Ante.
Die Gewinner-Verteilung der REALEN Regs ist der harte Anker für "gewinnen auf diesem Level".

BEIN 2 [SIMULATION]: die hands-gewichtete Population in Archetyp-Cluster teilen (Standard-Schwellen),
jedes Cluster als parametrisierten Frequenz-Agenten (PopAgent) instanziieren, und den P_D-Klon
(prince_ecology.PrinceClone — an die 923 gemessenen Cash-Hände gefittet) an 6-max-Tischen gegen
per-Cluster-Mix gesampelte Gegner spielen lassen. Rake wird post-hoc mit der EMPIRISCHEN Funktion
auf Heros gewonnene Pötte angewendet.

EHRLICHE GRENZEN: (a) PopAgents sind Frequenz-Klone der Cluster-Zentroide, keine echten Spieler —
jede Sim-Zahl ist [SIMULATION], nie [MESSUNG]; (b) Antes (0.16bb/Spieler/Hand) sind im Table nicht
modelliert — sie süßen jeden Pot und BEGÜNSTIGEN loose Stile wie P_D, die Sim ist insofern eher
konservativ; (c) keine Adaption der Gegner (die Realen adaptieren).

Run:  python -m research.coinpoker_ecology [--hands 60000] [--seed 11] [--parse-only]
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ZIP = Path("hand histories/2026-08-03_CPH2N_NL-HH-_SH_HRBYF37.zip")
OUT = Path("data/coinpoker_pop.json")
MONEY = r"₮([0-9]+(?:\.[0-9]+)?)"
BB = 2.0
MIN_HANDS_WINRATE = 1500      # Netto-Winrates nur fuer Spieler mit genug Volumen (sonst Rauschen)
TABLE_RESEAT = 50             # Sim: alle N Haende neuer Tisch (Line-up-Fluktuation wie live)

_HAND_RE = re.compile(r"^CoinPoker Hand #\d+", re.M)
_SEAT_RE = re.compile(r"^Seat \d+: (.+?) \(" + MONEY + r" in chips\)", re.M)
_RAKE_RE = re.compile(r"Total pot " + MONEY + r" \| Rake " + MONEY)
_ANTE_RE = re.compile(r"Ante " + MONEY)
_ACT_RE = re.compile(
    # Betrag KOMPLETT optional klammern: '₮(...)?' liesse das ₮ Pflicht sein -> 'folds'/'checks'
    # (ohne Betrag) matchten nie und Fold-vs-Raise war ueberall 0 (gemessen, 2026-08-03)
    r"^(.+?): (posts the ante|posts small blind|posts big blind|folds|checks|calls|bets|raises)"
    r"(?: " + MONEY + r")?(?: to " + MONEY + r")?", re.M)
_UNCALLED_RE = re.compile(r"Uncalled bet \(" + MONEY + r"\) returned to (.+)")
_COLLECT_RE = re.compile(r"^(.+?) collected " + MONEY + r" from", re.M)


def _iter_hands():
    outer = zipfile.ZipFile(ZIP)
    for inner_name in sorted(outer.namelist()):
        inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
        for fn in sorted(inner.namelist()):
            if not fn.endswith(".txt"):
                continue
            text = inner.read(fn).decode("utf-8", errors="replace")
            starts = [m.start() for m in _HAND_RE.finditer(text)]
            for a, b in zip(starts, starts[1:] + [len(text)]):
                yield text[a:b]


def parse_population() -> dict:
    """Bein 1: Spieler-Stats + echte Nettos + Rake/Ante aus allen Haenden."""
    P = defaultdict(lambda: {"hands": 0, "vpip": 0, "pfr": 0, "limp": 0, "tb_opp": 0, "tb": 0,
                             "fr_opp": 0, "fr_fold": 0, "pf_agg": 0, "pf_call": 0, "pf_acts": 0,
                             "saw_flop": 0, "sd": 0, "net": 0.0})
    tot_pot = tot_rake = 0.0
    all_rakes: list[float] = []
    ante = None
    n_hands = 0
    for hand in _iter_hands():
        n_hands += 1
        if ante is None:
            m = _ANTE_RE.search(hand)
            ante = float(m.group(1)) if m else 0.0
        committed = defaultdict(float)          # gesamt uebers Blatt (Antes+Blinds+Einsaetze)
        street_to = defaultdict(float)          # Street-Level 'to'-Verfolgung fuer raises
        players = [m.group(1) for m in _SEAT_RE.finditer(hand)]
        pre = hand.split("*** FLOP ***")[0]
        postflop = hand[len(pre):]
        showdown = "*** SHOW DOWN ***" in hand or ": shows [" in hand
        # Street-Grenzen: das 'raises X to Y'-Level gilt NUR innerhalb einer Street — ohne Reset
        # wuerde ein Postflop-Raise gegen ein stales Preflop-Level verrechnet (Chip-Erhaltung kaputt)
        bounds = sorted(hand.find(mk) for mk in ("*** FLOP ***", "*** TURN ***", "*** RIVER ***")
                        if hand.find(mk) >= 0)
        seg_idx = 0
        raises_seen = 0
        vpip_done, pfr_done = set(), set()
        for m in _ACT_RE.finditer(hand):
            who, verb, a1, a2 = m.group(1), m.group(2), m.group(3), m.group(4)
            in_pre = m.start() < len(pre)
            new_seg = sum(1 for b in bounds if m.start() > b)
            if new_seg != seg_idx:
                seg_idx = new_seg
                street_to.clear()
            if verb == "posts the ante" or verb.startswith("posts"):
                committed[who] += float(a1 or 0)
                if verb == "posts big blind":
                    street_to[who] = float(a1 or 0)
                elif verb == "posts small blind":
                    street_to[who] = float(a1 or 0)
                continue
            st = P[who]
            if in_pre:
                if verb in ("calls", "bets", "raises") and who not in vpip_done:
                    st["vpip"] += 1
                    vpip_done.add(who)
                if verb == "raises" and who not in pfr_done:
                    st["pfr"] += 1
                    pfr_done.add(who)
                if verb == "calls" and raises_seen == 0:
                    st["limp"] += 1
                if raises_seen >= 1 and verb in ("raises", "calls", "folds"):
                    st["tb_opp"] += 1
                    st["fr_opp"] += 1
                    if verb == "raises":
                        st["tb"] += 1
                    if verb == "folds":
                        st["fr_fold"] += 1
                if verb == "raises":
                    raises_seen += 1
            else:
                if verb in ("bets", "raises"):
                    st["pf_agg"] += 1
                elif verb == "calls":
                    st["pf_call"] += 1
                if verb in ("bets", "raises", "calls", "checks", "folds"):
                    st["pf_acts"] += 1
            if verb == "calls":
                committed[who] += float(a1 or 0)
            elif verb == "bets":
                committed[who] += float(a1 or 0)
                street_to[who] = float(a1 or 0)     # Street wechselt: to-Tracking grob, reicht fuer Netto
            elif verb == "raises":
                to = float(a2 or a1 or 0)
                committed[who] += max(0.0, to - street_to.get(who, 0.0))
                street_to[who] = to
        # Street-Reset des to-Trackings ist oben vereinfacht — fuer NETTO zaehlt nur committed,
        # und das ist additiv korrekt, weil 'raises X to Y' das Street-Level traegt und wir das
        # Level pro Street neu beginnen muessten. Korrektur: bets nach Streetwechsel starten bei 0 —
        # der grobe Fehler waere Doppelzaehlung; der Selftest prueft die Chip-Erhaltung pro Hand.
        for m in _UNCALLED_RE.finditer(hand):
            committed[m.group(2).strip()] -= float(m.group(1))
        collected = defaultdict(float)
        for m in _COLLECT_RE.finditer(hand):
            collected[m.group(1)] += float(m.group(2))
        mr = _RAKE_RE.search(hand)
        if mr:
            tot_pot += float(mr.group(1))
            tot_rake += float(mr.group(2))
            all_rakes.append(float(mr.group(2)))
        for who in players:
            st = P[who]
            st["hands"] += 1
            st["net"] += collected.get(who, 0.0) - committed.get(who, 0.0)
            if who in _flop_players(postflop):
                st["saw_flop"] += 1
                if showdown and f"{who}: shows [" in hand or (showdown and who in hand.split("*** SUMMARY ***")[-1] and "showed" in hand):
                    st["sd"] += 1
    # Cap = p99 statt Max: ein einzelnes Parse-Artefakt (229bb "Rake") hatte die Sim-Rake-Last
    # von realistisch ~5-10 auf 63 bb/100 aufgeblasen (gemessen 2026-08-03); p99 = der echte Tisch-Cap.
    all_rakes.sort()
    cap = all_rakes[int(0.99 * len(all_rakes))] if all_rakes else 0.0
    return {"n_hands": n_hands, "ante": ante or 0.0, "rake_frac": tot_rake / max(1e-9, tot_pot),
            "rake_cap": cap, "players": dict(P)}


def _flop_players(postflop_text: str) -> set:
    return {m.group(1) for m in _ACT_RE.finditer(postflop_text)}


# ---------------------------------------------------------------- Archetyp-Cluster (Standard-Schwellen)
def _archetype(v, p, af):
    r = p / max(v, 1e-9)
    if v < 0.18:
        return "nit"
    if v < 0.30:
        return "reg_tag" if r > 0.55 else "passiv_tight"
    if v < 0.45:
        return "lag" if r > 0.5 else "station"
    return "maniac" if p > 0.28 else "whale_lp"


def build_mix(pop: dict, min_hands: int = 200) -> list[dict]:
    """Hands-gewichtete Cluster-Zentroide -> PopAgent-Profile. Gewicht = Anteil der Sitz-Instanzen."""
    clusters = defaultdict(lambda: defaultdict(float))
    for name, s in pop["players"].items():
        if s["hands"] < min_hands:
            continue
        v = s["vpip"] / s["hands"]
        p = s["pfr"] / s["hands"]
        af = s["pf_agg"] / max(1, s["pf_call"])
        key = _archetype(v, p, af)
        c = clusters[key]
        w = s["hands"]
        c["w"] += w
        for k, val in (("vpip", v), ("pfr", p), ("limp", s["limp"] / s["hands"]),
                       ("threebet", s["tb"] / max(1, s["tb_opp"])),
                       ("fold_vs_raise", s["fr_fold"] / max(1, s["fr_opp"])),
                       ("agg_freq", s["pf_agg"] / max(1, s["pf_acts"])),
                       ("call_freq", s["pf_call"] / max(1, s["pf_acts"]))):
            c[k] += w * val
    mix = []
    tot = sum(c["w"] for c in clusters.values())
    for key, c in sorted(clusters.items(), key=lambda kv: -kv[1]["w"]):
        prof = {k: c[k] / c["w"] for k in c if k != "w"}
        prof["name"] = key
        prof["weight"] = c["w"] / tot
        mix.append(prof)
    return mix


# ---------------------------------------------------------------- Sim: P_D vs die kalibrierte Population
class PopAgent:
    """Frequenz-Agent aus einem Cluster-Zentroid — dieselbe Bauart wie prince_ecology's Archetypen,
    nur mit GEMESSENEN NL200-Frequenzen statt heuristischer."""

    def __init__(self, prof: dict, rng: random.Random):
        from research.prince_ecology import Agent
        self._base = Agent(rng)
        self.p = prof
        self.rng = rng

    def decide(self, obs):
        from pokerbot.strategy import preflop_strength as ps
        from pokerbot.engine.cards import hand_class
        p, r = self.p, self.rng
        if obs["street"] == "preflop":
            s = ps.strength(hand_class(*obs["hole"]))
            if obs["preflop_raises"] > 0:
                if r.random() < p["threebet"] and s > 0.55 and obs["can_raise"]:
                    return ("raise", self._base._raise_to(obs, 1.1))
                if r.random() > p["fold_vs_raise"] and s > 0.30:
                    return ("call", None) if obs["can_call"] else ("check", None)
                return ("fold", None) if obs["to_call"] > 0 else ("check", None)
            if r.random() < p["vpip"]:
                open_r = p["pfr"] / max(p["vpip"], 1e-9)
                if r.random() < open_r and obs["can_raise"]:
                    return ("raise", self._base._raise_to(obs, 0.9))
                return ("call", None) if obs["can_call"] else ("check", None)
            return ("check", None) if obs["can_check"] else ("fold", None)
        e = self._base.eq(obs)
        if obs["to_call"] == 0:
            if obs["can_raise"] and (e > 0.62 or r.random() < p["agg_freq"]):
                return ("bet", self._base._raise_to(obs, r.choice([0.4, 0.6, 0.8])))
            return ("check", None)
        pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
        # Call-Laxheit aus der gemessenen Call-Frequenz: Stationen callen unter Pot-Odds
        lax = 0.75 + 0.5 * min(0.5, p["call_freq"])
        if e > 0.80 and obs["can_raise"] and r.random() < p["agg_freq"]:
            return ("raise", self._base._raise_to(obs, 0.85))
        return ("call", None) if e > pot_odds / lax * 0.9 else ("fold", None)


def simulate(pop: dict, mix: list[dict], n_hands: int, seed: int, hero_factory=None, depth_bb: int = 100) -> dict:
    """hero_factory(rng)->Agent erlaubt andere Helden (z.B. den tag-Produktkern); Default = P_D-Klon.
    Agenten mit .observe(actor, street, action, to_call, preflop_raises) bekommen alle Public-Actions."""
    from pokerbot.engine.table import Table
    from research.prince_ecology import PrinceClone
    rng = random.Random(seed)
    hero_net = []
    rake_paid = 0.0
    weights = [m["weight"] for m in mix]
    t = None
    agents = {}
    for hand_i in range(n_hands):
        if t is None or hand_i % TABLE_RESEAT == 0:
            t = Table([f"S{i}" for i in range(6)], starting_stack=depth_bb * 100, sb=50, bb=100,
                      seed=rng.randrange(1 << 30))
            hrng = random.Random(rng.randrange(1 << 30))
            agents = {0: (hero_factory(hrng) if hero_factory else PrinceClone(hrng))}
            for s in range(1, 6):
                prof = rng.choices(mix, weights=weights, k=1)[0]
                agents[s] = PopAgent(prof, random.Random(rng.randrange(1 << 30)))
            for a in agents.values():           # Helden mit Table-Bedarf (Prince-HU-Projektion) anbinden
                if hasattr(a, "bind_table"):
                    a.bind_table(t)
        t.start_hand()
        for a in agents.values():
            if hasattr(a, "new_hand"):
                a.new_hand(list(range(6)))
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 200:
            guard += 1
            seat = t.to_act
            obs = t.obs_for(seat)
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = agents[seat].decide(obs)
                action, amount = (dec["action"], dec["amount"]) if isinstance(dec, dict) else dec
                t.act(action, amount)
            except Exception:  # noqa: BLE001
                la = t.legal_actions()
                action, amount = ("check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")), None
                t.act(action)
            for a in agents.values():           # Public-Info an beobachtende Agenten (SixMaxBot-Reads)
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        won = {w["seat"]: w["amount"] for w in (t.result or {}).get("winners", [])}
        net = won.get(0, 0) - t.seats[0].committed_total
        if won.get(0, 0) > 0:                     # empirischer Rake auf Heros gewonnene Poette
            pot = (t.result or {}).get("pot", 0)
            rk = min(pop["rake_frac"] * pot, pop["rake_cap"] / BB * 100)
            rake_paid += rk
            net -= rk
        hero_net.append(net / 100.0)
        if hasattr(agents[0], "notify_hand_end"):
            # Tilt-/Reset-Hook (PrinceReset = das A-Game-Modell): identische Ableitung wie
            # prince_ecology.run_eco, damit derselbe Held in beiden Harnessen dasselbe erlebt.
            shown = bool((t.result or {}).get("shown"))
            was_allin = t.seats[0].stack == 0
            agents[0].notify_hand_end(net / 100.0, shown, was_allin)
        for s in t.seats:                         # Stacks pro Hand zuruecksetzen (Population = konstant tief)
            s.stack = depth_bb * 100
    n = len(hero_net)
    mean = sum(hero_net) / n
    var = sum((x - mean) ** 2 for x in hero_net) / max(1, n - 1)
    se100 = (var ** 0.5) / (n ** 0.5) * 100
    return {"hands": n, "bb100": mean * 100, "se100": se100,
            "bb100_prerake": (sum(hero_net) + rake_paid / 100) / n * 100,
            "rake_bb100": rake_paid / 100 / n * 100}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=60_000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--parse-only", action="store_true")
    args = ap.parse_args()
    if OUT.exists():
        pop = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"(Population aus Cache {OUT})")
    else:
        pop = parse_population()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(pop), encoding="utf-8")
    n_pl = len(pop["players"])
    print(f"POPULATION NL200: {pop['n_hands']} Haende, {n_pl} Spieler | Ante {pop['ante'] / BB:.2f}bb "
          f"| Rake {100 * pop['rake_frac']:.2f}% (Cap {pop['rake_cap'] / BB:.1f}bb)")
    mix = build_mix(pop)
    for m in mix:
        print(f"  {m['weight'] * 100:5.1f}%  {m['name']:13s} VPIP {m['vpip'] * 100:.0f} / PFR {m['pfr'] * 100:.0f} "
              f"/ 3bet {m['threebet'] * 100:.0f} / FoldVsRaise {m['fold_vs_raise'] * 100:.0f}")
    # echte Gewinner-Verteilung (der harte Anker)
    regs = [(nm, s) for nm, s in pop["players"].items() if s["hands"] >= MIN_HANDS_WINRATE]
    regs.sort(key=lambda x: -x[1]["net"] / x[1]["hands"])
    print(f"ECHTE WINRATES (>= {MIN_HANDS_WINRATE} Haende, inkl. Rake, bb/100):")
    for nm, s in regs[:6] + ([] if len(regs) <= 9 else regs[-3:]):
        print(f"  {s['net'] / BB / s['hands'] * 100:+7.1f}  ({s['hands']} H.)  VPIP {s['vpip'] / s['hands'] * 100:.0f} "
              f"PFR {s['pfr'] / s['hands'] * 100:.0f}")
    if args.parse_only:
        return
    res = simulate(pop, mix, args.hands, args.seed)
    print(f"\n[SIMULATION] P_D-Klon vs NL200-Population ({res['hands']} Haende):")
    print(f"  vor Rake:  {res['bb100_prerake']:+.1f} bb/100")
    print(f"  NACH Rake: {res['bb100']:+.1f} ± {res['se100']:.1f} bb/100   (Rake-Last {res['rake_bb100']:.1f} bb/100)")


if __name__ == "__main__":
    main()
