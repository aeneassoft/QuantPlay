"""Tests for the exploit playbook (cold-start prior) + directive->nudge mapping + adaptive hook.
Run: python -m tests.test_playbook
"""
from __future__ import annotations

from pokerbot.strategy.adaptive import AdaptiveExploiter
from pokerbot.strategy.playbook import directive_to_nudge, shared


def test_directive_to_nudge():
    assert directive_to_nudge({"adjust": {"action": "bluff_more", "freq_delta": 0.2}, "confidence": 0.8})["bluff"] > 0
    assert directive_to_nudge({"adjust": {"action": "fold_more", "freq_delta": 0.2}, "confidence": 0.8})["foldcatch"] < 0
    assert directive_to_nudge({"adjust": {"action": "call_wider", "freq_delta": 0.2}, "confidence": 0.8})["foldcatch"] > 0
    assert directive_to_nudge(None) == {}
    assert directive_to_nudge({"adjust": {"action": "??"}}) == {}
    hi = directive_to_nudge({"adjust": {"action": "bluff_more", "freq_delta": 0.3}, "confidence": 1.0})["bluff"]
    lo = directive_to_nudge({"adjust": {"action": "bluff_more", "freq_delta": 0.3}, "confidence": 0.2})["bluff"]
    assert hi > lo                                                       # confidence scales magnitude
    print("directive_to_nudge OK")


def test_playbook_lookup():
    pb = shared()
    if not pb.available:
        print("playbook files missing - skip lookup test")
        return
    d = pb.lookup({"vpip": 16, "fold_to_cbet": 0.70, "af": 0.8}, "flop", "check")   # over-folding nit
    assert d is not None, "expected a nearest-profile directive"
    d2 = pb.lookup({"vpip": 16, "fold_to_cbet": 0.70, "af": 0.8}, "flop", "check")
    assert d2 == d                                                       # cached -> identical
    assert pb.lookup({"vpip": 30, "fold_to_cbet": 0.5, "af": 1.5}, "flop", "nonexist") is None
    print("lookup OK:", d.get("adjust"), "conf", d.get("confidence"))


def test_adaptive_uses_playbook():
    ex = AdaptiveExploiter(hero=0, use_playbook=True, calibrate=False)
    assert ex.playbook is None or ex.playbook.available
    print("adaptive playbook wired:", "on" if ex.playbook else "off (no files)")
    off = AdaptiveExploiter(hero=0, use_playbook=False, calibrate=False)
    assert off.playbook is None
    print("use_playbook=False -> off OK")


if __name__ == "__main__":
    test_directive_to_nudge()
    test_playbook_lookup()
    test_adaptive_uses_playbook()
    print("\nall playbook tests passed")
