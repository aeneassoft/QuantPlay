# 3_claude — range-tracker P0 consult

Elapsed: 123.6s

---

# CONCRETE RANGE TRACKER v2 — IMPLEMENTATION SPEC

## ANSWER TO THE FIVE HARD QUESTIONS

### (1) INCOMPLETE-BLUEPRINT UPDATE — THE FALLBACK POLICIES

**The Core Problem:** The blueprint gives P(bet) at bet/check nodes. It is silent on:
- **Facing-bet defense:** call/fold/raise after villain bets.
- **Bet sizing:** when villain chooses a specific size (e.g., 0.5×pot vs 1.2×pot).

**The Defensible Rule:**

#### A. Facing-Bet Defense (No Call/Fold/Raise Policy)
**Use equity-based heuristic with blocker adjustments:**

```python
def facing_bet_policy(hand, board, bet_size_bb, pot_bb):
    equity = calc_equity(hand, villain_range, board)
    pot_odds = bet_size_bb / (pot_bb + bet_size_bb)
    
    # MDF baseline: must defend pot_odds fraction to prevent exploits
    mdf = pot_odds
    
    # Blocker adjustment (±0.05 for nut/air blockers)
    blocker_bonus = blocker_effect(hand, board)  # -0.05 to +0.05
    defense_threshold = pot_odds - blocker_bonus
    
    if equity > defense_threshold + 0.15:
        # Strong hands: mix call/raise by equity percentile
        if equity > 0.75 or has_nut_blocker(hand, board):
            return {'call': 0.6, 'raise': 0.3, 'fold': 0.1}
        return {'call': 0.85, 'raise': 0.05, 'fold': 0.1}
    elif equity > defense_threshold:
        # Marginal: mostly call
        return {'call': 0.8, 'fold': 0.2}
    else:
        # Bluff-catchers: defend at MDF with best blockers
        if blocker_bonus > 0.02:
            return {'call': mdf * 0.9, 'fold': 1 - mdf * 0.9}
        return {'fold': 1.0}
```

**Justification:** Equity + pot odds is the *floor* any reasonable policy must respect. Blocker adjustments (e.g., Ah on A-high boards blocks villain value) are first-order exploitable reads. This won't be GTO, but it *won't put trash in the solver*—low-equity hands fold, high-equity hands defend, preserving range shape.

**RISK FLAG 🚩:** If villain is extremely unbalanced (e.g., only bluffs rivers), this MDF-based defense will be exploitably tight/loose. **v1 mitigation:** Clamp defense frequency to [0.4×MDF, 1.5×MDF].

#### B. Bet Sizing (No Size-Dependent Policy)
When villain bets 0.33×pot vs 1.5×pot, we lack a size-specific policy.

**Rule: Size-agnostic aggregation + polarization heuristic:**

```python
def update_for_bet_size(range_dict, size_bb, pot_bb):
    # Treat ALL bet sizes as "villain chose to bet"
    # Use the blueprint's P(bet) regardless of size
    # Then apply a polarization tilt based on size
    
    size_ratio = size_bb / pot_bb
    
    for hand, weight in range_dict.items():
        p_bet = blueprint.predict_bet_prob(hand, board, street, role='villain')
        
        # Polarization adjustment: large bets -> favor nuts/air
        if size_ratio > 0.9:  # overbet
            equity = hand_equity(hand)
            if equity > 0.7 or equity < 0.3:
                polarization_mult = 1.3
            else:
                polarization_mult = 0.7
        else:
            polarization_mult = 1.0
        
        range_dict[hand] = weight * p_bet * polarization_mult
    
    normalize(range_dict)
```

**Justification:** The blueprint's P(bet) is agnostic to size, so we treat "bet happened" as the primary signal. The polarization multiplier (larger bets → more polar) is a theory-driven *refinement* that won't break ranges. 

**RISK FLAG 🚩:** A solver trained on 0.5×pot bets will have different P(bet) than one trained on 2×pot. If the blueprint was trained on mixed sizes, this is safe; if trained on fixed-size-only games, this introduces noise. **v1 mitigation:** Log bet-size distributions; if >80% of training was single-size, disable polarization_mult.

