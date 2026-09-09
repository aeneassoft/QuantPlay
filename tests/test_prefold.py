"""VORAB-FOLD (User 2026-09-09): der Mensch foldet, bevor er dran ist; die Hand laeuft im Hintergrund zu Ende.
Prueft: Chip-Erhaltung, Hero gefoldet + Hand vorbei in EINEM Aufruf, Fold als benotete Entscheidung erfasst,
Fehler bei Doppel-Fold, und den Gratis-Check-Fall (Vorab-Fold wird aufgehoben, Hero ist normal dran).
Run: python -m tests.test_prefold"""
import warnings

warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient  # noqa: E402

from pokerbot.web import six_server as S  # noqa: E402

HUMAN = S.HUMAN


def _chips(v):
    # am Handende stecken die Gewinne schon in den Stacks; "pot" ist dann nur die Anzeige der vergebenen Summe
    return sum(s["stack"] for s in v["seats"]) + (0 if v["hand_over"] else v["pot"])


def _new(c, seed, mode="gto"):
    v = c.post("/api/new_session", json={"mode": mode, "seed": seed, "step": True}).json()
    assert "error" not in v, v
    return v


def test_prefold_folds_and_finishes():
    c = TestClient(S.app)
    n_fold = n_free = 0
    for seed in range(1, 25):
        v = _new(c, seed)
        if v["to_act"] == HUMAN:            # Hero handelt als Erster (UTG): kein Vorab-Fold moeglich
            continue
        start = _chips(v)
        v = c.post("/api/prefold", json={}).json()
        assert "error" not in v, v
        assert abs(_chips(v) - start) < 1e-6, "Chip-Erhaltung verletzt"
        hero = v["seats"][HUMAN]
        if v["prefold"] == "gefoldet":
            n_fold += 1
            assert hero["folded"] and v["hand_over"], "Hero muss gefoldet und die Hand vorbei sein"
            assert any((r.get("human_action") or {}).get("action") == "fold" for r in S.SESSION.last_graded), \
                "der Vorab-Fold muss als benotete Entscheidung erfasst sein"
            assert S.SESSION.hands_done == 1 and (v.get("coach") or {}).get("hand_no") == 1
            r = c.post("/api/prefold", json={})
            assert r.status_code == 400, "Doppel-Vorab-Fold muss abgewiesen werden"
        elif v["prefold"] == "kampflos":
            assert v["hand_over"] and not hero["folded"] and hero["won"] > 0, "kampflos: Hero gewinnt die Blinds"
        else:
            n_free += 1
            assert v["prefold"] == "check_frei" and not hero["folded"] and not v["hand_over"]
            assert v["to_act"] == HUMAN and v["legal"]["can_check"], "Gratis-Check: Hero ist normal dran"
    assert n_fold >= 5, f"zu wenige Fold-Faelle: {n_fold}"
    print(f"  Vorab-Fold: {n_fold} gefoldet (Hand sofort vorbei), {n_free} Gratis-Check aufgehoben")


def test_prefold_tournament():
    c = TestClient(S.app)
    v = _new(c, 42, mode="tournament")
    if v["to_act"] != HUMAN:
        v = c.post("/api/prefold", json={}).json()
        assert "error" not in v, v
        if v["prefold"] == "gefoldet":
            last = v["tournament"]["advisor"]["last"]
            assert last and last["human"] == "fold", "Turnier-Urteil zum Vorab-Fold fehlt"
    assert S.SESSION.mtt.total_chips() == 60 * 5000


def test_fractional_amount_is_rounded():
    """User-Fund 2026-09-09 (leerer Tisch): Turnier-bb 50 -> Slider-Raster 12,5 Chips -> amount 187.5 -> frueher
    422 {"detail"} (vom Client als Zustand gerendert). Jetzt: float wird gerundet, Antwort ist ein Zustand."""
    c = TestClient(S.app)
    for seed in range(1, 40):
        v = _new(c, seed, mode="tournament")
        while not v["hand_over"] and v["to_act"] != HUMAN:
            v = c.post("/api/step", json={}).json()
        if v["hand_over"] or not v["legal"].get("can_raise"):
            continue
        amt = v["legal"]["raise_min"] + 12.5
        r = c.post("/api/action", json={"action": "raise", "amount": amt, "step": True})
        assert r.status_code == 200, r.text
        v = r.json()
        assert "seats" in v and "error" not in v, v
        me = v["seats"][HUMAN]
        assert float(me["committed_street"]).is_integer(), "Chips muessen ganzzahlig bleiben"
        print(f"  Betrag {amt} -> gesetzt {me['committed_street']} (Seed {seed})")
        return
    raise AssertionError("kein Raise-Spot in 40 Seeds")


def run():
    test_prefold_folds_and_finishes()
    test_prefold_tournament()
    test_fractional_amount_is_rounded()
    print("VORAB-FOLD: alle Tests bestanden")


if __name__ == "__main__":
    run()
