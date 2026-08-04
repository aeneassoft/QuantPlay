"""600-SPIELER-MTT-SIM — das $1050/$600k-Event realistisch (User-Szenario, 2026-08-04).

Szenario: Buy-in $1050 ($1000 in den Pool), Prize Pool $600.000 => 600 Entries ohne Overlay.
220bb-Start (55.000 Chips bei 125/250), die ECHTE PS-Blind-Leiter aus den $1050-HHs, danach
multiplikativ verlaengert. 90 bezahlte Plaetze (PS-Konvention ~15% des Feldes); die Leiter ist
PS-FORM-synthetisiert (geometrischer Top-Abfall r=0.72 + Flat-Tiers, Min-Cash ~2x Buy-in) —
die gemine-ten Original-Leitern unserer HHs sind an der Spitze Deal-kontaminiert (2.=Sieger).

Feld = PSFieldAgent mit den GEMESSENEN Phasen-Frequenzen des echten $1050-Pools
(data/ps_tourney_field.json — deren ICM-/Bubble-Verhalten steckt in den Zahlen, User-These).
Ehrliche Einordnung: preflop kalibriert, postflop schlicht -> die absolute Winrate ist eine
OPTIMISTISCHE Schranke; der ARM-VERGLEICH (gepaarte Seeds) ist das belastbare Signal.

Multi-Table-Mechanik: ~100 Tische a 6, eine Hand je Tisch pro Runde, 12 Runden je Level
(PS-Proxy), Balancing auf +-1 Spieler, Tisch-Kollaps sobald ein Tisch frei wird, globale
Platzvergabe (Simultan-Busts: groesserer Start-Stack platziert hoeher — Sklansky-Regel).
Hero-Bust beendet die Sim (sein Platz steht fest — die Restwelt aendert ihn nicht).

Hero-Arme (gepaart, identische Deck-Seeds je Tisch/Hand):
  chipEV : tag-Kern pur, Reads AUS (2x2-Befund: Reads schaden im Turnier).
  druck  : dazu (a) Bubble-Fenster-Druck (90 < left <= 144): Open-Verbreiterung auf die
           gemessene Zwangs-Tightness kurzer gecoverter Stacks (FvR 54->62); (b) ab <=12
           Verbliebenen die EXAKTE ICM-Brille (Call-Seite + All-in-Schwellen + Druck-Hebel
           mit echten Bubble-Faktoren) — die im SNG validierte Schicht (mu-3: +10pp ROI).

  python -m research.mtt_sim --tourneys 5 --arm druck        # Smoke
  python -m research.mtt_sim --tourneys 200 --paired --out data/mtt_w0.json
"""
from __future__ import annotations

import argparse
import json
import random

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table
from pokerbot.strategy.tournament import icm_pressure_mult
from research.ps_tourney_duel import PSFieldAgent

N_PLAYERS = 600
START_STACK = 55_000            # 220bb bei 125/250
BUYIN = 1050.0
POOL = 600_000.0
SEATS_PER_TABLE = 6
HANDS_PER_LEVEL = 12            # eine Runde = eine Hand an jedem Tisch (Zeit-Proxy wie im Duell)
MAX_ROUNDS = 2000
EXACT_ICM_AT = 12               # ab hier ist die Bitmask-DP exakt bezahlbar (2^12)
BUBBLE_WINDOW = 1.6             # Druck-Fenster: paid < left <= paid*1.6
PRESSURE_CAP = 1.5
PRESSURE_SLOPE = 0.6            # mult = 1 + slope * Anteil gecoverter Gegner am Tisch

