"""GTO-floor advisor (#39): loads the trained MLP (data/advisor.pt, from extraction/train_advisor.py) and
predicts the solver's P(bet) for a hand at the FLOP donk/c-bet node, from blocker/potential features. bot.py
uses it for the flop bet decision (frequency AND hand-selection). Pure glue over EXISTING data; falls back to
None (-> heuristic floor) if torch or the model is absent. Trained on flops only -> valid on the flop only.
"""
from __future__ import annotations

from pokerbot import config
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.features import RANKS, hand_features

TIERS = ["air", "medium", "strong"]
TEX = ["high", "low", "connected", "monotone", "paired"]
BOOLS = ["flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight", "oesd", "gutshot", "has_draw"]
_NET = None
_TORCH = None


def _texture(board) -> str:
    from pokerbot.strategy.postflop import classify_board
    t = classify_board(board)
    if t.get("paired"):
        return "paired"
    if t.get("monotone"):
        return "monotone"
    if t.get("connected"):
        return "connected"
    return "high" if board and max(RANKS.index(c[0]) for c in board) >= RANKS.index("T") else "low"


def _vector(f, role, tex, strength) -> list:
    v = [1.0 if f["tier"] == t else 0.0 for t in TIERS]
    v += [1.0 if tex == t else 0.0 for t in TEX]
    v.append(1.0 if role == "IP" else 0.0)
    v += [1.0 if f[k] else 0.0 for k in BOOLS]
    v.append(f["overcards"] / 2.0)
    v.append(float(strength))
    return v


def _load():
    global _NET, _TORCH
    if _NET is None:
        try:
            import torch
            import torch.nn as nn
            _TORCH = torch
            ck = torch.load(config.KNOWLEDGE_DIR / "postflop" / "advisor.pt", map_location="cpu")
            d = ck["dims"]
            net = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(),
                                nn.Linear(64, 1), nn.Sigmoid())
            net.load_state_dict(ck["state"])
            net.eval()
            _NET = net
        except Exception:  # noqa: BLE001
            _NET = False
    return _NET


def available() -> bool:
    return bool(_load())


def p_bet(hole, board, role) -> float | None:
    """Advisor P(bet) for this hand at the flop donk (role='OOP') / c-bet (role='IP') node; None -> fall back."""
    net = _load()
    if not net:
        return None
    f = hand_features(hole, board)
    x = _TORCH.tensor([_vector(f, role, _texture(board), 1.0 - evaluate(board, hole) / 7462.0)],
                      dtype=_TORCH.float32)
    with _TORCH.no_grad():
        return float(net(x)[0, 0].item())
