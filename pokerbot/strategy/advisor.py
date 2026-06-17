"""GTO-floor advisor (#39 flop, #41 turn): loads the trained MLPs (advisor.pt = flop donk/c-bet,
turn_advisor.pt = turn lead/barrel; from extraction/train_advisor.py + train_turn_advisor.py) and predicts the
solver's P(bet) for a hand at that node, from blocker/potential features. bot.py uses it for the per-hand bet
decision (frequency AND hand-selection). Pure glue over EXISTING solver data; falls back to None (-> heuristic
floor) if torch or the model is absent. Each net is street-specific (flop net valid on the flop, turn on the turn).
"""
from __future__ import annotations

from pokerbot import config
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.features import RANKS, hand_features

TIERS = ["air", "medium", "strong"]
TEX = ["high", "low", "connected", "monotone", "paired"]
BOOLS = ["flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight", "oesd", "gutshot", "has_draw"]
_STREETS = ["flop", "turn", "river"]   # defense-advisor street one-hot (matches train_defense_advisor.feat)
_FILES = {"flop": "advisor.pt", "turn": "turn_advisor.pt", "river": "river_advisor.pt"}
_NETS: dict = {}
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


def _load(street: str = "flop"):
    """Load (and cache) the street's advisor MLP; False if torch / the model file is unavailable."""
    global _TORCH
    if street not in _NETS:
        try:
            import torch
            import torch.nn as nn
            _TORCH = torch
            ck = torch.load(config.KNOWLEDGE_DIR / "postflop" / _FILES[street], map_location="cpu")
            d = ck["dims"]
            net = nn.Sequential(nn.Linear(d, 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(),
                                nn.Linear(64, 1), nn.Sigmoid())
            net.load_state_dict(ck["state"])
            net.eval()
            _NETS[street] = net
        except Exception:  # noqa: BLE001
            _NETS[street] = False
    return _NETS[street]


def available(street: str = "flop") -> bool:
    return bool(_load(street))


def p_bet(hole, board, role, street: str = "flop") -> float | None:
    """Advisor P(bet) for this hand at the flop (role OOP=donk / IP=c-bet) or turn (OOP=lead / IP=barrel)
    node; None -> caller falls back to the heuristic floor."""
    net = _load(street)
    if not net:
        return None
    f = hand_features(hole, board)
    x = _TORCH.tensor([_vector(f, role, _texture(board), 1.0 - evaluate(board, hole) / 7462.0)],
                      dtype=_TORCH.float32)
    with _TORCH.no_grad():
        return float(net(x)[0, 0].item())


# ---- MVP C2: facing-bet DEFENSE advisor (3-output fold/call/raise; trained by extraction/train_defense_advisor) ----
_DEF: dict = {}


def _load_defense():
    """Load (and cache) the facing-bet defense advisor MLP (3-output fold/call/raise); False if torch/file absent."""
    global _TORCH
    if "net" not in _DEF:
        try:
            import torch
            import torch.nn as nn
            _TORCH = torch
            ck = torch.load(config.KNOWLEDGE_DIR / "postflop" / "defense_advisor.pt", map_location="cpu")
            net = nn.Sequential(nn.Linear(ck["dims"], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(),
                                nn.Linear(64, 3))
            net.load_state_dict(ck["state"])
            net.eval()
            _DEF["net"] = net
        except Exception:  # noqa: BLE001
            _DEF["net"] = False
    return _DEF["net"]


def defense_available() -> bool:
    return bool(_load_defense())


def p_defense(hole, board, role, size_faced: float, street: str = "flop"):
    """Solver (P_fold, P_call, P_raise) for this hand facing a bet of size_faced (× the pot it was bet into) on
    `street`, or None -> caller uses the heuristic. Trained on the flop+turn+river caches (turn added 2026-06-16)
    -> the caller gates to those streets. Feature vector EXACTLY matches extraction/train_defense_advisor.feat: tier, texture(flop), STREET,
    role, bools, overcards, strength, size_faced. Texture is keyed on the flop (board[:3]) as in build_defense_data."""
    net = _load_defense()
    if not net:
        return None
    f = hand_features(hole, board)
    tex = _texture(board[:3])
    strength = 1.0 - evaluate(board, hole) / 7462.0
    v = [1.0 if f["tier"] == t else 0.0 for t in TIERS]
    v += [1.0 if tex == t else 0.0 for t in TEX]
    v += [1.0 if street == s else 0.0 for s in _STREETS]
    v.append(1.0 if role == "IP" else 0.0)
    v += [1.0 if f[k] else 0.0 for k in BOOLS]
    v.append(f["overcards"] / 2.0)
    v.append(float(strength))
    v.append(float(size_faced))
    x = _TORCH.tensor([v], dtype=_TORCH.float32)
    with _TORCH.no_grad():
        p = _TORCH.softmax(net(x), dim=1)[0]
    return float(p[0]), float(p[1]), float(p[2])
