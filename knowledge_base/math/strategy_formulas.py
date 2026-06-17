"""Post-flop NLHE calculations — GPT-5.5-generated, ENGINE-VERIFIED (each self-check passes; gate +
materialize in research/postflop_calc_*). Pure stdlib. The callable library the engine-API exposes to the
brain. Regenerate via `python -m research.postflop_calc_materialize`. Per docs/math_accuracy_strategy.md."""
from __future__ import annotations

import itertools  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union  # noqa: F401


__all__ = ["preflop_open_raise_size_bb", "preflop_threebet_size_bb", "preflop_fourbet_size_bb", "preflop_squeeze_size_bb", "preflop_calling_range_fraction", "short_stack_open_shove_fraction", "balanced_bluff_combos", "polarization_degree", "capped_range_penalty", "nut_fraction", "range_morphology_selector", "mergedness_index", "cbet_frequency", "barrel_continuation_frequency", "give_up_frequency", "range_advantage_to_bet_frequency", "delayed_cbet_ev", "river_bluff_to_value_ratio", "bluff_catcher_breakeven_equity", "exploit_fold_deviation_ev", "exploit_call_deviation_ev", "minimum_check_raise_defense_combos", "fold_bias_bluff_ev", "set_mining_implied_odds_margin", "suited_connector_implied_odds_margin", "commitment_margin_by_spr", "reverse_implied_odds_discounted_equity", "bounded_read_deviation_ev", "stat_read_delta", "realized_equity_by_position_spr", "in_position_ev_premium", "initiative_value"]


def preflop_open_raise_size_bb(position: str, effective_bb: float, ante_bb: float = 0.0) -> float:
    """Open size in big blinds, rounded to 0.25bb. Example: BTN,100bb,0 ante -> 2.5."""
    base_by_pos = {"UTG": 2.25, "MP": 2.25, "HJ": 2.25, "CO": 2.50, "BTN": 2.50, "SB": 3.00}
    p = position.upper()
    if p not in base_by_pos:
        raise ValueError("position must be one of UTG, MP, HJ, CO, BTN, SB")
    stack_adjust = -0.25 if effective_bb < 15.0 else (-0.125 if effective_bb <= 40.0 else 0.0)
    raw = base_by_pos[p] + stack_adjust + min(0.5, 2.0 * max(0.0, ante_bb))
    clipped = max(2.0, min(3.5, raw))
    return round(clipped * 4.0) / 4.0


def preflop_threebet_size_bb(open_size_bb: float, in_position: bool, callers: int = 0, effective_bb: float | None = None) -> float:
    """3-bet size in big blinds. Example: 2.5bb open, OOP, 0 callers -> 10.0bb."""
    if open_size_bb <= 0.0 or callers < 0:
        raise ValueError("open_size_bb must be positive and callers nonnegative")
    multiplier = (3.0 if in_position else 4.0) + float(callers)
    raw = open_size_bb * multiplier
    if effective_bb is not None:
        raw = min(raw, effective_bb)
    return round(raw * 4.0) / 4.0


def preflop_fourbet_size_bb(threebet_size_bb: float, open_size_bb: float, in_position: bool, effective_bb: float | None = None) -> float:
    """4-bet size in big blinds. Example: 10bb 3bet, 2.5bb open, IP -> 22.0bb."""
    if threebet_size_bb <= 0.0 or open_size_bb <= 0.0:
        raise ValueError("sizes must be positive")
    multiplier = 2.2 if in_position else 2.5
    raw = max(threebet_size_bb + open_size_bb, threebet_size_bb * multiplier)
    if effective_bb is not None:
        raw = min(raw, effective_bb)
    return round(raw * 4.0) / 4.0


