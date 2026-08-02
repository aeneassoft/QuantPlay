"""Range-Erzählung — der Strategie-Abschnitt des Hand-Feedbacks, ECHT gerechnet (User-Auftrag 2026-08-02).

WHY: die erste Fassung war eine statische Heuristik (fast jede Hand bekam dieselben drei Sätze). Der
User-Auftrag ("Preflop repräsentiert der Gegner top 5% ... Du repräsentierst einen Flush-Draw") verlangt
echte Range-Konstruktion — und die Assets existieren längst: strategy/range_tracker.RangeTracker (der
Bayes-Tracker des Live-Bots, Advisor-Modelle inklusive), engine/equity.equity_vs_weighted_range und
evaluator.made_class (die geteilte Treffer-Taxonomie). Wir bauen den Tracker pro Straße auf dem
Record-Snapshot der Hero-Entscheidung auf (oracle.record_to_hu_state — dieselbe HU-Projektion, mit der
der Grader benotet) und erzählen, was beide Linien REPRÄSENTIEREN vs. was wirklich gehalten wird.

6-MAX-EHRLICHKEIT: die Tracker-Prioren sind HU-kalibriert (SB-Open 84% aller Hände) — als Lehrtext für
den 6-max-Trainer wäre das irreführend. StoryTracker überschreibt NUR die Preflop-Prioren mit üblichen
6-max-Bändern (Open ~20%, 3-Bet ~9%, ...); alle Postflop-Updates bleiben die echten Advisor-Modelle.
Die Bänder sind ERZÄHL-Prioren, kein Grading — die Noten oben im Feedback kommen weiter vom Oracle.

Fail-soft (Trainer-Doktrin): build_story gibt bei jedem harten Problem [] zurück — templates_de fällt
dann auf die alte Heuristik-Erzählung zurück. Deterministisch: MC-Equity seeded aus spot_fp+Straße.
Run: python -m pokerbot.coach.range_story   (Selftest: echte Table-Hand, Determinismus, Fail-soft)
"""
from __future__ import annotations

import random
import zlib
from collections import defaultdict

from pokerbot.engine.equity import equity_vs_weighted_range
from pokerbot.engine.evaluator import made_class
from pokerbot.strategy import preflop_strength as ps
from pokerbot.strategy import ranges as R
from pokerbot.strategy.range_tracker import RangeTracker

# 6-max-Erzähl-Prioren (Modern-Poker-Theory-übliche Bänder, über Positionen gemittelt): Anteil aller
# Starthände, den die jeweilige Preflop-Linie repräsentiert. Index = Anzahl Preflop-Raises.
RAISER_FRAC = {1: 0.20, 2: 0.09, 3: 0.04}      # Open / 3-Bet / 4-Bet+
CALLER_FRAC = {0: 0.55, 1: 0.28, 2: 0.12, 3: 0.06}   # Limp / Call-vs-Open / Call-vs-3-Bet / ...
RAISE_NAME = {1: "Raise", 2: "3-Bet", 3: "4-Bet"}
EQ_ITERS = 200            # MC-Equity flop/turn (~3.5pp SE — für eine Erzählung genug); River enumeriert exakt
N_EDGE_BEISPIELE = 2      # Range-UNTERGRENZE zeigen ("bis runter zu ...") — die lehrt, wo die Range endet
HIT = ("top-pair", "two-pair+", "monster")     # "Treffer" = Top-Paar oder besser (made_class-Taxonomie)
# DU-Zeile: erzählt die Linie mehr/weniger als das Blatt? Bänder auf dem repräsentierten Treffer-Anteil.
TOLD_VIEL, TOLD_WENIG = 0.50, 0.35

_SUIT = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
MADE_DE = {"air": "Luft", "pair": "ein Paar", "top-pair": "Top-Paar",
           "two-pair+": "zwei Paar oder besser", "monster": "ein Monster (Straße oder besser)"}
_TAG = {"preflop": "PREFLOP", "flop": "FLOP", "turn": "TURN", "river": "RIVER"}


def _card_de(c: str) -> str:
    """'Ks' -> 'K♠', 'Ts' -> '10♠' (kein T-Jargon für Einsteiger)."""
    r = "10" if c[:1] == "T" else c[:1]
    return r + _SUIT.get(c[1:2], c[1:2])


def _cards_de(cs) -> str:
    return " ".join(_card_de(c) for c in cs)


