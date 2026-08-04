"""GG-HIGH-STAKES-ÖKOLOGIE (User, 2026-08-04): unsere zwei Bot-Arme gegen die $10/$20-Population.

Quelle: hand histories/2026-08-04_GGP_NL-HH-_SH_VHEUK859.zip (NLHDiamond, 6-max, Klarnamen-Regs),
entpackt nach data/gg_hs/hh. Dieses Skript ist ein AUFSATZ auf research/coinpoker_ecology: es
verbiegt dessen Format-Konstanten auf GG ($-Währung, 'Poker Hand #'-Header, BB=20) und liest die
bereits entpackten txt direkt — die CoinPoker-Defaults im Modul bleiben unberührt.

Zwei Arme, gleiche Seeds, gleiche Population:
  GTO     = HybridHero (tag-Kern multiway, Prince v2.2 sobald heads-up; Exploit-Reads AUS)
  EXPLOIT = SixMaxBot 'tag' mit eingeschalteten Live-Reads (.observe bekommt alle Public-Actions)

  python -m research.gg_hs_ecology --hands 25000
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

import research.coinpoker_ecology as E

HH_DIR = "data/gg_hs/hh"
OUT = Path("data/gg_hs_pop.json")
MONEY = r"\$([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)"
BB = 20.0


def _configure_gg() -> None:
    """coinpoker_ecology auf das GG-Format umstellen (nur in diesem Prozess)."""
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

    def _iter_gg():
        for f in sorted(glob.glob(HH_DIR + "/**/*.txt", recursive=True)):
            text = open(f, encoding="utf-8", errors="replace").read()
            # GG schreibt '*** SHOWDOWN ***', der Parser prueft die Stars-Schreibweise mit Leerzeichen
            text = text.replace("*** SHOWDOWN ***", "*** SHOW DOWN ***")
            text = text.replace(",", "")          # $4,202.51 -> $4202.51 (Betraege mit Tausender-Komma)
            starts = [m.start() for m in E._HAND_RE.finditer(text)]
            for a, b in zip(starts, starts[1:] + [len(text)]):
                yield text[a:b]

    E._iter_hands = _iter_gg


def hero_gto():
    from research.sixmax_export import HybridHero
    return lambda rng: HybridHero()


def hero_exploit():
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot
    def make(rng):
        bot = SixMaxBot(0, PROFILES["tag"])      # Reads bleiben AN = der Exploit-Layer liest live mit
        return bot
    return make


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hands", type=int, default=25_000)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--parse-only", action="store_true")
    a = ap.parse_args()
    _configure_gg()
    if OUT.exists():
        pop = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"(Population aus Cache {OUT})")
    else:
        pop = E.parse_population()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(pop), encoding="utf-8")
    print(f"POPULATION $10/$20 (GG NLHDiamond): {pop['n_hands']} Haende, {len(pop['players'])} Spieler | "
          f"Rake {100 * pop['rake_frac']:.2f}% (Cap {pop['rake_cap'] / BB:.1f}bb)")
    mix = E.build_mix(pop)
    for m in mix:
        print(f"  {m['weight'] * 100:5.1f}%  {m['name']:13s} VPIP {m['vpip'] * 100:.0f} / PFR {m['pfr'] * 100:.0f} "
              f"/ 3bet {m['threebet'] * 100:.0f} / FoldVsRaise {m['fold_vs_raise'] * 100:.0f}")
    regs = [(nm, s) for nm, s in pop["players"].items() if s["hands"] >= 800]
    regs.sort(key=lambda x: -x[1]["net"] / x[1]["hands"])
    print("ECHTE WINRATES (>=800 Haende, inkl. Rake, bb/100):")
    for nm, s in regs[:8]:
        print(f"  {s['net'] / BB / s['hands'] * 100:+7.1f}  ({s['hands']} H.)  VPIP {s['vpip'] / s['hands'] * 100:.0f} "
              f"PFR {s['pfr'] / s['hands'] * 100:.0f}  {nm}")
    if a.parse_only:
        return
    for label, factory in (("GTO (Hybrid: tag+Prince-HU)", hero_gto()),
                           ("EXPLOIT (tag + Live-Reads)", hero_exploit())):
        res = E.simulate(pop, mix, a.hands, a.seed, hero_factory=factory)
        print(f"\n[{label}] vs $10/$20-Population ({res['hands']} Haende):")
        print(f"  vor Rake:  {res['bb100_prerake']:+.1f} bb/100")
        print(f"  NACH Rake: {res['bb100']:+.1f} ± {res['se100']:.1f} bb/100   "
              f"(Rake-Last {res['rake_bb100']:.1f} bb/100)")


if __name__ == "__main__":
    main()