def preflop_squeeze_size_bb(open_size_bb: float, callers: int, in_position: bool, effective_bb: float | None = None) -> float:
    """Squeeze size in big blinds. Example: 2.5bb open, 2 callers, OOP -> 15.0bb."""
    if open_size_bb <= 0.0 or callers < 1:
        raise ValueError("open_size_bb must be positive and callers >= 1")
    raw = open_size_bb * ((3.0 if in_position else 4.0) + float(callers))
    if effective_bb is not None:
        raw = min(raw, effective_bb)
    return round(raw * 4.0) / 4.0


def preflop_calling_range_fraction(pot_before_call_bb: float, call_bb: float, position_index: float, effective_bb: float) -> float:
    """Top-fraction proxy of hands callable preflop after realization. position_index: 0=OOP, 1=IP."""
    if pot_before_call_bb < 0.0 or call_bb <= 0.0 or effective_bb <= 0.0:
        raise ValueError("pot must be nonnegative; call and stack must be positive")
    pos = max(0.0, min(1.0, position_index))
    realization = max(0.45, min(0.90, 0.55 + 0.10 * pos + 0.0015 * min(effective_bb, 100.0)))
    pot_odds = call_bb / (pot_before_call_bb + call_bb)
    return max(0.0, min(1.0, 1.0 - pot_odds / realization))


def short_stack_open_shove_fraction(position: str, effective_bb: float, ante_bb_per_player: float = 0.0) -> float:
    """Nash-ish open-shove top fraction. Example: BTN 10bb no ante -> 0.4808326112."""
    import math
    base_by_pos = {"UTG": 0.12, "MP": 0.15, "HJ": 0.18, "CO": 0.25, "BTN": 0.34, "SB": 0.55}
    p = position.upper()
    if p not in base_by_pos or effective_bb <= 0.0:
        raise ValueError("bad position or nonpositive stack")
    raw = base_by_pos[p] * math.sqrt(20.0 / effective_bb) * (1.0 + 2.0 * max(0.0, min(0.25, ante_bb_per_player)))
    return max(0.0, min(1.0, raw))


def balanced_bluff_combos(value_combos: float, bet_size: float, pot_size: float, bluff_equity: float = 0.0) -> float:
    """Bluff combos paired with value combos. Example: V=30, bet=75, pot=100, e=0 -> 12.8571428571."""
    if value_combos < 0.0 or bet_size <= 0.0 or pot_size <= 0.0:
        raise ValueError("value must be nonnegative; bet and pot positive")
    e = max(0.0, min(0.999999, bluff_equity))
    alpha = bet_size / (pot_size + bet_size)
    return value_combos * alpha / (1.0 - e)


def polarization_degree(nut_combos: float, air_combos: float, medium_combos: float) -> float:
    """Fraction of range lying at nut-or-air tails. Example: 10,15,25 -> 0.5."""
    if nut_combos < 0.0 or air_combos < 0.0 or medium_combos < 0.0:
        raise ValueError("combos must be nonnegative")
    total = nut_combos + air_combos + medium_combos
    if total == 0.0:
        return 0.0
    return (nut_combos + air_combos) / total


def capped_range_penalty(hero_nut_fraction: float, opponent_nut_fraction: float, spr: float, bet_pot_fraction: float) -> float:
    """Scalar penalty for capped ranges. Example: .05 vs .15 at SPR4 and 75% pot -> .0375."""
    if spr < 0.0 or bet_pot_fraction < 0.0:
        raise ValueError("spr and bet fraction must be nonnegative")
    hn = max(0.0, min(1.0, hero_nut_fraction))
    on = max(0.0, min(1.0, opponent_nut_fraction))
    return max(0.0, on - hn) * (spr / (spr + 4.0)) * bet_pot_fraction


def nut_fraction(nut_combos: float, total_combos: float) -> float:
    """Nut-combo density. Example: 12 nut combos out of 120 -> 0.1."""
    if nut_combos < 0.0 or total_combos < 0.0 or nut_combos > total_combos:
        raise ValueError("require 0 <= nut_combos <= total_combos")
    if total_combos == 0.0:
        return 0.0
    return nut_combos / total_combos


