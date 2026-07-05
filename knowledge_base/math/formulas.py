"""Verified poker math functions, extracted from the books via OpenAI gpt-5.1."""
import math

# Pot Odds — Grounded in: Modern Poker Theory (Acevedo), GTO ranges & principles, pp. 20–22 and p. 26, where pot odds are defined as a reward-to-risk ratio and converted to a required equity percentage for call profitability comparisons.
from typing import Tuple

def compute_pot_odds(P: float, B: float, C: float) -> Tuple[float, float]:
    """Compute pot odds for a call in both ratio and percentage (required equity) form.

    Pot odds (ratio) is defined as the reward-to-risk ratio:
        (P + B) : C
    where
        P = current pot before villain's bet,
        B = villain's bet that is now in the pot and you can win,
        C = amount you must call.

    This function returns:
    - ratio: (P + B) / C, i.e. X such that pot odds are X:1
    - required_equity: C / (P + B + C), i.e. the break-even win probability as a fraction

    A call is +EV (ignoring future betting, rake, payout structure, etc.) if
        equity >= required_equity.

    Parameters
    ----------
    P : float
        Pot size before villain's bet.
    B : float
        Villain's bet size that is now in the pot.
    C : float
        Your call amount (risk) for this decision.

    Returns
    -------
    ratio : float
        Reward-to-risk pot odds, so that pot odds are ratio:1.
    required_equity : float
        Minimum winning probability (0-1) needed for a break-even call.
    """
    if C <= 0:
        raise ValueError("Call amount C must be positive.")
    total_pot_after_call = P + B + C
    if total_pot_after_call <= 0:
        raise ValueError("Total pot after call must be positive.")

    ratio = (P + B) / C
    required_equity = C / total_pot_after_call
    return ratio, required_equity

# Equity Needed to Call — Grounded in the standard pot-odds–to–equity relationship as described in Modern Poker Theory (Acevedo), specifically the section under “Key Metrics – Pot Odds and Outs,” where pot odds are converted into the statement “you need to win at least 33.3% of the time to justify calling.”
import math

def equity_needed_to_call(pot_before_call, call_amount, villain_risked_this_street=0.0):
    """Compute the minimum equity needed to make a call break-even in chip EV.

    This implements the standard poker relationship between pot odds and
    equity required to call, as discussed in Modern Poker Theory (Acevedo).

    Parameters
    ----------
    pot_before_call : float
        The current pot size before you call, including all existing bets
        on this street (in particular, including Villain's bet you are
        facing). This is the amount you can win if you call and win,
        ignoring rake.
    call_amount : float
        The additional amount you must put in now to call (your risk).
    villain_risked_this_street : float, optional
        Any additional chips Villain will necessarily commit only if you
        call (e.g., in a contrived toy model). In standard situations,
        this is 0 and the formula reduces to EquityNeeded = C / (P + C).

    Returns
    -------
    float
        The minimum equity required for a break-even call, as a fraction
        between 0.0 and 1.0.

    Notes
    -----
    - Standard case (villain_risked_this_street == 0):
          EquityNeeded = call_amount / (pot_before_call + call_amount)
    - If villain_risked_this_street > 0, the more general form is used:
          EquityNeeded = call_amount / (pot_before_call
                                       + call_amount
                                       + villain_risked_this_street)
    """
    if call_amount < 0 or pot_before_call < 0 or villain_risked_this_street < 0:
        raise ValueError("All monetary inputs must be non-negative.")
    if call_amount == 0:
        # If there is nothing to call, you need no equity to continue.
        return 0.0

    denominator = pot_before_call + call_amount + villain_risked_this_street
    if denominator <= 0:
        raise ValueError("Denominator must be positive; check inputs.")

    return call_amount / denominator

# Expected Value (EV) of a Poker Action — Grounded in: Modern Poker Theory (Acevedo), GTO ranges & principles, pp. 29–31, where EV is defined as the sum over outcomes of probability times payoff, and specialized to %W, %L, W, and R for standard poker decisions.
from typing import Sequence


