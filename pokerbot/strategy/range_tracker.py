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
        Flop-only (the defense advisor's coverage); size_faced default = a typical c-bet."""
        adv = self.adv
        if street != "flop" or adv is None or not getattr(adv, "defense_available", lambda: False)():
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

    def _update_action(self, seat, action, facing, board, role, street) -> None:
        """Reweight `seat`'s range by the likelihood of the observed action.
        bet/check (not facing) -> advisor P(bet); call/raise/allin (facing or first-in raise) -> legality-only
        (multiply by 1; o3-safe). Fold ends the hand (not seen in a live line). Counts silent updates for conf."""
        d = self.range[seat]
        self.total[seat] += 1
        if action in ("bet",) and not facing:
            modeled = False
            for c in list(d.keys()):
                p = self._p_bet(seat, c, board, role, street)
                if p is not None:
                    d[c] *= max(0.0, min(1.0, p))
                    modeled = True
            if not modeled:
                self.heur[seat] += 1          # advisor absent -> legality-only -> unmodeled
        elif action == "check" and not facing:
            modeled = False
            for c in list(d.keys()):
                p = self._p_bet(seat, c, board, role, street)
                if p is not None:
                    d[c] *= max(0.0, min(1.0, 1.0 - p))
                    modeled = True
            if not modeled:
                self.heur[seat] += 1
        elif action == "call" and facing:
            # KEYSTONE: narrow the range on a CALL via the defense advisor's P(call). Flop-only (advisor coverage);
            # turn/river calls fall through to legality-only. This is what gives the resolver correct-er ranges.
            modeled = False
            for c in list(d.keys()):
                pc = self._p_call(seat, c, board, role, street)
                if pc is not None:
                    d[c] *= max(0.0, min(1.0, pc))
                    modeled = True
            if not modeled:
                self.heur[seat] += 1
        else:
            # other silent actions (raise/allin facing a bet, or an unmodeled size): legality-only (provably safe).
            self.heur[seat] += 1
        self._normalize(seat)

    def build(self, state) -> "RangeTracker":
        """Walk preflop priors + the postflop betting line, reweighting both seats' ranges. Defensive: any
        malformed history -> the partial result stands and confidence() will be low (-> resolver gates to floor)."""
        self._init_preflop(state)
        board = state.get("board", [])
        history = state.get("history", []) or []
        try:
            cur_street = None
            street_bet = 0          # outstanding amount to call on the current street (0 = no bet yet)
            for h in history:
                act = h.get("action")
                if act == "deal":
                    st = h.get("street")
                    if st in ("flop", "turn", "river"):
                        cur_street = st
                        street_bet = 0
                        self._remove_dead(_board_at(board, st))
                    continue
                if cur_street is None or h.get("street") != cur_street:
                    continue
                if act not in ("bet", "raise", "allin", "check", "call", "fold"):
                    continue
                seat = h.get("player")
                if seat not in (0, 1):
                    continue
                facing = street_bet > 0
                if act != "fold":
                    self._update_action(seat, act, facing, _board_at(board, cur_street),
                                        self._role(seat, state), cur_street)
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
        conf = 1.0 - 0.5 * heur_ratio
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