def range_morphology_selector(spr: float, texture_wetness: float, nut_advantage: float) -> int:
    """Return 0 linear, 1 merged, 2 polar. Example: SPR8, dry .2, nut_adv .15 -> 2."""
    if spr < 0.0:
        raise ValueError("spr must be nonnegative")
    wet = max(0.0, min(1.0, texture_wetness))
    if spr <= 2.0 or wet >= 0.70:
        return 0
    if nut_advantage > 0.08 or (spr >= 6.0 and wet <= 0.45):
        return 2
    return 1


def mergedness_index(nut_combos: float, air_combos: float, medium_combos: float) -> float:
    """High when tails and middle are similarly represented. Example: 10,10,20 -> 1.0."""
    if nut_combos < 0.0 or air_combos < 0.0 or medium_combos < 0.0:
        raise ValueError("combos must be nonnegative")
    total = nut_combos + air_combos + medium_combos
    if total == 0.0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - abs((nut_combos + air_combos) - medium_combos) / total))


def cbet_frequency(texture_wetness: float, in_position: bool, spr: float, range_advantage: float, nut_advantage: float) -> float:
    """C-bet frequency scalar. Example: wet=.3, IP, SPR4, ra=.1, na=.05 -> .5475."""
    if spr < 0.0:
        raise ValueError("spr must be nonnegative")
    wet = max(0.0, min(1.0, texture_wetness))
    pos = 1.0 if in_position else 0.0
    raw = 0.45 + 0.20 * pos + 0.25 * range_advantage + 0.15 * nut_advantage - 0.25 * wet - 0.015 * min(spr, 20.0)
    return max(0.05, min(0.95, raw))


def barrel_continuation_frequency(previous_bet_frequency: float, equity_advantage: float, scare_card: float, in_position: bool, street: int) -> float:
    """Barrel continuation frequency. street: 3=turn after flop, 4=river after turn."""
    if street not in (3, 4):
        raise ValueError("street must be 3 or 4")
    prev = max(0.0, min(1.0, previous_bet_frequency))
    scare = max(0.0, min(1.0, scare_card))
    pos = 1.0 if in_position else 0.0
    k = 0.55 + 0.25 * equity_advantage + 0.15 * scare + 0.10 * pos - 0.05 * (street - 2)
    return max(0.0, min(1.0, prev * k))


def give_up_frequency(street_bet_frequency: float, showdown_value_fraction: float, fold_equity: float) -> float:
    """Residual give-up frequency. Example: bet=.5, sdv=.4, FE=.3 -> .36."""
    b = max(0.0, min(1.0, street_bet_frequency))
    sdv = max(0.0, min(1.0, showdown_value_fraction))
    fe = max(0.0, min(1.0, fold_equity))
    return max(0.0, min(1.0, 1.0 - b - 0.5 * sdv * (1.0 - fe)))


def range_advantage_to_bet_frequency(equity_advantage: float, nut_advantage: float, in_position: bool, street: int) -> float:
    """Map range/nut advantages to bet frequency. street: 2 flop, 3 turn, 4 river."""
    if street not in (2, 3, 4):
        raise ValueError("street must be 2, 3, or 4")
    pos = 1.0 if in_position else 0.0
    raw = 0.5 + 1.2 * equity_advantage + 0.4 * nut_advantage + 0.1 * pos - 0.05 * (street - 2)
    return max(0.0, min(1.0, raw))


def delayed_cbet_ev(pot_size: float, bet_size: float, fold_equity: float, realized_equity_when_called: float) -> float:
    """EV of delayed c-bet/stab. Example: pot=100, bet=50, FE=.4, realized_e=.3 -> 37."""
    if pot_size < 0.0 or bet_size < 0.0:
        raise ValueError("pot and bet must be nonnegative")
    fe = max(0.0, min(1.0, fold_equity))
    re = max(0.0, min(1.0, realized_equity_when_called))
    return fe * pot_size + (1.0 - fe) * (re * (pot_size + bet_size) - bet_size)


