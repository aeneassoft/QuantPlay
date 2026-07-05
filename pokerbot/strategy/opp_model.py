"""Exploit-primary opponent model (#49): a Dirichlet per-node posterior over villain's fold/call/raise response
to our bet, keyed by a coarse node bucket (street, role, line, board-class, bet-size-bucket). Prior = floor
frequencies x KAPPA (mild shrinkage); posterior = Dirichlet(prior + observed counts). Query returns the
posterior-mean response + n_eff (observed sample count = the LCB uncertainty driver). Static-opponent-friendly:
counts persist and can be saved/loaded. Pure stdlib (no numpy). Run: python -m pokerbot.strategy.opp_model
"""
from __future__ import annotations

import json
from collections import defaultdict

from pokerbot import config

KAPPA = 3.0                       # prior strength (mild shrinkage to the floor frequencies)
RESP = ("fold", "call", "raise")
DEFAULT_PRIOR = (0.5, 0.4, 0.1)   # generic fold/call/raise prior when no per-node floor is supplied
_SIZE_BINS = [(0.40, "q"), (0.58, "half"), (0.80, "twothird"), (1.10, "pot"), (1.60, "big")]  # > 1.60 -> "over"


def size_bucket(frac: float) -> str:
    """Bucket a bet size (fraction of pot) into coarse bins -- includes off-tree sizes between solver-tree nodes."""
    for hi, name in _SIZE_BINS:
        if frac <= hi:
            return name
    return "over"


def node_key(street: str, role: str, line: str, board_class: str, size_frac: float) -> str:
    return f"{street}|{role}|{line}|{board_class}|{size_bucket(size_frac)}"


class OppModel:
    """Dirichlet fold/call/raise posterior per node bucket. The exploit engine queries posterior() for the
    response distribution + n_eff; observe() accrues evidence from played hands (info persists vs a static bot)."""

    def __init__(self, kappa: float = KAPPA):
        self.kappa = kappa
        self.counts: dict = defaultdict(lambda: [0.0, 0.0, 0.0])

    def observe(self, key: str, resp: str, w: float = 1.0) -> None:
        if resp in RESP:
            self.counts[key][RESP.index(resp)] += w

    def posterior(self, key: str, prior=DEFAULT_PRIOR):
        """Return (mean=[P(fold),P(call),P(raise)], n_eff). Dirichlet(prior*kappa + observed counts)."""
        c = self.counts.get(key, [0.0, 0.0, 0.0])
        alpha = [prior[i] * self.kappa + c[i] for i in range(3)]
        s = sum(alpha) or 1.0
        return [a / s for a in alpha], sum(c)

    def save(self, path=None) -> None:
        out_path = path or (config.DATA_DIR / "opp_model.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(dict(self.counts)), encoding="utf-8")

    def load(self, path=None) -> None:
        in_path = path or (config.DATA_DIR / "opp_model.json")
        try:
            d = json.loads(in_path.read_text(encoding="utf-8"))
            self.counts = defaultdict(lambda: [0.0, 0.0, 0.0], {k: list(v) for k, v in d.items()})
        except Exception:  # noqa: BLE001
            pass


def seed_from_fold_curve(model: OppModel, curve_path=None, street: str = "river", n_eff: float = 30.0) -> int:
    """Seed the Dirichlet model's per-size river buckets from a MEASURED fold-curve [size, fold_prob, n]
    (e.g. knowledge_base/exploit/slumbot_fold.json), applied across board-classes + roles (an aggregate prior;
    live play would refine per-bucket). n_eff sets the seed confidence = the LCB driver. Returns #buckets seeded."""
    curve_file = curve_path or (config.KNOWLEDGE_DIR / "exploit" / "slumbot_fold.json")
    try:
        data = json.loads(open(curve_file, encoding="utf-8").read())
    except Exception:  # noqa: BLE001
        return 0
    seeded = 0
    for size, fold_p, _n in data.get(street, []):
        for bc in ("dry", "wet", "paired", "mono"):
            for role in ("IP", "OOP"):
                c = model.counts[node_key(street, role, "all", bc, float(size))]
                c[0] += fold_p * n_eff
                c[1] += (1 - fold_p) * 0.85 * n_eff
                c[2] += (1 - fold_p) * 0.15 * n_eff
                seeded += 1
    return seeded


if __name__ == "__main__":
    m = OppModel()
    k = node_key("river", "IP", "xb-c", "4flush", 1.0)
    print("cold-start (=prior):", [round(x, 3) for x in m.posterior(k)[0]], "n_eff", m.posterior(k)[1])
    for _ in range(40):
        m.observe(k, "fold")
    for _ in range(5):
        m.observe(k, "call")
    mean, n = m.posterior(k)
    print("after 45 obs (over-folder):", [round(x, 3) for x in mean], "n_eff", n)
    assert mean[0] > 0.7 and n == 45, "over-folder should dominate fold"
    print("OK")
