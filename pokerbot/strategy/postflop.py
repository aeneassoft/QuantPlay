"""Postflop engine: board texture, fold-equity-optimal bet sizing, and the fold model.

The edge: pick the bet size s (fraction of pot) that maximizes EV against the opponent's
fold-frequency-vs-size curve F(s).
  - Bluff EV (per pot):   ev_bluff(s)  = F(s) - s*(1 - F(s))      [win 1 pot on fold, lose s when called]
  - Value EV (per pot):   value_score(s) = F + (1-F)*(e_call*(1+2s) - s)   [fold-win + showdown; the bet s is
                          committed whenever called — bug-hunt fix 2026-07-05, the old form refunded it on wins]
Against a GTO opponent F(s) = s/(1+s) and every bluff size is break-even. Profit only comes from
an opponent who deviates — so a *learned* per-size fold model (e.g. from probing Slumbot) is what
turns this into an edge.
"""
from __future__ import annotations

import json
import os

from pokerbot.strategy.gto_mode import flag as _flag   # import-order-safe reads (GTOW-mode profile aware)

# candidate bet sizes as a fraction of the pot (overbets included to probe/exploit big-size folds)
CANDIDATE_SIZES = [0.33, 0.5, 0.66, 1.0, 1.5, 2.0]

# GTO-mode (POKERB_ONTREE, DEFAULT ON since the A/B): snap postflop BETS to GTOW's discrete size tree so the spot
# stays on GTOW's solution (off-tree variable sizing was the main SRP "UNSOLVED" driver). A/B (1000 hands each +
# duplicate.py): more on-tree + GTO-score 50.7->53.1 + EV-loss-vs-GTO 22.7->21.2, at NO realized-EV cost
# (-59.2 vs -60.6 bb/100, inside the noise) -> SHIPPED as default. Set POKERB_ONTREE=0 to restore the variable
# exploit-sizing (the edge vs very leaky fields; trades GTO-alignment for exploitation).
ONTREE = _flag("POKERB_ONTREE", "1") == "1"
TREE_SIZES = (0.33, 0.5, 0.75, 1.0, 1.25)            # standard GTOW tree fractions (drops 0.66/1.5/2.0)

# River VALUE-BET FLOOR (POKERB_RIVER_VALUE = the equity threshold, empty/0 = OFF). On the FINAL card a strong made
# hand has no protection concern, so the river advisor's MEASURED under-betting (checks ~67% of eq>=0.80 river hands
# = the #1 river leak; GTOW: river 47% perfect / 26% mistake+blunder) only FORGOES value. When enabled, a river hand
# with eq>=this floor bets at >= RIVER_VALUE_BET_FREQ (a high freq, not 100% -> keep a small check-back for balance)
# instead of the advisor's low mix. Default OFF -> floor 2.0 (eq never exceeds it) = baseline byte-identical.
_rvf = _flag("POKERB_RIVER_VALUE", "")
RIVER_VALUE_FLOOR_EQ = float(_rvf) if _rvf else 2.0
RIVER_VALUE_BET_FREQ = float(os.environ.get("POKERB_RIVER_VALUE_FREQ", "0.85"))


# S3 (plan 2026-07-04): GTOW's EMPIRICAL tree, measured from 12,483 logged GTOW actions
# (research/gtow_tree_census.py -> data/census/gtow_tree.json). The generic TREE_SIZES misses GTOW's dominant
# river 0.65 and the 1.5x overbet entirely. POKERB_GTOW_TREE=1 (GTOW-mode) snaps BETS to the street-specific
# census grid; raises get their own grid via snap_raise_to_tree (gated POKERB_ONTREE_RAISES in bot._raise_to).
GTOW_TREE = _flag("POKERB_GTOW_TREE", "0") == "1"
CENSUS_BETS = {"flop": (0.35, 0.75), "turn": (0.35, 0.75, 1.35), "river": (0.35, 0.65, 1.0, 1.5)}
CENSUS_RAISES = {"flop": (0.35, 0.75), "turn": (0.35, 0.75), "river": (0.5, 1.0, 1.5)}


