# 4_venice — range-tracker P0 consult

Elapsed: 12.4s

---

### Red Team Review of P0: The Range Tracker

#### (1) Incomplete-Blueprint Update

The blueprint's restricted output (P(bet) only) necessitates a policy for actions it doesn't cover: facing-bet defense (call/fold/raise) and bet sizes. Here are implementable rules:

- **Call/Check:** When villain calls, use the blueprint's `(1 - P(bet|h))` as the call policy. For checks, use `P(bet|h)` as the check policy. This indirectly infers a call probability of `1 - P(check)`.

- **Fold:** When villain folds, assign a fold probability of `P(fold) = 1 - P(call) - P(raise)`, using the call and raise probabilities from above. This ensures consistency.

- **Raise:** For a raise, use `P(raise) = 1 - P(call) - P(fold)`. If the blueprint outputs `P(bet)`, assume `P(raise)` is proportional to the raise size relative to the pot.

- **Bet Size:** If a bet size is specified, scale the bet probability by the size ratio. For example, a 0.5-pot bet gets `P(bet) * 0.5`.

These rules maintain range coherence but may not be perfect. Validate by simulating hand histories.

#### (2) Per-Combo Weighted Ranges in TexasSolver

Feeding per-combo weighted ranges (e.g., `AsKh:0.62`) is theoretically sound but has trade-offs:

- **Fidelity:** Per-combo weights preserve nuance but increase solve times.
- **Aggregation:** Class-level averages simplify but lose detail.

For v1, use per-combo weights for their fidelity. Monitor solve times and adjust if needed.

#### (3) Own-Range vs. Villain-Range Fidelity

Both ranges matter, but villain-range fidelity is often more critical. The resolver uses our range only for sampling our strategy, while the villain range directly affects their optimal response. Prioritize villain-range accuracy, especially for raises/calls.

#### (4) Validation Without Ground Truth

Leverage solver-based and equity-based checks:

- **Solve Consistency:** Ensure the tracker's ranges, when input into TexasSolver, return strategies that pass a pre-defined GTO test (e.g., no +EV exploits).
- **Equity-Based:** Simulate hand histories using the tracker's ranges. Compare the tracked ranges' equity distribution to the blueprint's expected equity. Large deviations indicate issues.

#### (5) The Safe Minimum-Viable Tracker

The simplest safe tracker updates ranges as follows:

- **Bet/Check:** Update as per (1) using the blueprint's `P(bet)`.
- **Facing Bet (Call/Raise/Fold):** Use the rules from (1).
- **Bet Size:** Ignore size; treat as a standard bet.

No gate on range confidence is necessary. This tracker is robust to inaccuracies and cannot degrade performance below the floor.

#### Risks and Detection

**(a) P(bet)-only blueprint's crudeness:** If `P(bet)` is the only policy, the tracker may be too crude. Test by comparing the tracker's ranges to those from a full-distribution blueprint. Large divergences indicate a problem.

**(b) Effort misallocation:** The team might overinvest in the tracker. Evaluate the marginal GTO improvement from a fully developed tracker vs. other components (e.g., blueprint, resolver). If gains are minimal, pivot resources.

**(c) The ONE thing:** If the blueprint's `P(bet)` is uncorrelated with optimal play, the tracker is useless. Detect this by comparing `P(bet)` to `P(optimal bet)` on a large hand dataset. Low correlation implies a waste.

---

### Conclusion

The P0 range tracker plan is theoretically sound but faces risks. Address (1)-(5) to mitigate these. If the red team's tests pass, P0 will be a robust foundation. If not, reassess the blueprint or pivot to other GTO improvements.
