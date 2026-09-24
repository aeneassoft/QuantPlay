"""MTT-DIREKTOR fuer den Trainer-Turniermodus — 60 Spieler, 6 Tische a 10 Sitze, ein Hero-Tisch.

Der Hero-Tisch wird vom Trainer (six_server) voll gespielt (UI + Berater); die Nebentische spielen
hier vollautomatisch je EINE Hand pro Hero-Hand (gleiche Turnieruhr = Runden, nicht Minuten).
Mechanik uebernommen aus research/mtt_sim.py (600er-Sim, Chip-Audit bestanden) + Director-Muster
aus pokerbot/strategy/tournament.py: Level je Hand, Antes, globale Platzvergabe (Simultan-Busts:
groesserer Start-Stack platziert hoeher — Sklansky-Regel), Tisch-Kollaps auf ceil(alive/10) Tische,
Balancing auf +-1 Spieler, ICM-Kontext fuer die Bots sobald die exakte Bitmask-DP bezahlbar ist.

Determinismus: EIN Turnier-Seed steuert Sitzlosung, Profil-Verteilung, jede Bot-RNG und jedes Deck
(Deck-Seed je Tisch-uid + Tisch-Handnummer) — zwei Laeufe mit gleichem Seed sind byte-gleich
(tests/test_tournament_mode.py).
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table
from pokerbot.strategy.icm import bubble_factor
from pokerbot.strategy.tournament import (BlindLevel, icm_pressure_mult, icm_required_equity,
                                          icm_scaled_req, pick_villain)

# ---------------------------------------------------------------- Struktur
N_PLAYERS = 60
SEATS_PER_TABLE = 10
START_STACK = 5000                 # = 100 BB bei 25/50
BUYIN = 10.0                       # Preispool 600 — Anzeigewaehrung, kein Echtgeld
HANDS_PER_LEVEL = 12               # Level-Uhr zaehlt Hero-Haende (Runden), nicht Minuten (Sim-Konvention)
# 10 Level, Ante ab Level 3 (~1/8 BB wie die PS-$1050-Leiter, data/ps_tourney_field.json: 0.13*bb).
MTT_LEVELS = (
    BlindLevel(25, 50, 0), BlindLevel(50, 100, 0), BlindLevel(75, 150, 15),
    BlindLevel(100, 200, 25), BlindLevel(150, 300, 40), BlindLevel(200, 400, 50),
    BlindLevel(300, 600, 75), BlindLevel(400, 800, 100), BlindLevel(600, 1200, 150),
    BlindLevel(800, 1600, 200),
)
LEVEL_EXTENSION_FACTOR = 1.5       # nach Level 10 waechst der BB weiter (Terminierungs-Garantie)
MAX_ROUNDS = 5000                  # Notbremse gegen Endlosschleifen in der Bots-only-Simulation
# Top-9-Auszahlung (Product-Owner-Vorgabe 25/17/12/9/7/6/5/4.5/4.5 = 90 % → auf 100 % normiert,
# Reste auf Platz 9 gerundet; die exakte Preispool-Summe stellt payouts() sicher).
PAYOUT_PCT_TOP9 = (0.278, 0.189, 0.133, 0.100, 0.078, 0.067, 0.056, 0.050, 0.049)

# ---------------------------------------------------------------- Feld = normale Online-Population
# Prior (kein gemessener Fit): der gemine-te PS-$1050-Pool (data/ps_tourney_field.json, 2.055 Haende,
# deep-Phase VPIP 31.7 / PFR 20.4 / 3bet 10.2 / FoldVsRaise 53.6 %) ist loose-passiv (VPIP-PFR-Luecke 11 pp)
# → Stations+Whales 35 %; der Regs-Kern (tag/lag/nit/rock/shark) 61 %; Maniacs selten (4 %). Die
# gemessene Zwangs-Tightness unter Druck (FoldVsRaise 54→62 %, Jam 1.1→13.1 % short) liefern die Bots
# selbst ueber obs['icm'] (tournament.icm_scaled_req), sobald die ICM-Rechnung exakt bezahlbar ist.
FIELD_MIX = {"station": 0.30, "tag": 0.22, "lag": 0.15, "nit": 0.12,
             "rock": 0.08, "whale": 0.05, "maniac": 0.04, "shark": 0.04}
AVATARS = {"station": "🐟", "tag": "🎯", "lag": "🔥", "nit": "🧊", "rock": "🗿",
           "whale": "🐳", "maniac": "🃏", "shark": "🦈", "hero": "🙂"}
NAME_POOL = [
    "Ava", "Ben", "Cleo", "Dex", "Eve", "Finn", "Gina", "Hugo", "Iris", "Jon", "Kai", "Lia", "Max",
    "Nia", "Oskar", "Pia", "Quin", "Rex", "Sara", "Tom", "Uma", "Vito", "Wim", "Xena", "Yuri", "Zoe",
    "Aron", "Bea", "Cem", "Dana", "Emil", "Fay", "Gus", "Hana", "Ivo", "Jule", "Karl", "Lena", "Milo",
    "Nora", "Otto", "Paul", "Rita", "Sam", "Tara", "Udo", "Vera", "Wolf", "Yara", "Zed", "Alma",
    "Bo", "Cato", "Dora", "Elan", "Fritz", "Greta", "Hans", "Ida", "Jo", "Kim", "Lou", "Mara",
]

# ---------------------------------------------------------------- ICM-Oekonomie (mtt_sim-Konstanten)
EXACT_ICM_AT = 12                  # ab hier ist die Bitmask-DP (2^n) exakt bezahlbar
BUBBLE_WINDOW_FACTOR = 1.6         # Druck-Fenster: paid < left <= paid*1.6 (mtt_sim.BUBBLE_WINDOW)
PRESSURE_CAP = 1.5
PRESSURE_SLOPE = 0.6               # mult = 1 + slope * Anteil gecoverter Gegner am Tisch
ICM_HINT_BF = 1.15                 # Berater zeigt den ICM-Hinweis erst ab diesem Bubble-Faktor


@dataclass
class Entrant:
    name: str
    profile: str                   # 'hero' oder ein PROFILES-Schluessel
    stack: int
    bot: SixMaxBot | None          # None = der Mensch
    alive: bool = True
    place: int | None = None

    @property
    def avatar(self) -> str:
        return AVATARS.get(self.profile, "🙂")


class TableHost:
    """Ein Tisch: Namensliste in Sitzordnung + Button-Gedaechtnis + stabile uid fuer Deck-Seeds."""

    __slots__ = ("uid", "names", "button_name", "hand_no")

    def __init__(self, uid: int, names: list[str]):
        self.uid = uid
        self.names = names
        self.button_name: str | None = None
        self.hand_no = 0


def field_counts(n_bots: int, mix: dict[str, float] = FIELD_MIX) -> dict[str, int]:
    """Groesste-Reste-Rundung der Profilanteile auf ganze Sitze (Summe exakt n_bots)."""
    raw = {p: n_bots * w for p, w in mix.items()}
    counts = {p: int(v) for p, v in raw.items()}
    rest = n_bots - sum(counts.values())
    for p in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[:rest]:
        counts[p] += 1
    return counts


def make_league_bot(profile: str, seed: int) -> SixMaxBot:
    """Liga-Bot wie im GTO-Modus des Trainers: Profil pur, Reads AUS, geseedetes Mixing."""
    bot = SixMaxBot(0, PROFILES[profile], seed=seed)
    bot._read = lambda obs: {}
    return bot


class MTT:
    """Zustand + Uhr eines Multi-Table-Turniers; der Trainer treibt es Runde fuer Runde."""

    def __init__(self, seed: int, hero_name: str = "You", hero_bot: SixMaxBot | None = None,
                 n_players: int = N_PLAYERS, seats_per_table: int = SEATS_PER_TABLE,
                 hands_per_level: int = HANDS_PER_LEVEL, start_stack: int = START_STACK):
        self.seed = seed
        self.rng = random.Random(seed * 7919 + 13)
        self.n_players, self.seats_per_table = n_players, seats_per_table
        self.hands_per_level, self.start_stack = hands_per_level, start_stack
        self.hero_name = hero_name
        self.entrants: dict[str, Entrant] = {}
        self._make_field(hero_bot)
        names = list(self.entrants)
        self.rng.shuffle(names)
        self.alive = list(names)
        # WHY Tisch-Index statt Namens-Offset als uid: die uid ist die sichtbare Tischnummer (1..6)
        # und der Deck-Seed-Anteil; ein Offset 0/10/20 zeigte "Tisch 11/6" im HUD.
        self.tables = [TableHost(i // seats_per_table, names[i:i + seats_per_table])
                       for i in range(0, len(names), seats_per_table)]
        self._next_uid = len(self.tables)
        self.next_place = n_players
        self.round_no = 0                  # Turnieruhr: eine Runde = eine Hand an jedem Tisch
        self.hero_place: int | None = None
        self.table_change: str | None = None   # einmalige UI-Meldung nach einem Hero-Umzug
        self.final_table_reached = False
        self.last_side_ms = 0.0            # Laufzeit der Nebentische in der letzten Runde
        self.side_tables_every = 1         # 2 = Nebentische nur jede 2. Hero-Hand (Laufzeit-Fallback)

    # ------------------------------------------------------------ Aufbau
    def _make_field(self, hero_bot: SixMaxBot | None) -> None:
        n_bots = self.n_players - 1
        pool = list(NAME_POOL)
        self.rng.shuffle(pool)
        profiles = [p for p, c in field_counts(n_bots).items() for _ in range(c)]
        self.rng.shuffle(profiles)
        self.entrants[self.hero_name] = Entrant(self.hero_name, "hero", self.start_stack, hero_bot)
        for i, prof in enumerate(profiles):
            name = pool[i] if i < len(pool) else f"Player{i}"
            self.entrants[name] = Entrant(name, prof, self.start_stack,
                                          make_league_bot(prof, self.seed * 104729 + i))

    # ------------------------------------------------------------ Zustand
    def level_index(self) -> int:
        return self.round_no // self.hands_per_level

    def level(self) -> BlindLevel:
        idx = self.level_index()
        if idx < len(MTT_LEVELS):
            return MTT_LEVELS[idx]
        last = MTT_LEVELS[-1]
        grow = LEVEL_EXTENSION_FACTOR ** (idx - len(MTT_LEVELS) + 1)
        bb = int(round(last.bb * grow / 100) * 100)
        return BlindLevel(bb // 2, bb, int(round(bb / 8 / 5) * 5))

    def hands_to_level(self) -> int:
        return self.hands_per_level - self.round_no % self.hands_per_level

    def prize_pool(self) -> float:
        return BUYIN * self.n_players

    def payouts(self) -> list[float]:
        """Top-9-Preisgelder; der Rundungsrest landet auf Platz 1, die Summe ist EXAKT der Pool."""
        pool = self.prize_pool()
        pays = [round(pool * p, 2) for p in PAYOUT_PCT_TOP9]
        pays[0] = round(pays[0] + pool - sum(pays), 2)
        return pays

    def payouts_remaining(self) -> list[float]:
        pays = self.payouts()
        return pays[: len(self.alive)] if len(self.alive) <= len(pays) else pays

    def over(self) -> bool:
        return len(self.alive) <= 1

    def hero_out(self) -> bool:
        return self.hero_place is not None

    def hero_host(self) -> TableHost | None:
        return next((h for h in self.tables if self.hero_name in h.names), None)

    def is_final_table(self) -> bool:
        return len(self.tables) == 1

    def rank_of(self, name: str) -> int:
        ranked = sorted(self.alive, key=lambda nm: -self.entrants[nm].stack)
        return ranked.index(name) + 1

    def avg_stack(self) -> float:
        return sum(self.entrants[nm].stack for nm in self.alive) / max(1, len(self.alive))

    def next_payout(self) -> tuple[int, float] | None:
        """Naechste Geldstufe (Platz, Betrag): fuer Platz p gilt Auszahlung, sobald <= p Spieler uebrig."""
        pays = self.payouts()
        left = len(self.alive)
        target = min(left - 1, len(pays)) if left > 1 else 1
        if target < 1:
            return None
        return target, pays[target - 1]

    # ------------------------------------------------------------ Tische
    def _deck_seed(self, host: TableHost) -> int:
        return self.seed * 1_000_003 + host.uid * 7919 + host.hand_no

    def build_table(self, host: TableHost) -> Table:
        """Frische Table fuer die naechste Hand dieses Tisches (Hero, falls anwesend, auf Sitz 0)."""
        names = list(host.names)
        if self.hero_name in names:                # Rotation erhaelt die Sitzreihenfolge
            k = names.index(self.hero_name)
            names = names[k:] + names[:k]
            host.names = names
        lv = self.level()
        t = Table(names, starting_stack=self.start_stack, sb=lv.sb, bb=lv.bb,
                  seed=self._deck_seed(host), human_seat=0,
                  stacks=[self.entrants[nm].stack for nm in names], ante=lv.ante, rebuy=False)
        # Button wandert ueber NAMEN (Sitze aendern sich mit Busts/Umzuegen; Director-Regel)
        btn = (names.index(host.button_name) + 1) % len(names) if host.button_name in names else 0
        t.button = btn - 1                         # start_hand rueckt +1 vor
        host.hand_no += 1
        return t

    def bots_for(self, table: Table) -> dict[int, SixMaxBot]:
        """Sitz -> Liga-Bot (Sitzindex je Hand gesetzt: das Initiative-Flag haengt daran — mtt_sim-Fund #4)."""
        out = {}
        for i, s in enumerate(table.seats):
            bot = self.entrants[s.name].bot
            if bot is not None:
                bot.seat = i
                out[i] = bot
        return out

    def start_stacks(self, table: Table) -> dict[str, int]:
        return {s.name: s.stack + s.committed_total for s in table.seats}

    def icm_ctx(self, table: Table, seat: int, aggressor: int | None,
                start_stacks: dict[str, int], pressure_cache: dict) -> dict | None:
        """obs['icm'] fuer EINEN Entscheider: exakt ab <= EXACT_ICM_AT Verbliebenen, im Geld-Bubble-
        Fenster nur der Druck-Multiplikator (exakte BFs unbezahlbar), sonst None (Chip-EV)."""
        left = len(self.alive)
        paid = len(PAYOUT_PCT_TOP9)
        if left <= EXACT_ICM_AT:
            others = [float(self.entrants[o].stack) for o in self.alive if o not in start_stacks]
            ctx = {"stacks": [float(start_stacks[s.name]) for s in table.seats] + others,
                   "payouts": self.payouts_remaining(), "seat": seat, "aggressor": aggressor,
                   "invested": {i: float(s.committed_total) for i, s in enumerate(table.seats)}}
            if seat not in pressure_cache:         # EINMAL pro Hand je Sitz, nur Tisch-Gegner
                table_v = [i for i in range(len(table.seats)) if i != seat]
                pressure_cache[seat] = icm_pressure_mult({"icm": ctx}, villains=table_v)
            ctx["pressure"] = True
            ctx["pressure_mult"] = pressure_cache[seat]
            return ctx
        if paid < left <= int(paid * BUBBLE_WINDOW_FACTOR):
            if seat not in pressure_cache:
                my = start_stacks[table.seats[seat].name]
                opp = [v for k, v in start_stacks.items() if k != table.seats[seat].name]
                covered = sum(1 for v in opp if v < my) / max(1, len(opp))
                pressure_cache[seat] = min(PRESSURE_CAP, 1.0 + PRESSURE_SLOPE * covered)
            return {"pressure": True, "pressure_mult": pressure_cache[seat]}
        return None

    def play_bot_hand(self, host: TableHost) -> list[tuple[str, int]]:
        """Eine komplette Hand nur mit Bots (Nebentisch oder Bots-only-Simulation). -> Busts."""
        t = self.build_table(host)
        t.start_hand()
        bots = self.bots_for(t)
        for b in bots.values():
            b.new_hand(list(range(t.n)))
        start = self.start_stacks(t)
        pressure_cache: dict = {}
        aggressor: int | None = None
        guard = 0
        while not t.hand_over and t.to_act is not None and guard < 300:
            guard += 1
            seat = t.to_act
            obs = t.obs_for(seat)
            ctx = self.icm_ctx(t, seat, aggressor, start, pressure_cache)
            if ctx is not None:
                obs["icm"] = ctx
            street, tc, pr = t.street, obs["to_call"], t.preflop_raises
            try:
                dec = bots[seat].decide(obs)
                action, amount = dec["action"], dec["amount"]
                t.act(action, amount)
            except Exception:  # noqa: BLE001 — ein Bot-Fehler killt kein Turnier (tourney.py-Muster)
                la = t.legal_actions()
                action = "check" if la.get("can_check") else ("call" if la.get("can_call") else "fold")
                t.act(action)
                amount = None
            if action in ("bet", "raise", "allin"):
                aggressor = seat
            for b in bots.values():
                b.observe(seat, street, "raise" if action == "allin" else action, tc, pr)
        return self.after_table_hand(t, host, start)

    def after_table_hand(self, table: Table, host: TableHost, start_stacks: dict[str, int]) -> list:
        """Stacks einsammeln, Button merken, Busts (Name, Start-Stack) melden — noch OHNE Platzvergabe."""
        host.button_name = table.seats[table.button].name
        busts = []
        for s in table.seats:
            self.entrants[s.name].stack = s.stack
            if s.stack <= 0:
                busts.append((s.name, start_stacks[s.name]))
        return busts

    # ------------------------------------------------------------ Runde + Balancing
    def _apply_busts(self, busts: list[tuple[str, int]]) -> None:
        """Globale Platzvergabe der Runde: kleinerer Start-Stack -> schlechterer Platz (Sklansky)."""
        for nm, _ in sorted(busts, key=lambda x: x[1]):
            e = self.entrants[nm]
            if not e.alive:
                continue
            e.alive = False
            e.place = self.next_place
            self.alive.remove(nm)
            if nm == self.hero_name:
                self.hero_place = self.next_place
            self.next_place -= 1
        if len(self.alive) == 1:
            w = self.entrants[self.alive[0]]
            w.place = 1
            if w.name == self.hero_name:
                self.hero_place = 1

    def _rebalance(self) -> None:
        """Kollaps auf ceil(alive/Sitze) Tische, dann Balance auf +-1 (Bewegung erst ab Differenz >= 2)."""
        before = self.hero_host()
        before_uid = before.uid if before else None
        alive_set = set(self.alive)
        for h in self.tables:
            h.names = [nm for nm in h.names if nm in alive_set]
        self.tables = [h for h in self.tables if h.names]
        target = max(1, -(-len(self.alive) // self.seats_per_table))
        while len(self.tables) > target:
            self.tables.sort(key=lambda h: len(h.names))
            dead = self.tables.pop(0)
            movers = list(dead.names)
            self.rng.shuffle(movers)
            for nm in movers:
                min(self.tables, key=lambda h: len(h.names)).names.append(nm)
        while self.tables:
            big = max(self.tables, key=lambda h: len(h.names))
            small = min(self.tables, key=lambda h: len(h.names))
            if len(big.names) - len(small.names) <= 1:
                break
            small.names.append(big.names.pop(self.rng.randrange(len(big.names))))
        after = self.hero_host()
        if after is not None and before_uid is not None and after.uid != before_uid:
            self.table_change = f"Table change: you're now seated at table {after.uid + 1}."
        if after is not None and self.is_final_table() and not self.final_table_reached:
            self.final_table_reached = True

    def play_side_tables(self) -> list[tuple[str, int]]:
        """Je eine Hand an jedem Tisch OHNE den Hero (die Turnieruhr laeuft ueberall gleich)."""
        t0 = time.perf_counter()
        busts: list[tuple[str, int]] = []
        for host in list(self.tables):
            if self.hero_name not in host.names and len(host.names) >= 2:
                busts.extend(self.play_bot_hand(host))
        self.last_side_ms = (time.perf_counter() - t0) * 1000
        return busts

    def advance_round(self, hero_busts: list[tuple[str, int]]) -> None:
        """Rundenschluss nach einer Hero-Hand: Nebentische spielen, Busts global, Balancing, Uhr +1."""
        side = self.play_side_tables() if self.round_no % self.side_tables_every == 0 else []
        self._apply_busts(list(hero_busts) + side)
        self._rebalance()
        self.round_no += 1

    def play_round_all(self) -> None:
        """Bots-only-Runde (Hero als Bot): alle Tische spielen, dann Busts/Balancing/Uhr (Tests)."""
        busts: list[tuple[str, int]] = []
        for host in list(self.tables):
            if len(host.names) >= 2:
                busts.extend(self.play_bot_hand(host))
        self._apply_busts(busts)
        self._rebalance()
        self.round_no += 1

    def total_chips(self) -> int:
        return sum(e.stack for e in self.entrants.values())

    # ------------------------------------------------------------ Hero-Berater (ICM-Brille)
    def hero_icm(self, table: Table, seat: int, aggressor: int | None,
                 start_stacks: dict[str, int], obs: dict) -> dict | None:
        """Bubble-Faktor + ICM-korrigierte Call-Schwelle des Heros — None, solange die exakte Rechnung
        unbezahlbar ist (> EXACT_ICM_AT Verbliebene) oder der BF unter ICM_HINT_BF liegt."""
        ctx = self.icm_ctx(table, seat, aggressor, start_stacks, {})
        if not ctx or "stacks" not in ctx:
            return None
        villain = pick_villain(ctx["stacks"], seat, aggressor)
        bf = bubble_factor(ctx["stacks"], ctx["payouts"], seat, villain)
        if bf == float("inf") or bf <= ICM_HINT_BF:
            return None
        to_call, pot = obs.get("to_call") or 0, obs.get("pot") or 0
        out = {"bf": round(bf, 2), "villain": table.seats[villain].name}
        if to_call > 0 and pot + to_call > 0:
            req = to_call / (pot + to_call)
            o = dict(obs, icm=ctx)
            req_icm = icm_scaled_req(req, o, to_call, pot)
            out["req_chip"] = round(req, 3)
            out["req_icm"] = round(req_icm, 3)
            out["text"] = (f"ICM: calling needs +{(req_icm - req) * 100:.0f} pp equity "
                           f"({req_icm:.0%} instead of {req:.0%}; bubble factor {bf:.2f} vs {out['villain']})")
        else:
            flip = icm_required_equity(0.5, bf)
            out["text"] = (f"ICM: bubble factor {bf:.2f} — a flip needs {flip:.0%}; "
                           f"fold equity is the protected kind of equity right now")
        return out

    # ------------------------------------------------------------ Simulation (Tests / Bots-only)
    def run_bots_only(self, max_rounds: int = MAX_ROUNDS, audit: bool = False) -> dict:
        """Ganzes Turnier ohne Menschen (Hero als Bot). -> Sieger, Plaetze, Runden."""
        if self.entrants[self.hero_name].bot is None:
            raise ValueError("run_bots_only requires a hero_bot")
        while not self.over() and self.round_no < max_rounds:
            self.play_round_all()
            if audit:
                self.audit_invariants()
        winner = self.alive[0] if self.alive else None
        return {"winner": winner, "rounds": self.round_no,
                "places": {nm: e.place for nm, e in self.entrants.items()}}

    def audit_invariants(self) -> None:
        total = self.total_chips()
        assert total == self.n_players * self.start_stack, f"Chip-Erhaltung verletzt: {total}"
        sizes = [len(h.names) for h in self.tables]
        if len(self.tables) > 1:
            assert min(sizes) >= 2, f"Tisch < 2 Spieler: {sizes}"
            assert max(sizes) - min(sizes) <= 1, f"Balance verletzt: {sizes}"
        assert sum(sizes) == len(self.alive), "Sitze != Ueberlebende"
        assert sorted(e.place for e in self.entrants.values() if e.place) == list(
            range(self.next_place + 1, self.n_players + 1)) or self.over(), "Platzvergabe lueckenhaft"