def snap_to_tree(bet_chips: int, pot: int, street: str | None = None) -> int:
    """Round a bet (chips) to the nearest GTOW-tree pot-fraction; returns the input if pot/bet non-positive.
    With POKERB_GTOW_TREE=1 and a street, uses GTOW's measured street grid instead of the generic one."""
    if pot <= 0 or bet_chips <= 0:
        return bet_chips
    sizes = CENSUS_BETS.get(street, TREE_SIZES) if GTOW_TREE else TREE_SIZES
    frac = bet_chips / pot
    best = min(sizes, key=lambda s: abs(s - frac))
    return max(1, round(best * pot))


def snap_raise_to_tree(desired_to: int, call_level: int, pot: int, to_call: int, street: str) -> int:
    """Snap a postflop RAISE onto GTOW's measured raise grid (S3). The raise is expressed the way solvers size
    it: increment OVER the call, as a fraction of the POST-CALL pot. Returns the snapped raise-to
    (street-cumulative chips); inputs it can't interpret are returned unchanged."""
    pot_after_call = pot + to_call
    incr = desired_to - call_level
    if pot_after_call <= 0 or incr <= 0:
        return desired_to
    grid = CENSUS_RAISES.get(street) or CENSUS_RAISES["flop"]
    best = min(grid, key=lambda s: abs(s - incr / pot_after_call))
    return call_level + max(1, round(best * pot_after_call))

VALUE_EQ = 0.58      # bet for value at/above this equity vs the continuing range
BLUFF_EQ = 0.38      # only bluff below this equity
THIN_BAND = (0.45, 0.58)


def classify_board(board: list[str]) -> dict:
    if len(board) < 3:
        return {"paired": False, "monotone": False, "twotone": False,
                "connected": False, "high": False, "dynamic": False}
    from pokerbot.engine.cards import RANK_ORDER
    ranks = sorted((RANK_ORDER[c[0]] for c in board), reverse=True)
    suits = [c[1] for c in board]
    suit_counts = {s: suits.count(s) for s in set(suits)}
    maxsuit = max(suit_counts.values())
    uniq = sorted(set(ranks))
    spread = max(uniq) - min(uniq) if len(uniq) > 1 else 0
    paired = len(set(ranks)) < len(ranks)
    monotone = maxsuit >= 3
    twotone = maxsuit == 2
    connected = spread <= 4 and len(uniq) >= 2
    high = ranks[0] >= RANK_ORDER["T"]
    dynamic = monotone or twotone or connected            # wet/drawy -> protect, charge draws
    return {"paired": paired, "monotone": monotone, "twotone": twotone,
            "connected": connected, "high": high, "dynamic": dynamic}


# Flop c-bet (frequency, primary size as pot fraction) by board class, hero IN POSITION as the PFR.
# From knowledge_base/postflop/openai_strategy.json ("Flop c-bet frequency & size"). Frequencies match our
# solver cache (~80% dry/high vs ~55% monotone); sizes are small range-bets on dry, bigger on dynamic.
FLOP_CBET = {
    "High_dry":     (0.80, 0.33),
    "Low_dry":      (0.65, 0.33),
    "High_dynamic": (0.70, 0.50),
    "Low_dynamic":  (0.55, 0.50),
    "Paired":       (0.75, 0.33),
    "Monotone":     (0.55, 0.50),
}


def flop_class(tex: dict) -> str:
    """Map classify_board() flags to one of the 6 openai_strategy flop categories."""
    if tex["monotone"]:
        return "Monotone"
    if tex["paired"]:
        return "Paired"
    drawy = tex["twotone"] or tex["connected"]
    if drawy:
        return "High_dynamic" if tex["high"] else "Low_dynamic"
    return "High_dry" if tex["high"] else "Low_dry"


def cbet_policy(board: list[str], ip: bool = True) -> tuple[float, float]:
    """Texture-conditioned flop c-bet (frequency, size as pot fraction). OOP: ~15% less often, sized up.
    Turn/river boards still classify, but callers should prefer street-specific logic there."""
    f, s = FLOP_CBET[flop_class(classify_board(board))]
    if not ip:
        f = max(0.35, min(0.85, f - 0.15))
        s = max(s, 0.50)
    return f, s


def ev_bluff(s: float, F: float) -> float:
    return F - s * (1.0 - F)


