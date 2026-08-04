"""SPIN & GOLD-SIM (User, 2026-08-04): 3-max-Hyper-Lotterie-SNG auf GGPoker, kleine Buy-ins.

Oekonomie (von der GG-Seite, verifiziert): 7% Gebuehr je Buy-in -> E[ausgeschuetteter Pool] =
3 x 0.93 = 2.79 Buy-ins, UNABHAENGIG von der Multiplikator-Tabelle (die formt nur die Varianz;
2x dominiert — die Versicherung greift genau dort). Winner-take-all im Normalfall ->
Breakeven-P(Sieg) ~ 1/2.79 = 35.8% (Basis 33.3%: der Skill-Edge muss +2.5pp P(Sieg) liefern).

Format-Annahmen (GG publiziert Startstack/Blinds nicht exakt — "je nach Multiplikator"):
300 Chips = 15bb bei 10/20, Level alle 8 Haende (3-min-Proxy), keine Antes. Das ist die
GG-typische Hyper-Form; Robustheit ueber --depth 25 pruefbar.

Arme (gleiche Seeds + identisches Feld je Seed): clone (P_D Ist) | agame (Tilt-Reset, hier
inkl. notify-Verdrahtung) | prep (das NL2-Buendel) | tag (unser Produkt-Kern, Referenz).
Felder: rec (70% LP / 30% TAG — Micro-Spins) | reg (TAG/GTOapx — der harte Pool).

  python -m research.spin_sim --games 2500 --arm prep --field rec --out data/spin_prep_rec.json
"""
from __future__ import annotations

import argparse
import json
import random

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table

import research.prince_ecology as PE
from pokerbot.engine.equity import equity_vs_class_range

_ALL_CLASSES = None


def _seeded_eq(self, obs):
    """Agent.eq mit der EIGENEN geseedeten rng (der Default zog OS-Entropie -> Messung
    nicht deterministisch; Purify-Kontext-Split: live darf rauschen, die Messung nie)."""
    global _ALL_CLASSES
    if _ALL_CLASSES is None:
        from pokerbot.engine.cards import all_hand_classes
        _ALL_CLASSES = all_hand_classes()
    try:
        e = equity_vs_class_range(obs["hole"], _ALL_CLASSES, obs["board"],
                                  iters=PE.EQ_ITERS, rng=self.rng)
        opp = max(1, obs["n_active"] - 1)
        return e ** opp if opp > 1 else e
    except Exception:  # noqa: BLE001
        return 0.5


PE.Agent.eq = _seeded_eq

BUYIN = 1.0                     # alles in Buy-in-Einheiten
POOL_EV = 3 * 0.93              # 7% Gebuehr je Buy-in (GG-Seite)
LEVELS = [(10, 20), (15, 30), (20, 40), (30, 60), (40, 80), (60, 120),
          (80, 160), (120, 240), (160, 320), (240, 480), (320, 640), (480, 960)]
HANDS_PER_LEVEL = 8
MAX_HANDS = 400


def make_field(kind: str, rng: random.Random):
    from research.prince_ecology import GTOapx, LP, TAG
    if kind == "rec":
        cls = LP if rng.random() < 0.7 else TAG
    else:
        cls = TAG if rng.random() < 0.5 else GTOapx
    return cls(random.Random(rng.randrange(1 << 30)))


def make_hero(arm: str, rng: random.Random):
    if arm == "tag":
        bot = SixMaxBot(0, PROFILES["tag"])
        bot._read = lambda obs: {}
        bot.rng = random.Random(rng.randrange(1 << 30))
        return bot
    from research.gg_nl2_pop import make_hero as nl2_hero
    key = {"clone": "clone", "agame": "agame", "prep": "agame+all"}[arm]
    return nl2_hero(key)(random.Random(rng.randrange(1 << 30)))