def expected_value(probabilities: Sequence[float], payoffs: Sequence[float]) -> float:
    """Compute the Expected Value (EV) of a poker action.

    This implements the general EV definition:

        EV = sum_i p_i * x_i

    where p_i is the probability of outcome i
    and x_i is the net payoff (chips/money) for outcome i.

    Args:
        probabilities: Sequence of outcome probabilities p_i. Must be non-negative
            and sum (approximately) to 1.
        payoffs: Sequence of net payoffs x_i corresponding to each outcome,
            measured from the current decision point (wins positive, losses negative).

    Returns:
        The expected value EV as a float (same unit as payoffs).

    Raises:
        ValueError: If the input lengths differ, or if probabilities are invalid.
    """
    if len(probabilities) != len(payoffs):
        raise ValueError("probabilities and payoffs must have the same length")

    if not probabilities:
        raise ValueError("probabilities must be a non-empty sequence")

    # Basic validation: non-negative probabilities and sum close to 1
    total_p = sum(probabilities)
    if total_p <= 0:
        raise ValueError("sum of probabilities must be positive")

    # Normalize tiny numerical drift if necessary
    norm_probs = [p / total_p for p in probabilities]

    ev = 0.0
    for p, x in zip(norm_probs, payoffs):
        if p < 0:
            raise ValueError("probabilities must be non-negative")
        ev += p * x
    return ev

# Minimum Defense Frequency (MDF) — Grounded in: Modern Poker Theory (Acevedo), especially pp. 60–65 and 74, where Alpha = b/(b+p) and the BB’s minimum defense frequency is 1−Alpha = p/(p+b).
import math

def minimum_defense_frequency(pot: float, bet: float) -> float:
    """Compute Minimum Defense Frequency (MDF) versus a single bet.

    MDF is the minimum fraction of a defender's range that must
    continue (call and/or raise) against a bet of size `bet` into a
    pot of size `pot` so that the bettor's zero-equity bluffs are
    exactly break-even.

    The formula is:
        MDF = pot / (pot + bet)

    Args:
        pot: Current pot size before facing the bet (same units as bet).
        bet: Bet size being faced (same units as pot).

    Returns:
        MDF as a float in [0, 1]. For example, 0.67 means the defender
        must continue with 67% of their range to prevent the bettor
        from auto-profiting with pure bluffs.

    Raises:
        ValueError: If pot < 0, bet < 0, or pot + bet == 0.
    """
    if pot < 0 or bet < 0:
        raise ValueError("pot and bet must be non-negative")
    total = pot + bet
    if total == 0:
        raise ValueError("pot + bet must be greater than 0")
    return pot / total

# Bluff-to-Value Ratio and Bluffing Frequency — Grounded in standard GTO one-street bluffing models (as used in modern solver-based theory) and consistent with the pot-odds and EV framework in Acevedo, "Modern Poker Theory," particularly the discussion of pot odds, equity, and optimal frequencies in early chapters on theory and metrics.
from typing import Tuple

def bluff_to_value_and_frequencies(P: float,
                                  B: float,
                                  n_value: float,
                                  n_total: float) -> Tuple[float, float, float, float, float]:
    """Compute GTO bluff-to-value ratio and related bluffing frequencies.

    This function assumes a single betting decision where Hero bets B into pot P,
    Villain can call or fold, and Hero's betting range is composed of pure value
    hands (always winning when called) and pure bluffs (always losing when called).

    Under the standard GTO condition that makes Villain indifferent to calling
    (EV(call) = EV(fold)), the value share of Hero's betting range must be
    P/(P+B), so the optimal bluff-to-value ratio r = N_bluff/N_value is:

        r = B / P

    Given a chosen number of value combinations n_value in Hero's betting range
    and the total number of hand combinations n_total Hero can have in this spot,
    the function returns:

        - r:          bluff-to-value ratio (N_bluff / N_value)
        - n_bluff:    number of bluff combos implied by r and n_value
        - f_bluff:    bluffing frequency among all possible hands (n_bluff / n_total)
        - f_bluff_bet:bluffing fraction within the betting range (n_bluff / (n_value + n_bluff))
        - p_value_given_bet: probability Hero has value given that Hero bets
                              (= 1 / (1 + r))

    Parameters
    ----------
    P : float
        Pot size before Hero's bet.
    B : float
        Hero's bet size.
    n_value : float
        Number of value-bet combinations in Hero's betting range.
    n_total : float
        Total number of hand combinations Hero can hold at this node.

    Returns
    -------
    Tuple[float, float, float, float, float]
        (r, n_bluff, f_bluff, f_bluff_bet, p_value_given_bet)
    """
    if B <= 0:
        raise ValueError("Bet size B must be positive.")
    if P <= 0:
        raise ValueError("Pot size P must be positive (r = B/P divides by it).")
    if n_value < 0 or n_total <= 0:
        raise ValueError("n_value must be >= 0 and n_total must be > 0.")

    # 1. GTO bluff-to-value ratio = B/P (Villain indifferent: value share of the bet range = P/(P+B))
    r = B / P

    # 2. Number of bluff combos implied by r and n_value
    n_bluff = r * n_value

    # 3. Bluffing frequency among all hands
    f_bluff = n_bluff / n_total

    # 4. Bluffing fraction within betting range
    n_bet = n_value + n_bluff
    f_bluff_bet = 0.0 if n_bet == 0 else n_bluff / n_bet

    # 5. Probability of value given that we bet
    p_value_given_bet = 1.0 / (1.0 + r)

    return r, n_bluff, f_bluff, f_bluff_bet, p_value_given_bet