---

### (2) PER-COMBO vs CLASS-LEVEL WEIGHTS

**The Right Call for v1: Per-Combo Weighted Ranges.**

**Reasoning:**
- TexasSolver v0.2.0 explicitly supports `'AsKh:0.62'` syntax.
- **Blockers are combo-specific:** `AsKs` and `AdKd` have identical equity preflop but *different* blocker effects postflop (AsKs blocks nut flush draws on spade boards). Aggregating to class-level ("AKs:0.6") loses this.
- **Solver stability:** Modern CFR+ solvers handle sparse/weighted ranges fine; this is not 2015 PioSOLVER.

**Format:**
```python
def emit_solver_range(range_dict, dead_cards):
    lines = []
    for hand_str, weight in range_dict.items():
        if weight < 1e-6:  # prune near-zero
            continue
        if any(card in dead_cards for card in hand_str):
            continue
        lines.append(f"{hand_str}:{weight:.4f}")
    return ",".join(lines)
```

**Stability Check:** If TexasSolver throws errors on >500 weighted combos, fall back to top-N combos (keep top 200 by weight, renormalize). But test this—I expect v0.2.0 handles it.

---

### (3) OWN-RANGE vs VILLAIN-RANGE FIDELITY

**The Asymmetry:**

The resolver computes a Nash equilibrium strategy profile for both players at the subgame root, then we *sample our own hand's strategy*. So:

