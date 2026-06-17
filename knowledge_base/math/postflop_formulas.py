"""Post-flop NLHE calculations — GPT-5.5-generated, ENGINE-VERIFIED (each self-check passes; gate +
materialize in research/postflop_calc_*). Pure stdlib. The callable library the engine-API exposes to the
brain. Regenerate via `python -m research.postflop_calc_materialize`. Per docs/math_accuracy_strategy.md."""
from __future__ import annotations

import itertools  # noqa: F401
import math  # noqa: F401
from fractions import Fraction  # noqa: F401
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union  # noqa: F401


__all__ = ["alpha_break_even_bluff_frequency", "optimal_value_to_bluff_ratio", "bluff_to_value_ratio_by_pot_fraction", "polarized_bet_ev", "semi_bluff_ev", "breakeven_fold_equity_pure_bluff", "required_fold_fraction_for_raise", "minimum_defense_frequency_by_bet_fraction", "bluff_catcher_call_ev", "calling_frequency_to_indifferent_bluffer", "fold_frequency_exploit_ev", "pot_odds_required_equity_with_rake", "implied_odds_extra_needed", "reverse_implied_odds_max_future_loss", "effective_multi_street_required_equity", "stackoff_equity_threshold_from_spr", "commitment_spr_for_equity", "geometric_bet_fraction_to_all_in", "per_street_geometric_bets", "equity_realization_ev", "range_vs_range_ev", "nut_advantage_index", "equity_denial_value", "hand_class_combo_count", "range_combo_count", "target_bluff_combos_for_polar_bet", "card_removal_fraction", "call_ev_with_implied_gain", "raise_ev_with_fold_equity", "check_raise_vs_check_call_delta", "multiway_independent_equity_need", "exact_two_card_draw_equity", "combined_draw_outs", "discounted_outs_equivalent"]


def alpha_break_even_bluff_frequency(bet: float, pot: float) -> float:
    '''Return the break-even fold frequency for a pure bluff bet.

    Example: betting 50 into 100 needs folds 50/(100+50)=1/3.
    '''
    if bet < 0 or pot <= 0:
        raise ValueError('bet must be non-negative and pot must be positive')
    return bet / (pot + bet)


def optimal_value_to_bluff_ratio(bet: float, pot: float) -> float:
    '''Return optimal value:bluff combo ratio for a polarized bet.

    Example: pot-sized bet has value:bluff = (100+100)/100 = 2:1.
    '''
    if bet <= 0 or pot < 0:
        raise ValueError('bet must be positive and pot must be non-negative')
    return (pot + bet) / bet


def bluff_to_value_ratio_by_pot_fraction(pot_fraction: float) -> float:
    '''Return optimal bluff:value ratio for bet fraction f of pot.

    Example: 75% pot gives 0.75/1.75 = 0.428571 bluffs per value combo.
    '''
    if pot_fraction <= 0:
        raise ValueError('pot_fraction must be positive')
    return pot_fraction / (1.0 + pot_fraction)


def polarized_bet_ev(value_combos: float, bluff_combos: float, value_equity_when_called: float, bluff_equity_when_called: float, pot: float, bet: float, fold_freq: float) -> float:
    '''Return average EV per betting combo for a polarized betting range.

    Example: 3 value combos at 100% equity and 1 bluff at 0%, pot=100, bet=100, folds=50% gives 112.5.
    '''
    total = value_combos + bluff_combos
    if total <= 0 or pot < 0 or bet < 0 or not (0 <= fold_freq <= 1):
        raise ValueError('invalid combo, pot, bet, or fold frequency')
    if not (0 <= value_equity_when_called <= 1 and 0 <= bluff_equity_when_called <= 1):
        raise ValueError('equities must be in [0, 1]')
    avg_equity = (value_combos * value_equity_when_called + bluff_combos * bluff_equity_when_called) / total
    called_ev = avg_equity * (pot + 2.0 * bet) - bet
    return fold_freq * pot + (1.0 - fold_freq) * called_ev