class StoryTracker(RangeTracker):
    """Der echte Bayes-Tracker mit 6-max-Erzähl-Prioren statt der HU-Prioren (nur _init_preflop ersetzt).

    BUDGET-KONSTRUKTION (gemessen: voll 1.6s > 800ms-Fenster): EIN Repräsentant pro Starthand-Klasse
    statt aller ~1300 Combos, gewichtet mit der LEBENDEN Combo-Anzahl der Klasse (Offsuit 12 / Suited 4 /
    Paar 6 minus Board-Kollisionen) — der Klassen-Mix bleibt damit fast exakt, die Advisor-Calls fallen
    ~8x. Der Repräsentant wird board-DISJUNKT gewählt, sonst killt _remove_dead eine ganze Klasse, deren
    übrige Combos noch leben."""

    def __init__(self, board_hint=(), advisor=None):
        super().__init__(advisor=advisor)
        self._dead_hint = frozenset(board_hint)

    def _init_preflop(self, state) -> None:
        from pokerbot.engine.cards import expand_class
        hist = state.get("history") or []
        raises = [h for h in hist if h.get("street") == "preflop"
                  and h.get("action") in ("bet", "raise", "allin")]
        n = min(len(raises), 3)
        last_raiser = raises[-1].get("player") if raises else None
        for seat in (0, 1):
            frac = RAISER_FRAC[max(n, 1)] if seat == last_raiser else CALLER_FRAC[n]
            rng_seat: dict[tuple, float] = {}
            for hc in sorted(ps.range_top(frac)):          # sorted = der Determinismus-Fix (ranges.py:76)
                live = [cb for cb in expand_class(hc) if not (set(cb) & self._dead_hint)]
                if live:
                    rng_seat[live[0]] = float(len(live))
            self.range[seat] = rng_seat
            self._normalize(seat)


# ---------------------------------------------------------------- Bausteine der Erzählung
def _pre_line(records: list[dict]) -> str:
    """PREFLOP-Zeile ohne Tracker (funktioniert auch, wenn kein Street-Record HU-projizierbar ist)."""
    last = records[-1]
    hist = last.get("history") or []
    hero_seat = (last.get("spot") or {}).get("hero_seat", 0)
    raises = [h for h in hist if str(h.get("street")) == "preflop"
              and h.get("action") in ("bet", "raise", "allin")]
    n = min(len(raises), 3)
    if n == 0:
        return (f"{_TAG['preflop']} · Kein Raise — alle Ranges bleiben breit "
                f"(über die Hälfte aller Starthände).")
    frac, gegner_frac = RAISER_FRAC[n], CALLER_FRAC[n]
    edge = ", ".join(sorted(ps.range_top(frac), key=ps.percentile)[:N_EDGE_BEISPIELE])
    wer_hero = raises[-1].get("player") == hero_seat
    verb = RAISE_NAME[n]
    if wer_hero:
        return (f"{_TAG['preflop']} · Dein {verb} repräsentiert ~{frac * 100:.0f}% der Starthände "
                f"(bis runter zu {edge}) — wer dagegen callt, zeigt ~{gegner_frac * 100:.0f}%.")
    return (f"{_TAG['preflop']} · Sein {verb} repräsentiert ~{frac * 100:.0f}% der Starthände "
            f"(bis runter zu {edge}) — dein Call dagegen: ~{gegner_frac * 100:.0f}%.")


def _hu_tracker(rec: dict):
    """Record -> (StoryTracker, hu_state) via die Grader-Projektion; None, wenn der Spot nicht HU ist."""
    from pokerbot.coach.oracle import record_to_hu_state
    try:
        st = record_to_hu_state(rec)
    except Exception:  # noqa: BLE001 — multiway/malformed -> diese Straße hat keine Quantitativ-Zeile
        return None
    return StoryTracker(board_hint=st.get("board") or ()).build(st), st


def _mix(tracker, seat: int, board: list[str]) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for c, w in tracker.range.get(seat, {}).items():
        out[made_class(board, list(c))] += w
    tot = sum(out.values())
    return {k: v / tot for k, v in out.items()} if tot > 0 else {}


def _hit_share(mix: dict[str, float]) -> float:
    return sum(mix.get(k, 0.0) for k in HIT)


def _vill_ansage(hu_state: dict, street: str) -> str:
    """Was der Gegner auf dieser Straße VOR Heros Entscheidung angesagt hat (HU-projizierte History)."""
    acts = [h.get("action") for h in hu_state.get("history") or []
            if h.get("player") == 1 and str(h.get("street")) == street]
    last = acts[-1] if acts else None
    if last in ("bet", "raise", "allin"):
        verb = {"bet": "Bet", "raise": "Raise", "allin": "All-in"}[last]
        return f"seine {verb} erzählt einen Treffer"
    if last == "call":
        return "sein Call hält die Mitte"
    if last == "check":
        return "sein Check meldet wenig an"
    return "noch keine Ansage von ihm"


