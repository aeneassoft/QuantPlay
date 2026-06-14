"""Lightweight opponent model for exploitative adjustments.

Tracks a few high-signal tendencies across hands. Adjustments are blended toward the
GTO baseline until enough samples accumulate (so early hands stay near-optimal).
"""
from __future__ import annotations


class OpponentModel:
    def __init__(self) -> None:
        self.hands = 0
        # preflop
        self.pf_actions = 0
        self.pf_vpip = 0            # called or raised preflop
        self.pf_raises = 0
        self.faced_open = 0
        self.threebet = 0
        # facing aggression
        self.faced_bet = 0
        self.fold_to_bet = 0
        # taking aggression
        self.could_bet = 0
        self.did_bet = 0

    # --- recording -------------------------------------------------------
    def record(self, street: str, action: str, facing_bet: bool) -> None:
        if street == "preflop":
            self.pf_actions += 1
            if action in ("call", "bet", "raise", "allin"):
                self.pf_vpip += 1
            if action in ("bet", "raise", "allin"):
                self.pf_raises += 1
        if facing_bet:
            self.faced_bet += 1
            if action == "fold":
                self.fold_to_bet += 1
        else:
            self.could_bet += 1
            if action in ("bet", "raise", "allin"):
                self.did_bet += 1

    def end_hand(self) -> None:
        self.hands += 1

    # --- read-outs (with sane priors) ------------------------------------
    # Bayesian shrinkage toward the prior (pseudo-count k): at n=4 the raw rate has se~0.25, so blend
    # toward the prior rather than a hard <4 gate that jumps prior->raw (matches adaptive._shrink).
    def fold_to_bet_freq(self, k: int = 6) -> float:
        return (self.fold_to_bet + 0.5 * k) / (self.faced_bet + k)

    def aggression_freq(self, k: int = 6) -> float:
        return (self.did_bet + 0.5 * k) / (self.could_bet + k)

    def vpip(self, k: int = 6) -> float:
        return (self.pf_vpip + 0.7 * k) / (self.pf_actions + k)  # HU baseline is loose (prior 0.7)

    def confidence(self) -> float:
        """0..1 — how much to trust the reads (scales exploit strength)."""
        return min(1.0, self.faced_bet / 20.0 + self.pf_actions / 30.0)

    def summary(self) -> dict:
        return {
            "hands": self.hands,
            "vpip": round(self.vpip(), 2),
            "fold_to_bet": round(self.fold_to_bet_freq(), 2),
            "aggression": round(self.aggression_freq(), 2),
            "confidence": round(self.confidence(), 2),
        }
