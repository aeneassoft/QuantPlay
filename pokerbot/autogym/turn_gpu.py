"""TURN-GPU-GUARD — die Turn-Version der GPU-Solver-Chirurgie (r8-Muster).

Uebertragt river_gpu_guard (improver.py) auf den Turn: in grossen Turn-Toepfen
wird das Turn+River-Subgame mit den am TURN-BEGINN eingefrorenen Tracker-Ranges
auf der GPU geloest (TurnCFR: Turn-Betting + 48-Runout-River-Batch); die
Basis-Aktion wird NUR ueberschrieben, wenn der Solver sie klar verwirft
(p_basis < p_max_basis UND p_alternative > p_min_alt) — konservative Chirurgie,
das Mixing der Basis bleibt sonst unangetastet (Seesaw). Deterministisch
(kein RNG, argmax nur im Klarfall). HU-only; feuert NIE nach dem River-Deal.

Latenz-Budget: der Baum ist bewusst KLEIN (eine Turn-Bet-Size 0.75, ein Raise
2.7x, max_raises=1; River nur 0.75-Bet ohne Raise) — der 48-Runout-Batch ist
trotzdem der Kostentreiber; der Selbsttest misst kalt + warm.

  python -m pokerbot.autogym.turn_gpu           # Selbsttest (Big-Pot + Klein-Pot)
"""
from __future__ import annotations

from pokerbot.strategy.gpu_cfr import TurnCFR, combo_index, range_vector
from pokerbot.strategy.gpu_resolver import POT_NORM, _injiziere

# Baum-Geometrie der Chirurgie (klein fuer Latenz; Vorgabe der r8-Turn-Spec)
TURN_BETS = (0.75,)
RAISE_SIZES = (2.7,)
MAX_RAISES = 1
RIVER_KW = {"bet_sizes": (0.75,), "raise_sizes": (), "max_raises": 1}


def _turn_seq(hist_nach_deal: list, hero_seat: int) -> list | None:
    """Turn-History (nach dem Deal) -> Sequenz (wer, kind, zusatz_chips);
    identische Uebersetzung wie in river_gpu_guard (Level-Verfolgung je Sitz).
    None bei einem weiteren Deal (nach dem River-Deal feuert der Guard nie)."""
    lvl = {0: 0.0, 1: 0.0}
    seq = []
    for h in hist_nach_deal:
        if h.get("action") == "deal":
            return None
        akt, s2 = h.get("action"), h.get("player")
        if s2 not in (0, 1):
            continue
        wer = "hero" if s2 == hero_seat else "vill"
        if akt in ("bet", "raise", "allin"):
            to = float(h.get("to") or h.get("amount") or 0.0)
            seq.append((wer, "raise" if lvl[s2] or max(lvl.values()) else "bet",
                        max(0.0, to - lvl[s2])))
            lvl[s2] = max(lvl[s2], to)
        elif akt == "call":
            need = max(lvl.values()) - lvl[s2]
            seq.append((wer, "call", need))
            lvl[s2] = max(lvl.values())
        elif akt == "check":
            seq.append((wer, "check", 0.0))
    return seq


def _navigiere_turn(cfr: TurnCFR, seq: list, skala: float):
    """Laeuft die gespielte Turn-Sequenz (ohne die Frage-Aktion) durch den
    geloesten Baum; Vorlage gpu_resolver._navigiere. Bets/Raises werden auf den
    nearest-Arm ueber die invest-DIFFERENZ des Aktors gesnappt (normiert);
    check/call direkt; fold beendet. None bei Desync/Terminal/Chance-Knoten."""
    node = cfr.root
    for _wer, kind, size in seq:
        if node.terminal is not None:                # auch 'chance' — Turn-Ebene vorbei
            return None
        if kind in ("check", "call"):
            if kind not in node.acts:
                return None
            node = node.kids[node.acts.index(kind)]
        elif kind in ("bet", "raise"):
            kandidaten = [(i, k) for i, (a2, k) in enumerate(zip(node.acts, node.kids))
                          if a2.startswith(("bet", "raise"))]
            if not kandidaten:
                return None
            ziel = size * skala
            aktor = node.actor
            basis_inv = node.invest[aktor]
            i_best = min(kandidaten,
                         key=lambda ik: abs((ik[1].invest[aktor] - basis_inv) - ziel))[0]
            node = node.kids[i_best]
        else:                                        # fold beendet — nichts zu pruefen
            return None
    if node.terminal is not None or node.actor < 0:
        return None
    return node


