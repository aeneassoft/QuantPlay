"""GG-NL2-ÖKOLOGIE (User, 2026-08-04): Princedarkness' neues Habitat — die $0.01/$0.02-Population.

Quelle: hand histories/2026-08-04_GGP_NL-HH-_SH_IMPJP104.zip (~600k Hände, 96 Tage, 6-max),
entpackt nach data/gg_nl2/hh. Aufsatz auf research/coinpoker_ecology (das gg_hs_ecology-Muster),
BB=$0.02. ZEIT-ACHSE (User-Auftrag): Hände nach Europe/Berlin-Stunde gebuckelt — GG-PokerCraft-
Zeitstempel sind UTC (Annahme, dokumentiert); EU-Fenster = 09:00-03:00 Berlin, Rest = "Nacht"
(03-09 Uhr Berlin = das EU-Schlafloch, dort spielt der Asien/US-Rest).

Drei Stufen:
  --zeit       nur der billige Zeit/Stats-Pass (beide Fenster im Kontrast)
  --parse-only Population des EU-Fensters parsen + Mix + echte Winrates
  (default)    dazu die Hero-Arme simulieren (gleiche Seeds je Arm):
               clone (P_D Ist-Zustand) | agame (PrinceReset) | + Hebel auf dem A-Game:
               agame+nolimp | agame+valuegate | agame+3bet | agame+calldisc

  python -m research.gg_nl2_pop --zeit
  python -m research.gg_nl2_pop --hands 40000 --arm agame --out data/gg_nl2_agame.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import research.coinpoker_ecology as E

HH_DIR = "data/gg_nl2/hh"
OUT = Path("data/gg_nl2_pop.json")
MONEY = r"\$([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
BB = 0.02
BERLIN = ZoneInfo("Europe/Berlin")
_TS_RE = re.compile(r"- (\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})")
EU_HOURS = set(range(9, 24)) | {0, 1, 2}        # 09:00-03:00 Berlin


def berlin_hour(hand_text: str) -> int | None:
    m = _TS_RE.search(hand_text[:120])
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g) for g in m.groups())
    dt = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)     # GG exportiert UTC (Annahme)
    return dt.astimezone(BERLIN).hour


def _iter_all():
    for f in sorted(glob.glob(HH_DIR + "/**/*.txt", recursive=True)):
        text = open(f, encoding="utf-8", errors="replace").read()
        text = text.replace("*** SHOWDOWN ***", "*** SHOW DOWN ***").replace(",", "")
        starts = [m.start() for m in re.finditer(r"^Poker Hand #\w+", text, re.M)]
        for a, b in zip(starts, starts[1:] + [len(text)]):
            yield text[a:b]


def _configure_gg(eu_only: bool) -> None:
    """coinpoker_ecology auf GG-NL2 umstellen; optional nur das EU-Fenster liefern."""
    E.BB = BB
    E.OUT = OUT
    E.MONEY = MONEY
    E._HAND_RE = re.compile(r"^Poker Hand #\w+", re.M)
    E._SEAT_RE = re.compile(r"^Seat \d+: (.+?) \(" + MONEY + r" in chips\)", re.M)
    E._RAKE_RE = re.compile(r"Total pot " + MONEY + r" \| Rake " + MONEY)
    E._ANTE_RE = re.compile(r"Ante " + MONEY)
    E._ACT_RE = re.compile(
        r"^(.+?): (posts the ante|posts small blind|posts big blind|folds|checks|calls|bets|raises)"
        r"(?: " + MONEY + r")?(?: to " + MONEY + r")?", re.M)
    E._UNCALLED_RE = re.compile(r"Uncalled bet \(" + MONEY + r"\) returned to (.+)")
    E._COLLECT_RE = re.compile(r"^(.+?) collected " + MONEY + r" from", re.M)

    def _iter():
        for hand in _iter_all():
            if eu_only and berlin_hour(hand) not in EU_HOURS:
                continue
            yield hand

    E._iter_hands = _iter


# ---------------------------------------------------------------- Zeit/Stats-Pass (billig)
_SEAT_Q = re.compile(r"^Seat \d+: .+? \(" + MONEY + r" in chips\)", re.M)
_ACT_Q = re.compile(r"^(.+?): (folds|checks|calls|bets|raises)", re.M)
_RAISE_Q = re.compile(r"^.+?: raises ", re.M)


def zeit_pass() -> dict:
    """Ein Regex-Pass: Volumen + Kern-Frequenzen je Berlin-Stunde (Preflop-zaehlend wie
    ps_tourney_field: VPIP/PFR/Limp je Spieler-Hand, 3bet je Gelegenheit, FvR je Gelegenheit)."""
    H = {h: {"hands": 0, "ph": 0, "vpip": 0, "pfr": 0, "limp": 0, "tb": 0, "tb_opp": 0,
             "fr_fold": 0, "fr_opp": 0, "sd": 0, "depth": 0.0} for h in range(24)}
    for hand in _iter_all():
        h = berlin_hour(hand)
        if h is None:
            continue
        st = H[h]
        st["hands"] += 1
        stacks = [float(m) for m in re.findall(_SEAT_Q, hand.replace(",", "")) or []]
        # _SEAT_Q findall liefert die MONEY-Gruppe
        if stacks:
            st["depth"] += sum(float(s) for s in stacks) / len(stacks) / BB
        if ": shows [" in hand:
            # GG druckt die SHOWDOWN-Sektion in JEDE Hand — echter Showdown = jemand zeigt Karten
            st["sd"] += 1
        pre = hand.split("*** FLOP ***")[0]
        raises_seen = 0
        seen: set[str] = set()
        for am in _ACT_Q.finditer(pre):
            who, verb = am.group(1), am.group(2)
            if who not in seen:
                st["ph"] += 1
            if verb in ("calls", "bets", "raises"):
                if who not in seen:
                    st["vpip"] += 1
                if verb == "raises":
                    if raises_seen == 1:
                        st["tb"] += 1
                    if who not in seen:
                        st["pfr"] += 1
                    raises_seen += 1
                elif verb == "calls" and raises_seen == 0:
                    st["limp"] += 1
            if raises_seen >= 1 and verb in ("folds", "calls", "raises"):
                st["fr_opp"] += 1
                if verb == "folds":
                    st["fr_fold"] += 1
            if raises_seen == 1 and verb in ("folds", "calls"):
                st["tb_opp"] += 1
            seen.add(who)
    return H


def _window(H: dict, hours) -> dict:
    agg = {k: sum(H[h][k] for h in hours) for k in next(iter(H.values()))}
    ph = max(1, agg["ph"])
    return {"hands": agg["hands"], "vpip": agg["vpip"] / ph, "pfr": agg["pfr"] / ph,
            "limp": agg["limp"] / ph, "threebet": agg["tb"] / max(1, agg["tb_opp"]),
            "fold_vs_raise": agg["fr_fold"] / max(1, agg["fr_opp"]),
            "showdown": agg["sd"] / max(1, agg["hands"]),
            "depth_bb": agg["depth"] / max(1, agg["hands"])}


def print_zeit(H: dict) -> None:
    print("Berlin-Stunde | Haende | VPIP | PFR | Limp | 3bet | FvR | SD% | Depth")
    for h in list(range(9, 24)) + list(range(0, 9)):
        w = _window(H, [h])
        print(f"  {h:02d}:00  {'EU ' if h in EU_HOURS else 'nac'} | {w['hands']:6d} | "
              f"{w['vpip']*100:4.0f} | {w['pfr']*100:3.0f} | {w['limp']*100:4.0f} | "
              f"{w['threebet']*100:4.1f} | {w['fold_vs_raise']*100:3.0f} | "
              f"{w['showdown']*100:4.1f} | {w['depth_bb']:5.0f}bb")
    eu, nacht = _window(H, EU_HOURS), _window(H, set(range(24)) - EU_HOURS)
    for label, w in (("EU-FENSTER 9-3h", eu), ("NACHT 3-9h", nacht)):
        print(f"{label:16s}: {w['hands']:6d} H. | VPIP {w['vpip']*100:.0f} / PFR {w['pfr']*100:.0f} / "
              f"Limp {w['limp']*100:.0f} / 3bet {w['threebet']*100:.1f} / FvR {w['fold_vs_raise']*100:.0f} / "
              f"SD {w['showdown']*100:.0f}% / Depth {w['depth_bb']:.0f}bb")


# ---------------------------------------------------------------- Hero-Arme
def make_hero(arm: str):
    from research.prince_ecology import PD, PrinceClone, PrinceReset, _hc
    from pokerbot.strategy import preflop_strength as ps

    if arm == "clone":
        return lambda rng: PrinceClone(rng)
    if arm == "agame":
        return lambda rng: PrinceReset(rng)

    nolimp = arm in ("agame+nolimp", "agame+all")
    valuegate = arm in ("agame+valuegate", "agame+all")
    calldisc = arm in ("agame+calldisc", "agame+all")

    class PDPrep(PrinceReset):
        """A-Game + Hebel (einzeln isoliert ODER als gemessenes Buendel 'agame+all')."""

        def decide(self, obs):
            r = self.rng
            if nolimp and obs["street"] == "preflop" and self.lock <= 0 \
                    and obs["preflop_raises"] == 0:
                # LIMP-CUT: raise-or-fold statt der gemessenen 39% Limps (VPIP-Masse -> Opens)
                s = ps.strength(_hc(obs["hole"]))
                if s > 0.42 and obs["can_raise"]:
                    return ("raise", self._raise_to(obs, 1.0))
                return ("check", None) if obs["can_check"] else ("fold", None)
            if arm == "agame+3bet" and obs["street"] == "preflop" and self.lock <= 0 \
                    and obs["preflop_raises"] == 1:
                # 3BET-UP: die Mini-Opens des Pools haerter bestrafen (Wert + Fold Equity)
                s = ps.strength(_hc(obs["hole"]))
                if s > 0.62 and obs["can_raise"]:
                    return ("raise", self._raise_to(obs, 1.2))
            if obs["street"] != "preflop" and self.lock <= 0:
                if valuegate and obs["to_call"] == 0:
                    # VALUE-GATE: gegen Stationen nur noch mit Equity betten (Bluff-Anteil weg),
                    # Overbets NUR als Value (e>.75) — die gemessenen 28% Overbet-Bluffs sterben.
                    e = self.eq(obs)
                    if e > 0.55 and obs["can_raise"]:
                        frac = 1.5 if (e > 0.75 and r.random() < PD["overbet_share"]) else 0.66
                        return ("bet", self._raise_to(obs, frac))
                    return ("check", None)
                if calldisc and obs["to_call"] > 0:
                    # CALL-DISZIPLIN: Pot-Odds als harte Grenze (statt 0.62x = Light-Calldowns)
                    e = self.eq(obs)
                    pot_odds = obs["to_call"] / max(1, obs["pot"] + obs["to_call"])
                    if e > 0.72 and obs["can_raise"] and r.random() < 0.45:
                        return ("raise", self._raise_to(obs, 0.8))
                    return ("call", None) if e >= pot_odds else ("fold", None)
            return super().decide(obs)

    return lambda rng: PDPrep(rng)


ARMS = ("clone", "agame", "agame+nolimp", "agame+valuegate", "agame+3bet", "agame+calldisc", "agame+all")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=40_000)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--zeit", action="store_true")
    ap.add_argument("--parse-only", action="store_true")
    ap.add_argument("--arm", choices=ARMS, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.zeit:
        print_zeit(zeit_pass())
        return

    _configure_gg(eu_only=True)
    if OUT.exists():
        pop = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"(Population aus Cache {OUT})")
    else:
        pop = E.parse_population()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(pop), encoding="utf-8")
    print(f"POPULATION NL2 EU-Fenster: {pop['n_hands']} Haende, {len(pop['players'])} Spieler | "
          f"Rake {100 * pop['rake_frac']:.2f}% (Cap {pop['rake_cap'] / BB:.1f}bb)")
    mix = E.build_mix(pop)
    for m in mix:
        print(f"  {m['weight'] * 100:5.1f}%  {m['name']:13s} VPIP {m['vpip'] * 100:.0f} / "
              f"PFR {m['pfr'] * 100:.0f} / 3bet {m['threebet'] * 100:.0f} / "
              f"FoldVsRaise {m['fold_vs_raise'] * 100:.0f}")
    regs = [(nm, s) for nm, s in pop["players"].items() if s["hands"] >= 2000]
    regs.sort(key=lambda x: -x[1]["net"] / x[1]["hands"])
    print(f"ECHTE WINRATES (>=2000 Haende, n={len(regs)}, inkl. Rake, bb/100):")
    for nm, s in regs[:6] + regs[-3:]:
        print(f"  {s['net'] / BB / s['hands'] * 100:+7.1f}  ({s['hands']:5d} H.)  "
              f"VPIP {s['vpip'] / s['hands'] * 100:2.0f} PFR {s['pfr'] / s['hands'] * 100:2.0f}  {nm}")
    if a.parse_only:
        return

    arms = (a.arm,) if a.arm else ARMS
    results = {}
    for arm in arms:
        res = E.simulate(pop, mix, a.hands, a.seed, hero_factory=make_hero(arm))
        results[arm] = res
        print(f"[{arm:16s}] {res['bb100']:+7.1f} ± {res['se100']:.1f} bb/100 nach Rake "
              f"(vor Rake {res['bb100_prerake']:+.1f}, Rake-Last {res['rake_bb100']:.1f})")
    if a.out:
        Path(a.out).write_text(json.dumps({k: {kk: v[kk] for kk in ("bb100", "se100", "bb100_prerake", "rake_bb100", "hands")}
                                           for k, v in results.items()}), encoding="utf-8")
        print(f"-> {a.out}")


if __name__ == "__main__":
    main()