def _street_line(rec: dict, street: str) -> tuple[str, object] | None:
    """Eine Straßen-Zeile mit ECHTEN Zahlen: Gegner-Range-Mix (Treffer/Luft) + Heros Equity dagegen."""
    built = _hu_tracker(rec)
    if built is None:
        return None
    tracker, st = built
    board = list(st.get("board") or [])
    if len(board) < 3 or not tracker.range.get(1):
        return None
    mix = _mix(tracker, 1, board)
    if not mix:
        return None
    hit, luft = _hit_share(mix), mix.get("air", 0.0)
    hero_hole = list((rec.get("spot") or {}).get("hero_hole") or [])
    rng = random.Random(zlib.crc32(f"{rec.get('spot_fp')}:{street}".encode()))
    eq = equity_vs_weighted_range(hero_hole, tracker.range[1], board, iters=EQ_ITERS, rng=rng)
    eq_txt = f" Deine Equity dagegen: {eq * 100:.0f}%." if eq == eq else ""   # NaN-Guard
    return (f"{_TAG[street]} {_cards_de(board)} · {_vill_ansage(st, street)} — seine Range: "
            f"{hit * 100:.0f}% Treffer (Top-Paar+), {luft * 100:.0f}% Luft.{eq_txt}", tracker)


def _du_line(rec: dict, tracker) -> str | None:
    """DU-Zeile: was Heros Linie repräsentiert vs. was er wirklich hält — die Kohärenz-Lektion."""
    spot = rec.get("spot") or {}
    hole, board = list(spot.get("hero_hole") or []), list(spot.get("board") or [])
    if len(board) < 3 or not hole or not tracker.range.get(0):
        return None
    told = _hit_share(_mix(tracker, 0, board))
    real = made_class(board, hole)
    fd = ""
    if len(board) <= 4:
        for suit in "shdc":
            if (sum(1 for c in hole + board if c[1:2] == suit) == 4
                    and any(c[1:2] == suit for c in hole)):
                fd = " plus Flush-Draw"
                break
    real_hit = real in HIT
    if real_hit and told < TOLD_WENIG:
        urteil = "mehr Blatt als Geschichte — hier bleibt Value liegen."
    elif not real_hit and told >= TOLD_VIEL:
        # ein Paar ist halbe Substanz, kein reiner Bluff — die Probe nannte beides "Bluff-Territorium"
        urteil = ("mehr Geschichte als Blatt — Bluff-Territorium, nur mit Plan." if real == "air"
                  else "mehr Geschichte als Blatt — halbe Substanz: als Semi-Bluff okay, als Value zu dünn.")
    elif real_hit:
        urteil = "Geschichte und Blatt decken sich."
    else:
        urteil = "beides dünn — kleine Töpfe sind hier dein Freund."
    return (f"DU · Deine Linie repräsentiert {told * 100:.0f}% Treffer — du hältst "
            f"{MADE_DE.get(real, real)}{fd}: {urteil}")


def _showdown_line(records: list[dict], hand_result: dict) -> str | None:
    """Erzählte Geschichte gegen die aufgedeckte Wahrheit prüfen — nur Gewinner zeigen (Mucking-Regel)."""
    if not isinstance(hand_result, dict) or hand_result.get("reason") != "showdown":
        return None
    last = records[-1]
    spot = last.get("spot") or {}
    hero_seat = spot.get("hero_seat", 0)
    live = [s for s in spot.get("seats") or [] if not s.get("folded") and s.get("seat") != hero_seat]
    if len(live) != 1:
        return None
    vill_seat = live[0].get("seat")
    shown = (hand_result.get("shown") or {}).get(vill_seat)
    board = list(hand_result.get("board") or [])
    if not shown or len(board) != 5:
        return None
    hole = list(shown.get("hole") or [])
    vcls = made_class(board, hole)
    aggro = any(str(h.get("street")) != "preflop" and h.get("player") == vill_seat
                and h.get("action") in ("bet", "raise", "allin") for h in last.get("history") or [])
    if aggro:
        # nur LUFT ist ein echter Bluff — ein aufgedecktes mittleres Paar, das gesetzt hat, ist
        # Schutz/dünne Value (die Probe nannte beides "Bluff", das lehrt falsch).
        if vcls in HIT:
            urteil = "die Geschichte stimmte."
        elif vcls == "air":
            urteil = "die Geschichte war geliehen (Bluff)."
        else:
            urteil = "mittleres Paar — eher Schutz als reiner Bluff."
    elif vcls in HIT:
        urteil = "still gespielt, stark gehalten (Slowplay)."
    else:
        return None                     # passiv + dünn gewonnen = keine Lektion, kein Rauschen
    return f"SHOWDOWN · Er zeigt {_cards_de(hole)} = {MADE_DE.get(vcls, vcls)} — {urteil}"