# Implied Odds — Modern Poker Theory (Acevedo): implied odds defined as how much you may expect to win on future betting rounds when you complete your draw; discussion of speculative hands and stack depth (pp. 25, 40–41, 154, 169–172). The Theory of Poker (Sklansky) p.32: distinction between implied odds (expecting to win future bets when a card hits) and reverse implied odds.
import math

def required_future_winnings_for_implied_odds(pot_size: float, call_cost: float, hit_probability: float) -> float:
    """Compute the minimum expected future winnings (F_min) needed so that
    calling with a drawing hand is break-even when implied odds are considered.

    The break-even condition (in chip-EV) for a pure drawing call is:

        hit_probability * (pot_size + F) = (1 - hit_probability) * call_cost

    (hero's call returns to him inside the pot he wins, so it must NOT appear in the
    win branch — the +call_cost variant is exactly the double-count the 2026-06-20
    audit already fixed in the CODE; the equation here previously showed that wrong
    form while the implementation below was correct. Found + pinned by
    tests/test_math_suite.py against the independent Fraction derivation.)

    Solving for F gives:

        F_min = max(0, call_cost * (1/hit_probability - 1) - pot_size)

    where:
        - pot_size (P): current pot before caller adds the call (includes
          villain's bet, excludes hero's call).
        - call_cost (C): amount hero must call to continue.
        - hit_probability (p_hit): probability that hero's draw completes
          to a winning hand in a way that he realizes the pot and future winnings.

    If the result is <= 0, then the existing pot odds alone (without any
    future winnings) are already sufficient for a break-even or profitable call,
    so this function returns 0.0.

    Parameters
    ----------
    pot_size : float
        The current pot size P before calling.
    call_cost : float
        The amount required to call C.
    hit_probability : float
        The probability p_hit that the draw completes and wins.
        Must satisfy 0 < hit_probability <= 1.

    Returns
    -------
    float
        F_min: the minimum expected future winnings needed (in the same
        chip units as pot_size and call_cost) for the call to be break-even.

    Raises
    ------
    ValueError
        If hit_probability is not in (0, 1].
    """
    if not (0 < hit_probability <= 1):
        raise ValueError("hit_probability must be in the interval (0, 1].")

    # raw required future winnings from EV=0 WITH Hero's own call returned on a win:
    # p*(P+C+F) − (1−p)*C = 0 → F = C*(1/p − 1) − P  (the old form omitted the returned call C)
    raw_F = call_cost * (1.0 / hit_probability - 1.0) - pot_size

    # If raw_F <= 0, pot odds alone are enough; no future winnings are required.
    return max(0.0, raw_F)

# Fold Equity — Modern Poker Theory, Michael Acevedo, esp. pp. 31–34 (definition and example of Fold Equity and solving for minimum fold frequency), and pp. 198–216 (discussion of rejamming and dependence on opponent folding frequency).
import math

