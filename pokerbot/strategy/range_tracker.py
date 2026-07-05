"""MVP#2 P0: range tracker — reconstruct BOTH players' ranges at the current public node so the resolver
solves the actual public STATE, not just our hand.

v2 (2026-06-15): per-combo Bayesian tracker, grounded in the 4-API consult (o3 + gpt + Claude + Perplexity,
`docs/range_tracker_consult_*.md`). Design = o3's PROVABLY-SAFE v0 + Claude's confidence gate:

  range_next(h) ∝ range_prev(h) · policy(observed_action | state, h)

The blueprint (advisor) only gives P(bet) (bet-vs-check), so the policy is INCOMPLETE. The safety theorem
(o3): only reweight where we have a real model (bet/check via the advisor); for the SILENT actions
(call / raise / bet-size) do a *legality-only* update (multiply by 1, never by 0 unless a card is
logically impossible). Then `‖tracked − true‖₁` can only shrink, so the worst-case extra exploitability the
tracker can inject is bounded by (CapPot/2)·L1 — whereas a *badly narrowed* range (zeroing a live combo) is
unbounded-worse than the floor. "Do nothing unless certain" is the safe default.

Fidelity budget (o3 bound: villain-range L1 error costs ≤ (CapPot/2)·L1; own-range error is loose / often
zero for the actually-held card on the river) → spend it on the VILLAIN range.

v1 (preflop-only class-sets) is preserved below as `river_ranges` (the resolver's current fallback). HU only.
"""
from __future__ import annotations

from collections import defaultdict

from pokerbot.engine.cards import hand_class
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy import ranges as R

# ----------------------------------------------------------------------------- v1 (preserved fallback)


def _preflop_raises(state) -> int:
    return sum(1 for h in state.get("history", [])
               if h.get("street") == "preflop" and h.get("action") in ("bet", "raise", "allin"))


def _seat_classes(is_button: bool, raises: int):
    if raises >= 2:
        return ps.range_top(0.18)                 # 3-bet+ pot (tighter; approximate)
    if raises == 1:
        return R.sb_open() if is_button else R.bb_defend()   # SRP: button opened, BB defended
    return ps.range_top(0.85)                     # limped / unopened (wide)


def river_ranges(state) -> tuple[str, str]:
    """v1 (preserved): -> (oop_range_str, ip_range_str) as TexasSolver class strings, preflop-line-aware only.
    BB (non-button) = OOP postflop, SB/BTN (button) = IP. The resolver's current fallback when the v2 tracker's
    confidence is too low."""
    raises = _preflop_raises(state)
    oop = ",".join(sorted(_seat_classes(False, raises)))   # BB
    ip = ",".join(sorted(_seat_classes(True, raises)))     # button
    return oop, ip


# ----------------------------------------------------------------------------- v2 (per-combo Bayesian tracker)

WEIGHT_FLOOR = 1e-6        # prune microscopic mass (o3: avoid numerical cancellation), renormalise
EMIT_FLOOR = 1e-4         # don't emit combos below this weight into the solver string
CONF_THRESHOLD = 0.5      # resolver gate: min(conf_oop, conf_ip) below this -> fall back to floor (Claude)

