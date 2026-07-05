"""Heads-Up No-Limit Hold'em game state machine.

Chips are integers. In HU the Button is also the Small Blind: it acts FIRST preflop and
LAST postflop. Designed so the betting/showdown core can later generalize to >2 players.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from pokerbot.engine.cards import Deck
from pokerbot.engine.evaluator import best_five_name, evaluate

STREETS = ["preflop", "flop", "turn", "river"]
_DEAL = {"flop": 3, "turn": 1, "river": 1}


@dataclass
class Player:
    name: str
    stack: int
    hole: list[str] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    committed_street: int = 0   # chips put in this street
    committed_total: int = 0    # chips put in this hand
    has_acted: bool = False     # acted (voluntarily) since the last aggression this street


class HeadsUpGame:
    def __init__(self, names=("You", "Bot"), starting_stack=10000, sb=50, bb=100, seed=None):
        self.sb, self.bb, self.start_stack = sb, bb, starting_stack
        self.rng = random.Random(seed)
        self.players = [Player(names[0], starting_stack), Player(names[1], starting_stack)]
        self.button = 1            # flips to 0 on the first hand
        self.hand_no = 0
        self.board: list[str] = []
        self.street = "preflop"
        self.deck: Deck | None = None
        self.current_bet = 0
        self.min_raise = bb
        self.to_act: int | None = None
        self.hand_over = True
        self.result: dict | None = None
        self.history: list[dict] = []

    # ------------------------------------------------------------------ helpers
    def _other(self, i: int) -> int:
        return 1 - i

    def pot(self) -> int:
        return sum(p.committed_total for p in self.players)

    def match_over(self) -> bool:
        return any(p.stack <= 0 for p in self.players) and self.hand_over

    def _commit(self, idx: int, amount: int) -> int:
        p = self.players[idx]
        actual = min(amount, p.stack)
        p.stack -= actual
        p.committed_street += actual
        p.committed_total += actual
        if p.stack == 0:
            p.all_in = True
        return actual

    # ------------------------------------------------------------------ hand setup
    def start_hand(self) -> None:
        if any(p.stack <= 0 for p in self.players):
            raise RuntimeError("A player is busted; the match is over.")
        self.hand_no += 1
        self.button = 0 if self.hand_no == 1 else self._other(self.button)
        for p in self.players:
            p.hole = []
            p.folded = p.all_in = p.has_acted = False
            p.committed_street = p.committed_total = 0
        self.board = []
        self.street = "preflop"
        self.current_bet = 0
        self.min_raise = self.bb
        self.hand_over = False
        self.result = None
        self.history = []
        self.deck = Deck(rng=self.rng)
        for p in self.players:
            p.hole = self.deck.deal(2)

        sb_idx = self.button                 # BTN = SB in HU
        bb_idx = self._other(self.button)
        self._commit(sb_idx, self.sb)
        self._commit(bb_idx, self.bb)
        self.current_bet = self.bb
        self.min_raise = self.bb
        self.to_act = sb_idx                 # SB/BTN acts first preflop

    # ------------------------------------------------------------------ legality
    def legal_actions(self) -> dict:
        if self.hand_over or self.to_act is None:
            return {"to_act": None}
        i = self.to_act
        p, opp = self.players[i], self.players[self._other(self.to_act)]
        to_call = self.current_bet - p.committed_street
        can_check = to_call == 0
        can_call = to_call > 0
        call_amount = min(to_call, p.stack)
        # raising
        can_raise = (p.stack > to_call) and (not opp.all_in)
        raise_min = raise_max = None
        is_bet = self.current_bet == 0
        if can_raise:
            raise_max = p.committed_street + p.stack          # all-in (to)
            if is_bet:
                raise_min = min(p.committed_street + self.bb, raise_max)
            else:
                raise_min = min(self.current_bet + self.min_raise, raise_max)
        return {
            "to_act": i,
            "to_call": to_call,
            "can_fold": can_call,            # only meaningful to fold when facing a bet
            "can_check": can_check,
            "can_call": can_call,
            "call_amount": call_amount,
            "can_raise": can_raise,
            "is_bet": is_bet,                # True => label 'bet', else 'raise'
            "raise_min": raise_min,          # target total street commitment
            "raise_max": raise_max,
            "pot": self.pot(),
        }

    # ------------------------------------------------------------------ actions
    def act(self, action: str, amount: int | None = None) -> None:
        if self.hand_over:
            raise RuntimeError("Hand is over.")
        la = self.legal_actions()
        i = self.to_act
        p = self.players[i]
        opp_idx = self._other(i)
        opp = self.players[opp_idx]
        action = action.lower()

        if action == "fold":
            p.folded = True
            self.history.append({"player": i, "action": "fold", "street": self.street})
            self._end_hand_by_fold(opp_idx)
            return

        if action == "check":
            if not la["can_check"]:
                raise ValueError("Cannot check.")
            p.has_acted = True
            self.history.append({"player": i, "action": "check", "street": self.street})

        elif action == "call":
            if not la["can_call"]:
                raise ValueError("Cannot call.")
            self._commit(i, la["to_call"])
            p.has_acted = True
            self.history.append({"player": i, "action": "call", "amount": la["call_amount"],
                                 "street": self.street})

        elif action in ("bet", "raise", "allin"):
            if not la["can_raise"]:
                raise ValueError("Cannot bet/raise.")
            if action == "allin":
                target = la["raise_max"]
            else:
                if amount is None:
                    raise ValueError("bet/raise needs a target amount.")
                target = int(amount)
            target = max(la["raise_min"], min(target, la["raise_max"]))
            prev_bet = self.current_bet
            self._commit(i, target - p.committed_street)
            self.current_bet = p.committed_street
            increment = self.current_bet - prev_bet
            if increment >= self.min_raise:
                self.min_raise = increment
            opp.has_acted = False            # opponent must respond to the (re)raise
            p.has_acted = True
            label = "bet" if prev_bet == 0 else "raise"
            self.history.append({"player": i, "action": label, "to": self.current_bet,
                                 "street": self.street})
        else:
            raise ValueError(f"Unknown action: {action}")

        self._advance_after_action()

    # ------------------------------------------------------------------ flow control
    def _advance_after_action(self) -> None:
        active = [k for k, pl in enumerate(self.players) if not pl.folded]
        if len(active) == 1:
            self._end_hand_by_fold(active[0])
            return
        round_over = all(
            self.players[k].all_in or
            (self.players[k].has_acted and self.players[k].committed_street == self.current_bet)
            for k in active
        )
        if not round_over:
            self.to_act = self._other(self.to_act)
            # if the next player is all-in (nothing to do), skip — handled by round_over next loop
            if self.players[self.to_act].all_in:
                self._advance_after_action()
            return
        self._close_betting_round()

    def _close_betting_round(self) -> None:
        self._refund_uncalled()
        for p in self.players:
            p.committed_street = 0
            p.has_acted = False
        self.current_bet = 0
        self.min_raise = self.bb

        active = [k for k, pl in enumerate(self.players) if not pl.folded]
        someone_all_in = any(self.players[k].all_in for k in active)

        if someone_all_in and len(active) > 1:
            # No more betting possible — run out the board and show down.
            while len(self.board) < 5:
                self._deal_next_street(silent=True)
            self._showdown()
            return

        if self.street == "river":
            self._showdown()
            return

        self._deal_next_street()
        # postflop: out-of-position player (the BB, i.e. non-button) acts first
        self.to_act = self._other(self.button)
        if self.players[self.to_act].folded or self.players[self.to_act].all_in:
            self.to_act = self._other(self.to_act)

    def _deal_next_street(self, silent: bool = False) -> None:
        nxt = STREETS[STREETS.index(self.street) + 1]
        self.street = nxt
        self.board += self.deck.deal(_DEAL[nxt])
        if not silent:
            self.history.append({"action": "deal", "street": nxt, "board": list(self.board)})

    def _refund_uncalled(self) -> None:
        active = [self.players[k] for k in range(2) if not self.players[k].folded]
        if len(active) < 2:
            return
        commits = sorted((pl.committed_street for pl in active), reverse=True)
        if commits[0] > commits[1]:
            diff = commits[0] - commits[1]
            top = max(active, key=lambda pl: pl.committed_street)
            top.stack += diff
            top.committed_street -= diff
            top.committed_total -= diff

    # ------------------------------------------------------------------ resolution
    def _end_hand_by_fold(self, winner_idx: int) -> None:
        self._refund_uncalled()
        pot = self.pot()
        self.players[winner_idx].stack += pot
        self.result = {"winner": winner_idx, "reason": "fold", "pot": pot,
                       "reveal": False, "board": list(self.board)}
        self.to_act = None
        self.hand_over = True

    def _showdown(self) -> None:
        i, j = 0, 1
        si = evaluate(self.board, self.players[i].hole)
        sj = evaluate(self.board, self.players[j].hole)
        pot = self.pot()
        if si < sj:
            winner = i
        elif sj < si:
            winner = j
        else:
            winner = None
        if winner is None:                       # split (odd chip to BB)
            half = pot // 2
            self.players[0].stack += half
            self.players[1].stack += pot - half
        else:
            self.players[winner].stack += pot
        self.result = {
            "winner": winner, "reason": "showdown", "pot": pot, "reveal": True,
            "board": list(self.board),
            "hands": [{"name": self.players[k].name, "hole": self.players[k].hole,
                       "rank": best_five_name(self.board, self.players[k].hole)} for k in (0, 1)],
        }
        self.to_act = None
        self.hand_over = True

    # ------------------------------------------------------------------ snapshot
    def state(self, hide: int | None = None) -> dict:
        def pview(k: int) -> dict:
            p = self.players[k]
            hole = p.hole
            if hide is not None and k == hide and not (self.result and self.result.get("reveal")):
                hole = ["??", "??"]
            return {"idx": k, "name": p.name, "stack": p.stack, "hole": hole,
                    "folded": p.folded, "all_in": p.all_in,
                    "committed_street": p.committed_street, "committed_total": p.committed_total,
                    "is_button": k == self.button}
        return {
            "hand_no": self.hand_no, "button": self.button, "street": self.street,
            "board": list(self.board), "pot": self.pot(), "current_bet": self.current_bet,
            "to_act": self.to_act, "hand_over": self.hand_over, "result": self.result,
            "sb": self.sb, "bb": self.bb, "history": list(self.history),
            "players": [pview(0), pview(1)],
            "legal": self.legal_actions() if not self.hand_over else {"to_act": None},
        }