def required_fold_equity(P, R, C, E):
    """Compute the minimum fold equity (Villain folding probability) needed
    for a shove/bet to be breakeven (EV = 0), given pot, risk, call size,
    and our equity when called.

    Parameters
    ----------
    P : float
        Current pot size before we shove/bet.
    R : float
        Our additional risked amount (the amount we put in with the shove/bet).
    C : float
        Villain's additional contribution when they call (their call amount).
    E : float
        Our equity versus Villain's *calling* range (0 <= E <= 1).

    Returns
    -------
    FE_required : float
        The minimum fold frequency (between -inf and +inf in pure math terms,
        but practically clamped in [0, 1]) that makes the play breakeven.
        Values < 0 mean the shove is profitable even if Villain never folds.
        Values > 1 mean the shove cannot be made breakeven by any feasible
        fold frequency (i.e., it is always -EV).

    Notes
    -----
    The formula is derived from the EV decomposition:

        EV = FE * P + (1 - FE) * (E * (P + R + C) - R)

    Setting EV = 0 and solving for FE yields

        FE = (R - E * (P + R + C)) / (P + R - E * (P + R + C))

    which this function returns.
    """
    pot_when_called = P + R + C
    numerator = R - E * pot_when_called
    denominator = P + R - E * pot_when_called   # the call-branch risks R (loses R, not 2R) → +R here

    if denominator == 0:
        # Edge case: the equation for FE is degenerate. In practice this
        # happens only in contrived setups; we signal via ValueError.
        raise ValueError("Denominator is zero; FE is undefined for these inputs.")

    return numerator / denominator

# Outs to Equity (Rule of 2 and 4) — Grounded in standard NLHE theory and the discussion of outs, equity, and the approximate outs→odds method in Modern Poker Theory (Acevedo, esp. pp. 20–25, including the example Q♥J♥ vs A♠K♠ and the explanation of outs, dead outs, and drawing odds).
from typing import Literal


def outs_to_equity_rule_2_and_4(outs: int, cards_to_come: Literal[1, 2]) -> float:
    """Approximate drawing equity from a number of outs using the Rule of 2 and 4.

    The Rule of 2 and 4 is a mental shortcut used in no-limit hold'em to estimate
    the probability of completing a draw based on the number of *live outs*.

    - With two cards to come (typically on the flop, seeing turn and river),
      equity ≈ 4% per out.
    - With one card to come (typically on the turn, seeing only the river),
      equity ≈ 2% per out.

    This function returns the approximate equity as a decimal between 0.0 and 1.0.
    Any value above 1.0 from the linear approximation is capped at 1.0.

    Parameters
    ----------
    outs : int
        Number of live outs – unseen cards that make your hand at least as good
        as needed when they appear. Dead outs (that also improve Villain to a
        better hand) should already be removed from this count.
    cards_to_come : {1, 2}
        Number of remaining cards to be dealt that you will see:
        - 2: use Rule of 4 approximation (usually flop → river).
        - 1: use Rule of 2 approximation (usually turn → river, or flop → turn
             when all-in and only one card will be dealt).

    Returns
    -------
    float
        Approximate equity (probability) as a decimal in [0.0, 1.0].

    Examples
    --------
    >>> # 9-out flush draw on the flop, two cards to come
    >>> round(outs_to_equity_rule_2_and_4(9, 2), 3)
    0.36

    >>> # 8-out straight draw on the turn, one card to come
    >>> round(outs_to_equity_rule_2_and_4(8, 1), 3)
    0.16
    """
    if outs < 0:
        raise ValueError("outs must be non-negative")
    if cards_to_come not in (1, 2):
        raise ValueError("cards_to_come must be 1 or 2 for the Rule of 2 and 4")

    if cards_to_come == 2:
        equity = 0.04 * outs  # Rule of 4: ~4% per out
    else:  # cards_to_come == 1
        equity = 0.02 * outs  # Rule of 2: ~2% per out

    # Cap at 100% equity
    if equity > 1.0:
        equity = 1.0

    # Also ensure lower bound is not negative (for completeness)
    if equity < 0.0:
        equity = 0.0

    return equity

# Stack-to-Pot Ratio (SPR) — Modern Poker Theory (Acevedo), GTO ranges & principles, p40–41: "Stack to Pot Ratio (SPR) — SPR is the effective stack size divided by the size of the pot" and surrounding discussion of low/medium/high SPR ranges.
from typing import Iterable


def compute_spr(effective_stack: float, pot_size: float) -> float:
    """Compute the Stack-to-Pot Ratio (SPR).

    SPR is defined as the effective stack divided by the pot size at the
    start of a betting street (most commonly the flop).

    Mathematically:
        SPR = S_eff / P

    where
        S_eff : effective_stack : smallest remaining stack among active players
                                   (after prior-round betting), in chips or BB.
        P     : pot_size       : current pot size in the same units.

    Args:
        effective_stack: The effective stack size S_eff (must be > 0).
        pot_size: The pot size P at the start of the street (must be > 0).

    Returns:
        The Stack-to-Pot Ratio as a float.

    Raises:
        ValueError: If effective_stack <= 0 or pot_size <= 0.
    """
    if effective_stack <= 0:
        raise ValueError("effective_stack must be positive.")
    if pot_size <= 0:
        raise ValueError("pot_size must be positive.")

    return effective_stack / pot_size

