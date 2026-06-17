"""The canonical 6-max poker SPOT — the single, source-agnostic representation the LLM brain sees, byte-identical
across SFT / RL self-play / live inference / eval (per docs/DATASET_SPEC.md). Aligned to PokerBench's encoding
(positions UTG/HJ/CO/BTN/SB/BB, the betting line, board, pot, hero holding, legal moves), in BIG-BLIND units.

`Spot` is the dataclass; `spot_from_table(table, seat)` builds it from the live engine (`pokerbot/engine/table.py`,
the RL environment); `format_spot(spot)` renders the canonical prompt text. `ACTION_RE` is the shared output parser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The ONE output contract: the brain ends with `ACTION: <fold|check|call|bet N|raise N|all-in>` (N = total bet in bb).
ACTION_RE = re.compile(r"ACTION:\s*(fold|check|call|all-in|allin|bet|raise)\s*([0-9]*\.?[0-9]+)?", re.IGNORECASE)


@dataclass
class Spot:
    """A poker decision point in canonical form. Chip fields are RAW engine chips; `bb` is the big blind in chips."""
    street: str                      # preflop|flop|turn|river
    board: list                      # ['As','Kd','2h', ...]
    bb: int                          # big blind in chips (100 in our engine)
    hero_seat: int
    hero_pos: str                    # BTN|SB|BB|UTG|HJ|CO
    hero_hole: list                  # ['As','Kd']
    pot: int                         # chips
    to_call: int                     # chips
    n_active: int
    seats: list = field(default_factory=list)    # [{seat,pos,stack,committed_total,folded,all_in}]
    legal: dict = field(default_factory=dict)    # {can_fold,can_check,can_call,can_raise,raise_min,raise_max} (chips)
    line: list = field(default_factory=list)     # ordered [{street,pos,action,amount_bb}] (public actions only)
    villain_fold: float = 0.5    # observed villain fold-to-bet tendency in [0,1] (0.5 = neutral/unknown) — the "which-GTO-here" READ
    villain_aggro: float = 0.5   # observed villain aggression in [0,1] (a session-accumulated, confidence-gated read)

    def b(self, chips) -> float:
        """chips -> big blinds (rounded)."""
        return round((chips or 0) / self.bb, 2)


def _line_from_history(table, hero_seat) -> list:
    out = []
    for h in table.history:
        a = h.get("action")
        if a in ("blinds", "deal"):
            continue
        seat = h.get("player")
        if seat is None:
            continue
        amt = h.get("to", h.get("amount"))
        out.append({"street": h.get("street", "preflop"), "pos": table.position_label(seat),
                    "action": a, "amount_bb": (round((amt or 0) / table.bb, 2) if amt else None),
                    "hero": seat == hero_seat})
    return out


def spot_from_table(table, seat: int) -> "Spot":
    """Build the canonical Spot from a live Table at `seat`'s decision point."""
    la = table.legal_actions()
    s = table.seats[seat]
    seats = [{"seat": i, "pos": table.position_label(i), "stack": sq.stack,
              "committed_total": sq.committed_total, "folded": sq.folded, "all_in": sq.all_in}
             for i, sq in enumerate(table.seats)]
    return Spot(
        street=table.street, board=list(table.board), bb=table.bb, hero_seat=seat,
        hero_pos=table.position_label(seat), hero_hole=list(s.hole), pot=table.pot(),
        to_call=la.get("to_call", 0), n_active=len(table._active()), seats=seats,
        legal={k: la.get(k) for k in ("can_fold", "can_check", "can_call", "can_raise", "raise_min", "raise_max")},
        line=_line_from_history(table, seat),
    )


def _street_line(spot: "Spot", street: str) -> str:
    acts = [a for a in spot.line if a["street"] == street]
    if not acts:
        return ""
    parts = []
    for a in acts:
        if a["action"] in ("bet", "raise"):
            parts.append(f"{a['pos']} {a['action']} to {a['amount_bb']}")
        elif a["action"] == "call":
            parts.append(f"{a['pos']} call")
        else:
            parts.append(f"{a['pos']} {a['action']}")
    return ", ".join(parts)


def format_spot(spot: "Spot") -> str:
    """Render the canonical prompt text (the user message). Deterministic; big-blind units."""
    stacks = ", ".join(f"{s['pos']} {spot.b(s['stack'])}" + ("(hero)" if s["seat"] == spot.hero_seat else "")
                       for s in spot.seats if not s["folded"] or s["seat"] == spot.hero_seat)
    lines = [
        f"6-max NLHE, {spot.n_active} active. Big blind = 1bb.",
        f"Hero: {spot.hero_pos}, holding {' '.join(spot.hero_hole)}.",
        f"Stacks (bb): {stacks}.",
    ]
    for st in ("preflop", "flop", "turn", "river"):
        seg = _street_line(spot, st)
        if st == "preflop" or seg or (st == spot.street):
            board = ""
            if st in ("flop", "turn", "river"):
                n = {"flop": 3, "turn": 4, "river": 5}[st]
                board = f" [{' '.join(spot.board[:n])}]" if len(spot.board) >= (3 if st == "flop" else n) else ""
            if seg or st == spot.street:
                lines.append(f"{st.capitalize()}{board}: {seg or '(checks through / to act)'}")
    legal = []
    if spot.legal.get("can_fold"):
        legal.append("fold")
    if spot.legal.get("can_check"):
        legal.append("check")
    if spot.legal.get("can_call"):
        legal.append(f"call {spot.b(spot.to_call)}")
    if spot.legal.get("can_raise"):
        legal.append(f"bet/raise {spot.b(spot.legal.get('raise_min'))}..{spot.b(spot.legal.get('raise_max'))}")
    lines.append(f"Pot {spot.b(spot.pot)}bb, to-call {spot.b(spot.to_call)}bb. Legal: {', '.join(legal)}.")
    if spot.villain_fold != 0.5 or spot.villain_aggro != 0.5:    # render the READ only when informative (non-neutral)
        lines.append(f"Villain read: fold-to-bet {spot.villain_fold:.2f}, aggression {spot.villain_aggro:.2f}.")
    lines.append(f"Hero to act on the {spot.street}.")
    return "\n".join(lines)