def value_score(s: float, F: float, eq: float) -> float:
    """Value-bet EV vs size (pot units, P=1): fold wins the pot (1); a called win nets pot + villain's
    call = 1+s; the bet s is committed whenever called, win or lose -> called-EV = e_call*(1+2s) - s.
    BUG-HUNT FIX (2026-07-05): the previous `- (1-e_call)*s` charged the bet only on LOSSES, i.e. refunded
    hero's own bet as profit on wins (+e_call*s overcredit, slope 3e-1 instead of 2e-1) -> the score rose
    with size exactly in the thin-value zone e_call in (1/3, 1/2) and mis-ranked sizes toward jams."""
    e_call = max(0.10, eq - 0.25 * s)        # equity vs the (tightening) calling range; may drop below 0.5
    return F + (1.0 - F) * (e_call * (1.0 + 2.0 * s) - s)


# GTOW mode (POKERB_GTO_FOLD_PRIOR=1, default OFF): drop the +0.04 "they over-fold" default below — vs a
# near-GTO opponent that assumption is an exploit prior baked into value/bluff sizing (S1, plan 2026-07-04).
GTO_FOLD_PRIOR = _flag("POKERB_GTO_FOLD_PRIOR", "0") == "1"


class PriorFoldModel:
    """Default opponent fold curve: GTO indifference s/(1+s), nudged by the live read."""

    def __init__(self, fold_to_bet: float = 0.5, confidence: float = 0.0):
        self.ftb = fold_to_bet
        self.conf = confidence

    def fold(self, street: str, s: float) -> float:
        base = s / (1.0 + s)
        base += (self.ftb - 0.5) * 0.5 * self.conf      # exploit the aggregate read
        if not GTO_FOLD_PRIOR:
            base += 0.04 * (1.0 - self.conf)            # mild default over-fold assumption
        return max(0.02, min(0.96, base))


class LearnedFoldModel:
    """Per-(street, size) fold frequencies learned from observed responses (e.g. Slumbot).

    With `max_dist` set, a learned rate is used ONLY when the queried size is within that distance of a
    measured spot — otherwise it falls back to the GTO prior. This makes a SPARSE, spot-specific table
    (e.g. the few significant Pluribus over-fold points) deviate from GTO *only where a leak was actually
    measured* and play the indifference curve everywhere else, so the exploit is confined to proven spots
    rather than generalized blindly. (A dense curve like Slumbot's leaves max_dist=None = nearest-always.)"""

    def __init__(self, table: dict, min_n: int = 6, max_dist: float | None = None):
        self.table = table              # {street: [[size, fold_rate, n], ...]}
        self.min_n = min_n
        self.max_dist = max_dist
        self.prior = PriorFoldModel()

    @classmethod
    def load(cls, path) -> "LearnedFoldModel | None":
        try:
            with open(path, encoding="utf-8") as f:
                return cls(json.load(f))
        except (OSError, ValueError):     # ValueError covers JSONDecodeError: a corrupt model file must
            return None                   # degrade to the documented None fallback, never crash the bot

    def fold(self, street: str, s: float) -> float:
        rows = self.table.get(street) or self.table.get("all") or []
        best = None
        for size, fr, n in rows:
            if n >= self.min_n and (best is None or abs(size - s) < abs(best[0] - s)):
                best = (size, fr)
        if best is not None and (self.max_dist is None or abs(best[0] - s) <= self.max_dist):
            return max(0.02, min(0.98, best[1]))
        return self.prior.fold(street, s)


def _to_amount_for_size(s: float, pot: int, hero_committed: int, hero_stack: int) -> int:
    """Bet sizing when first in / leading (current_bet == 0): bet s*pot, capped at all-in."""
    bet = min(round(s * pot), hero_stack)
    return hero_committed + bet


# AUDIT-FIX bundle (2026-07-05, default OFF = byte-identical; ONE flag = ONE gated Analyzer arm). The two
# sizers below shared the eCall sizer's PHANTOM-SIZE defect (fixed there 2026-07-05): candidates the stack
# cannot realize all map to the same all-in amount but were scored at their phantom fold rate F(s) — the
# argmax then fires all-in bluffs/value on a fold rate villain never faces. Same remedy: realizable
# candidates only + the true jam, jam capped at 2x pot (the eCall precedent).
AUDIT_FIX = _flag("POKERB_AUDIT_FIX", "0") == "1"
SIZER_JAM_CAP = 2.0