def river_bluff_to_value_ratio(bet_size: float, pot_size: float) -> float:
    """Balanced river bluff-to-value ratio. Example: bet=75 into 100 -> 0.4285714286."""
    if bet_size <= 0.0 or pot_size <= 0.0:
        raise ValueError("bet and pot must be positive")
    return bet_size / (pot_size + bet_size)


def bluff_catcher_breakeven_equity(call_amount: float, pot_before_call: float) -> float:
    """Break-even equity for a bluff-catcher. Example: call 50 to win pot 150 -> .25."""
    if call_amount <= 0.0 or pot_before_call <= 0.0:
        raise ValueError("call and pot must be positive")
    return call_amount / (pot_before_call + call_amount)


def exploit_fold_deviation_ev(pot_size: float, bet_size: float, actual_fold_frequency: float, equilibrium_fold_frequency: float) -> float:
    """EV gain of bluffing versus an over-fold read. Example: P=100,B=50,F=.6,F_eq=1/3 -> 40."""
    if pot_size < 0.0 or bet_size < 0.0:
        raise ValueError("pot and bet must be nonnegative")
    f = max(0.0, min(1.0, actual_fold_frequency))
    feq = max(0.0, min(1.0, equilibrium_fold_frequency))
    return (f - feq) * (pot_size + bet_size)


def exploit_call_deviation_ev(call_amount: float, pot_before_call: float, actual_bluff_fraction: float, equilibrium_bluff_fraction: float) -> float:
    """EV gain of bluff-catching versus excess bluffs. Example: C=50,P=150,q=.4,qeq=.25 -> 30."""
    if call_amount < 0.0 or pot_before_call < 0.0:
        raise ValueError("call and pot must be nonnegative")
    q = max(0.0, min(1.0, actual_bluff_fraction))
    qeq = max(0.0, min(1.0, equilibrium_bluff_fraction))
    return (q - qeq) * (pot_before_call + call_amount)


def minimum_check_raise_defense_combos(check_range_combos: float, pot_size: float, bet_size: float, check_call_fraction_of_range: float) -> float:
    """Minimum XR combos to fill MDF after check-call allocation. Example: N=100,P=100,B=50,CC=.5 -> 16.6666667."""
    if check_range_combos < 0.0 or pot_size <= 0.0 or bet_size <= 0.0:
        raise ValueError("combos nonnegative; pot and bet positive")
    cc = max(0.0, min(1.0, check_call_fraction_of_range))
    mdf = pot_size / (pot_size + bet_size)
    return max(0.0, mdf - cc) * check_range_combos


def fold_bias_bluff_ev(pot_size: float, bet_size: float, actual_defense_frequency: float) -> float:
    """Signed bluff EV from defense frequency. Example: P=100,B=50,D=.5 -> 25."""
    if pot_size < 0.0 or bet_size < 0.0:
        raise ValueError("pot and bet must be nonnegative")
    d = max(0.0, min(1.0, actual_defense_frequency))
    return pot_size - d * (pot_size + bet_size)


def set_mining_implied_odds_margin(call_bb: float, effective_bb: float, stack_off_fraction: float = 1.0) -> float:
    """Positive iff implied odds meet set-mining threshold. Example: call2, eff30, stackoff .8 -> 0."""
    if call_bb <= 0.0 or effective_bb <= 0.0:
        raise ValueError("call and stack must be positive")
    sf = max(0.000001, min(1.0, stack_off_fraction))
    return effective_bb / call_bb - 12.0 / sf


def suited_connector_implied_odds_margin(call_bb: float, effective_bb: float, in_position: bool, multiway_callers: int) -> float:
    """Positive iff suited-connector call has sufficient implied odds. Example: call2, eff40, IP, 2 callers -> 7."""
    if call_bb <= 0.0 or effective_bb <= 0.0 or multiway_callers < 0:
        raise ValueError("call/stack positive; callers nonnegative")
    p = 1.0 if in_position else 0.0
    threshold = max(8.0, 20.0 - 3.0 * p - 2.0 * min(multiway_callers, 3))
    return effective_bb / call_bb - threshold


