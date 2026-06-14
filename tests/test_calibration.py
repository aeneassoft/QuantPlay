"""Tests for the prediction -> measurement -> calibration loop + its AdaptiveExploiter hook.
Run: python -m tests.test_calibration
"""
from __future__ import annotations

import random
import tempfile
from pathlib import Path

from pokerbot.strategy.adaptive import AdaptiveExploiter
from pokerbot.strategy.calibration import Calibrator

_TMP = Path(tempfile.gettempdir())


def test_bias_correction():
    c = Calibrator(path=str(_TMP / "_cal_bias.json"), half_life=None)
    rng = random.Random(0)
    # predictor always claims 0.70 fold, but the opponent actually folds only ~40%
    for _ in range(300):
        c.record("fe_bluff", 0.70, rng.random() < 0.40)
    b = c.bias("fe_bluff")
    assert -0.38 < b < -0.22, f"bias {b}"                       # ~ -0.30
    adj = c.adjust("fe_bluff", 0.70)
    assert 0.34 < adj < 0.50, f"adjusted {adj}"                 # corrected down toward ~0.40
    assert c.confidence("fe_bluff") > 0.0
    print("bias-correction OK: bias", round(b, 3), "adj", round(adj, 3),
          "conf", c.confidence("fe_bluff"), "brier", round(c.brier("fe_bluff"), 3))


def test_no_data_is_noop():
    c = Calibrator(path=str(_TMP / "_cal_empty.json"), half_life=None)
    assert c.adjust("anything", 0.66) == 0.66                   # no data -> unchanged
    assert c.confidence("anything") == 0.0
    assert c.bias("anything") == 0.0
    print("no-data no-op OK")


def test_recency_tracks_change():
    c = Calibrator(path=str(_TMP / "_cal_recency.json"), half_life=30.0)
    for _ in range(150):           # opponent USED to never fold
        c.record("k", 0.5, False)
    for _ in range(150):           # ... then switched to always folding
        c.record("k", 0.5, True)
    assert c.bias("k") > 0.2, f"recency should track the switch, bias={c.bias('k')}"
    print("recency OK: bias", round(c.bias("k"), 3))


def test_persistence():
    p = _TMP / "_cal_persist.json"
    if p.exists():
        p.unlink()
    c = Calibrator(path=str(p), half_life=None)
    for _ in range(20):
        c.record("k", 0.8, False)
    c.save()
    c2 = Calibrator(path=str(p), half_life=None)
    assert abs(c2.bias("k") - c.bias("k")) < 1e-9
    print("persistence OK")


def test_adaptive_hook():
    ex = AdaptiveExploiter(hero=0, calibrate=True, calib_name="_unit_test")
    # we bet (pending set); opponent faces the bet and folds -> recorded as a hit
    ex._pending = ("fe_bluff", 0.65)
    ex.observe_opponent({"street": "flop", "legal": {"to_call": 10, "pot": 20}}, "fold")
    assert ex._pending is None
    s = ex.calib.summary()
    assert "fe_bluff" in s and s["fe_bluff"]["obs"] == 1.0, s
    # an opponent action NOT facing our bet must not resolve a pending prediction
    ex._pending = ("fe_bluff", 0.65)
    ex.observe_opponent({"street": "flop", "legal": {"to_call": 0, "pot": 20}}, "bet")
    assert ex._pending is not None
    ex.observe_hand_end()
    assert ex._pending is None
    print("adaptive hook OK:", s)


if __name__ == "__main__":
    test_bias_correction()
    test_no_data_is_noop()
    test_recency_tracks_change()
    test_persistence()
    test_adaptive_hook()
    print("\nall calibration tests passed")