def _candidate_sizes(pot: int, hero_stack: int) -> list[float]:
    if not pot:
        return list(CANDIDATE_SIZES)
    jam = hero_stack / pot
    if not AUDIT_FIX:
        return CANDIDATE_SIZES + [jam]
    return [s for s in CANDIDATE_SIZES if s <= jam] + ([jam] if jam <= SIZER_JAM_CAP else [])


def pick_bluff_size(pot: int, model, street: str, hero_committed: int, hero_stack: int):
    """Return (to_amount, best_ev, size_frac). best_ev<=0 means no profitable bluff."""
    best = (None, -1e9, 0.0)
    for s in _candidate_sizes(pot, hero_stack):
        if s <= 0 or s * pot < 1:
            continue
        F = model.fold(street, min(s, 3.0))
        ev = ev_bluff(s, F)
        if ev > best[1]:
            best = (_to_amount_for_size(s, pot, hero_committed, hero_stack), ev, s)
    return best


def pick_value_size(pot: int, model, street: str, hero_committed: int, hero_stack: int, eq: float):
    """Return (to_amount, score, size_frac) maximizing the exact value_score(s) (fold-win + showdown)."""
    best = (None, -1e9, 0.0)
    for s in _candidate_sizes(pot, hero_stack):
        if s <= 0 or s * pot < 1:
            continue
        F = model.fold(street, min(s, 3.0))
        sc = value_score(s, F, eq)
        if sc > best[1]:
            best = (_to_amount_for_size(s, pot, hero_committed, hero_stack), sc, s)
    return best


# PRINCE v2 L1 (books wave #2: ToP pp.86-87 "equity when CALLED" + Beyond GTO thin-value floor; POKERB_RIVER_ECALL):
# the river value gate/size from the TRACKED ranges instead of the e_call surrogate above. Per candidate size s the
# villain's CALLING SET = his combos whose equity vs HERO'S perceived range >= s/(1+2s) (his pot odds); F(s) and
# e_call(s) then come from the SAME distribution -> internally consistent, and "bet the LARGEST size that keeps
# eq-vs-callers >= ~0.55" emerges from the argmax naturally. River-only: no cards to come -> exact enumeration.
# Known approximation (documented): per-pair blocker removal between the two ranges is skipped (hero's own combo
# IS exact vs every villain combo); acceptable for a sizing gate, not for a solve.
ECALL_SIZES = [0.35, 0.65, 1.0, 1.5]     # the census river grid (GTOW's own arms) + the jam added by the caller


# v3.2 thin-value SELECTION thresholds: a bet is VALUE iff the range that actually CALLS is one we beat
# (e_call >= 0.5 = the textbook definition), and the calling set must be a real share of his range (else the
# "value" read rests on a sliver of the tracked range = noise, and the bet is really a bluff decision).
THIN_ECALL_MIN = 0.50
THIN_CALL_SHARE_MIN = 0.15