def commitment_margin_by_spr(spr: float, equity_when_called: float) -> float:
    """Positive iff call-off/stack-off is pot-odds committed. Example: SPR2, equity .45 -> .05."""
    if spr < 0.0:
        raise ValueError("spr must be nonnegative")
    e = max(0.0, min(1.0, equity_when_called))
    threshold = spr / (1.0 + 2.0 * spr)
    return e - threshold


def reverse_implied_odds_discounted_equity(raw_equity: float, domination_risk: float, spr: float, in_position: bool) -> float:
    """Equity after reverse-implied-odds discount. Example: E=.4,r=.5,SPR4,OOP -> .3."""
    if spr < 0.0:
        raise ValueError("spr must be nonnegative")
    e = max(0.0, min(1.0, raw_equity))
    r = max(0.0, min(1.0, domination_risk))
    p = 1.0 if in_position else 0.0
    discounted = e * (1.0 - r * (spr / (spr + 4.0)) * (1.0 - 0.2 * p))
    return max(0.0, min(1.0, discounted))


def bounded_read_deviation_ev(read_delta: float, confidence: float, pot_size: float, risk_amount: float, sensitivity: float = 1.0) -> float:
    """Bounded read-based deviation EV. Example: d=.2,c=.75,P=100,R=50,s=2 -> 45."""
    if pot_size < 0.0 or risk_amount < 0.0:
        raise ValueError("pot and risk must be nonnegative")
    c = max(0.0, min(1.0, confidence))
    edge = max(-1.0, min(1.0, c * read_delta * sensitivity))
    return edge * (pot_size + risk_amount)


def stat_read_delta(vpip: float, pfr: float, fold_to_cbet: float, aggression_factor: float) -> float:
    """Composite exploit read delta. Example: .40,.10,.60,.75 -> .295."""
    v = max(0.0, min(1.0, vpip))
    p = max(0.0, min(1.0, pfr))
    ftc = max(0.0, min(1.0, fold_to_cbet))
    af = max(0.0, aggression_factor)
    raw = 0.5 * (v - p) + 0.3 * (ftc - 0.45) + 0.2 * ((1.5 - af) / 1.5)
    return max(-1.0, min(1.0, raw))


def realized_equity_by_position_spr(raw_equity: float, in_position: bool, spr: float, has_initiative: bool) -> float:
    """Realized equity. Example: E=.4, IP, SPR5, initiative -> .37."""
    if spr < 0.0:
        raise ValueError("spr must be nonnegative")
    e = max(0.0, min(1.0, raw_equity))
    p = 1.0 if in_position else 0.0
    i = 1.0 if has_initiative else 0.0
    r = max(0.5, min(1.05, 0.65 + 0.15 * p + 0.05 * i + 0.015 * min(spr, 10.0)))
    return e * r


def in_position_ev_premium(pot_size: float, raw_equity: float, realization_ip: float, realization_oop: float) -> float:
    """EV premium from position via realization gap. Example: P=100,E=.5,Rip=.9,Roop=.75 -> 7.5."""
    if pot_size < 0.0:
        raise ValueError("pot must be nonnegative")
    e = max(0.0, min(1.0, raw_equity))
    return pot_size * e * (realization_ip - realization_oop)


def initiative_value(pot_size: float, fold_equity_gain: float, realization_gain: float, raw_equity: float) -> float:
    """EV value of initiative. Example: P=100, dFE=.08,dR=.10,E=.4 -> 12."""
    if pot_size < 0.0:
        raise ValueError("pot must be nonnegative")
    e = max(0.0, min(1.0, raw_equity))
    return pot_size * (fold_equity_gain + realization_gain * e)