def _turn_urteil(st: dict, a, amt, iters: int, p_max_basis: float,
                 p_min_alt: float) -> dict | None:
    """Kern der Chirurgie OHNE Trigger/Except (fuer den Selbsttest direkt
    aufrufbar). Liefert {'acts', 'sigma', 'p_basis', 'urteil'} — 'urteil' ist
    (action, amount) NUR im Klarfall, sonst None; None gesamt = kein Solve
    moeglich (Navigation/Range/History-Desync)."""
    from pokerbot.strategy.range_tracker import RangeTracker

    me = st["players"][st["to_act"]]
    to_call = max(0, st["current_bet"] - me["committed_street"])
    board4 = st["board"][:4]
    if len(board4) != 4 or len(st["players"]) != 2:
        return None
    # Ranges am TURN-BEGINN: history bis inkl. Turn-Deal schneiden
    hist = st.get("history", []) or []
    schnitt = next((i for i, h in enumerate(hist)
                    if h.get("action") == "deal" and h.get("street") == "turn"),
                   None)
    if schnitt is None:
        return None
    st0 = dict(st)
    st0["history"] = hist[:schnitt + 1]
    t = RangeTracker().build(st0)
    hero_w = t.range.get(st["to_act"], {})
    vill_w = t.range.get(1 - st["to_act"], {})
    if not hero_w or not vill_w:
        return None
    # Turn-Sequenz (Zusatz-Betraege) + Frage-Aktion (Basis-Entscheid) anfuegen
    seq = _turn_seq(hist[schnitt + 1:], st["to_act"])
    if seq is None:
        return None
    frage = ("raise" if a in ("raise", "allin") and to_call > 0 else
             "bet" if a in ("bet", "raise", "allin") else a)
    seq.append(("hero", frage, 0.0))
    # Pot/eff-Stack am TURN-BEGINN: Turn-Einsaetze aus st['pot'] herausrechnen
    turn_einsaetze = sum(z for _, k, z in seq if k in ("bet", "raise", "call"))
    pot_turn = st["pot"] - turn_einsaetze
    eff = min(p["stack"] + p["committed_street"] for p in st["players"])
    if pot_turn <= 0 or eff <= 0:
        return None
    # pot-normiert loesen (Poker ist pot-skalen-invariant, wie gpu_resolver);
    # EIN Spot pro Entscheidung -> exakter SPR statt Bucket (kein Batching noetig)
    skala = POT_NORM / pot_turn
    hero_oop = (st["to_act"] != st.get("button", 0))     # HU: Button = IP postflop
    r_hero = range_vector(_injiziere(hero_w, tuple(me["hole"])))
    r_vill = range_vector(vill_w)
    r_oop, r_ip = (r_hero, r_vill) if hero_oop else (r_vill, r_hero)
    cfr = TurnCFR(board4, r_oop, r_ip, pot=POT_NORM, eff_stack=eff * skala,
                  turn_bets=TURN_BETS, raise_sizes=RAISE_SIZES,
                  max_raises=MAX_RAISES, river_kw=RIVER_KW)
    cfr.solve(iters=iters)
    node = _navigiere_turn(cfr, seq[:-1], skala)
    if node is None:
        return None
    hero_rolle = 0 if hero_oop else 1
    if node.actor != hero_rolle:
        return None                                  # Sequenz-Desync — ehrlich auslassen
    sig = cfr.avg_sigma(node)[0]                     # Turn-Knoten: [1,1326,n] -> [1326,n]
    ci = combo_index(*me["hole"])
    p = [float(x) for x in sig[ci]]
    acts = list(node.acts)
    if frage in ("bet", "raise"):
        kand = [i for i, x in enumerate(acts) if x.startswith(("bet", "raise"))]
        p_basis = max((p[i] for i in kand), default=0.0)
    elif frage in acts:
        p_basis = p[acts.index(frage)]
    else:
        return None
    best = max(range(len(p)), key=lambda i: p[i])
    urteil = None
    if p_basis < p_max_basis and p[best] > p_min_alt:
        alt = acts[best]
        if alt == "fold" and to_call > 0:
            urteil = ("fold", None)
        elif alt == "call" and to_call > 0:
            urteil = ("call", None)
        elif alt == "check" and to_call == 0:
            urteil = ("check", None)
        elif alt.startswith("bet") and to_call == 0:
            urteil = ("bet", int(0.75 * st["pot"]))
    return {"acts": acts, "sigma": p, "p_basis": p_basis, "urteil": urteil}


def turn_gpu_guard(make_strat, min_pot_chips: int = 3000, iters: int = 120,
                   p_max_basis: float = 0.10, p_min_alt: float = 0.70):
    """GPU-SOLVER-CHIRURGIE am TURN — Wrapper-Fabrik im Guard-Kontrakt des
    Improvers (river_gpu_guard-Struktur): Trigger nur street=='turn' und
    pot >= min_pot_chips; jede Exception laesst die Basis-Aktion stehen."""
    def make(seat):
        base = make_strat(seat)

        def d(st):
            a, amt = base(st)
            if st["street"] != "turn" or st["pot"] < min_pot_chips:
                return a, amt
            try:
                res = _turn_urteil(st, a, amt, iters, p_max_basis, p_min_alt)
                if res is not None and res["urteil"] is not None:
                    return res["urteil"]
            except Exception:  # noqa: BLE001
                pass            # defensiv: im Zweifel bleibt die Basis-Aktion
            return a, amt
        return d
    return make


