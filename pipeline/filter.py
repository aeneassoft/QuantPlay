"""The deterministic EV-TRUTH filter — the PC-hub's anti-hallucination gate (Phase 3, the heart).

The architecture's hardest rule (CLAUDE.md clean boundary): FRONTIER models are a PRIOR, the ENGINE is TRUTH. Every
frontier-distilled candidate passes a HARD-CODED, deterministic CPU gate before it can enter the dataset. No frontier
claim is trusted; only an engine-verifiable one survives. This is what stops the −10/−30 imitation/hallucination
ceiling from being re-imported through distillation.

Gates (in order):
  G1 schema     — valid record (dataset/schema.validate)
  G2 relevance  — poker/strategy/math/code only (the user's "no hair-shampoo" gate)
  G3 decontam   — spot-key NOT in the PokerBench test set (no train/test leak)
  G4 dedup      — spot-key not already seen this run
  G5 legality   — STRUCTURED spots: the proposed action is LEGAL as-is (the engine is truth)
  G6 EV-sanity  — STRUCTURED spots: reject gross -EV blunders the engine can PROVE:
                    * fold for free (dominated by a free check)
                    * call with equity clearly below the pot-odds break-even, measured vs a GENEROUS (random) range
                      so we only ever reject a CLEAR loser (vs a real betting range hero equity is even lower)

Structured spots (a `Spot`) get G1–G6; text-only candidates (prose→DSL distillations) get G1–G4 — the engine cannot
EV-check a spot it cannot compute on, so those rely on relevance + dedup + decontam (stated honestly).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

from dataset import schema
from pokerbot.brain import api
from pokerbot.brain.format_spot import Spot
from pokerbot.engine.cards import make_deck

_DECK = make_deck()
CALL_EQ_MARGIN = 0.15          # reject a call only if equity is CLEARLY below break-even (conservative: few false drops)
_EQ_ITERS = 400                # MC iters for the random-range bound (river enumerates exactly inside equity)


def _norm(a: str) -> str:
    """Collapse the aggressive family (bet/raise/all-in legalize interchangeably) so naming alone never trips G5."""
    a = (a or "").lower()
    return "aggressive" if a in ("bet", "raise", "allin", "all-in") else a


def _random_equity(hero: list, board: list | None, seed: int = 0) -> float:
    """Hero equity vs a UNIFORM random hand = a generous UPPER bound on hero's true equity vs any betting range."""
    dead = set(hero) | set(board or [])
    combos = [c for c in itertools.combinations([c for c in _DECK if c not in dead], 2)]
    return api.equity(hero, combos, board, iters=_EQ_ITERS, seed=seed)


@dataclass
class Verdict:
    ok: bool
    reason: str
    gate: str = ""


class EVFilter:
    """Stateful gate (tracks `seen` for dedup + the decontam set). One instance per build/loop run."""

    def __init__(self, decontam_keys: set | None = None):
        self.decontam = set(decontam_keys or set())
        self.seen: set = set()
        self.stats = {"in": 0, "kept": 0, "schema": 0, "irrelevant": 0,
                      "decontam": 0, "dup": 0, "illegal": 0, "ev": 0}

    def _common(self, ex: dict) -> Verdict | None:
        if not schema.validate(ex):
            self.stats["schema"] += 1
            return Verdict(False, "invalid record", "G1")
        if not schema.is_relevant(ex["spot"] + " " + ex["completion"]):
            self.stats["irrelevant"] += 1
            return Verdict(False, "off-domain (no poker/math content)", "G2")
        k = schema.spot_key(ex["spot"])
        if k in self.decontam:
            self.stats["decontam"] += 1
            return Verdict(False, "PokerBench-test leak", "G3")
        if k in self.seen:
            self.stats["dup"] += 1
            return Verdict(False, "duplicate spot", "G4")
        return None

    def _engine(self, ex: dict, spot: Spot) -> Verdict | None:
        act = ex.get("action") or {}
        a = (act.get("action") or "").lower()
        coerced, _ = api.legalize(spot, a, act.get("size_bb"))
        if _norm(coerced) != _norm(a):
            self.stats["illegal"] += 1
            return Verdict(False, f"illegal action: {a or '∅'} -> engine forces {coerced}", "G5")
        if a == "fold" and spot.to_call == 0:
            self.stats["ev"] += 1
            return Verdict(False, "fold for free (dominated by a free check)", "G6")
        if a == "call" and spot.to_call > 0:
            req = api.required_equity(spot.to_call, spot.pot)
            eq = _random_equity(spot.hero_hole, spot.board)
            if eq + CALL_EQ_MARGIN < req:
                self.stats["ev"] += 1
                return Verdict(False, f"call eq {eq:.2f} << break-even {req:.2f} (vs a generous range)", "G6")
        return None

    def gate(self, ex: dict, spot: Spot | None = None) -> Verdict:
        """Run the full gate. `ex` = a dataset record (dataset.schema.make_example). Pass the structured `spot` to
        enable G5/G6 (legality + EV-sanity); omit it for prose→DSL text candidates (G1–G4 only)."""
        self.stats["in"] += 1
        v = self._common(ex)
        if v:
            return v
        if spot is not None:
            v = self._engine(ex, spot)
            if v:
                return v
        self.seen.add(schema.spot_key(ex["spot"]))
        self.stats["kept"] += 1
        return Verdict(True, "accepted")