def semi_bluff_ev(fold_equity: float, equity_when_called: float, pot: float, final_pot: float, cost: float) -> float:
    '''Return semi-bluff EV.

    Example: 40% folds, 30% called equity, pot=100, final_pot=200, cost=50 gives 46.
    '''
    if not (0 <= fold_equity <= 1 and 0 <= equity_when_called <= 1):
        raise ValueError('probabilities must be in [0, 1]')
    if pot < 0 or final_pot < 0 or cost < 0:
        raise ValueError('money amounts must be non-negative')
    return fold_equity * pot + (1.0 - fold_equity) * (equity_when_called * final_pot - cost)


def breakeven_fold_equity_pure_bluff(risk: float, reward: float) -> float:
    '''Return fold equity needed for a zero-equity bluff to break even.

    Example: risk 75 to win 100 requires 75/(75+100)=0.428571.
    '''
    if risk < 0 or reward <= 0:
        raise ValueError('risk must be non-negative and reward positive')
    return risk / (risk + reward)


def required_fold_fraction_for_raise(raise_risk: float, pot_reward: float) -> float:
    '''Return folds needed for a pure raise bluff.

    Example: risk 300 to win 150 requires 300/(300+150)=2/3.
    '''
    if raise_risk < 0 or pot_reward <= 0:
        raise ValueError('raise_risk must be non-negative and pot_reward positive')
    return raise_risk / (raise_risk + pot_reward)


def minimum_defense_frequency_by_bet_fraction(pot_fraction: float) -> float:
    '''Return MDF versus a bet fraction of pot.

    Example: versus half-pot, MDF=1/(1+0.5)=2/3.
    '''
    if pot_fraction < 0:
        raise ValueError('pot_fraction must be non-negative')
    return 1.0 / (1.0 + pot_fraction)


def bluff_catcher_call_ev(pot: float, bet: float, bluff_fraction: float) -> float:
    '''Return bluff-catcher call EV versus polarized value/bluff.

    Example: pot=100, bet=50, bluff_fraction=25% gives EV 0.
    '''
    if pot < 0 or bet < 0 or not (0 <= bluff_fraction <= 1):
        raise ValueError('invalid pot, bet, or bluff_fraction')
    return bluff_fraction * (pot + bet) - (1.0 - bluff_fraction) * bet


def calling_frequency_to_indifferent_bluffer(pot: float, bet: float) -> float:
    '''Return defense call frequency that sets pure bluff EV to zero.

    Example: pot=100, bet=50 gives call frequency 100/150=2/3.
    '''
    if pot < 0 or bet < 0 or pot + bet <= 0:
        raise ValueError('pot+bet must be positive')
    return pot / (pot + bet)


def fold_frequency_exploit_ev(pot: float, bet: float, observed_fold_freq: float) -> float:
    '''Return EV of pure bluff versus actual fold frequency.

    Example: bet 50 into 100 and villain folds 70% gives EV 55.
    '''
    if pot < 0 or bet < 0 or not (0 <= observed_fold_freq <= 1):
        raise ValueError('invalid inputs')
    return observed_fold_freq * pot - (1.0 - observed_fold_freq) * bet


def pot_odds_required_equity_with_rake(to_call: float, pot: float, rake_fraction: float, rake_cap: float) -> float:
    '''Return required call equity after rake.

    Example: call 50 into pot 150, 5% rake capped at 10: rake=10, required=50/190.
    '''
    if to_call < 0 or pot <= 0 or rake_fraction < 0 or rake_cap < 0:
        raise ValueError('invalid money or rake inputs')
    rake = min(rake_cap, rake_fraction * (pot + to_call))
    denom = pot + to_call - rake
    if denom <= 0:
        raise ValueError('rake leaves non-positive final pot')
    return to_call / denom


def implied_odds_extra_needed(to_call: float, pot: float, equity: float) -> float:
    '''Return extra future chips needed on wins for a call to break even.

    Example: call 50 into 100 at 25% equity needs 50 extra.
    '''
    if to_call < 0 or pot < 0 or not (0 < equity <= 1):
        raise ValueError('invalid inputs')
    return max(0.0, to_call / equity - pot - to_call)