def run_game(seed: int, arm: str, field: str, start_stack: int = 300) -> dict:
    """EIN Spin bis zum Sieger. -> {'win': 0/1, 'place': 1..3, 'hands': n}."""
    rng = random.Random(seed * 6007 + 3)
    names = ["hero", "v1", "v2"]
    rng.shuffle(names)
    agents = {nm: (make_hero(arm, rng) if nm == "hero" else make_field(field, rng))
              for nm in names}                       # feste Reihenfolge -> Feld identisch je Seed
    stacks = {nm: start_stack for nm in names}
    button_name = None
    hand_no = 0
    place_of = {}
    next_place = 3
    while len([n for n in stacks.values() if n > 0]) > 1 and hand_no < MAX_HANDS:
        live = [nm for nm in names if stacks[nm] > 0]
        sb, bb = LEVELS[min(hand_no // HANDS_PER_LEVEL, len(LEVELS) - 1)]
        btn = (live.index(button_name) + 1) % len(live) if button_name in live else 0
        t = Table(live, starting_stack=start_stack, sb=sb, bb=bb,
                  seed=seed * 100003 + hand_no, stacks=[stacks[nm] for nm in live],
                  ante=0, rebuy=False)
        t.button = btn - 1
        t.start_hand()
        button_name = t.seats[t.button].name
        hand_no += 1
        start = {s.name: s.stack + s.committed_total for s in t.seats}
        hero_here = "hero" in live
        for i, s in enumerate(t.seats):
            a = agents[s.name]
            if hasattr(a, "seat"):
                a.seat = i
            if hasattr(a, "new_hand"):
                a.new_hand(list(range(len(live))))
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 200:
            guard += 1
            seat = t.to_act
            nm = t.seats[seat].name
            obs = t.obs_for(seat)
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = agents[nm].decide(obs)
                action, amount = (dec["action"], dec["amount"]) if isinstance(dec, dict) else dec
                t.act(action, amount)
            except Exception:  # noqa: BLE001
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
            for s in t.seats:
                a = agents[s.name]
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        busts = []
        for s in t.seats:
            stacks[s.name] = s.stack
            if s.stack <= 0:
                busts.append((s.name, start[s.name]))
            if s.name == "hero" and hero_here and hasattr(agents["hero"], "notify_hand_end"):
                # Tilt-/Reset-Verdrahtung (die Oekologie-Konvention; tourney.py hat sie nicht)
                net_bb = (s.stack - (start[s.name])) / bb
                was_sd = bool(t.result and t.result.get("reason") == "showdown")
                agents["hero"].notify_hand_end(net_bb, was_sd, s.all_in)
        busts.sort(key=lambda x: x[1])              # kleinerer Start-Stack -> schlechterer Platz
        for nm, _ in busts:
            place_of[nm] = next_place
            next_place -= 1
    for nm in names:
        if stacks[nm] > 0 and nm not in place_of:
            place_of[nm] = 1
    hp = place_of.get("hero", 1)
    return {"win": int(hp == 1), "place": hp, "hands": hand_no}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=2500)
    ap.add_argument("--seed", type=int, default=70_000)
    ap.add_argument("--arm", choices=("clone", "agame", "prep", "tag"), default="prep")
    ap.add_argument("--field", choices=("rec", "reg"), default="rec")
    ap.add_argument("--depth", type=int, default=300, help="Startchips (300=15bb GG-Form)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    recs = [run_game(a.seed + k, a.arm, a.field, a.depth) for k in range(a.games)]
    n = len(recs)
    p1 = sum(r["win"] for r in recs) / n
    se = (p1 * (1 - p1) / n) ** 0.5
    # WTA-Naeherung: E[1.-Preis] in [2.6, 2.79] Buy-ins (Hoch-Multiplikatoren zahlen 2./3.)
    roi_mid = p1 * 2.7 - 1
    out = {"arm": a.arm, "field": a.field, "n": n, "p1": p1, "se_p1": se,
           "roi_mid": roi_mid, "roi_lo": p1 * 2.6 - 1, "roi_hi": p1 * 2.79 - 1,
           "hands_mean": sum(r["hands"] for r in recs) / n}
    print(f"[{a.arm}/{a.field}] P(Sieg) {p1*100:.1f}% ± {se*100:.1f} | "
          f"ROI(mid) {roi_mid*100:+.1f}% [{out['roi_lo']*100:+.1f}, {out['roi_hi']*100:+.1f}] | "
          f"{out['hands_mean']:.0f} Haende/Spiel")
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(out))


if __name__ == "__main__":
    main()