# ---------------------------------------------------------------------------
# Selbsttest: synthetischer Big-Pot-Turn-State (Guard MUSS den Solver-Pfad
# durchlaufen) + Klein-Pot-State (Trigger DARF nicht feuern) + Latenz.
# ---------------------------------------------------------------------------
def _big_pot_state() -> dict:
    """3-bet-Pot, BB (Sitz 1, OOP) checkt den Turn, BTN barrelt 0.75 Pot —
    Hero=BB mit Luft steht vor der Frage-Entscheidung (Basis: call)."""
    board = ["2c", "7d", "9h", "Kd"]
    hist = [
        {"player": 0, "action": "raise", "street": "preflop", "to": 300},
        {"player": 1, "action": "raise", "street": "preflop", "to": 900},
        {"player": 0, "action": "call", "street": "preflop", "amount": 600},
        {"action": "deal", "street": "flop", "board": board[:3]},
        {"player": 1, "action": "bet", "street": "flop", "to": 900},
        {"player": 0, "action": "call", "street": "flop", "amount": 900},
        {"action": "deal", "street": "turn", "board": board},
        {"player": 1, "action": "check", "street": "turn"},
        {"player": 0, "action": "bet", "street": "turn", "to": 2700},
    ]
    players = [
        {"idx": 0, "hole": ["??", "??"], "stack": 15500,
         "committed_street": 2700, "committed_total": 4500,
         "folded": False, "all_in": False},
        {"idx": 1, "hole": ["Qh", "3d"], "stack": 18200,
         "committed_street": 0, "committed_total": 1800,
         "folded": False, "all_in": False},
    ]
    return {"street": "turn", "board": list(board), "pot": 6300,
            "current_bet": 2700, "to_act": 1, "button": 0, "bb": 100,
            "players": players, "history": hist}


def _klein_pot_state() -> dict:
    """Limped Pot, Turn-Bet 300 in 600 — pot 900 < min_pot_chips: kein Trigger."""
    st = _big_pot_state()
    st["pot"] = 900
    st["current_bet"] = 300
    st["players"][0]["committed_street"] = 300
    st["history"][-1] = {"player": 0, "action": "bet", "street": "turn", "to": 300}
    return st


def _selbsttest() -> None:
    import sys
    import time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from pokerbot.engine.gpu_eval import DEVICE
    print(f"Device: {DEVICE}")

    def make_basis(_seat):
        return lambda st: ("call", None)

    strat = turn_gpu_guard(make_basis)(1)

    # 1) Big-Pot: der Solver-Pfad muss OHNE Exception durchlaufen (direkter
    #    Kern-Aufruf, damit das defensive except nichts verschluckt)
    st = _big_pot_state()
    t0 = time.perf_counter()
    res = _turn_urteil(st, "call", None, iters=120, p_max_basis=0.10, p_min_alt=0.70)
    t_kalt = time.perf_counter() - t0
    assert res is not None, "Solver-Pfad lieferte None (Navigation/Range-Desync)"
    sigsum = sum(res["sigma"])
    assert abs(sigsum - 1.0) < 1e-3, f"Sigma-Summe {sigsum} != 1"
    print(f"Big-Pot-Urteil: acts={res['acts']} "
          f"sigma={['%.3f' % x for x in res['sigma']]} (Summe {sigsum:.4f}) "
          f"p_basis={res['p_basis']:.3f} urteil={res['urteil']}")
    print(f"Latenz kalt (inkl. CUDA-Init): {t_kalt:.2f}s")

    # 2) Guard-Wrapper auf demselben State (warm): Ergebnis muss konsistent sein
    t0 = time.perf_counter()
    a, amt = strat(st)
    t_warm = time.perf_counter() - t0
    erwartet = res["urteil"] if res["urteil"] is not None else ("call", None)
    assert (a, amt) == erwartet, f"Guard {a,amt} != Kern-Urteil {erwartet}"
    print(f"Guard (warm): {(a, amt)} in {t_warm:.2f}s")

    # 3) Klein-Pot: Trigger darf nicht feuern (Basis unveraendert, quasi 0 Latenz)
    st_klein = _klein_pot_state()
    t0 = time.perf_counter()
    a2, amt2 = strat(st_klein)
    t_klein = time.perf_counter() - t0
    assert (a2, amt2) == ("call", None), "Klein-Pot: Basis-Aktion veraendert!"
    assert t_klein < 0.1, f"Klein-Pot-Latenz {t_klein:.3f}s — Trigger hat gefeuert?"
    print(f"Klein-Pot: Basis steht ({a2}), Latenz {t_klein*1000:.1f}ms — Trigger stumm")

    # 4) River-Street: der Guard ist Turn-only
    st_river = dict(st)
    st_river["street"] = "river"
    a3, amt3 = strat(st_river)
    assert (a3, amt3) == ("call", None), "River-State: Guard haette schweigen muessen"
    print("River-State: Guard stumm (Turn-only bestaetigt)")
    print("Selbsttest OK.")


if __name__ == "__main__":
    _selbsttest()