# Hand Combinatorics and Blockers — Modern Poker Theory (Michael Acevedo), especially pp. 16–19 (combinatorics, range breakdown, and card removal examples) and pp. 75–76, 89, 93, 106 (discussion of blockers and their strategic effect on ranges and 3-bet frequencies).
from itertools import combinations

def count_hand_combos_with_blockers(pattern, known_cards):
    """Count remaining combos for a given Hold'em hand pattern given blockers.

    Parameters
    ----------
    pattern : str
        Hand pattern string describing ranks and suitedness, using standard poker
        notation for two-card hands:
          - Pocket pairs: 'AA', 'KK', ..., '22'
          - Suited unpaired: like 'AKs', 'QJs' (distinct ranks, trailing 's')
          - Offsuit unpaired: like 'AQo', 'KJo' (distinct ranks, trailing 'o')
          - Unspecified suitedness: like 'AK', 'QJ' (distinct ranks, no suffix),
            meaning any suits (both suited and offsuit).

        Ranks use characters '2','3','4','5','6','7','8','9','T','J','Q','K','A'.

    known_cards : iterable of str
        Iterable of known card strings, e.g. ['Ac', 'Jh', '9h', 'Ad'].
        Each card is a 2-character string: rank + suit where
          rank in '23456789TJQKA' and suit in 'cdhs'.
        These cards are treated as blockers (Hero's hand + board), and are
        removed from Villain's possible holdings.

    Returns
    -------
    int
        Number of distinct two-card combos matching the pattern that Villain can
        still hold, given the blockers.

    Notes
    -----
    - The function builds the remaining deck (52 minus known_cards), then
      filters all 2-card combinations that match the requested pattern exactly.
      This is fully general and works for pocket pairs, suited, offsuit, and
      "any-suit" patterns with arbitrary blockers.
    - This directly implements the formal definition of blockers:
        #combos(H | K) = #{ h ⊆ D \\ K : h matches H }.
    """
    # Basic validation maps
    rank_order = '23456789TJQKA'
    suits = 'cdhs'

    def parse_card(card):
        if len(card) != 2:
            raise ValueError(f"Invalid card: {card}")
        r, s = card[0], card[1]
        if r not in rank_order or s not in suits:
            raise ValueError(f"Invalid card: {card}")
        return r, s

    # Normalize and validate known cards
    known_set = set()
    for c in known_cards:
        r, s = parse_card(c)
        known_set.add(r + s)

    # Build full deck and remaining deck after blockers
    full_deck = [r + s for r in rank_order for s in suits]
    remaining_deck = [c for c in full_deck if c not in known_set]

    # Parse pattern
    pat = pattern.strip()
    if len(pat) not in (2, 3):
        raise ValueError(f"Invalid pattern: {pattern}")

    r1 = pat[0]
    r2 = pat[1]
    if r1 not in rank_order or r2 not in rank_order:
        raise ValueError(f"Invalid rank(s) in pattern: {pattern}")

    if len(pat) == 2:
        # No suitedness spec: any suits
        suited_spec = None
    else:
        suited_spec = pat[2]
        if suited_spec not in ('s', 'o'):
            raise ValueError(f"Invalid suitedness suffix in pattern: {pattern}")

    # Helper to check if a 2-card combo matches pattern
    def matches_pattern(card1, card2):
        (R1, S1) = parse_card(card1)
        (R2, S2) = parse_card(card2)

        # Order the ranks so we can match patterns like 'AK' regardless of
        # which card is first in the combo.
        ranks = sorted([R1, R2], key=rank_order.index)
        suits_pair = (S1, S2)

        if r1 == r2:
            # Pocket pair pattern, e.g. 'AA'
            if R1 != R2 or R1 != r1:
                return False
            # suited_spec should be None for pairs in our input contract
            return True
        else:
            # Unpaired pattern
            # Pattern ranks sorted
            pattern_ranks_sorted = sorted([r1, r2], key=rank_order.index)
            if ranks != pattern_ranks_sorted:
                return False

            same_suit = (S1 == S2)
            if suited_spec is None:
                # Any suits
                return True
            elif suited_spec == 's':
                return same_suit
            else:  # 'o'
                return not same_suit

    # Count combos in remaining deck that match the pattern
    count = 0
    for c1, c2 in combinations(remaining_deck, 2):
        if matches_pattern(c1, c2):
            count += 1

    return count

