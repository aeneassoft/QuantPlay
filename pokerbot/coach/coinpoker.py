"""CoinPoker hand-history -> engine Spots, for the personal coaching path (docs/plans/ROADMAP.md §B).

The one genuinely-new piece the roadmap flagged: a CoinPoker HH parser + a replay that snapshots each HERO decision as
a canonical `Spot` (pokerbot/brain/format_spot.py). Once a decision is a Spot, the whole engine stack works on it —
`format_spot` renders it, `understanding.strategic_read` grounds it (SPR/MDF/texture/made-hand/principles), and `api.*`
computes exact equity/odds — so Claude can coach the user's OWN play engine-grounded + GTO-anchored.

CoinPoker format: chips are ₮ (USDT ≈ $1); the hero is literally "Hero"; "raises X to Y" (Y=total), "bets X", "calls X",
"NAME: ALLIN X" (X = the increment added), "checks", "folds"; "NAME collected ₮X from pot" has NO colon. Stakes NL =
100·BB ($): ₮1/₮2 = NL200, ₮2/₮5 = NL500.

Public API: `parse_file(path) -> list[Hand]`; `hero_decisions(hand) -> list[Decision]` (a Spot + the action Hero took).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from pokerbot.brain.format_spot import Spot

_NUM = r"([\d,]+(?:\.\d+)?)"


def _amt(s: str) -> float:
    m = re.search(r"₮" + _NUM, s)
    return float(m.group(1).replace(",", "")) if m else 0.0


@dataclass
class Hand:
    hid: str
    sb: float
    bb: float
    button_seat: int
    seats: dict                       # seat -> {"name", "stack"}
    pos: dict = field(default_factory=dict)     # seat -> position label
    hero_seat: int | None = None
    hero_hole: list = field(default_factory=list)
    actions: list = field(default_factory=list)  # ordered [{street,seat,act,to,inc}]
    boards: dict = field(default_factory=dict)   # street -> [cards]
    collected: dict = field(default_factory=dict)  # name -> chips collected (post-rake)
    went_sd: bool = False
    date: str = ""


@dataclass
class Decision:
    spot: Spot
    action: str                       # fold|check|call|bet|raise|all-in
    amount_bb: float | None           # the total bet/raise hero made, in bb (None for fold/check)
    street: str
    hid: str


def parse_file(path: str) -> list:
    text = open(path, encoding="utf-8", errors="replace").read()
    blocks, cur = [], []
    for ln in text.splitlines():
        if ln.startswith("CoinPoker Hand #"):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    return [h for h in (_parse_hand(b) for b in blocks) if h is not None]


# ---------------------------------------------------------------- position labels (button-relative)
def _assign_positions(button_seat: int, occupied: list, sb_seat, bb_seat) -> dict:
    """Map each occupied seat to a 6-max label. Anchor SB/BB from the posts; CO = the seat just before the button."""
    order = sorted(occupied)
    rot = order[order.index(button_seat) + 1:] + order[:order.index(button_seat)]   # seats after the button, in order
    pos = {button_seat: "BTN"}
    if sb_seat is not None:
        pos[sb_seat] = "SB"
    if bb_seat is not None:
        pos[bb_seat] = "BB"
    middle = [s for s in rot if s not in (sb_seat, bb_seat)]    # the non-blind seats between BB and the button
    labels = {1: ["CO"], 2: ["UTG", "CO"], 3: ["UTG", "HJ", "CO"]}.get(len(middle), ["UTG"] * len(middle))
    for s, lab in zip(middle, labels):
        pos[s] = lab
    return pos


def _parse_hand(lines: list):
    head = lines[0]
    m = re.search(r"Hand #(\d+): NLH \(([^)]*)\)\s+(\d{4}/\d{2}/\d{2})", head)
    if not m:
        return None
    nums = re.findall(r"₮" + _NUM, m.group(2))
    sb, bb = (float(nums[0].replace(",", "")), float(nums[1].replace(",", ""))) if len(nums) >= 2 else (0, 0)
    bseat = int(re.search(r"Seat #(\d+) is the button", lines[1]).group(1)) if "is the button" in lines[1] else 0
    h = Hand(hid=m.group(1), sb=sb, bb=bb, button_seat=bseat, seats={}, date=m.group(3))
    sb_seat = bb_seat = None
    street = "preflop"
    for ln in lines:
        ms = re.match(r"Seat (\d+): (\S+) \(₮" + _NUM + r" in chips\)", ln)
        if ms:
            seat = int(ms.group(1))
            h.seats[seat] = {"name": ms.group(2), "stack": float(ms.group(3).replace(",", ""))}
            if ms.group(2) == "Hero":
                h.hero_seat = seat
            continue
        if ln.startswith("Dealt to Hero ["):
            h.hero_hole = ln.split("[")[1].rstrip("]").split()
            continue
        for tag, st in (("*** FLOP", "flop"), ("*** TURN", "turn"), ("*** RIVER", "river")):
            if ln.startswith(tag):
                street = st
                h.boards[st] = re.findall(r"[2-9TJQKA][shdc]", ln)
        if "*** SHOW" in ln:
            h.went_sd = True
        mc = re.match(r"(\S+) collected ₮([\d,]+(?:\.\d+)?)", ln)   # "NAME collected ₮X from pot" (no colon)
        if mc:
            h.collected[mc.group(1)] = h.collected.get(mc.group(1), 0.0) + float(mc.group(2).replace(",", ""))
            continue
        if ":" not in ln:
            continue
        who, body = ln.split(":", 1)[0], ln.split(":", 1)[1].strip()
        seat = next((s for s, d in h.seats.items() if d["name"] == who), None)
        if seat is None:
            continue
        if "posts small blind" in body:
            sb_seat = seat; h.actions.append({"street": "preflop", "seat": seat, "act": "post", "to": _amt(body), "inc": _amt(body)})
        elif "posts big blind" in body:
            bb_seat = seat; h.actions.append({"street": "preflop", "seat": seat, "act": "post", "to": _amt(body), "inc": _amt(body)})
        elif "posts ante" in body:
            h.actions.append({"street": "preflop", "seat": seat, "act": "ante", "to": 0.0, "inc": _amt(body)})
        elif body.startswith("folds"):
            h.actions.append({"street": street, "seat": seat, "act": "fold", "to": None, "inc": 0.0})
        elif body.startswith("checks"):
            h.actions.append({"street": street, "seat": seat, "act": "check", "to": None, "inc": 0.0})
        elif body.startswith("calls"):
            h.actions.append({"street": street, "seat": seat, "act": "call", "to": None, "inc": _amt(body)})
        elif body.startswith("bets"):
            h.actions.append({"street": street, "seat": seat, "act": "bet", "to": _amt(body), "inc": _amt(body)})
        elif body.startswith("raises"):
            to = float(re.search(r"to ₮" + _NUM, body).group(1).replace(",", ""))
            h.actions.append({"street": street, "seat": seat, "act": "raise", "to": to, "inc": _amt(body)})
        elif body.startswith("ALLIN"):
            h.actions.append({"street": street, "seat": seat, "act": "allin", "to": None, "inc": _amt(body)})
        elif body.startswith("RETURN"):                        # uncalled bet returned -> un-invest it
            h.actions.append({"street": street, "seat": seat, "act": "return", "to": None, "inc": _amt(body)})
    h.pos = _assign_positions(bseat, list(h.seats), sb_seat, bb_seat)
    return h


# ---------------------------------------------------------------- replay -> a Spot per HERO decision
_ACT_LABEL = {"allin": "all-in", "bet": "bet", "raise": "raise", "call": "call", "check": "check", "fold": "fold"}


def hero_decisions(hand) -> list:
    """Replay the betting; snapshot a canonical Spot the instant before each HERO decision (not posts/antes)."""
    if hand.hero_seat is None:
        return []
    contrib = {s: 0.0 for s in hand.seats}        # current-street contribution
    committed = {s: 0.0 for s in hand.seats}      # total across all streets (= the pot share)
    stack = {s: hand.seats[s]["stack"] for s in hand.seats}
    folded = {s: False for s in hand.seats}
    allin = {s: False for s in hand.seats}
    street, line, out = "preflop", [], []
    for a in hand.actions:
        if a["street"] != street:                 # new street -> reset per-street contributions
            street, contrib = a["street"], {s: 0.0 for s in hand.seats}
        seat, act = a["seat"], a["act"]
        if seat == hand.hero_seat and act in _ACT_LABEL:
            out.append(_snapshot(hand, street, list(line), dict(contrib), dict(committed), dict(stack), dict(folded),
                                 dict(allin), a))
        if act == "return":                                    # uncalled bet returned -> reverse it (no public line entry)
            committed[seat] -= a["inc"]; stack[seat] += a["inc"]
            continue
        if act in ("ante", "post"):
            committed[seat] += a["inc"]; stack[seat] -= a["inc"]
            if act == "post":
                contrib[seat] = a["to"]
            continue
        if act == "fold":
            folded[seat] = True
        elif act == "call":
            committed[seat] += a["inc"]; contrib[seat] += a["inc"]; stack[seat] -= a["inc"]
        elif act in ("bet", "raise"):
            inc = a["to"] - contrib[seat]
            committed[seat] += inc; contrib[seat] = a["to"]; stack[seat] -= inc
        elif act == "allin":
            committed[seat] += a["inc"]; contrib[seat] += a["inc"]; stack[seat] -= a["inc"]; allin[seat] = True
        if act != "check":
            amt_bb = (contrib[seat] / hand.bb) if act in ("bet", "raise", "allin") else None
            line.append({"street": street, "pos": hand.pos.get(seat, "?"), "action": _ACT_LABEL[act],
                         "amount_bb": round(amt_bb, 2) if amt_bb else None, "hero": seat == hand.hero_seat})
        else:
            line.append({"street": street, "pos": hand.pos.get(seat, "?"), "action": "check",
                         "amount_bb": None, "hero": seat == hand.hero_seat})
    return out


def _snapshot(hand, street, line, contrib, committed, stack, folded, allin, a) -> "Decision":
    hero = hand.hero_seat
    active = [s for s in hand.seats if not folded[s]]
    to_call = max(0.0, max((contrib[s] for s in active), default=0.0) - contrib[hero])
    pot = sum(committed.values())
    board = hand.boards.get(street, []) if street != "preflop" else []
    seats = [{"seat": s, "pos": hand.pos.get(s, "?"), "stack": stack[s], "committed_total": committed[s],
              "folded": folded[s], "all_in": allin[s]} for s in sorted(hand.seats)]
    legal = {"can_fold": to_call > 0, "can_check": to_call <= 0, "can_call": to_call > 0,
             "can_raise": stack[hero] > to_call, "raise_min": min(stack[hero], to_call + hand.bb),
             "raise_max": stack[hero]}
    spot = Spot(street=street, board=list(board), bb=hand.bb, hero_seat=hero, hero_pos=hand.pos.get(hero, "?"),
                hero_hole=list(hand.hero_hole), pot=pot, to_call=to_call, n_active=len(active),
                seats=seats, legal=legal, line=line)
    amt_bb = None
    if a["act"] in ("bet", "raise"):
        amt_bb = round(a["to"] / hand.bb, 2)
    elif a["act"] == "allin":
        amt_bb = round((contrib[hero] + a["inc"]) / hand.bb, 2)
    return Decision(spot=spot, action=_ACT_LABEL[a["act"]], amount_bb=amt_bb, street=street, hid=hand.hid)


def summary(hand) -> dict:
    """Hand-level Hero stats for the report layer: net (post-rake chips) + VPIP/PFR/WTSD/won-SD/all-in flags."""
    invested, contrib, folded = defaultdict(float), defaultdict(float), set()
    street, vpip, pfr, allin = "preflop", False, False, False
    hero = hand.hero_seat
    for a in hand.actions:
        if a["street"] != street:
            street, contrib = a["street"], defaultdict(float)
        s, act = a["seat"], a["act"]
        if act in ("ante", "post"):
            invested[s] += a["inc"]
            if act == "post":
                contrib[s] = a["to"]
        elif act == "fold":
            if s == hero:
                folded.add(hero)
        elif act == "call":
            invested[s] += a["inc"]; contrib[s] += a["inc"]
            if s == hero and street == "preflop":
                vpip = True
        elif act in ("bet", "raise"):
            invested[s] += max(0.0, a["to"] - contrib[s]); contrib[s] = a["to"]
            if s == hero and street == "preflop":
                vpip = pfr = True
        elif act == "allin":
            invested[s] += a["inc"]; contrib[s] += a["inc"]; allin = True
            if s == hero and street == "preflop":
                vpip = pfr = True
        elif act == "return":
            invested[s] -= a["inc"]
    name = hand.seats.get(hero, {}).get("name", "")
    hero_in = hero not in folded
    return {"net": hand.collected.get(name, 0.0) - invested[hero], "vpip": vpip, "pfr": pfr,
            "wtsd": hand.went_sd and hero_in, "won_sd": hand.went_sd and hero_in and hand.collected.get(name, 0) > 0,
            "allin": allin, "n_players": len(hand.seats), "date": hand.date, "bb": hand.bb, "hid": hand.hid}