def reverse_implied_odds_max_future_loss(to_call: float, pot: float, equity: float) -> float:
    '''Return maximum extra loss on losing outcomes before the call becomes -EV.

    Example: call 50 into 150 with 40% equity tolerates 50 future loss on misses.
    '''
    import math
    if to_call < 0 or pot < 0 or not (0 < equity <= 1):
        raise ValueError('invalid inputs')
    if equity == 1:
        return math.inf
    return (equity * (pot + to_call) - to_call) / (1.0 - equity)


from typing import Sequence

def effective_multi_street_required_equity(hero_costs: Sequence[float], current_pot: float, villain_future_contributions: Sequence[float]) -> float:
    '''Return required equity for a multi-street investment plan.

    Example: invest 50 then 100 into pot 100 while villain contributes 50 then 100 gives 150/400.
    '''
    if current_pot < 0:
        raise ValueError('current_pot must be non-negative')
    total_cost = sum(hero_costs)
    total_villain = sum(villain_future_contributions)
    if total_cost < 0 or total_villain < 0:
        raise ValueError('costs/contributions must not sum negative')
    final_pot = current_pot + total_cost + total_villain
    if final_pot <= 0:
        raise ValueError('final pot must be positive')
    return total_cost / final_pot


def stackoff_equity_threshold_from_spr(spr_value: float) -> float:
    '''Return all-in equity threshold from SPR.

    Example: SPR 4 needs 4/(1+8)=44.444% equity.
    '''
    if spr_value < 0:
        raise ValueError('spr_value must be non-negative')
    return spr_value / (1.0 + 2.0 * spr_value)


def commitment_spr_for_equity(equity: float) -> float:
    '''Return breakeven commitment SPR for equity below 50%.

    Example: 40% equity commits up to SPR 2.
    '''
    if not (0 <= equity < 0.5):
        raise ValueError('equity must be in [0, 0.5) for a finite threshold')
    return equity / (1.0 - 2.0 * equity)


def geometric_bet_fraction_to_all_in(spr_value: float, streets: int) -> float:
    '''Return constant pot fraction that exhausts stack over streets when called.

    Example: SPR 4 over 3 streets requires about 54.004% pot each street.
    '''
    if spr_value < 0 or streets <= 0:
        raise ValueError('spr_value must be non-negative and streets positive')
    return ((1.0 + 2.0 * spr_value) ** (1.0 / streets) - 1.0) / 2.0


def per_street_geometric_bets(pot: float, effective_stack: float, streets: int) -> list[float]:
    '''Return geometric bet amounts over remaining streets, assuming calls.

    Example: pot 100, stack 400, 3 streets starts with bet about 54.004.
    '''
    if pot <= 0 or effective_stack < 0 or streets <= 0:
        raise ValueError('pot positive, stack non-negative, streets positive required')
    fraction = ((1.0 + 2.0 * (effective_stack / pot)) ** (1.0 / streets) - 1.0) / 2.0
    bets: list[float] = []
    current_pot = pot
    remaining = effective_stack
    for _ in range(streets):
        bet = min(remaining, fraction * current_pot)
        bets.append(bet)
        remaining -= bet
        current_pot += 2.0 * bet
    if bets:
        bets[-1] += remaining
    return bets


def equity_realization_ev(equity: float, realization: float, pot: float, cost: float) -> float:
    '''Return EV using realized equity = equity * realization.

    Example: 50% raw equity, R=0.8, call 50 into 100 gives EV 10.
    '''
    if not (0 <= equity <= 1) or realization < 0 or pot < 0 or cost < 0:
        raise ValueError('invalid inputs')
    return equity * realization * (pot + cost) - cost


from typing import Sequence

def range_vs_range_ev(equities: Sequence[float], weights: Sequence[float], pot: float, cost: float) -> float:
    '''Return weighted EV for a range equity distribution.

    Example: equities [0.6,0.4] with weights [2,1], pot=100, cost=50 gives EV 30.
    '''
    if len(equities) != len(weights) or len(equities) == 0:
        raise ValueError('equities and weights must have same nonzero length')
    if pot < 0 or cost < 0:
        raise ValueError('pot and cost must be non-negative')
    total_w = sum(weights)
    if total_w <= 0:
        raise ValueError('sum of weights must be positive')
    weighted_eq = sum(e * w for e, w in zip(equities, weights)) / total_w
    if not (0 <= weighted_eq <= 1):
        raise ValueError('weighted equity must be in [0, 1]')
    return weighted_eq * (pot + cost) - cost


