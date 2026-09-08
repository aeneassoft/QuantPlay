"""Integrator-Tests v10 (docs/V10_BUILD_CARD.md E4 + Arm B): hand_id-Injektion im Spiegel, r10_stack-Registry,
RC_STACK/wickle_decide. Laeuft als `python -m tests.test_integration_v10` (pytest ist lokal nicht installiert)."""
from __future__ import annotations

import os


def _ohne_pokerb_env() -> None:
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)


def _aufzeichner(protokoll: list):
    """Strategie-Fabrik, die je Entscheidung (seat, hand_id) mitschreibt und passiv spielt."""
    def make(seat):
        def d(st):
            protokoll.append((seat, st.get("hand_id")))
            la = st["legal"]
            return ("check", None) if la["can_check"] else ("call", None)
        return d
    return make


def test_hand_id_gleich_fuer_beide_spiegelhaelften_und_deckeindeutig():
    from pokerbot.benchmark.duplicate import HAND_ID_STRIDE_JE_DECKSEED, duplicate_ab, gen_decks
    decks = gen_decks(5, seed=11)
    prot_a, prot_b = [], []
    duplicate_ab(_aufzeichner(prot_a), _aufzeichner(prot_b), decks, hand_id_basis=7 * HAND_ID_STRIDE_JE_DECKSEED)
    ids_a = {hid for _, hid in prot_a}
    ids_b = {hid for _, hid in prot_b}
    erwartet = {7 * HAND_ID_STRIDE_JE_DECKSEED + i for i in range(5)}
    assert ids_a == ids_b == erwartet, (ids_a, ids_b)            # beide Haelften, beide Seiten: dieselbe Deck-Adresse
    assert all(hid is not None for _, hid in prot_a + prot_b)   # jede Entscheidung traegt die Adresse
    # A auf Sitz 0 (Haelfte 1) und B auf Sitz 0 (Haelfte 2) sehen je Deck dieselbe (hand_id, seat)-Lage
    assert {(s, h) for s, h in prot_a if s == 0} == {(s, h) for s, h in prot_b if s == 0}


def test_privater_gym_seed_symmetrisch_im_spiegel():
    """A/A exakt 0 verlangt: gleiche Adresse + gleicher Sitz -> gleicher Seed (river_plan.privater_seed_gym)."""
    from pokerbot.autogym.river_plan import privater_seed_gym
    assert privater_seed_gym("1080013000004", 0) == privater_seed_gym("1080013000004", 0)
    assert privater_seed_gym("1080013000004", 0) != privater_seed_gym("1080013000005", 0)   # 2k/2k+1 = der Nonzero-Bug
    assert privater_seed_gym("1080013000004", 0) != privater_seed_gym("1080013000004", 1)


def test_r10_stack_registriert_gym_und_live_kanal(tmp_path=None):
    _ohne_pokerb_env()
    from pokerbot.autogym import pargate
    from pokerbot.autogym.river_plan import RiverPlanFabrik
    assert "r10_stack" in pargate.KANDIDATEN
    passiv = lambda seat: (lambda st: ("check", None))       # noqa: E731
    gym = pargate._wickle("r10_stack", passiv)
    assert isinstance(gym, RiverPlanFabrik)
    assert (gym.modus, gym.deadline_s, gym.min_pot_chips, gym.iters, gym.trace_pfad) == ("gym", None, 1500, 150, None)
    assert gym.private_seed_quelle == "deck_hand_id_sitz"
    os.environ[pargate.K2_TRACE_ENV] = "data/runs/v10/_test_trace.jsonl"
    try:
        live = pargate._wickle("r10_stack", passiv, kanal="live")
    finally:
        os.environ.pop(pargate.K2_TRACE_ENV, None)
    assert (live.modus, live.deadline_s, live.trace_pfad) == ("live", pargate.K2_LIVE_DEADLINE_S, "data/runs/v10/_test_trace.jsonl")
    assert live.private_seed_quelle == "os_urandom"
    try:
        pargate._wickle("r10_stack", passiv, kanal="egal")
        raise AssertionError("unbekannter Kanal muss werfen")
    except ValueError:
        pass


def test_rc_stack_aufloesbar_und_wickle_decide_traegt_seedquelle():
    _ohne_pokerb_env()
    from pokerbot.autogym.pargate import KANDIDATEN
    from pokerbot.strategy.auslese import FINAL_STACK, RC_STACK, wickle_decide
    assert RC_STACK == "r10_stack" and RC_STACK in KANDIDATEN and FINAL_STACK == "r8_stack"
    from pokerbot.strategy.bot import PokerBot
    pb = PokerBot(0, seed=1, exploit=False)
    wickle_decide(pb, FINAL_STACK)
    assert getattr(pb, "private_seed_quelle", None) is None          # r8: keine K2-Seedquelle
    wickle_decide(pb, RC_STACK)
    assert pb.private_seed_quelle == "os_urandom"                    # live-Kanal (K4-Fingerprint liest es)


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    rot = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except Exception as e:  # noqa: BLE001
            rot += 1
            print(f"ROT  {t.__name__}: {type(e).__name__}: {e}")
    print(f"{len(tests) - rot}/{len(tests)} gruen")
    sys.exit(1 if rot else 0)