# ---- S2 (plan 2026-07-04): the two measured defects behind "the resolver fires 93% on a WRONG equilibrium" ----
# (a) INVERSION: the advisor's p_bet is a MARGINAL bet-frequency; applying it multiplicatively per street
#     compounds correlated evidence — after check/check a strong combo (p~0.9) is x0.01'd away, so the tracked
#     range INVERTS toward air and the resolver over-bluffs/over-thin-values. Damping: d *= p^ALPHA (ALPHA<1
#     softens each update while keeping its direction). Default 1.0 = today's behavior, byte-identical.
# (b) DEAD GATE: confidence = 1 - 0.5*heur_ratio floors at exactly 0.5 — and `rconf < CONF_THRESHOLD(=0.5)`
#     PASSES at 0.5, so even a 100%-unmodeled reconstruction was trusted. A steeper slope (0.7) gates
#     heur_ratio >= ~0.72 reconstructions. Default 0.5 = today's behavior, byte-identical.
# Both flipped by the GTOW-mode profile (gto_mode.PROFILE); overridable per-arm for the A/B.
from pokerbot.strategy.gto_mode import flag as _flag
TRACKER_ALPHA = float(_flag("POKERB_TRACKER_ALPHA", "1.0"))
TRACKER_CONF_SLOPE = float(_flag("POKERB_TRACKER_CONF_SLOPE", "0.5"))
# Aggression-conditional damping override (the Kc3h 200bb stack-off fix, 2026-07-05): the alpha damping was built
# against the check/check OVER-narrowing — but it also under-narrows vs MULTI-STREET AGGRESSION (bluffs stay in the
# barreler's range -> hero's bluffcatch equity over-rated -> the fat-tail call-downs; measured: PRINCE folds the
# river with alpha=1, calls with alpha=0.5). From the seat's 2nd aggressive POSTFLOP action on, believe the
# narrowing fully (alpha -> 1): repeated barrels are exactly where the marginal-frequency evidence stops being
# "correlated noise" and starts being a story.
TRACKER_AGGRO_FULL = _flag("POKERB_TRACKER_AGGRO_FULL", "0") == "1"
# v3.3 (2026-07-05): a raise FACING A BET was legality-only (the provably-safe v0 default) — but that leaves a
# check-raise-JAM range as wide as before the raise, so hero's bluffcatch equity is a fiction (RANK4: 30/30
# seeds called a 4bet-pot turn jam with K2o at "37%" vs a range that is really ~62% two-pair+). Reweight the
# raiser's range toward GTOW's MINED raise-range class mix (research/raise_mine.py; 488 raises / 17,132 logged
# hands, both holes always logged = exact). Flag value = blend strength lambda in (0,1]: weight *= (target_share
# / current_share)^lambda per made-hand class; lambda=1 reproduces the mined mix exactly. Never zeroes a combo
# (every class has nonzero mined share) -> the o3 safety bound's "never multiply by 0" is respected.
RAISE_NARROW = float(_flag("POKERB_RAISE_NARROW", "0"))
# AUDIT-FIX bundle member (2026-07-05): count a raise-facing-bet as the seat's aggressive action for the
# TRACKER_AGGRO_FULL alpha escalation, whether or not the v3.3 mix model applies (see _update_action).
AUDIT_FIX = _flag("POKERB_AUDIT_FIX", "0") == "1"
# Mined targets (data/freq_targets/gtow_raise_ranges.json, pooled): jams pooled across streets (n=29 — small,
# but the classes agree: nutted); normal/huge raises pooled per street (huge folded into normal: river-huge is
# AIR-heavy 47%, so treating it as normal is the conservative side).
RAISE_MIX = {
    "flop":  {"air": 0.529, "two-pair+": 0.160, "pair": 0.160, "top-pair": 0.137, "monster": 0.015},
    "turn":  {"air": 0.333, "two-pair+": 0.271, "pair": 0.188, "top-pair": 0.125, "monster": 0.083},
    "river": {"two-pair+": 0.350, "air": 0.210, "monster": 0.210, "pair": 0.130, "top-pair": 0.100},
}
RAISE_MIX_JAM = {"two-pair+": 0.414, "monster": 0.207, "pair": 0.172, "top-pair": 0.138, "air": 0.069}


def _board_at(board: list[str], street: str) -> list[str]:
    n = {"flop": 3, "turn": 4, "river": 5}.get(street, len(board))
    return list(board[:n])


def _combo_str(combo) -> str:
    return combo[0] + combo[1]