def _ecall_rows(pot: int, hero_committed: int, hero_stack: int,
                hole: list, board: list, villain_w: dict, hero_w: dict):
    """Per-candidate-size eCall analysis [(size_frac, to_amount, F, e_call, call_share, score)], smallest size
    first, or None (tracked ranges can't support the enumeration). Shared by the value SIZER (argmax by score)
    and the thin-value SELECTION probe (the smallest size's e_call)."""
    from pokerbot.engine.evaluator import evaluate
    if not villain_w or not hero_w or len(board) < 5 or not pot:
        return None
    dead = set(hole) | set(board)
    hero_sc = evaluate(board, list(hole))
    # score each range once (treys: LOWER = stronger); hero range = villain's view of us (same Bayesian walk).
    # BUG-HUNT FIX: filter hero_w by the BOARD only — villain cannot see our hole, so combos sharing our cards
    # legitimately stay in his view of us (filtering them re-introduced the bias _tracked_ranges_both avoids).
    hs = sorted((evaluate(board, list(c)), w) for c, w in hero_w.items() if not set(c) & set(board))
    if not hs:
        return None
    total_h = sum(w for _, w in hs)
    # prefix sums -> equity of a villain score vs the hero range in O(log n)
    import bisect
    scores = [sc for sc, _ in hs]
    prefix = [0.0]
    for _, w in hs:
        prefix.append(prefix[-1] + w)

    def eq_vs_hero(sv: float) -> float:
        lo = bisect.bisect_left(scores, sv)               # hero combos STRONGER than sv (score < sv)
        hi = bisect.bisect_right(scores, sv)              # [lo, hi) = ties
        beaten = total_h - prefix[hi]                     # hero combos villain beats (score > sv)
        ties = prefix[hi] - prefix[lo]
        return (beaten + 0.5 * ties) / total_h if total_h > 0 else 0.0

    vil = [(w, evaluate(board, list(c))) for c, w in villain_w.items() if not set(c) & dead]
    total_v = sum(w for w, _ in vil)
    if not vil or total_v <= 0:
        return None
    rows = []
    jam = hero_stack / pot
    # BUG-HUNT FIX: candidates the stack cannot realize all map to the same all-in amount but were scored at
    # their PHANTOM size (fold equity of a bet villain never faces) — drop them; the jam covers all-in.
    # STRESS-SUITE FIX (2026-07-05, sizer.*.thin B174.5!): the jam candidate is CAPPED at 2x pot — when the
    # tracked range predicted "nobody calls a jam", the F=1.0 plateau beat every real-caller size and the sizer
    # over-jammed 3.4x pot HAND-STRENGTH-INSENSITIVELY (the paired canary even rewarded it: GTOBaseline over-folds
    # to jams — an exploit of the test opponent, not value). Census max = 1.5x; 2x allows natural short-stack jams.
    for s in [c for c in ECALL_SIZES if c <= jam] + ([jam] if jam <= 2.0 else []):
        if s <= 0 or s * pot < 1:
            continue
        thr = s / (1.0 + 2.0 * s)                         # villain's pot odds facing a bet of s
        callers = [(w, sv) for w, sv in vil if eq_vs_hero(sv) >= thr]
        cw = sum(w for w, _ in callers)
        F = 1.0 - cw / total_v
        if cw <= 0:
            continue                                      # STRESS-SUITE FIX: "everyone folds" is NOT a value bet —
                                                          # never pick a size on pure fold-out (that decision
                                                          # belongs to the bluff/advisor path, not the value sizer)
        win = sum(w for w, sv in callers if sv > hero_sc)
        tie = sum(w for w, sv in callers if sv == hero_sc)
        e_call = (win + 0.5 * tie) / cw                   # hero's equity vs the ACTUAL calling set
        # called win nets 1+s (pot + villain's call); the bet s is spent whenever called (see value_score)
        sc = F + (1.0 - F) * (e_call * (1.0 + 2.0 * s) - s)
        rows.append((s, _to_amount_for_size(s, pot, hero_committed, hero_stack), F, e_call, cw / total_v, sc))
    return rows or None


def pick_value_size_ecall(pot: int, hero_committed: int, hero_stack: int,
                          hole: list, board: list, villain_w: dict, hero_w: dict):
    """(to_amount, score, size_frac) from tracked-range e_call/F on the RIVER, or None (caller falls back).
    villain_w/hero_w: {combo: weight} from the range tracker (both already confidence-gated by the caller)."""
    rows = _ecall_rows(pot, hero_committed, hero_stack, hole, board, villain_w, hero_w)
    if not rows:
        return None
    s, to, _F, _e, _share, sc = max(rows, key=lambda row: row[5])
    return (to, sc, s)


def thin_value_probe(pot: int, hero_committed: int, hero_stack: int,
                     hole: list, board: list, villain_w: dict, hero_w: dict):
    """(to_amount, e_call, call_share, size_frac) at the SMALLEST viable size, or None. The v3.2 thin-value
    SELECTION gate: the smallest size has the WIDEST calling set — if hero doesn't beat even that set
    (e_call < THIN_ECALL_MIN), no thin value exists at any size. This is the selection v3.1's flat frequency
    floor lacked (paired-Analyzer REFUTED 19.76 vs 17.93: GTOW bets 43% of river pairs but CHOOSES which)."""
    rows = _ecall_rows(pot, hero_committed, hero_stack, hole, board, villain_w, hero_w)
    if not rows:
        return None
    s, to, _F, e_call, share, _sc = rows[0]
    return (to, e_call, share, s)