# Die echte PS-Leiter (13 Stufen aus den HHs), dann x1.25 bis das Spiel enden MUSS
_BBS = [250, 300, 350, 400, 500, 600, 700, 800, 1000, 1200, 1600, 2000, 2500]
while _BBS[-1] < N_PLAYERS * START_STACK // 16:
    _BBS.append(int(_BBS[-1] * 1.25) // 100 * 100)
LEVELS = [(bb // 2, bb, int(round(bb * 0.13))) for bb in _BBS]


def build_payouts(pool: float = POOL) -> list[float]:
    """90 Plaetze, PS-Form: Top 8 geometrisch (r=0.72), darunter Flat-Tiers, Summe EXAKT pool."""
    top = [15.80 * 0.72 ** i for i in range(8)]                    # 1.-8.
    tiers = [(4, 1.35), (6, 1.05), (6, 0.82), (12, 0.65),          # 9-12, 13-18, 19-24, 25-36
             (18, 0.52), (18, 0.42), (18, 0.35)]                   # 37-54, 55-72, 73-90
    pct = top + [p for cnt, p in tiers for _ in range(cnt)]
    scale = 100.0 / sum(pct)
    pays = [round(p * scale * pool / 100.0, 2) for p in pct]
    pays[0] = round(pays[0] + (pool - sum(pays)), 2)               # Rundungsrest auf Platz 1
    return pays


PAYOUTS = build_payouts()


class _TableHost:
    """Ein Tisch des MTT: Namensliste + Button-Gedaechtnis + stabile uid fuer Deck-Pairing."""

    __slots__ = ("uid", "names", "button_name", "hand_no")

    def __init__(self, uid: int, names: list[str]):
        self.uid = uid
        self.names = names
        self.button_name: str | None = None
        self.hand_no = 0


BOT_FIELD_PROFILES = ("tag", "tag", "lag", "nit", "station")   # kompetenter Regs-Mix


class MTT:
    def __init__(self, seed: int, arm: str = "chipEV", field: str = "freq"):
        self.seed = seed
        self.arm = arm
        self.field = field
        self.rng = random.Random(seed * 7919 + 13)
        names = ["hero"] + [f"reg_{i}" for i in range(N_PLAYERS - 1)]
        self.rng.shuffle(names)
        self.stacks = {nm: START_STACK for nm in names}
        self.alive = list(names)
        self.next_place = N_PLAYERS
        self.hero_place: int | None = None
        self.round_no = 0
        self._uid = 0
        self.tables: list[_TableHost] = []
        for i in range(0, len(names), SEATS_PER_TABLE):
            self.tables.append(_TableHost(self._new_uid(), names[i:i + SEATS_PER_TABLE]))
        self.hero_bot = SixMaxBot(0, PROFILES["tag"])
        self.hero_bot._read = lambda obs: {}                 # Reads AUS (2x2-Befund)
        # GESEEDETES Mixing fuers MESSEN (Purify-Kontext-Split: live CSPRNG, Messung seeded) —
        # sonst zieht der Bot OS-Entropie und die gepaarten Arme verlieren Pairing-Power.
        self.hero_bot.rng = random.Random(seed * 31 + 7)
        self.field_agents = {nm: PSFieldAgent(random.Random(self.rng.randrange(1 << 30)))
                             for nm in names if nm != "hero"}
        # KONSERVATIVER Modus 'bots_local': sitzt ein Reg an HEROS Tisch, entscheidet ein
        # kompetenter SixMaxBot-Kern statt des Frequenz-Agenten (die Schranke von unten —
        # das Frequenz-Feld ist postflop schlicht = Schranke von oben). Hintergrund-Tische
        # bleiben Frequenz (dort zaehlt nur Eliminierungs-Tempo/Stack-Fluss, nicht Spielguete).
        self._local_bots: dict[str, SixMaxBot] = {}
        self.checkpoints = {"itm": False, "ft": False}
        self.stop_on_hero_bust = True       # Tests setzen False (voller Platz-Audit)
        self.audit = False                  # Tests: Chip-Erhaltung je Runde pruefen
        self.places: dict[str, int] = {}    # alle vergebenen Plaetze (Audit + Debug)

    def _local_bot(self, nm: str) -> SixMaxBot:
        bot = self._local_bots.get(nm)
        if bot is None:
            idx = int(nm.split("_")[1])
            bot = SixMaxBot(0, PROFILES[BOT_FIELD_PROFILES[idx % len(BOT_FIELD_PROFILES)]])
            bot._read = lambda obs: {}
            bot.rng = random.Random(self.seed * 104729 + idx)
            self._local_bots[nm] = bot
        return bot

    def _new_uid(self) -> int:
        self._uid += 1
        return self._uid

    def _level(self) -> tuple[int, int, int]:
        return LEVELS[min(self.round_no // HANDS_PER_LEVEL, len(LEVELS) - 1)]

    # ---------------------------------------------------------------- eine Hand an einem Tisch
    def _play_hand(self, host: _TableHost) -> list[tuple[str, int]]:
        """Spielt EINE Hand. -> Busts [(name, start_stack)] dieses Tisches."""
        sb, bb, ante = self._level()
        names = [nm for nm in host.names if self.stacks[nm] > 0]
        if len(names) < 2:
            return []
        if host.button_name in names:
            btn = (names.index(host.button_name) + 1) % len(names)
        else:
            btn = 0
        t = Table(names, starting_stack=START_STACK, sb=sb, bb=bb,
                  seed=self.seed * 1_000_003 + host.uid * 10_007 + host.hand_no,
                  stacks=[self.stacks[nm] for nm in names], ante=ante, rebuy=False)
        t.button = btn - 1
        t.start_hand()
        host.button_name = t.seats[t.button].name
        host.hand_no += 1
        start_stacks = {s.name: s.stack + s.committed_total for s in t.seats}

        hero_here = "hero" in names
        deciders: dict[str, object] = {}
        for nm in names:
            if nm == "hero":
                deciders[nm] = self.hero_bot
            elif self.field == "bots_local" and hero_here:
                deciders[nm] = self._local_bot(nm)
            else:
                deciders[nm] = self.field_agents[nm]
        for nm, a in deciders.items():
            if hasattr(a, "seat"):
                # Der REVIEW-Fund #4: SixMaxBot(0,...) traegt seat=0 fest, Heros Tisch-Index
                # wandert aber mit jedem Balancing -> das Initiative-Flag (aggr = pf_aggressor
                # == seat) war in ~5/6 der Haende falsch (kein C-Bet im eigenen Pot). Sitz je
                # Hand setzen + new_hand-Reset (sonst traegt pf_aggressor Stale-State weiter).
                a.seat = names.index(nm)
            if hasattr(a, "new_hand"):
                a.new_hand(list(range(len(names))))
            if hasattr(a, "bind_table"):
                a.bind_table(t)
        pressure_mult = None                        # lazy, einmal pro Hand
        exact_ctx_base = None
        aggressor: int | None = None
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 300:
            guard += 1
            seat = t.to_act
            nm = t.seats[seat].name
            obs = t.obs_for(seat)
            left = len(self.alive)
            wants_icm = (nm == "hero" and self.arm != "chipEV") or (
                nm != "hero" and self.field == "bots_local" and hero_here
                and left <= EXACT_ICM_AT)   # das FELD spielt selbst ICM an der FT (User-These)
            if wants_icm:
                if left <= EXACT_ICM_AT:
                    # EXAKTE ICM-Brille (die SNG-validierte Schicht): Stack-Vektor = Tisch in
                    # Sitzordnung + die Spieler des anderen Tisches hintendran.
                    if exact_ctx_base is None:
                        others = [float(self.stacks[o]) for o in self.alive
                                  if o not in start_stacks]
                        exact_ctx_base = others
                    ctx = {
                        "stacks": [float(start_stacks[s.name]) for s in t.seats] + exact_ctx_base,
                        "payouts": PAYOUTS[:len(self.alive)] if len(self.alive) <= len(PAYOUTS)
                                   else list(PAYOUTS),
                        "seat": seat,
                        "aggressor": aggressor,
                        "invested": {i: float(s.committed_total) for i, s in enumerate(t.seats)},
                    }
                    if nm == "hero" and self.arm == "druck":
                        if pressure_mult is None:
                            # EINMAL pro Hand, nicht pro Entscheidung — und NUR ueber die
                            # Tisch-Gegner gemittelt (Off-Table-BFs koennen nicht folden)
                            table_v = [i for i in range(len(t.seats)) if i != seat]
                            pressure_mult = icm_pressure_mult({"icm": ctx}, villains=table_v)
                        ctx["pressure"] = True
                        ctx["pressure_mult"] = pressure_mult
                    obs["icm"] = ctx
                elif len(PAYOUTS) < left <= int(len(PAYOUTS) * BUBBLE_WINDOW):
                    # GELD-BUBBLE-FENSTER: exakte BFs unbezahlbar -> gemessene Zwangs-Tightness
                    # ernten. Gecoverte (kuerzere) Stacks am Tisch = die Fold-Equity-Quelle.
                    if pressure_mult is None:
                        my = start_stacks.get("hero", 0)
                        opp = [v for k, v in start_stacks.items() if k != "hero"]
                        covered = sum(1 for v in opp if v < my) / max(1, len(opp))
                        pressure_mult = min(PRESSURE_CAP, 1.0 + PRESSURE_SLOPE * covered)
                    obs["icm"] = {"pressure": True, "pressure_mult": pressure_mult}
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = deciders[nm].decide(obs)
                action, amount = (dec["action"], dec["amount"]) if isinstance(dec, dict) else dec
                t.act(action, amount)
            except Exception:  # noqa: BLE001 — ein Agenten-Fehler killt kein Turnier
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
            if action in ("bet", "raise", "allin"):
                aggressor = seat
            for a in deciders.values():
                if hasattr(a, "observe"):
                    a.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        if not t.hand_over:
            # TRIPWIRE (2026-08-04): verliesse die Schleife mit UNAUFGELOESTER Hand (guard),
            # wuerde der Stack-Sweep unten den Pot vernichten. Gemessen ist das im freq-Feld
            # praktisch unerreichbar (laengste Hand: 31 Aktionen bei guard=300, n=235k Haende) —
            # falls es je feuert: Hand annullieren (committed Chips zurueck) statt vernichten.
            for s in t.seats:
                s.stack += s.committed_total
            print(f"[mtt_sim] WARNUNG: unaufgeloeste Hand annulliert (Runde {self.round_no}, "
                  f"Tisch {host.uid}/{host.hand_no - 1}, Street {t.street})", flush=True)
        end_total = sum(s.stack for s in t.seats)
        if end_total != sum(start_stacks.values()):
            # Chip-Erhaltung JE HAND (self.audit prueft nur je Runde die Gesamtsumme): der Dump
            # macht die naechste Anomalie sofort diagnostizierbar statt erst in der End-Summe.
            msg = (f"Chip-Erhaltung je Hand verletzt: {end_total} != {sum(start_stacks.values())} "
                   f"(Runde {self.round_no}, Tisch {host.uid}, hand_over={t.hand_over}, "
                   f"to_act={t.to_act}, Street {t.street}, bb={t.bb}, ante={t.ante}, "
                   f"Sitze={[(s.name, s.stack, s.committed_total, s.folded, s.all_in) for s in t.seats]}, "
                   f"History={t.history})")
            if self.audit:
                raise AssertionError(msg)
            print(f"[mtt_sim] {msg}", flush=True)
        busts = []
        for s in t.seats:
            self.stacks[s.name] = s.stack
            if s.stack <= 0:
                busts.append((s.name, start_stacks[s.name]))
        return busts

    # ---------------------------------------------------------------- Runde + Balancing
    def _rebalance(self) -> None:
        alive_set = set(self.alive)
        for h in self.tables:
            h.names = [nm for nm in h.names if nm in alive_set]
        self.tables = [h for h in self.tables if h.names]
        target = max(1, -(-len(self.alive) // SEATS_PER_TABLE))          # ceil
        # Kollaps: die kleinsten Tische aufloesen, Spieler in freie Sitze der anderen
        while len(self.tables) > target:
            self.tables.sort(key=lambda h: len(h.names))
            dead = self.tables.pop(0)
            movers = list(dead.names)
            self.rng.shuffle(movers)
            for nm in movers:
                dest = min(self.tables, key=lambda h: len(h.names))
                dest.names.append(nm)
        # Balance auf +-1
        while True:
            big = max(self.tables, key=lambda h: len(h.names))
            small = min(self.tables, key=lambda h: len(h.names))
            if len(big.names) - len(small.names) <= 1:
                break
            mover = big.names.pop(self.rng.randrange(len(big.names)))
            small.names.append(mover)

    def _apply_busts(self, busts: list[tuple[str, int]]) -> None:
        """Globale Platzvergabe der Runde: kleinerer Start-Stack -> schlechterer Platz."""
        busts.sort(key=lambda x: x[1])
        for nm, _ in busts:
            self.alive.remove(nm)
            self.places[nm] = self.next_place
            if nm == "hero":
                self.hero_place = self.next_place
            self.next_place -= 1

    def run(self) -> dict:
        while (len(self.alive) > 1 and self.round_no < MAX_ROUNDS
               and (self.hero_place is None or not self.stop_on_hero_bust)):
            round_busts: list[tuple[str, int]] = []
            for host in list(self.tables):
                round_busts.extend(self._play_hand(host))
            self._apply_busts(round_busts)
            self._rebalance()
            self.round_no += 1
            if self.audit:
                total = sum(self.stacks.values())
                assert total == N_PLAYERS * START_STACK, (
                    f"Chip-Erhaltung verletzt: {total} != {N_PLAYERS * START_STACK} "
                    f"(Runde {self.round_no})")
                assert sorted(self.places.values()) == list(
                    range(self.next_place + 1, N_PLAYERS + 1)), "Platzvergabe lueckenhaft"
            left = len(self.alive)
            if not self.checkpoints["itm"] and left <= len(PAYOUTS) and "hero" in self.alive:
                self.checkpoints["itm"] = True
            if not self.checkpoints["ft"] and left <= SEATS_PER_TABLE and "hero" in self.alive:
                self.checkpoints["ft"] = True
        if self.hero_place is None:
            # Hero lebt am Ende: Sieger (alive==1) oder Guard-Abbruch -> Platz nach Stack-Rang
            if len(self.alive) == 1:
                self.hero_place = 1
            else:
                ranked = sorted(self.alive, key=lambda nm: -self.stacks[nm])
                self.hero_place = ranked.index("hero") + 1
        payout = PAYOUTS[self.hero_place - 1] if self.hero_place <= len(PAYOUTS) else 0.0
        return {"place": self.hero_place, "payout": payout, "rounds": self.round_no,
                "itm": self.checkpoints["itm"] or self.hero_place <= len(PAYOUTS),
                "ft": self.checkpoints["ft"] or self.hero_place <= SEATS_PER_TABLE}


def run_one(seed: int, arm: str, field: str = "freq") -> dict:
    return MTT(seed, arm, field=field).run()


def _summarize(recs: list[dict]) -> dict:
    n = len(recs)
    nets = [r["payout"] - BUYIN for r in recs]
    m = sum(nets) / n
    se = (sum((x - m) ** 2 for x in nets) / max(1, n - 1)) ** 0.5 / n ** 0.5
    return {
        "n": n, "roi_pct": 100 * m / BUYIN, "se_pct": 100 * se / BUYIN,
        "p_itm": sum(r["itm"] for r in recs) / n,
        "p_ft": sum(r["ft"] for r in recs) / n,
        "p_top3": sum(r["place"] <= 3 for r in recs) / n,
        "p_win": sum(r["place"] == 1 for r in recs) / n,
        "median_place": sorted(r["place"] for r in recs)[n // 2],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tourneys", type=int, default=5)
    ap.add_argument("--seed", type=int, default=90_000)
    ap.add_argument("--arm", default="druck", choices=("chipEV", "druck"))
    ap.add_argument("--paired", action="store_true", help="beide Arme auf identischen Seeds")
    ap.add_argument("--field", default="freq", choices=("freq", "bots_local"))
    ap.add_argument("--out", default=None, help="Rohdaten-JSON fuer den Parallel-Merger")
    a = ap.parse_args()
    arms = ("chipEV", "druck") if a.paired else (a.arm,)
    raw = {arm: [] for arm in arms}
    for k in range(a.tourneys):
        for arm in arms:
            raw[arm].append(run_one(a.seed + k, arm, field=a.field))
    if a.out:
        open(a.out, "w", encoding="utf-8").write(json.dumps(raw))
        print(f"fertig: {a.tourneys} Turniere x {len(arms)} Arme -> {a.out}")
        return
    for arm, recs in raw.items():
        s = _summarize(recs)
        print(f"[{arm:6s}] n={s['n']} ROI {s['roi_pct']:+.1f}% ± {s['se_pct']:.1f} | "
              f"ITM {s['p_itm']*100:.1f}% | FT {s['p_ft']*100:.2f}% | Top3 {s['p_top3']*100:.2f}% | "
              f"P(1.) {s['p_win']*100:.2f}% | Median-Platz {s['median_place']}")


if __name__ == "__main__":
    main()