class RangeTracker:
    """Per-combo Bayesian range tracker for HU. Walks the postflop betting line and reweights each player's
    1326-combo range by the observed action's likelihood — via the advisor for bet/check, legality-only for the
    silent actions (provably safe). Emits TexasSolver per-combo weighted-range strings + a confidence score."""

    def __init__(self, advisor=None):
        # advisor: a module/obj exposing p_bet(hole, board, role, street)->float|None and available(street).
        # None -> lazy-load pokerbot.strategy.advisor (degrades to legality-only if torch/model absent).
        if advisor is None:
            try:
                from pokerbot.strategy import advisor as _adv
                advisor = _adv
            except Exception:  # noqa: BLE001
                advisor = None
        self.adv = advisor
        self.range: dict[int, dict] = {}      # seat -> {combo(tuple): weight}
        self.heur: dict[int, int] = {0: 0, 1: 0}   # # of silent/unmodeled updates applied to each seat
        self.total: dict[int, int] = {0: 0, 1: 0}  # # of postflop updates applied to each seat
        self.aggro: dict[int, int] = {0: 0, 1: 0}  # # of postflop aggressive actions per seat (alpha escalation)

    # ---- construction -------------------------------------------------------
    def _init_preflop(self, state) -> None:
        raises = _preflop_raises(state)
        button = state["button"]
        for seat in (0, 1):
            classes = _seat_classes(seat == button, raises)
            combos = R.combos_for_classes(classes, [])     # dead-card removal happens per street below
            self.range[seat] = {c: 1.0 for c in combos}
            self._normalize(seat)

    def _p_bet(self, seat, combo, board, role, street):
        """Advisor P(bet) for a combo, or None if unavailable (-> caller does a legality-only update)."""
        if self.adv is None or not self.adv.available(street):
            return None
        try:
            return self.adv.p_bet([combo[0], combo[1]], board, role, street)
        except Exception:  # noqa: BLE001
            return None

    def _p_call(self, seat, combo, board, role, street, size_faced: float = 0.66):
        """KEYSTONE: defense-advisor P(call | facing a ~size_faced-pot bet) for a combo, or None (-> legality-only).
        Narrows the opponent's range on a CALL (the missing piece that gives the resolver correct-er ranges).
        ALL streets (the defense advisor is now multi-street: flop+turn+river, retrained 2026-06-16). size_faced
        default = a typical c-bet; the ACTUAL size is not threaded yet — at a too-small queried size the range only
        errs WIDE (o3-safe), and the range-L1 gate (`extraction/check_range_l1.py`) measures whether threading the
        real size is needed before adding that complexity."""
        adv = self.adv
        if street not in ("flop", "turn", "river") or adv is None or not getattr(adv, "defense_available", lambda: False)():
            return None
        try:
            pd = adv.p_defense([combo[0], combo[1]], board, role, size_faced, street)
            return pd[1] if pd else None      # P_call
        except Exception:  # noqa: BLE001
            return None

    def _role(self, seat, state) -> str:
        return "IP" if seat == state["button"] else "OOP"

    def _normalize(self, seat) -> None:
        d = self.range[seat]
        s = sum(d.values())
        if s <= 0:
            return
        for c in list(d.keys()):
            w = d[c] / s
            if w < WEIGHT_FLOOR:
                del d[c]
            else:
                d[c] = w
        # renormalise after the floor prune
        s2 = sum(self.range[seat].values())
        if s2 > 0:
            for c in self.range[seat]:
                self.range[seat][c] /= s2

    def _remove_dead(self, dead) -> None:
        dead = set(dead)
        for seat in (0, 1):
            d = self.range[seat]
            for c in list(d.keys()):
                if c[0] in dead or c[1] in dead:
                    del d[c]
            self._normalize(seat)

    def _update_action(self, seat, action, facing, board, role, street, size_cls=None) -> None:
        """Reweight `seat`'s range by the likelihood of the observed action.
        bet/check (not facing) -> advisor P(bet); call -> defense advisor P(call); raise/allin facing a bet ->
        the mined GTOW raise-mix reweight under RAISE_NARROW (else legality-only; o3-safe). Fold ends the hand
        (not seen in a live line). Counts silent updates for conf. size_cls: 'jam'|'normal' from the build walk."""
        d = self.range[seat]
        self.total[seat] += 1
        if action in ("bet",) and not facing:
            # aggression-conditional damping: the seat's 2nd+ postflop aggressive action narrows at FULL strength
            # (alpha=1) under TRACKER_AGGRO_FULL — repeated barrels are a story, not correlated noise.
            alpha = 1.0 if (TRACKER_AGGRO_FULL and self.aggro.get(seat, 0) >= 1) else TRACKER_ALPHA
            self.aggro[seat] = self.aggro.get(seat, 0) + 1
            modeled = False
            for c in list(d.keys()):
                p = self._p_bet(seat, c, board, role, street)
                if p is not None:
                    d[c] *= max(0.0, min(1.0, p)) ** alpha
                    modeled = True
            if not modeled:
                self.heur[seat] += 1          # advisor absent -> legality-only -> unmodeled
        elif action == "check" and not facing:
            modeled = False
            for c in list(d.keys()):
                p = self._p_bet(seat, c, board, role, street)
                if p is not None:
                    d[c] *= max(0.0, min(1.0, 1.0 - p)) ** TRACKER_ALPHA
                    modeled = True
            if not modeled:
                self.heur[seat] += 1
        elif action == "call" and facing:
            # KEYSTONE: narrow the range on a CALL via the defense advisor's P(call). ALL streets now (the defense
            # advisor is multi-street as of 2026-06-16) — turn/river calls used to fall to legality-only (too-wide
            # ranges = the resolver-neutral leak this fixes). This is what gives the resolver correct-er ranges.
            modeled = False
            for c in list(d.keys()):
                pc = self._p_call(seat, c, board, role, street)
                if pc is not None:
                    d[c] *= max(0.0, min(1.0, pc)) ** TRACKER_ALPHA
                    modeled = True
            if not modeled:
                self.heur[seat] += 1
        elif action in ("raise", "allin") and facing:
            # AUDIT FIX (POKERB_AUDIT_FIX): a raise IS the seat's aggressive action — TRACKER_AGGRO_FULL's own
            # contract says "from the 2nd aggressive POSTFLOP action on", but the bump only existed inside the
            # v3.3 branch, so under v3-shipped a check-raise-then-barrel line stayed alpha-damped (the Kc3h
            # class). Count it here regardless of whether the mix model applies.
            if AUDIT_FIX:
                self.aggro[seat] = self.aggro.get(seat, 0) + 1
            if (RAISE_NARROW > 0 and street in RAISE_MIX
                    and self._narrow_raise(seat, board, street, size_cls)):
                # v3.3: reweighted toward the mined GTOW raise mix = a MODELED update (no heur bump)
                if not AUDIT_FIX:
                    self.aggro[seat] = self.aggro.get(seat, 0) + 1   # pre-bundle v3.3 semantics
            else:
                self.heur[seat] += 1                                 # legality-only (provably safe)
        else:
            # other silent actions (an unmodeled size): legality-only (provably safe).
            self.heur[seat] += 1
        self._normalize(seat)

    def _narrow_raise(self, seat, board, street, size_cls) -> bool:
        """Blend `seat`'s class mix toward the mined raise-range target: weight *= (target/current)^lambda per
        made-hand class. True iff applied (guards: empty range / no class overlap -> caller falls to heur)."""
        from pokerbot.engine.evaluator import made_class
        d = self.range[seat]
        if not d:
            return False
        target = RAISE_MIX_JAM if size_cls == "jam" else RAISE_MIX[street]
        cls_of, mass = {}, defaultdict(float)
        for c in d:
            cls_of[c] = made_class(list(board), list(c))
            mass[cls_of[c]] += d[c]
        total = sum(mass.values())
        avail = {k: v for k, v in target.items() if mass.get(k, 0.0) > 0.0}
        z = sum(avail.values())
        if total <= 0 or z <= 0:
            return False
        for c in d:
            cls = cls_of[c]
            if cls in avail:
                ratio = (avail[cls] / z) / (mass[cls] / total)
                d[c] *= ratio ** RAISE_NARROW
            # a class outside the mined mix keeps its weight: never zero a live combo (the o3 bound)
        return True

    def build(self, state) -> "RangeTracker":
        """Walk preflop priors + the postflop betting line, reweighting both seats' ranges. Defensive: any
        malformed history -> the partial result stands and confidence() will be low (-> resolver gates to floor)."""
        self._init_preflop(state)
        board = state.get("board", [])
        history = state.get("history", []) or []
        try:
            cur_street = None
            street_bet = 0          # outstanding amount to call on the current street (0 = no bet yet)
            # commitment walk for the v3.3 jam read: blinds are absorbed into commitments (no history rows);
            # 'to' on aggressive rows = the street-CUMULATIVE round level (engine + gtowizard parity, verified)
            bb = float(state.get("bb", 100))
            btn = state.get("button", 0)
            players = state.get("players", [])
            starts = {s: float(players[s].get("stack", 0)) + float(players[s].get("committed_total", 0))
                      for s in (0, 1)} if len(players) >= 2 else {0: float("inf"), 1: float("inf")}
            committed = {btn: bb / 2.0, 1 - btn: bb}
            round_c = dict(committed)
            for h in history:
                act = h.get("action")
                if act == "deal":
                    st = h.get("street")
                    if st in ("flop", "turn", "river"):
                        cur_street = st
                        street_bet = 0
                        self._remove_dead(_board_at(board, st))
                    round_c = {0: 0.0, 1: 0.0}               # new betting round
                    continue
                seat = h.get("player")
                if seat not in (0, 1):
                    continue
                size_cls = None
                if act in ("bet", "raise", "allin"):
                    to = float(h.get("to") or h.get("amount") or 0.0)
                    inc = max(0.0, to - round_c[seat])
                    # a missing amount degrades to inc=0 -> 'normal' (never a false jam read)
                    size_cls = "jam" if committed[seat] + inc >= starts[seat] - 1.0 else "normal"
                    committed[seat] += inc
                    round_c[seat] = max(round_c[seat], to)
                elif act == "call":
                    lvl = max(round_c.values())
                    committed[seat] += max(0.0, lvl - round_c[seat])
                    round_c[seat] = lvl
                if cur_street is None or h.get("street") != cur_street:
                    continue
                if act not in ("bet", "raise", "allin", "check", "call", "fold"):
                    continue
                facing = street_bet > 0
                if act != "fold":
                    self._update_action(seat, act, facing, _board_at(board, cur_street),
                                        self._role(seat, state), cur_street, size_cls)
                # track the outstanding bet within the street
                if act in ("bet", "raise", "allin"):
                    street_bet = max(street_bet, h.get("to") or h.get("amount") or 1)
                elif act == "call":
                    street_bet = 0     # call closes the action level (HU)
        except Exception:  # noqa: BLE001
            pass
        return self

    # ---- outputs ------------------------------------------------------------
    def confidence(self, seat) -> float:
        """Trust in seat's reconstructed range, in [0.2, 1.0]: decays with the share of silent/unmodeled
        updates (heuristic ratio), capped low only on a genuinely COLLAPSED range. Collapse is measured by
        the EFFECTIVE combo count (inverse Herfindahl), NOT an absolute per-combo-weight threshold — a wide
        range has tiny per-combo weights (~1/N) by construction, so an absolute threshold falsely flags it.
        Over-narrowing (small eff) is the real danger (o3); a too-WIDE range is safe (just conservative)."""
        d = self.range.get(seat, {})
        if not d:
            return 0.0
        eff = 1.0 / sum(w * w for w in d.values())   # inverse Herfindahl = effective #combos (N for uniform)
        heur_ratio = self.heur[seat] / max(1, self.total[seat])
        # slope 0.5 floors at exactly CONF_THRESHOLD -> `< 0.5` passes even a 100%-unmodeled reconstruction
        # (the DEAD gate). The GTOW-mode slope 0.7 gates heur_ratio >= ~0.72 (S2, plan 2026-07-04).
        conf = 1.0 - TRACKER_CONF_SLOPE * heur_ratio
        if eff < 10:                                 # range collapsed to a handful of combos -> distrust
            conf = min(conf, 0.4)
        return max(0.2, min(1.0, conf))

    def emit(self, seat, dead) -> str:
        """seat's range as a TexasSolver CLASS-level weighted string ('AQs:0.62,KQo:0.31,...').

        IMPORTANT (verified 2026-06-15, against the consult's wrong consensus): TexasSolver v0.2.0 does NOT
        usably accept PER-COMBO range strings ('AsKh:0.6') — the solve produces an EMPTY/failed per-combo
        strategy dump, so `strategy_for` can't read our action. CLASS-level weighted strings work (the solver
        expands internally + keys the dump per-combo, so the lookup still works). We therefore keep the tracker
        per-combo internally (advisor P(bet) + exact dead-card removal) but AGGREGATE to class-mean weights on
        emit. Cost: within-class weight variation is lost; the solver still does per-card removal during the
        solve. Weights are normalised to max=1 (TexasSolver weights are relative within a range)."""
        dead = set(dead)
        cls_w: dict[str, list] = defaultdict(list)
        for c, w in self.range.get(seat, {}).items():
            if c[0] in dead or c[1] in dead:        # exact per-combo dead-card removal (drops 1..3 of a class)
                continue
            cls_w[hand_class(c[0], c[1])].append(w)
        entries = [(hc, sum(ws) / len(ws)) for hc, ws in cls_w.items()]
        entries = [(hc, m) for hc, m in entries if m >= EMIT_FLOOR]
        if not entries:
            return ""
        mx = max(m for _, m in entries)
        return ",".join(f"{hc}:{m / mx:.4f}" for hc, m in sorted(entries, key=lambda x: -x[1]))


def weighted_ranges(state, advisor=None) -> tuple[str, str, float]:
    """Build the v2 tracker for `state` and return (oop_str, ip_str, confidence) as CLASS-level weighted
    TexasSolver range strings. OOP = non-button (BB), IP = button. Both exclude the board (standard
    range-vs-range; the solver handles card removal between the two ranges during the solve). confidence =
    min over the two seats; the resolver uses these when confidence >= CONF_THRESHOLD, else floors."""
    t = RangeTracker(advisor=advisor).build(state)
    board = set(state.get("board", []))
    oop_seat = 0 if state["button"] == 1 else 1     # non-button = OOP
    ip_seat = state["button"]
    oop = t.emit(oop_seat, board)
    ip = t.emit(ip_seat, board)
    conf = min(t.confidence(oop_seat), t.confidence(ip_seat))
    return oop, ip, conf