# ---------------------------------------------------------------- Public API
def build_story(records: list[dict], hand_result: dict | None = None) -> list[str]:
    """Records + Hand-Ergebnis -> die Range-Erzählung als Zeilen (max. 6); [] = Aufrufer fällt auf Heuristik."""
    try:
        recs = [r for r in (records or []) if isinstance(r, dict) and r.get("spot")]
        if not recs:
            return []
        lines = [_pre_line(recs)]
        last_tracker, last_rec = None, None
        for street in ("flop", "turn", "river"):
            st_recs = [r for r in recs if str(r.get("street", "")).lower() == street]
            if not st_recs:
                continue
            made = _street_line(st_recs[-1], street)
            if made is not None:
                lines.append(made[0])
                last_tracker, last_rec = made[1], st_recs[-1]
        if last_tracker is not None:
            du = _du_line(last_rec, last_tracker)
            if du:
                lines.append(du)
        sd = _showdown_line(recs, hand_result or {})
        if sd:
            lines.append(sd)
        return lines
    except Exception:  # noqa: BLE001 — Strategie ist Zusatz, nie Blocker (Trainer-Doktrin)
        return []


# ---------------------------------------------------------------- Selftest (echte Table, kein Server)
def _selftest() -> None:
    import time

    from pokerbot.coach import decision_log as dl
    from pokerbot.engine.table import Table

    def spiel_hand(seed: int) -> tuple[list[dict], dict]:
        """HU-Table bis zum Hand-Ende: Hero callt/checkt, der Bot-Sitz setzt jede Postflop-Straße an."""
        t = Table(["Du", "Ava"], starting_stack=10000, sb=50, bb=100, seed=seed, human_seat=0)
        t.start_hand()
        records: list[dict] = []
        while not t.hand_over and t.to_act is not None:
            la = t.legal_actions()
            if t.to_act == 0:
                act = "call" if la["can_call"] else "check"
                records.append(dl.capture_decision(t, "storytest", t.hand_no, "gto", act, None))
                t.act(act)
            elif la.get("is_bet") and t.street in ("flop", "turn", "river"):
                t.act("raise", max(la["raise_min"], min(la["raise_max"], t.pot() // 2)))
            else:
                t.act("check" if la["can_check"] else ("call" if la["can_call"] else "fold"))
        return records, dict(t.result or {})

    records, result = spiel_hand(11)
    assert records and result.get("reason") in ("fold", "showdown"), (len(records), result.get("reason"))
    t0 = time.perf_counter()
    kalt = build_story(records, result)          # Lauf 1 zahlt den einmaligen Advisor-Modell-Load
    kalt_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    lines = build_story(records, result)         # Budget zählt WARM — im Server lädt grader.prewarm() vor
    dauer_ms = (time.perf_counter() - t0) * 1000
    assert kalt == lines and lines, "Story leer oder kalt/warm verschieden"
    assert lines[0].startswith("PREFLOP"), lines[0]
    assert any(l.split()[0] in ("FLOP", "TURN", "RIVER") for l in lines[1:]) or len(records) == 1, lines
    assert any("Treffer" in l for l in lines), lines
    # Determinismus: zweiter Lauf byte-identisch (MC-Equity ist spot_fp-geseedet)
    assert build_story(records, result) == lines, "Range-Story nicht deterministisch"
    # Fail-soft: Müll-Records und leere Eingaben stören nie
    assert build_story([{"grade": "ok"}], None) == []
    assert build_story([], {}) == []
    assert build_story([{"spot": {"seats": "kaputt"}}], {"reason": "showdown"}) == []
    # Budget-Ehrlichkeit: die Erzählung muss ins 800ms-Grading-Fenster passen (six_server WARN-Budget)
    assert dauer_ms < 700, f"build_story warm {dauer_ms:.0f}ms — sprengt das Feedback-Budget"
    print(f"OK - range_story: {len(lines)} Zeilen aus {len(records)} Records ({result.get('reason')}), "
          f"deterministisch, fail-soft, warm {dauer_ms:.0f}ms (kalt {kalt_ms:.0f}ms Modell-Load).")
    for l in lines:
        print("   ", l)


if __name__ == "__main__":
    _selftest()