# Breakeven Bluff Percentage (Alpha) from Bet Risk–Reward — Modern Poker Theory (Acevedo), esp. pp. 60–63, 74, 113: definition and use of Alpha as b/(b+p), the fraction of times a 0%-equity bluff must succeed to break even, directly tied to bet risk–reward and minimum defense frequency.
import math

def breakeven_bluff_percentage(bet_size: float, pot_size: float) -> float:
    """Compute the breakeven bluff percentage (Alpha) from bet risk–reward.

    This function assumes a pure bluff with 0% equity when called.
    Alpha is the minimum fold probability needed for the bluff
    to have zero expected value.

    Formula:
        Alpha = bet_size / (bet_size + pot_size)

    Args:
        bet_size: The additional amount you risk by betting (b > 0).
        pot_size: The current pot size before your bet (p >= 0).

    Returns:
        A float in (0, 1] representing the breakeven bluff percentage.

    Raises:
        ValueError: If bet_size <= 0 or pot_size < 0.
    """
    if bet_size <= 0:
        raise ValueError("bet_size must be positive.")
    if pot_size < 0:
        raise ValueError("pot_size cannot be negative.")

    return bet_size / (bet_size + pot_size)

# Equity Realization (R) — Modern Poker Theory (Acevedo), GTO ranges & principles, pp. 34–40, especially the sections “Equity Realization (EqR)”, “Rescaling EV to %EV”, and the 9♣5♦ BB vs UTG example.
from typing import Tuple

def equity_realization(eq: float, pot: float, cost: float, ev: float | None = None) -> Tuple[float, float, float]:
    """Compute equity realization (R) and related quantities.

    This function formalizes the equity realization concept from Modern Poker Theory.

    There are two main use-cases:
    1) Given raw equity Eq, pot P, cost C, and realized EV, compute R.
    2) Given Eq, P, C, and assuming break-even EV=0, compute the *required* R.

    Model (cash-units form):
        EV = R * Eq * P - C

    Hence:
        R = (EV + C) / (Eq * P)

    For EV = 0 (break-even):
        R_req = C / (Eq * P)

    Additionally, we compute:
        percent_ev = EV / P  (if EV is provided)

    Parameters
    ----------
    eq : float
        Raw equity Eq in [0, 1]. Example: 29.5% equity -> 0.295.
    pot : float
        Total pot size P at the decision point (same units as cost and EV).
    cost : float
        Additional amount C Hero must invest to continue (e.g., the call amount).
    ev : float | None, optional
        Actual expected value EV of continuing with the hand. If None, the
        function assumes EV=0 (break-even) and returns the *required* R to
        justify the investment.

    Returns
    -------
    r : float
        Equity realization factor R corresponding to the given Eq, pot, cost,
        and EV (or required R if EV is None / 0).
    r_required : float
        Required equity realization R_req for the play to be break-even
        (EV = 0), given Eq, pot, and cost.
    percent_ev : float
        EV expressed as a fraction of the pot: EV / pot. If EV is None, this
        is 0.0 (break-even by definition).

    Notes
    -----
    - If eq == 0 or pot == 0, R is undefined; this function will raise ValueError.
    - R > 1 means the hand over-realizes its raw equity; R < 1 means it
      under-realizes.
    - This is a simple algebraic tool; in practice, EV or R are usually
      estimated from data or solvers, then used with this relationship.
    """

    if pot <= 0:
        raise ValueError("pot must be positive")
    if eq <= 0:
        raise ValueError("eq must be positive to define equity realization")

    # If EV is not provided, analyze the break-even case EV=0.
    if ev is None:
        ev = 0.0

    # Break-even required R (EV = 0): R_req = C / (Eq * P)
    r_required = cost / (eq * pot)

    # Observed R from given EV: R = (EV + C) / (Eq * P)
    r = (ev + cost) / (eq * pot)

    percent_ev = ev / pot

    return r, r_required, percent_ev