def nut_advantage_index(hero_nut_combos: float, hero_total_combos: float, villain_nut_combos: float, villain_total_combos: float) -> float:
    '''Return nut density advantage: hero density minus villain density.

    Example: hero 12/100 nuts and villain 6/100 nuts gives 0.06.
    '''
    if hero_nut_combos < 0 or villain_nut_combos < 0 or hero_total_combos <= 0 or villain_total_combos <= 0:
        raise ValueError('invalid combo counts')
    return hero_nut_combos / hero_total_combos - villain_nut_combos / villain_total_combos


def equity_denial_value(pot: float, folded_range_equity: float, fold_frequency: float) -> float:
    '''Return equity-denial value from folds.

    Example: fold 50% of a range with 60% equity in pot 100 denies 30 chips.
    '''
    if pot < 0 or not (0 <= folded_range_equity <= 1) or not (0 <= fold_frequency <= 1):
        raise ValueError('invalid inputs')
    return pot * folded_range_equity * fold_frequency


from typing import Optional, Sequence

def hand_class_combo_count(rank1: str, rank2: str, suited: Optional[str], known_cards: Sequence[str]) -> int:
    '''Return remaining combos for a two-rank hand class with blockers.

    Cards use rank then suit, e.g. As, Kd. suited='s', 'o', or None. Pairs ignore suited.
    Example: AKs with As and Kd known leaves AhKh and AcKc = 2 combos.
    '''
    import math
    suits = ('c', 'd', 'h', 's')
    r1 = rank1.upper()
    r2 = rank2.upper()
    if len(r1) != 1 or len(r2) != 1:
        raise ValueError('use one-character ranks: 23456789TJQKA')
    known = {(c[0].upper(), c[1].lower()) for c in known_cards}
    avail1 = [s for s in suits if (r1, s) not in known]
    avail2 = [s for s in suits if (r2, s) not in known]
    if r1 == r2:
        return math.comb(len(avail1), 2)
    suited_count = sum(1 for s in suits if s in avail1 and s in avail2)
    total = len(avail1) * len(avail2)
    if suited == 's':
        return suited_count
    if suited == 'o':
        return total - suited_count
    if suited is None:
        return total
    raise ValueError("suited must be 's', 'o', or None")


from typing import Optional, Sequence, Tuple

def range_combo_count(hand_classes: Sequence[Tuple[str, str, Optional[str]]], known_cards: Sequence[str]) -> int:
    '''Return total combos for a tuple-defined range after blockers.

    Example: AA plus AKs with no known cards has 6 + 4 = 10 combos.
    '''
    import math
    suits = ('c', 'd', 'h', 's')
    known = {(c[0].upper(), c[1].lower()) for c in known_cards}
    total_count = 0
    for rank1, rank2, suited in hand_classes:
        r1 = rank1.upper(); r2 = rank2.upper()
        avail1 = [s for s in suits if (r1, s) not in known]
        avail2 = [s for s in suits if (r2, s) not in known]
        if r1 == r2:
            total_count += math.comb(len(avail1), 2)
        else:
            suited_count = sum(1 for s in suits if s in avail1 and s in avail2)
            total = len(avail1) * len(avail2)
            if suited == 's':
                total_count += suited_count
            elif suited == 'o':
                total_count += total - suited_count
            elif suited is None:
                total_count += total
            else:
                raise ValueError("suited must be 's', 'o', or None")
    return total_count


def target_bluff_combos_for_polar_bet(value_combos: float, pot: float, bet: float) -> float:
    '''Return target bluff combos for optimal polarized betting.

    Example: 30 value combos, pot bet, target bluffs = 15.
    '''
    if value_combos < 0 or pot < 0 or bet <= 0:
        raise ValueError('invalid inputs')
    return value_combos * bet / (pot + bet)