- **Villain range fidelity:** Directly affects the equilibrium structure. A badly wrong villain range means the solver computes a strategy against a phantom opponent. *High impact.*
- **Our own range fidelity:** Affects whether the equilibrium "believes" our hand is in-range, which affects our own strategy primarily via *removal effects* (if solver thinks we're very unlikely to have hand X, it might under-defend against X-heavy lines). *Moderate impact, second-order.*

**Budget Allocation:**

| Component            | Fidelity Investment |
|----------------------|---------------------|
| Villain range        | **HIGH** — use blueprint + equity fallback, per-combo |
| Our own range        | **MEDIUM** — acceptable to use class-level aggregates if performance bottleneck |
| Dead-card removal    | **CRITICAL** — must be exact (board + known cards) |

**Practical Rule:** Track both at per-combo level (it's cheap—1326 floats). If solver timeout becomes an issue, coarsen *our own* range first (e.g., aggregate suited connectors), never the villain's.

---

### (4) VALIDATION WITHOUT GROUND TRUTH

**The Self-Consistency Checks:**

#### A. Mathematical Invariants
```python
def validate_range(range_dict, street, history, board):
    # 1. Non-negative, sums to ~1
    assert all(w >= 0 for w in range_dict.values())
    assert 0.95 < sum(range_dict.values()) < 1.05
    
    # 2. Monotonic shrinkage: range[street] ⊆ range[street-1]
    if street > 0:
        prev_support = set(prev_street_range.keys())
        curr_support = set(range_dict.keys())
        assert curr_support <= prev_support  # no new hands appear
    
    # 3. Dead-card exclusion
    dead = set(board + hero_hand)
    for hand_str in range_dict:
        assert not any(card in dead for card in parse_hand(hand_str))
```

#### B. Equity Distribution Cross-Check
A calling range after a bet should have *higher average equity* than the preflop range (villain folded trash). Conversely, a betting range should be *polarized* (bimodal equity distribution).

```python
def equity_sanity_check(range_dict, board, action_type):
    equities = [calc_equity(h, opponent_range, board) * w 
                for h, w in range_dict.items()]
    mean_eq = sum(equities) / sum(range_dict.values())
    
    if action_type == 'call':
        # Calling range should be >= 35% equity (pot odds dependent)
        assert mean_eq > 0.35, f"Calling range has {mean_eq:.2%} equity (too weak)"
    
    if action_type == 'bet':
        # Betting range should be polarized: check stdev or bimodality
        stdev = np.std(equities)
        assert stdev > 0.15, "Betting range not polarized"
```

#### C. Solver-Based Validation (The Big One)
Run a *known toy scenario* (e.g., river, 1 PSB left, monotone board) where GTO is analytically known or TexasSolver-computed offline. Compare:

```python
def test_known_river_spot():
    # Setup: Ks Qs Js rainbow board, river 2c, pot=100, stack=100
    # Known GTO: IP bets ~70% (value+bluffs at 2:1 ratio)
    
    range_tracker = RangeTracker()
    # ... simulate history leading to this spot
    ip_range = range_tracker.get_range('IP', street='river')
    oop_range = range_tracker.get_range('OOP', street='river')
    
    # Solve with tracker ranges
    solver_strat = texasolver.solve(ip_range, oop_range, ...)
    
    # Compare to offline-computed GTO
    offline_strat = load_reference_solution('river_monotone_psb.json')
    
    ev_diff = abs(solver_strat['ev'] - offline_strat['ev'])
    assert ev_diff < 0.05, f"EV gap {ev_diff:.3f} BB too large"
```

**The Gate:** Maintain a library of 10-20 canonical spots. If tracker passes all, it's trusted.

---

### (5) SAFE MINIMUM-VIABLE TRACKER + CONFIDENCE GATE

**The MVP Tracker: "Equity + Blockers with Blueprint Bet/Check Only"**

```python
class SafeMVPTracker:
    def __init__(self):
        self.ranges = {'IP': {}, 'OOP': {}}  # hand_str -> weight
        
    def init_preflop(self, position):
        # Use existing class-set priors (sb_open, bb_defend)
        self.ranges[position] = preflop_ranges[position].copy()
    
    def update(self, position, action, street, board, pot, bet_size):
        range_dict = self.ranges[position]
        
        if action == 'bet':
            for hand, weight in list(range_dict.items()):
                p_bet = blueprint.predict(hand, board, street, role=position)
                range_dict[hand] = weight * p_bet
        
        elif action == 'check':
            for hand, weight in list(range_dict.items()):
                p_bet = blueprint.predict(hand, board, street, role=position)
                range_dict[hand] = weight * (1 - p_bet)
        
        elif action in ['call', 'fold', 'raise']:
            # FALLBACK: equity + MDF heuristic
            policy = facing_bet_policy(hand, board, bet_size, pot)
            for hand, weight in list(range_dict.items()):
                range_dict[hand] = weight * policy[action]
        
        self.normalize(position)
        self.remove_dead_cards(position, board)
    
    def confidence(self, position, street):
        """Return confidence ∈ [0,1] that this range is trustworthy."""
        range_dict = self.ranges[position]
        
        # 1. Support size: very sparse = low confidence
        support = sum(1 for w in range_dict.values() if w > 0.01)
        if support < 20:
            return 0.3  # too few hands
        
        # 2. Effective mass (inverse of Herfindahl index)
        weights = list(range_dict.values())
        herfindahl = sum(w**2 for w in weights)
        eff_combos = 1 / herfindahl if herfindahl > 0 else 0
        
        if eff_combos < 10:
            return 0.4  # too concentrated
        
        # 3. Number of heuristic-based actions (non-blueprint)
        # Track this in update() via a counter
        heuristic_ratio = self.heuristic_action_count / self.total_action_count
        confidence = 1.0 - 0.5 * heuristic_ratio  # decay by heuristic use
        
        return max(0.2, confidence)  # floor at 0.2
```

**The Resolver Gate:**

```python
def resolve_subgame(hero_hand, history, board):
    tracker = get_tracker(history)
    
    confidence_ip = tracker.confidence('IP', street)
    confidence_oop = tracker.confidence('OOP', street)
    min_confidence = min(confidence_ip, confidence_oop)
    
    CONFIDENCE_THRESHOLD = 0.5  # tunable
    
    if min_confidence < CONFIDENCE_THRESHOLD:
        logger.warn(f"Range confidence {min_confidence:.2f} < {CONFIDENCE_THRESHOLD}, using floor")
        return floor_policy(hero_hand, history)
    
    ip_range_str = tracker.emit_solver_range('IP', dead_cards)
    oop_range_str = tracker.emit_solver_range('OOP', dead_cards)
    
    try:
        solution = texasolver.solve(ip_range_str, oop_range_str, board, pot, ...)
        return solution.get_strategy(hero_hand)
    except TimeoutError:
        return floor_policy(hero_hand, history)
```

**Why This is Safe:**
- **Fallback is always available.** Low confidence → use floor (which is known to be -160bb/100, acceptable).
- **Confidence metric is conservative.** It penalizes sparse ranges (which cause solver instability) and heuristic-heavy lines (which lack blueprint grounding).
- **No silent failures.** If the tracker is garbage, confidence will be low, and we explicitly avoid the resolver.

---

## THE COMPLETE v2 ALGORITHM

### Data Structure
```python
@dataclass
class RangeState:
    combos: Dict[str, float]  # "AsKh" -> weight
    action_history: List[Tuple[str, str]]  # (action_type, street)
    heuristic_count: int
    total_count: int
    
class RangeTracker:
    def __init__(self):
        self.ip_range = RangeState(combos={}, action_history=[], ...)
        self.oop_range = RangeState(combos={}, action_history=[], ...)
```

### Street-by-Street Walk
```python
def process_history(self, history: List[Action], hero_hand: str):
    self.init_preflop(history[0].position)
    
    for action in history:
        street = action.street
        position = action.position
        
        # Update the acting player's range
        self._update_range(
            range_state=self.get_range(position),
            action=action.type,  # bet/check/call/fold/raise
            amount=action.amount,
            street=street,
            board=get_board_at_street(street),
            pot=get_pot_before_action(action)
        )
        
        # Remove dead cards after each street transition
        if action.closes_street():
            self._remove_dead_cards(get_board_at_street(street + 1))
```

### The Update Rule (Per Action Type)
```python
def _update_range(self, range_state, action, amount, street, board, pot):
    range_state.total_count += 1
    
    if action == 'bet':
        # Blueprint-driven
        for hand, weight in range_state.combos.items():
            p_bet = self.blueprint.predict_bet(hand, board, street)
            range_state.combos[hand] = weight * p_bet
    
    elif action == 'check':
        for hand, weight in range_state.combos.items():
            p_bet = self.blueprint.predict_bet(hand, board, street)
            range_state.combos[hand] = weight * (1 - p_bet)
    
    elif action == 'call':
        # 🚩 HEURISTIC FALLBACK
        range_state.heuristic_count += 1
        bet_size = amount
        for hand, weight in range_state.combos.items():
            policy = self._facing_bet_policy(hand, board, bet_size, pot)
            range_state.combos[hand] = weight * policy['call']
    
    elif action == 'fold':
        range_state.heuristic_count += 1
        for hand, weight in range_state.combos.items():
            policy = self._facing_bet_policy(hand, board, amount, pot)
            range_state.combos[hand] = weight * policy['fold']
    
    elif action == 'raise':
        range_state.heuristic_count += 1
        # Raising range: polarized high equity + bluffs with blockers
        for hand, weight in range_state.combos.items():
            eq = calc_equity(hand, opponent_range, board)
            blocker = blocker_score(hand, board)
            
            if eq > 0.65 or (eq < 0.4 and blocker > 0.03):
                range_state.combos[hand] = weight * 0.15  # 15% raise freq
            else:
                range_state.combos[hand] = weight * 0.01  # rarely raise marginal
    
    self._normalize(range_state)
    range_state.action_history.append((action, street))
```

### Dead-Card Handling
```python
def _remove_dead_cards(self, board_cards: List[str]):
    dead = set(board_cards)
    
    for range_state in [self.ip_range, self.oop_range]:
        for hand_str in list(range_state.combos.keys()):
            if any(card in dead for card in parse_hand(hand_str)):
                del range_state.combos[hand_str]
        
        self._normalize(range_state)
```

### Normalization
```python
def _normalize(self, range_state):
    total = sum(range_state.combos.values())
    if total < 1e-9:
        raise ValueError("Range collapsed to zero")
    
    for hand in range_state.combos:
        range_state.combos[hand] /= total
```

### Emit to TexasSolver
```python
def emit_solver_range(self, position: str, dead_cards: Set[str]) -> str:
    range_state = self.get_range(position)
    
    entries = []
    for hand_str, weight in sorted(range_state.combos.items(), 
                                     key=lambda x: -x[1]):  # descending weight
        if weight < 1e-4:  # prune tiny weights
            continue
        if any(card in dead_cards for card in parse_hand(hand_str)):
            continue
        entries.append(f"{hand_str}:{weight:.6f}")
    
    if len(entries) == 0:
        raise ValueError(f"Empty range for {position}")
    
    return ",".join(entries)
```

---

## UNIT TESTS THAT GATE P0

```python
def test_basic_invariants():
    tracker = RangeTracker()
    tracker.init_preflop('SB')
    
    # Test 1: Sum to 1
    assert abs(sum(tracker.ip_range.combos.values()) - 1.0) < 0.01
    
    # Test 2: Process a bet, range shrinks
    initial_support = len(tracker.ip_range.combos)
    tracker.update('IP', 'bet', street='flop', board=['Ah', 'Kd', '7c'], pot=10, bet_size=5)
    assert len(tracker.ip_range.combos) <= initial_support
    
    # Test 3: Dead-card removal
    tracker._remove_dead_cards(['Ah', 'Kd', '7c'])
    for hand_str in tracker.ip_range.combos:
        assert 'Ah' not in parse_hand(hand_str)
        assert 'Kd' not in parse_hand(hand_str)

def test_equity_after_call():
    tracker = RangeTracker()
    # Simulate river call after a pot-sized bet
    tracker.update('OOP', 'call', street='river', board=RIVER_BOARD, pot=100, bet_size=100)
    
    avg_equity = compute_avg_equity(tracker.oop_range.combos, tracker.ip_range.combos, RIVER_BOARD)
    assert avg_equity > 0.33, "Calling range too weak"

def test_confidence_gate():
    tracker = RangeTracker()
    # Simulate a line with many heuristic actions
    for _ in range(5):
        tracker.update('IP', 'call', ...)  # all heuristic
    
    conf = tracker.confidence('IP', 'river')
    assert conf < 0.5, "Confidence should be low for heuristic-heavy line"

def test_solver_round_trip():
    tracker = RangeTracker()
    range_str = tracker.emit_solver_range('IP', dead_cards={'Ah', 'Kd'})
    
    # Verify TexasSolver can parse it
    solution = texasolver.solve(range_str, "random", board=BOARD, ...)
    assert solution is not None
```

---

## RISK SUMMARY

| Risk | Mitigation | Severity |
|------|-----------|----------|
| 🚩 Equity heuristic is exploitable | Clamp to MDF bounds, log exploitation metrics | **MEDIUM** |
| 🚩 Polarization multiplier assumes theory-trained blueprint | Disable if training was fixed-size | **LOW** |
| 🚩 Sparse ranges crash solver | Confidence gate + minimum support check | **HIGH** (mitigated) |
| 🚩 Heuristic-heavy lines degrade to floor anyway | Confidence gate ensures explicit fallback | **LOW** (by design) |
| 🚩 Blueprint trained on different stack depths | Track stack depth distribution in training, warn on mismatch | **MEDIUM** |

---

## FINAL CHECKLIST

- [ ] Implement `facing_bet_policy` with MDF + blocker adjustments  
- [ ] Add polarization multiplier for bet sizing (with training-data gate)  
- [ ] Per-combo weight dict, normalized after every update  
- [ ] Dead-card removal on street transitions  
- [ ] Emit TexasSolver range string with `:weight` syntax  
- [ ] Confidence metric: support size + effective combos + heuristic ratio  
- [ ] Resolver gate: `if confidence < 0.5: use floor`  
- [ ] Unit tests: invariants, equity sanity, solver round-trip  
- [ ] Integration test: 10 canonical spots with known GTO solutions  
- [ ] Logging: track heuristic usage, confidence scores, range support per street  

**This is shippable.** The heuristics are conservative, the gate is explicit, and the failure mode (fall back to floor) is acceptable. The blueprint drives where it has signal; equity + game theory drives where it doesn't. The resolver will get *better ranges than random*, and the confidence gate ensures you never silently make things worse. P0 unblocked.
