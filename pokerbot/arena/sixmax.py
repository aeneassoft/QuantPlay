"""6-max No-Limit Hold'em decision logic: an independent, position-aware TAG core + per-seat PROFILES
+ an integrity-correct ONLINE exploiter.

INTEGRITY (this is load-bearing): every bot is its OWN agent. It decides from its OWN hole cards +
public info only, and its opponent reads are built ONLY from publicly observable actions — never hole
cards, never a shared/peeked state. Five bots may independently form the same read of a player; that is
convergent observation, not collusion.

Public API:
  * decide_6max(obs) -> dict   — the neutral TAG core (kept for tests / simple callers).
  * SixMaxBot(seat, knobs)     — a stateful agent: .new_hand(seats), .observe(...) per public action,
                                  .decide(obs). Holds a per-opponent model and exploits it (bounded,
                                  confidence-gated, so it never spews).
  * PROFILES                   — named knob sets: nit / tag / lag / station / maniac.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from pokerbot.engine.cards import hand_class
from pokerbot.engine.equity import equity_vs_class_range
from pokerbot.engine.evaluator import best_five_name
from pokerbot.strategy import postflop as pf
from pokerbot.strategy import preflop_gto
from pokerbot.strategy import preflop_strength as ps

OPEN_FRAC = {"EP": 0.16, "UTG": 0.16, "MP": 0.20, "HJ": 0.22, "CO": 0.28, "BTN": 0.48, "SB": 0.45, "BB": 1.0}
# Multiway-Label-Abbildung (7/8/9/10-max -> das 6-max-Vokabular der Kern-Tabellen). BEWUSST nur
# fuer die NEUEN Labels: jede 6-max-Position verhaelt sich byte-identisch zum vermessenen Anker.
# (Der Audit-Fund, dass "UTG" in OPEN_FRAC fehlt und darum 0.20 statt EP-0.16 oeffnet, bleibt
# ABSICHTLICH unangetastet - Anker-Schutz; als gegateter Re-Test in NOTES.md vermerkt.)
POS_FRAC_BUCKET = {"UTG+1": "EP", "UTG+2": "EP", "UTG+3": "EP", "LJ": "MP"}
POS_RFI_BUCKET = {"UTG+1": "UTG", "UTG+2": "UTG", "UTG+3": "UTG", "LJ": "HJ"}
EQ_ITERS = 400   # equity Monte-Carlo iterations for live play (snappy)


@dataclass
class Knobs:
    """A static per-seat profile. The neutral defaults reproduce the plain TAG core exactly."""
    name: str = "tag"
    open_mult: float = 1.0          # scales opening width by position
    tb_pct: float = 0.92            # percentile to 3-bet a single open for value
    fb_pct: float = 0.95            # percentile to 4-bet vs a 3-bet
    flat_hi: float = 0.34           # cap on flatting an open (curbs loose multiway)
    cont_lo: float = 0.18           # FLOOR on continuing vs a 3-bet (anti over-fold)
    value_eq: float = pf.VALUE_EQ   # postflop value-bet equity
    raise_eq: float = 0.74          # postflop raise-for-value equity
    bluff_mult: float = 1.0         # scales bluff frequency
    call_delta: float = 0.0         # bluff-catch bias: + folds more, - calls wider
    flat_guard: bool = False        # FLAT-FIX (2026-09-09): dominierte Offsuit-Broadways nie vs Open flatten


PROFILES = {
    "nit":     Knobs("nit",     open_mult=0.70, tb_pct=0.95, fb_pct=0.97, flat_hi=0.22, cont_lo=0.14, bluff_mult=0.4, call_delta=0.06),
    # FLAT-FIX ANGEWENDET (Tag sixmax-tag-flatfix-v1, 2026-09-09): pargate6 3x vs altem tag = +17,7±6,4 / +11,4±6,9 /
    # +19,2±7,0 bb/100 (2992 Decks je Lauf, gepoolt ~+16 bei ~4 SE). Alter Kern = Tag sixmax-tag-pre-flatfix.
    "tag":     Knobs("tag",     open_mult=1.00, tb_pct=0.92, fb_pct=0.95, flat_hi=0.34, cont_lo=0.18, bluff_mult=1.0, call_delta=0.0, flat_guard=True),
    # Kandidat (User-Fund 2026-09-09: A2o CO vs LJ-Open als "Call" — Perzentil 0,691 > Schwelle 0,665, weil das
    # Hot-and-Cold-Ranking Offsuit-Asse ueberschaetzt; Analyzer-Leak "Preflop-Caller-Linien"). Gate: pargate6.
    "tag_flatfix": Knobs("tag_flatfix", open_mult=1.00, tb_pct=0.92, fb_pct=0.95, flat_hi=0.34, cont_lo=0.18, bluff_mult=1.0, call_delta=0.0, flat_guard=True),
    "lag":     Knobs("lag",     open_mult=1.35, tb_pct=0.87, fb_pct=0.92, flat_hi=0.40, cont_lo=0.26, bluff_mult=1.7, call_delta=-0.03),
    "station": Knobs("station", open_mult=1.10, tb_pct=0.96, fb_pct=0.98, flat_hi=0.52, cont_lo=0.30, bluff_mult=0.4, call_delta=-0.10),
    "maniac":  Knobs("maniac",  open_mult=1.65, tb_pct=0.82, fb_pct=0.88, flat_hi=0.34, cont_lo=0.30, bluff_mult=2.4, call_delta=-0.05),
    # ---- HELD-OUT variants (distinct types the RL policy never trains against; the robustness eval league) ----
    "rock":    Knobs("rock",    open_mult=0.55, tb_pct=0.97, fb_pct=0.98, flat_hi=0.18, cont_lo=0.12, bluff_mult=0.2, call_delta=0.10),
    "whale":   Knobs("whale",   open_mult=1.20, tb_pct=0.97, fb_pct=0.98, flat_hi=0.65, cont_lo=0.35, bluff_mult=0.3, call_delta=-0.15),
    "shark":   Knobs("shark",   open_mult=1.15, tb_pct=0.89, fb_pct=0.93, flat_hi=0.36, cont_lo=0.24, bluff_mult=1.3, call_delta=-0.02),
    # ---- PUNISHER-Profile (Trainer-'punish'-Modus, 2026-08-03): jedes zielt auf ein GEMESSENES
    # Princedarkness-Leak (Linien-Sektion der 458 Ernst-Haende + Stress-Session, docs/STATE.md).
    # sheriff:      killt die Ein-Schlag-Fold-Equity-Maschine (+8.5bb/Versuch) — callt den ERSTEN Schlag
    #               sehr breit (call_delta -0.15), bluff-arm; sein Overbet-Einkommen stirbt, Value wird bezahlt.
    # iso_hammer:   bestraft Limps (19%) + breite Calls — oeffnet/isoliert sehr breit (1.5x), 3-bettet ab
    #               Top-16% (tb .84): er spielt aufgeblasene Poette mit dominierten Haenden.
    # value_press:  bestraft die leichten Call-downs (W$SD .39) — tight rein, DUENNE Value-Dauerfeuer
    #               (value_eq .54, raise_eq .66), bluff_mult .05: jede Bet ist echt, er zahlt trotzdem.
    # trap_nit:     gewinnt die RIESENPOETTE (Top-8-Poette = 350% seines Nettos) — steinhart preflop,
    #               eskaliert nur mit Monstern (raise_eq .85), gibt kleine Poette her (call_delta +.08).
    # blind_fighter: besteuert die breiten Opens + sein FvR 40 (callt 3-Bets zu breit) — 3-Bet-Maschine
    #               (tb .82/fb .90), foldet selbst nicht vs seine 3-Bet-Jams (cont_lo .30).
    "sheriff":       Knobs("sheriff",       open_mult=0.95, tb_pct=0.90, fb_pct=0.95, flat_hi=0.30, cont_lo=0.24, bluff_mult=0.3,  call_delta=-0.15),
    "iso_hammer":    Knobs("iso_hammer",    open_mult=1.50, tb_pct=0.84, fb_pct=0.92, flat_hi=0.22, cont_lo=0.26, bluff_mult=1.2,  call_delta=-0.03),
    "value_press":   Knobs("value_press",   open_mult=0.85, tb_pct=0.93, fb_pct=0.96, flat_hi=0.26, cont_lo=0.20, value_eq=0.54, raise_eq=0.66, bluff_mult=0.05, call_delta=-0.05),
    "trap_nit":      Knobs("trap_nit",      open_mult=0.60, tb_pct=0.96, fb_pct=0.97, flat_hi=0.20, cont_lo=0.16, raise_eq=0.85, bluff_mult=0.2,  call_delta=0.08),
    "blind_fighter": Knobs("blind_fighter", open_mult=1.10, tb_pct=0.82, fb_pct=0.90, flat_hi=0.24, cont_lo=0.30, bluff_mult=0.9,  call_delta=0.0),
}

# Sitzbelegung des Punishment-Tisches (Trainer-Modus 'punish'): 5 Jaeger, je ein gemessenes Leak.
PUNISHER_ASSIGN = {1: "sheriff", 2: "iso_hammer", 3: "value_press", 4: "trap_nit", 5: "blind_fighter"}


_FLAT_GUARD_MIN_KICKER = {"A": "T", "K": "T", "Q": "T", "J": "9"}   # Offsuit-Broadway braucht mindestens diesen Kicker
_RANK_ORDER = "23456789TJQKA"


def _dominated_offsuit(hc: str) -> bool:
    """A2o..A9o, K2o..K9o, Q2o..Q9o, J2o..J8o: vs eine Open-Range dominiert (jedes hoehere Ax/Kx schlaegt uns,
    Equity kaum realisierbar) — im Hot-and-Cold-Perzentil aber hoch gerankt. Suited + Paare unberuehrt."""
    if len(hc) != 3 or hc[2] != "o":
        return False
    hi, lo = hc[0], hc[1]
    need = _FLAT_GUARD_MIN_KICKER.get(hi)
    return need is not None and _RANK_ORDER.index(lo) < _RANK_ORDER.index(need)


def _eff_bb(obs: dict) -> float:
    return obs["my_stack"] / obs["bb"]


def _made_tier(hole, board, made: str) -> str:
    """Coarse made-hand strength so we never call down with underpairs (anti-spew).
    'strong' = two pair+, 'top' = top pair / overpair, 'weak' = underpair / middle-or-worse / air."""
    order = "23456789TJQKA"
    if made in ("Two Pair", "Three of a Kind", "Straight", "Flush", "Full House",
                "Four of a Kind", "Straight Flush"):
        return "strong"
    if made == "Pair" and board:
        top = max(order.index(c[0]) for c in board)
        if hole[0][0] == hole[1][0]:                       # pocket pair: over- vs under-pair
            return "top" if order.index(hole[0][0]) >= top else "weak"
        paired = [order.index(c[0]) for c in hole if any(c[0] == b[0] for b in board)]
        return "top" if paired and max(paired) >= top else "weak"
    return "weak"


_RNG = random.Random()  # persistent module rng -> REAL mixing for stateless callers


def seed_modul_rng(seed: int | None) -> None:
    """Macht die Modul-RNG (Pfad der zustandslosen Aufrufer, decide_6max) reproduzierbar — fuer gepaarte
    6-max-Laeufe (pargate6). Nicht aufrufen = das bisherige echte Mixing bleibt byte-identisch."""
    _RNG.seed(seed)


def _decide(obs: dict, k: Knobs, read: dict, aggressor: bool | None = None,
            rng: random.Random | None = None) -> dict:
    """Core decision, parametrized by a profile `k` and live exploit deltas `read`. `aggressor` = does this
    bot hold the preflop initiative (True=aggressor/c-bet role, False=caller/check-to-raiser, None=unknown).
    Step 4c: role-awareness fixes the measured over-donk (OOP 52% vs GTO 22%) + under-c-bet (IP 61% vs 73%)."""
    hole, board = obs["hole"], obs["board"]
    bb, to_call, pot = obs["bb"], obs["to_call"], obs["pot"]
    can_check, can_raise = obs["can_check"], obs["can_raise"]
    hc = hand_class(*hole)
    pct = ps.percentile(hc)
    eff = _eff_bb(obs)
    pos = obs["position"]
    if rng is None:          # per-spot reseed made every frequency deterministic per spot (fake mixing)
        rng = _RNG

    def raise_to(amount):
        lo, hi = obs["raise_min"], obs["raise_max"]
        return hi if lo is None else max(lo, min(int(amount), hi))

    def mk(action, amount, why):
        return {"action": action, "amount": amount,
                "rationale": {"hand": hc, "percentile": round(pct, 2), "pos": pos, "profile": k.name,
                              "eff_bb": round(eff, 1), "reasoning": why}}

    if not board:   # ---------------- PREFLOP ----------------
        if obs["preflop_raises"] == 0:        # unopened: open or fold
            frac = min(0.95, OPEN_FRAC.get(POS_FRAC_BUCKET.get(pos, pos), 0.2) * k.open_mult)
            if obs.get("icm") and obs["icm"].get("pressure"):
                # TURNIER-DRUCK (Doktrin 9): Gegner unter hohem BF gegen uns muessen folden -
                # der Coverstack erntet ihre Zwangs-Tightness als weitere Steals.
                from pokerbot.strategy.tournament import icm_pressure_mult
                frac = min(0.95, frac * icm_pressure_mult(obs))
            if eff <= 12 and pct >= 1 - frac * 0.8 and can_raise:
                return mk("raise", raise_to(obs["raise_max"]), f"Short-stack open-shove {hc} from {pos}.")
            rec = preflop_gto.rfi(POS_RFI_BUCKET.get(pos, pos), hc) if k.name == "tag" else None   # solver-distilled GTO open (deep)
            if rec is not None:                # GTO table is the neutral floor's open strategy (Step 4a)
                act = rec["action"]
                if act == "raise" and can_raise:
                    return mk("raise", raise_to(round(rec.get("raise_bb", 2.5) * bb)),
                              f"GTO open {hc} from {pos} (solver table, n={rec['n']}).")
                if act in ("fold", "check"):
                    return mk("check" if can_check else "fold", None, f"GTO fold {hc} from {pos} (solver table).")
                if act == "call" and obs.get("can_call"):
                    return mk("call", None, f"GTO complete {hc} from {pos} (solver table).")
            if pct >= 1 - frac:
                return mk("raise", raise_to(round(2.5 * bb)), f"Open {hc} from {pos} (top {int(frac*100)}%).")
            return mk("check" if can_check else "fold", None, f"{hc} below {pos} opening range.")
        # facing a raise: MDF/pot-odds defense with a FLOOR (don't over-fold to big 3bets) + CAP on flatting
        req = to_call / (pot + to_call) if to_call else 0
        if obs.get("icm") and to_call:
            # TURNIER: verlorene Chips zaehlen Bubble-Faktor-fach (Endgame-Doktrin). Der Aufschlag
            # sitzt exakt hier, weil ALLE Weiterspiel-Schwellen (cont/flat) aus req abgeleitet sind:
            # Call-Ranges schrumpfen automatisch staerker als Open-Ranges (Gap Concept).
            from pokerbot.strategy.tournament import icm_scaled_req
            req = icm_scaled_req(req, obs, to_call, pot)
        cur = obs.get("cur_bet", to_call)
        pos_bonus = 0.06 if pos in ("BTN", "CO") else 0.0
        if obs["preflop_raises"] >= 2:                      # facing a 3bet+ (we likely opened)
            if pct >= k.fb_pct and can_raise:
                return mk("raise", raise_to(round(cur + 1.0 * (pot + to_call))), f"4-bet for value with {hc}.")
            cont = max(k.cont_lo, min(0.40, 0.55 - 1.1 * req)) + pos_bonus + read.get("cont_bonus", 0.0)
            if obs["can_call"] and pct >= 1 - cont:
                return mk("call", None, f"Continue {hc} vs 3bet (Top {int(cont*100)}%{read.get('tag','')}).")
            return mk("check" if can_check else "fold", None, f"Fold {hc} vs the 3bet.")
        if pct >= k.tb_pct and can_raise:                   # vs a single open: value 3-bet the top
            return mk("raise", raise_to(round(cur + 1.0 * (pot + to_call))), f"3-bet for value with {hc}.")
        flat = max(0.12, min(k.flat_hi, 0.80 - 1.6 * req)) + pos_bonus + read.get("flat_bonus", 0.0)
        if obs["can_call"] and pct >= 1 - flat and not (k.flat_guard and _dominated_offsuit(hc)):
            return mk("call", None, f"Flat {hc} vs open (Top {int(flat*100)}%).")
        return mk("check" if can_check else "fold", None, f"Fold {hc} vs the open.")

    # ---------------- POSTFLOP ----------------
    n_opp = max(1, obs["n_active"] - 1)
    base = 0.55 if n_opp == 1 else max(0.18, 0.55 - 0.12 * (n_opp - 1))
    if to_call > 0:
        r = to_call / (pot + to_call)
        sf = {"flop": 0.9, "turn": 0.75, "river": 0.6}.get(obs["street"], 1.0)
        base = max(0.06, base * sf * (1.0 - 0.7 * r))       # bigger bet + later street -> narrower range
    opp_range = list(ps.range_top(base))
    eq = equity_vs_class_range(hole, opp_range, board, iters=EQ_ITERS, rng=rng)
    made = best_five_name(board, hole)
    tier = _made_tier(hole, board, made)
    fm = pf.PriorFoldModel()
    hero_committed = obs.get("my_committed_street", 0)
    texd = pf.classify_board(board)
    scare = texd["monotone"] or (texd["connected"] and len(board) >= 4)

    if to_call > 0:
        req = to_call / (pot + to_call)
        if obs.get("icm"):
            from pokerbot.strategy.tournament import icm_scaled_req
            req = icm_scaled_req(req, obs, to_call, pot)
        thresh = req + (0.10 if scare else -0.05)
        if made == "High Card":
            thresh = req + 0.08
        if tier == "weak" and made != "High Card":          # underpair / weak pair: don't call down
            thresh = max(thresh, req + 0.12)
            if obs["street"] in ("turn", "river"):
                thresh += 0.06
        thresh += k.call_delta + read.get("call_delta", 0.0)  # profile + live read (bluff-catch bias)
        if eq >= k.raise_eq and can_raise and tier in ("strong", "top"):
            return mk("raise", raise_to(obs.get("cur_bet", to_call) + round(0.8 * (pot + to_call))),
                      f"Raise for value ({eq:.0%} vs {n_opp}). {made}.")
        if eq >= thresh:
            return mk("call", None, f"Call: {eq:.0%} (Pot-Odds {req:.0%}{read.get('tag','')}). {made}.")
        return mk("fold", None, f"Fold: {eq:.0%} < {thresh:.0%}. {made}.")

    if not can_raise:
        return mk("check", None, "Check.")
    if aggressor is False:                      # caller w/o initiative: check to the raiser; donk ~GTO 22%
        if eq >= 0.62 and rng.random() < 0.45:
            to, _, _ = pf.pick_value_size(pot, fm, obs["street"], hero_committed, obs["my_stack"], eq)
            return mk("raise", raise_to(to or obs["raise_min"]), f"Donk for value ({eq:.0%}). {made}.")
        return mk("check", None, f"Check to the raiser ({eq:.0%}, {made}).")
    if aggressor is True and len(board) == 3:   # aggressor flop: texture-conditioned c-bet to GTO frequency
        f_cbet, size = pf.cbet_policy(board, ip=True)
        if eq >= 0.72 or rng.random() < f_cbet:
            return mk("raise", raise_to(round(size * pot) or obs["raise_min"]),
                      f"C-bet (texture {int(f_cbet*100)}%, {eq:.0%}). {made}.")
        return mk("check", None, f"Check back ({eq:.0%}, {made}).")
    if eq >= k.value_eq:                         # turn/river aggressor, or unknown role: value + bluff
        to, _, sf = pf.pick_value_size(pot, fm, obs["street"], hero_committed, obs["my_stack"], eq)
        return mk("raise", raise_to(to or obs["raise_min"]), f"Value bet ({eq:.0%} vs {n_opp}). {made}.")
    bluff_freq = (0.25 if n_opp == 1 else 0.10) * k.bluff_mult * read.get("bluff_mult", 1.0)
    bluff_freq = max(0.0, min(0.85, bluff_freq))
    if eq <= pf.BLUFF_EQ and rng.random() < bluff_freq:
        return mk("raise", raise_to(round(0.55 * pot) or obs["raise_min"]),
                  f"Bluff ~55% pot ({eq:.0%}); FE vs {n_opp}{read.get('tag','')}. {made}.")
    return mk("check", None, f"Check ({eq:.0%}, {made}).")


def decide_6max(obs: dict) -> dict:
    """Neutral TAG core — unchanged behaviour, kept for tests and simple callers."""
    return _decide(obs, PROFILES["tag"], {})


# ---------------------------------------------------------------- online opponent model + agent
@dataclass
class OppModel:
    hands: int = 0
    vpip: int = 0
    pfr: int = 0
    tb: int = 0          # 3-bets made
    tb_opp: int = 0      # times faced a raise preflop and could 3-bet
    faced_bet: int = 0   # postflop decisions facing a bet
    fold_bet: int = 0    # of those, folded
    agg: int = 0         # postflop bets/raises
    agg_opp: int = 0     # postflop voluntary actions

    def fold_to_bet(self):
        return self.fold_bet / self.faced_bet if self.faced_bet >= 8 else None

    def threebet(self):
        return self.tb / self.tb_opp if self.tb_opp >= 6 else None

    def aggression(self):
        return self.agg / self.agg_opp if self.agg_opp >= 8 else None


class SixMaxBot:
    """One independent seat: a profile + an opponent model built only from observed public actions."""

    def __init__(self, seat: int, knobs: Knobs, seed: int | None = None):
        self.seat = seat
        self.k = knobs
        # one persistent rng per seat -> real mixing; seed=None (Default) = unveraendert nicht-deterministisch,
        # ein Seed macht die Entscheidungsfolge reproduzierbar (gepaarte 6-max-Gates, pargate6).
        self.rng = random.Random(seed)
        self.opp: dict[int, OppModel] = defaultdict(OppModel)
        self._new_hand_state([])

    def _new_hand_state(self, seats):
        self.active = set(seats)
        self.cur_agg = None         # last aggressor on the current street (who we'd be facing)
        self.pf_aggressor = None    # last seat to raise preflop = who holds postflop initiative
        self._street = "preflop"
        self._vpip_done = set()
        self._pfr_done = set()

    def new_hand(self, seats):
        self._new_hand_state(seats)
        for s in seats:
            if s != self.seat:
                self.opp[s].hands += 1

    def observe(self, actor: int, street: str, action: str, to_call: int, preflop_raises: int):
        """Feed ONE public action (any seat). Only public info — no hole cards."""
        if street == "preflop" and action == "raise":
            self.pf_aggressor = actor       # postflop initiative = last preflop raiser (self or other)
        if actor == self.seat:
            if action in ("bet", "raise"):
                self.cur_agg = actor
            return
        if street != self._street:                 # new street -> reset who's the aggressor
            self._street = street
            self.cur_agg = None
        m = self.opp[actor]
        if street == "preflop":
            if action in ("call", "raise") and actor not in self._vpip_done:
                m.vpip += 1
                self._vpip_done.add(actor)
            if action == "raise" and actor not in self._pfr_done:
                m.pfr += 1
                self._pfr_done.add(actor)
            if preflop_raises >= 1:                 # a raise was already in: this is a 3bet spot
                m.tb_opp += 1
                if action == "raise":
                    m.tb += 1
        else:
            if to_call > 0:
                m.faced_bet += 1
                if action == "fold":
                    m.fold_bet += 1
            if action in ("bet", "raise", "call", "check"):
                m.agg_opp += 1
                if action in ("bet", "raise"):
                    m.agg += 1
        if action in ("bet", "raise"):
            self.cur_agg = actor
        if action == "fold":
            self.active.discard(actor)

    def _read(self, obs: dict) -> dict:
        """Bounded, confidence-gated exploit deltas vs the relevant target. Empty => play the profile."""
        read: dict = {}
        board = obs["board"]
        n_opp = max(1, obs["n_active"] - 1)
        if not board:
            if obs["preflop_raises"] >= 2 and self.cur_agg is not None:   # facing a 3bet: who 3bet a lot?
                tb = self.opp[self.cur_agg].threebet()
                if tb is not None and tb > 0.11:
                    read["cont_bonus"] = min(0.15, (tb - 0.08) * 1.4)     # continue wider vs a 3bet-bluffer
                    read["tag"] = " · vs 3bet-happy"
            return read
        if obs["to_call"] > 0 and self.cur_agg is not None:               # facing a bet: how bluffy is he?
            ag = self.opp[self.cur_agg].aggression()
            if ag is not None:
                if ag > 0.55:
                    read["call_delta"] = -0.07; read["tag"] = " · bluff-catch vs aggro"
                elif ag < 0.30:
                    read["call_delta"] = 0.07; read["tag"] = " · he only value-bets"
        elif obs["to_call"] == 0 and n_opp == 1:                          # we can bet: does he over-fold?
            others = [s for s in self.active if s != self.seat]
            if len(others) == 1:
                f = self.opp[others[0]].fold_to_bet()
                if f is not None:
                    if f > 0.55:
                        read["bluff_mult"] = min(2.2, 1.0 + (f - 0.45) * 3); read["tag"] = " · he over-folds"
                    elif f < 0.30:
                        read["bluff_mult"] = 0.4; read["tag"] = " · station, no bluff"
        return read

    def decide(self, obs: dict) -> dict:
        aggr = (self.pf_aggressor == self.seat) if obs.get("board") else None
        return _decide(obs, self.k, self._read(obs), aggressor=aggr, rng=self.rng)
