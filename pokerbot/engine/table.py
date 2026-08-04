"""N-player (3-6) No-Limit Hold'em table with correct side pots.

Standard positions: SB = button+1, BB = button+2, UTG (first to act preflop) = button+3.
Postflop the first active player left of the button acts first. Auto-rebuy keeps seats full
for a casual session. Designed for the play-vs-bots web app.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from pokerbot.engine.cards import Deck
from pokerbot.engine.evaluator import best_five_name, evaluate

STREETS = ["preflop", "flop", "turn", "river"]
_DEAL = {"flop": 3, "turn": 1, "river": 1}
POS_LABELS = {  # by offset from button among N active players (button = offset 0 from the end)
    10: ["BTN", "SB", "BB", "UTG", "UTG+1", "UTG+2", "UTG+3", "LJ", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    4: ["BTN", "SB", "BB", "CO"],
    3: ["BTN", "SB", "BB"],
    2: ["BTN", "BB"],
}


@dataclass
class Seat:
    name: str
    stack: int
    is_human: bool = False
    hole: list[str] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    committed_street: int = 0
    committed_total: int = 0
    has_acted: bool = False


class Table:
    def __init__(self, names, starting_stack=10000, sb=50, bb=100, seed=None,
                 human_seat=0, stacks=None, ante=0, rebuy=True):
        self.n = len(names)
        self.sb, self.bb, self.start_stack = sb, bb, starting_stack
        # Turnier-Erweiterungen (2026-08-04), alle default-identisch zum Cash-Verhalten:
        # stacks = individuelle Startstacks (Turnier: ungleich), ante = tote Vorab-Steuer je Hand,
        # rebuy=False laesst Pleite-Spieler pleite (der Direktor eliminiert sie zwischen den Haenden).
        self.ante, self.rebuy = ante, rebuy
        self.rng = random.Random(seed)
        per_seat = list(stacks) if stacks is not None else [starting_stack] * self.n
        self.seats = [Seat(nm, per_seat[i], is_human=(i == human_seat))
                      for i, nm in enumerate(names)]
        self.button = self.rng.randrange(self.n)
        self.hand_no = 0
        self.board: list[str] = []
        self.street = "preflop"
        self.deck: Deck | None = None
        self.current_bet = 0
        self.min_raise = bb
        self.to_act: int | None = None
        self.preflop_raises = 0
        self.hand_over = True
        self.result: dict | None = None
        self.history: list[dict] = []

    # ------------------------------------------------------------- helpers
    def _clockwise(self, start: int):
        for k in range(self.n):
            yield (start + k) % self.n

    def _commit(self, i: int, amount: int) -> int:
        s = self.seats[i]
        actual = min(amount, s.stack)
        s.stack -= actual
        s.committed_street += actual
        s.committed_total += actual
        if s.stack == 0:
            s.all_in = True
        return actual

    def _active(self):
        return [i for i, s in enumerate(self.seats) if not s.folded]

    def _can_act(self, i):
        s = self.seats[i]
        return not s.folded and not s.all_in

    def pot(self) -> int:
        return sum(s.committed_total for s in self.seats)

    def position_label(self, seat: int) -> str:
        labels = POS_LABELS.get(self.n, ["P"] * self.n)
        order = list(self._clockwise(self.button))   # order[0]=button, [1]=SB, ...
        # map: button -> BTN, then SB, BB, ...
        seq = ["BTN"] + labels[1:]
        idx = order.index(seat)
        return seq[idx] if idx < len(seq) else "?"

    # ------------------------------------------------------------- setup
    def start_hand(self) -> None:
        for s in self.seats:                       # auto-rebuy so the table stays full (Cash-Modus)
            if self.rebuy and s.stack < self.bb:
                s.stack = self.start_stack
            s.hole = []
            s.folded = s.all_in = s.has_acted = False
            s.committed_street = s.committed_total = 0
        self.hand_no += 1
        self.button = (self.button + 1) % self.n
        self.board = []
        self.street = "preflop"
        self.current_bet = self.bb
        self.min_raise = self.bb
        self.preflop_raises = 0
        self.hand_over = False
        self.result = None
        self.history = []
        self.deck = Deck(rng=self.rng)
        for i in self._clockwise(self.button):
            self.seats[i].hole = self.deck.deal(2)

        if self.ante:
            # Antes VOR den Blinds (Turnier): tote Steuer jedes Sitzes; _commit kappt am Stack,
            # ein Kurzstack kann also schon durch die Ante all-in sein — die Side-Pot-Logik
            # rechnet ueber committed_total ohnehin korrekt. Die Ante ist KEIN Street-Einsatz:
            # committed_street muss danach 0 sein, sonst zaehlt sie gegen current_bet (der BB
            # bekaeme to_call<0 -> can_check False -> Fold im Limped-Pot; Caller zahlten
            # bb-ante; die Ante-Schicht ueber dem hoechsten Eligible-Layer verwaiste bei der
            # Auszahlung — alle drei im 600er-MTT-Audit gefangen, Chip-Erhaltung -32/Tisch).
            for i in self._clockwise(self.button):
                self._commit(i, self.ante)
                self.seats[i].committed_street = 0
            self.history.append({"action": "antes", "amount": self.ante})
        if self.n == 2:
            # HEADS-UP-Regel: der Button IST der Small Blind, setzt zuerst preflop und zuletzt
            # postflop. Vorher invertiert (Button zahlte BB) — vom 600er-MTT-Review gefangen;
            # betraf jedes Multiway-Endspiel, das auf 2 Spieler schrumpfte.
            sb_i, bb_i = self.button, (self.button + 1) % 2
        else:
            sb_i = (self.button + 1) % self.n
            bb_i = (self.button + 2) % self.n
        self._commit(sb_i, self.sb)
        self._commit(bb_i, self.bb)
        self.history.append({"action": "blinds", "sb": sb_i, "bb": bb_i})
        # UTG (button+3) acts first preflop; heads-up: button/SB acts first
        start = self.button if self.n == 2 else (self.button + 3) % self.n
        self.to_act = self._find_actor(start)
        if self.to_act is None and not self.hand_over:
            # ALLE Sitze schon durch Antes/Blinds all-in (spaete Turnier-Level): niemand kann
            # handeln -> direkt ausspielen, sonst wird der Pot vernichtet und der rechtmaessige
            # Gewinner als Bust gewertet (Review-Fund #5).
            self._close_round()

    def _find_actor(self, start: int):
        for i in self._clockwise(start):
            if self._can_act(i):
                return i
        return None

    # ------------------------------------------------------------- legality
    def legal_actions(self) -> dict:
        if self.hand_over or self.to_act is None:
            return {"to_act": None}
        i = self.to_act
        s = self.seats[i]
        to_call = self.current_bet - s.committed_street
        others_live = any(j != i and self._can_act(j) for j in range(self.n))
        can_raise = s.stack > to_call and others_live
        is_bet = self.current_bet == 0
        raise_max = s.committed_street + s.stack
        if is_bet:
            raise_min = min(s.committed_street + self.bb, raise_max)
        else:
            raise_min = min(self.current_bet + self.min_raise, raise_max)
        return {"to_act": i, "to_call": to_call, "can_fold": to_call > 0,
                "can_check": to_call == 0, "can_call": to_call > 0,
                "call_amount": min(to_call, s.stack), "can_raise": can_raise,
                "is_bet": is_bet, "raise_min": raise_min if can_raise else None,
                "raise_max": raise_max if can_raise else None, "pot": self.pot()}

    # ------------------------------------------------------------- actions
    def act(self, action: str, amount: int | None = None) -> None:
        if self.hand_over:
            raise RuntimeError("hand over")
        la = self.legal_actions()
        i = self.to_act
        s = self.seats[i]
        action = action.lower()
        if action == "fold":
            s.folded = True
            self.history.append({"player": i, "action": "fold", "street": self.street})
        elif action == "check":
            if not la["can_check"]:
                raise ValueError("cannot check")
            s.has_acted = True
            self.history.append({"player": i, "action": "check", "street": self.street})
        elif action == "call":
            if not la["can_call"]:
                raise ValueError("cannot call")
            amt = self._commit(i, la["to_call"])
            s.has_acted = True
            self.history.append({"player": i, "action": "call", "amount": amt, "street": self.street})
        elif action in ("bet", "raise", "allin"):
            if not la["can_raise"]:
                raise ValueError("cannot raise")
            target = la["raise_max"] if action == "allin" else max(la["raise_min"], min(int(amount), la["raise_max"]))
            prev = self.current_bet
            self._commit(i, target - s.committed_street)
            self.current_bet = s.committed_street
            inc = self.current_bet - prev
            if inc >= self.min_raise:
                self.min_raise = inc
            for j in range(self.n):                 # a (re)raise reopens action
                if j != i and self._can_act(j):
                    self.seats[j].has_acted = False
            s.has_acted = True
            if self.street == "preflop":
                self.preflop_raises += 1
            self.history.append({"player": i, "action": "bet" if prev == 0 else "raise",
                                 "to": self.current_bet, "street": self.street})
        else:
            raise ValueError(f"bad action {action}")
        self._advance()

    def _advance(self) -> None:
        if len(self._active()) == 1:
            self._end_single(self._active()[0])
            return
        nxt = None
        for j in self._clockwise((self.to_act + 1) % self.n):
            s = self.seats[j]
            if self._can_act(j) and (not s.has_acted or s.committed_street < self.current_bet):
                nxt = j
                break
        if nxt is None:
            self._close_round()
        else:
            self.to_act = nxt

    def _close_round(self) -> None:
        for s in self.seats:
            s.committed_street = 0
            s.has_acted = False
        self.current_bet = 0
        self.min_raise = self.bb
        active = self._active()
        if len(active) == 1:
            self._end_single(active[0])
            return
        can_still = [i for i in active if self._can_act(i)]
        if len(can_still) <= 1:                      # all-in: run it out
            while len(self.board) < 5:
                self._deal_next(silent=True)
            self._showdown()
            return
        if self.street == "river":
            self._showdown()
            return
        self._deal_next()
        self.to_act = self._find_actor((self.button + 1) % self.n)  # SB-side acts first postflop

    def _deal_next(self, silent: bool = False) -> None:
        nxt = STREETS[STREETS.index(self.street) + 1]
        self.street = nxt
        self.board += self.deck.deal(_DEAL[nxt])
        if not silent:
            self.history.append({"action": "deal", "street": nxt, "board": list(self.board)})

    # ------------------------------------------------------------- resolution
    def _build_pots(self):
        contribs = {i: s.committed_total for i, s in enumerate(self.seats) if s.committed_total > 0}
        pots = []
        while contribs:
            m = min(contribs.values())
            members = list(contribs.keys())
            amt = m * len(members)
            eligible = [i for i in members if not self.seats[i].folded]
            pots.append((amt, eligible, m, members))
            for i in members:
                contribs[i] -= m
                if contribs[i] == 0:
                    del contribs[i]
        return pots

    def _end_single(self, winner: int) -> None:
        pot = self.pot()
        self.seats[winner].stack += pot
        self.result = {"reason": "fold", "pot": pot, "reveal": False,
                       "winners": [{"seat": winner, "name": self.seats[winner].name, "amount": pot}],
                       "board": list(self.board)}
        self.to_act = None
        self.hand_over = True

    def _showdown(self) -> None:
        pots = self._build_pots()
        winnings = {i: 0 for i in range(self.n)}
        refunds = {i: 0 for i in range(self.n)}
        pot_results = []
        for amt, eligible, layer, members in pots:
            if not eligible:
                # VERWAISTE Schicht: nur Chips gefoldeter Spieler (Fold OBERHALB eines
                # All-in-Caps). Niemand kann sie gewinnen -> zurueck an die Einzahler, sonst
                # werden sie vernichtet (Fuzz-Fund: -99 Chips auch ohne Antes moeglich).
                # Getrennt von winnings: eine Rueckerstattung ist kein Gewinn (kein Reveal).
                for i in members:
                    refunds[i] += layer
                continue
            scores = {i: evaluate(self.board, self.seats[i].hole) for i in eligible}
            best = min(scores.values())
            winners = [i for i in eligible if scores[i] == best]
            share = amt // len(winners)
            rem = amt - share * len(winners)
            for w in winners:
                winnings[w] += share
            # odd chip to first winner clockwise from button
            for j in self._clockwise((self.button + 1) % self.n):
                if j in winners:
                    winnings[j] += rem
                    break
            pot_results.append({"amount": amt, "winners": [self.seats[w].name for w in winners]})
        for i, w in winnings.items():
            self.seats[i].stack += w + refunds[i]
        winners_list = [{"seat": i, "name": self.seats[i].name, "amount": w,
                         "rank": best_five_name(self.board, self.seats[i].hole)}
                        for i, w in winnings.items() if w > 0]
        self.result = {
            "reason": "showdown", "pot": self.pot(), "reveal": True, "pots": pot_results,
            "board": list(self.board),
            "winners": winners_list,
            # mucking: only winners reveal their cards (nobody else has to show)
            "shown": {w["seat"]: {"hole": self.seats[w["seat"]].hole, "rank": w["rank"]}
                      for w in winners_list},
        }
        self.to_act = None
        self.hand_over = True

    # ------------------------------------------------------------- obs for bots
    def obs_for(self, seat: int) -> dict:
        s = self.seats[seat]
        la = self.legal_actions()
        return {
            "hole": s.hole, "board": list(self.board),
            "to_call": la["to_call"], "pot": self.pot(), "my_stack": s.stack,
            "bb": self.bb, "n_active": len(self._active()),
            "position": self.position_label(seat), "preflop_raises": self.preflop_raises,
            "cur_bet": self.current_bet, "my_committed_street": s.committed_street,
            "street": self.street, "can_check": la["can_check"], "can_call": la["can_call"],
            "can_raise": la["can_raise"],
            "raise_min": la["raise_min"], "raise_max": la["raise_max"],
        }
