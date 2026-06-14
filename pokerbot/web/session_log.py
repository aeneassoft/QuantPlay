"""Log each played hand (positions, actions, sizes, board, result, per-seat net) to a JSONL
session file, tagging the human's actions — for end-of-session analysis."""
from __future__ import annotations

import json


def build_hand_record(table) -> dict:
    seats = table.seats
    won = {w["seat"]: w["amount"] for w in (table.result or {}).get("winners", [])}
    human_seat = next((i for i, s in enumerate(seats) if s.is_human), None)
    actions = []
    for h in table.history:
        if "player" not in h:
            continue
        seat = h["player"]
        actions.append({
            "street": h.get("street"), "seat": seat,
            "pos": table.position_label(seat), "action": h["action"],
            "amount": h.get("to") or h.get("amount"),
            "is_human": seats[seat].is_human,
        })
    return {
        "hand_no": table.hand_no, "button": table.button, "sb": table.sb, "bb": table.bb,
        "human_seat": human_seat,
        "positions": {i: table.position_label(i) for i in range(table.n)},
        "hole": {i: seats[i].hole for i in range(table.n)},
        "board": list(table.board),
        "actions": actions,
        "result": table.result,
        "net": {i: won.get(i, 0) - seats[i].committed_total for i in range(table.n)},
    }


def append_record(path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