def card_removal_fraction(before_count: float, after_count: float) -> float:
    '''Return fraction of combos removed from a range.

    Example: 100 combos before, 85 after blockers means 15% removed.
    '''
    if before_count <= 0 or after_count < 0:
        raise ValueError('before_count positive and after_count non-negative required')
    return (before_count - after_count) / before_count


def call_ev_with_implied_gain(equity: float, pot: float, to_call: float, future_gain: float = 0.0) -> float:
    '''Return EV of a call, optionally including future gain when hero wins.

    Example: 25% equity, call 50 into 100, with 100 implied gain gives EV 12.5.
    '''
    if not (0 <= equity <= 1) or pot < 0 or to_call < 0 or future_gain < 0:
        raise ValueError('invalid inputs')
    return equity * (pot + to_call + future_gain) - to_call


def raise_ev_with_fold_equity(fold_freq: float, equity_when_called: float, pot_reward: float, raise_risk: float, called_final_pot: float) -> float:
    '''Return EV of a raise bluff/value/semi-bluff line.

    Example: 50% folds, 30% called equity, win 100 now, risk 150, called final pot 400 gives EV 35.
    '''
    if not (0 <= fold_freq <= 1 and 0 <= equity_when_called <= 1):
        raise ValueError('probabilities must be in [0, 1]')
    if pot_reward < 0 or raise_risk < 0 or called_final_pot < 0:
        raise ValueError('money amounts must be non-negative')
    return fold_freq * pot_reward + (1.0 - fold_freq) * (equity_when_called * called_final_pot - raise_risk)


def check_raise_vs_check_call_delta(check_call_ev: float, raise_fold_freq: float, raise_equity_when_called: float, pot_reward: float, raise_risk: float, called_final_pot: float) -> float:
    '''Return EV(check-raise) - EV(check-call).

    Example: if check-call EV is 10 and check-raise EV is 35, delta is 25.
    '''
    if not (0 <= raise_fold_freq <= 1 and 0 <= raise_equity_when_called <= 1):
        raise ValueError('probabilities must be in [0, 1]')
    check_raise_ev = raise_fold_freq * pot_reward + (1.0 - raise_fold_freq) * (raise_equity_when_called * called_final_pot - raise_risk)
    return check_raise_ev - check_call_ev


def multiway_independent_equity_need(target_field_equity: float, opponents: int) -> float:
    '''Return per-opponent independent win probability needed to beat all opponents with target probability.

    Example: to have 25% field equity versus 2 independent opponents, need sqrt(0.25)=0.5 versus each.
    '''
    if not (0 <= target_field_equity <= 1) or opponents <= 0:
        raise ValueError('target in [0,1] and opponents positive required')
    return target_field_equity ** (1.0 / opponents)


def exact_two_card_draw_equity(outs: int, unseen_cards: int = 47) -> float:
    '''Return exact two-card hit probability for a draw.

    Example: 9 outs from flop to river is 1 - C(38,2)/C(47,2) = 378/1081.
    '''
    import math
    if outs < 0 or unseen_cards < 2 or outs > unseen_cards:
        raise ValueError('invalid outs or unseen_cards')
    return 1.0 - math.comb(unseen_cards - outs, 2) / math.comb(unseen_cards, 2)


from typing import Sequence

def combined_draw_outs(draw_out_sets: Sequence[Sequence[str]]) -> int:
    '''Return unique out count across multiple draws.

    Example: ['Ah','Kh'] plus ['Kh','Qh','Jh'] has 4 unique outs.
    '''
    outs: set[str] = set()
    for group in draw_out_sets:
        for card in group:
            outs.add(card)
    return len(outs)


def discounted_outs_equivalent(raw_outs: float, dirty_outs: float, dirty_out_weight: float) -> float:
    '''Return clean-equivalent outs after discounting dirty outs.

    Example: 12 raw outs, 3 dirty outs worth half each gives 10.5 equivalent outs.
    '''
    if raw_outs < 0 or dirty_outs < 0 or dirty_outs > raw_outs or not (0 <= dirty_out_weight <= 1):
        raise ValueError('invalid outs or weight')
    return raw_outs - dirty_outs * (1.0 - dirty_out_weight)
