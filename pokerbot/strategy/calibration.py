"""Prediction -> measurement -> calibration loop (ported from the Mycelium trading bot's learning-engine).

Every probability PREDICTION we ACT on (e.g. "opponent folds to this bet") is logged with the later
OBSERVED outcome. From that we (a) correct systematic bias in future predictions and (b) expose a
data-driven confidence = how well-calibrated we actually are. Effect: exploits become self-correcting —
if we systematically over-estimate fold equity, bluffs throttle themselves automatically.

Why this is not redundant with the raw fold-curve model: it is SELECTION-AWARE. It calibrates predictions
in the spots we ACTUALLY choose to act in (a bias the raw frequency model, averaged over all spots, never
sees — e.g. our bluffs get called more than the population fold rate suggests). Recency-weighted so it
tracks opponents who change. Persists per opponent so reads survive across sessions.
"""
from __future__ import annotations

import json
from pathlib import Path

from pokerbot import config


class Calibrator:
    """Per-key reliability tracker. A key is a prediction TYPE (e.g. "fe_med" = fold-equity, medium bet)."""

    def __init__(self, name: str = "default", path: str | None = None,
                 half_life: float | None = 300.0) -> None:
        self.name = name
        self.path = Path(path) if path else (config.DATA_DIR / "calibration" / f"{name}.json")
        # recency: each new observation decays old mass by `decay` (half_life=None -> pure counting)
        self.decay = 1.0 if half_life is None else 0.5 ** (1.0 / float(half_life))
        self.k: dict[str, dict] = {}
        self._load()

    # --- core loop -------------------------------------------------------
    def record(self, key: str, predicted: float, outcome: bool) -> None:
        """Log one (predicted probability, observed boolean outcome) pair."""
        p = min(1.0, max(0.0, float(predicted)))
        o = 1.0 if outcome else 0.0
        s = self.k.setdefault(key, {"n": 0.0, "sp": 0.0, "so": 0.0, "sse": 0.0})
        d = self.decay
        s["n"] = s["n"] * d + 1.0
        s["sp"] = s["sp"] * d + p          # sum predicted
        s["so"] = s["so"] * d + o          # sum observed
        s["sse"] = s["sse"] * d + (p - o) ** 2   # sum squared error (Brier)

    def bias(self, key: str) -> float:
        """mean(observed - predicted): >0 we UNDER-predicted, <0 we OVER-predicted. 0 with no data."""
        s = self.k.get(key)
        return (s["so"] - s["sp"]) / s["n"] if s and s["n"] > 1e-9 else 0.0

    def adjust(self, key: str, raw: float) -> float:
        """Bias-correct a raw prediction; correction is shrunk by sample size (no data -> raw unchanged)."""
        s = self.k.get(key)
        if not s or s["n"] < 1e-9:
            return raw
        w = s["n"] / (s["n"] + 8.0)                       # trust the correction more with more data
        return min(1.0, max(0.0, raw + w * self.bias(key)))

    def brier(self, key: str) -> float | None:
        """Mean Brier score (0 = perfect, 0.25 = a coin-flip). None with no data."""
        s = self.k.get(key)
        return (s["sse"] / s["n"]) if s and s["n"] > 1e-9 else None

    def confidence(self, key: str) -> float:
        """0..1 trust in this key's (bias-corrected) predictions = data volume x calibration quality."""
        s = self.k.get(key)
        if not s or s["n"] < 1e-9:
            return 0.0
        vol = s["n"] / (s["n"] + 10.0)
        cal = 1.0 - min(1.0, abs(self.bias(key)) / 0.50)
        return round(vol * cal, 4)

    # --- io / introspection ---------------------------------------------
    def summary(self) -> dict:
        out = {}
        for k, v in self.k.items():
            if v["n"] > 1e-9:
                out[k] = {"n": round(v["n"], 1), "pred": round(v["sp"] / v["n"], 3),
                          "obs": round(v["so"] / v["n"], 3), "bias": round(self.bias(k), 3),
                          "brier": round(self.brier(k), 3), "conf": self.confidence(k)}
        return out

    def _load(self) -> None:
        try:
            self.k = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  (missing/corrupt -> start fresh)
            self.k = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.k), encoding="utf-8")
        tmp.replace(self.path)
