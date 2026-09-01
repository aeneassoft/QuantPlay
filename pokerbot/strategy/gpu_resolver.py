"""GPU-RIVER-RESOLVER — Batch-Subgame-Solves + Sequenz-Navigation (auf gpu_cfr).

Semantik (Resolver-Standard): die Tracker-Ranges beider Seiten werden am
RIVER-BEGINN eingefroren; das River-Subgame wird von dort GELOEST (RiverCFRBatch);
die tatsaechlich gespielte River-Sequenz wird im geloesten Baum navigiert
(Bet-Sizes nearest-Arm-gesnappt, wie resolver._match_label); am Zielknoten wird
die Durchschnitts-Strategie fuer Heros konkrete Combo ausgegeben.

Gegen die dokumentierte hand-not-in-range-Falle (Flop-Resolver-Erstflug 0/3):
heros reale Combo wird mit Mindestgewicht in die eigene Range INJIZIERT.

Batching: Spots werden nach Baum-GEOMETRIE gruppiert (Poker ist pot-skalen-
invariant -> pot=100 normiert, eff_stack = SPR-Bucket); jede Gruppe ist EIN
GPU-Batch — die 100%-Auslastungs-Form (gemessen: B=64..256 ~1000 Subgame-Iter/s).

  python -m pokerbot.strategy.gpu_resolver     # Selbsttest (synthetischer Spot)
"""
from __future__ import annotations

import torch

from pokerbot.strategy.gpu_cfr import (DEVICE, N_COMBOS, RiverCFRBatch, Node,
                                       combo_index, range_vector)

# SPR-Buckets fuer die Geometrie-Gruppierung (eff_stack/pot am River-Beginn)
SPR_BUCKETS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 7.0, 10.0)
POT_NORM = 100.0
HERO_MIN_GEWICHT = 0.02          # Injektions-Masse relativ zur Range-Gesamtmasse
DEFAULT_ITERS = 300


def spr_bucket(spr: float) -> float:
    for b in SPR_BUCKETS:
        if spr <= b * 1.25:
            return b
    return SPR_BUCKETS[-1]


class RiverSpot:
    """Ein River-Spot: Board, Ranges am River-Beginn, Geometrie, gespielte
    River-Sequenz bis zur Frage-Entscheidung, Heros Combo + Sitzrolle."""

    def __init__(self, board: list[str], hero_w: dict, vill_w: dict,
                 pot_river: float, eff_stack: float, hero_oop: bool,
                 seq: list[tuple[str, str, float]], hero_hole: tuple[str, str],
                 tag=None):
        self.board = board
        self.hero_w = dict(hero_w)
        self.vill_w = dict(vill_w)
        self.pot = float(pot_river)
        self.eff = float(eff_stack)
        self.hero_oop = hero_oop
        # seq: Liste (wer, kind, size_chips) mit wer in {'hero','vill'},
        # kind in {'check','bet','raise','call','fold'}; size = Ziel-Level in Chips
        self.seq = seq
        self.hero_hole = hero_hole
        self.tag = tag
        self.spr = self.eff / max(self.pot, 1.0)

    def geometrie(self) -> float:
        return spr_bucket(self.spr)


def _injiziere(w: dict, combo: tuple[str, str]) -> dict:
    masse = sum(v for v in w.values() if v > 0) or 1.0
    schluessel = tuple(combo)
    if w.get(schluessel, 0.0) < HERO_MIN_GEWICHT * masse:
        w = dict(w)
        w[schluessel] = HERO_MIN_GEWICHT * masse
    return w


def _navigiere(cfr: RiverCFRBatch, spot: RiverSpot, b_idx: int) -> tuple[Node, int] | None:
    """Laeuft die gespielte Sequenz durch den geloesten Baum; liefert den Knoten
    der LETZTEN Sequenz-Aktion (= Heros Frage-Entscheidung) + Aktions-Index-Map.
    Die letzte Aktion in spot.seq ist Heros zu pruefende Entscheidung — navigiert
    wird bis VOR sie; zurueck kommt der Knoten, an dem Hero am Zug ist."""
    node = cfr.root
    skala = POT_NORM / max(spot.pot, 1e-9)
    for wer, kind, size in spot.seq[:-1]:
        if node.terminal is not None:
            return None
        if kind == "check":
            if "check" not in node.acts:
                return None
            node = node.kids[node.acts.index("check")]
        elif kind == "call":
            if "call" not in node.acts:
                return None
            node = node.kids[node.acts.index("call")]
        elif kind in ("bet", "raise"):
            # nearest-Arm auf den ZUSATZ-Einsatz des Aktors (normiert)
            kandidaten = [(i, k) for i, (a, k) in enumerate(zip(node.acts, node.kids))
                          if a.startswith(("bet", "raise"))]
            if not kandidaten:
                return None
            ziel = size * skala
            def zusatz(k: Node) -> float:
                return (k.invest[node.actor] - node.invest[node.actor])
            i_best = min(kandidaten, key=lambda ik: abs(zusatz(ik[1]) - ziel))[0]
            node = node.kids[i_best]
        else:                                    # fold beendet — nichts zu navigieren
            return None
    if node.terminal is not None or node.actor < 0:
        return None
    return node, b_idx


def _navigiere_mit_reach(cfr: RiverCFRBatch, spot: RiverSpot, b_idx: int,
                         gegner_range: torch.Tensor):
    """Wie _navigiere, fuehrt aber die GEGNER-Reach mit (Range x avg_sigma-
    Faktoren an jedem Gegner-Knoten des Pfads). Rueckgabe (node, reach [1326])."""
    node = cfr.root
    reach = gegner_range.clone()
    skala = POT_NORM / max(spot.pot, 1e-9)
    hero_rolle = 0 if spot.hero_oop else 1
    for wer, kind, size in spot.seq[:-1]:
        if node.terminal is not None:
            return None
        if kind == "check":
            if "check" not in node.acts:
                return None
            i_arm = node.acts.index("check")
        elif kind == "call":
            if "call" not in node.acts:
                return None
            i_arm = node.acts.index("call")
        elif kind in ("bet", "raise"):
            kandidaten = [(i, k) for i, (a, k) in enumerate(zip(node.acts, node.kids))
                          if a.startswith(("bet", "raise"))]
            if not kandidaten:
                return None
            ziel = size * skala
            def zusatz(k: Node) -> float:
                return k.invest[node.actor] - node.invest[node.actor]
            i_arm = min(kandidaten, key=lambda ik: abs(zusatz(ik[1]) - ziel))[0]
        else:
            return None
        if node.actor != hero_rolle:                       # Gegner handelt
            sig = cfr.avg_sigma(node)[b_idx]               # [1326, n_acts]
            reach = reach * sig[:, i_arm]
        node = node.kids[i_arm]
    if node.terminal is not None or node.actor < 0:
        return None
    return node, reach


def solve_spots(spots: list[RiverSpot], iters: int = DEFAULT_ITERS,
                max_batch: int = 192, mit_evs: bool = False,
                **baum_kw) -> list[dict | None]:
    """Loest alle Spots (geometrie-gruppiert, GPU-Batches) und liefert je Spot
    die Hero-Strategie am Frage-Knoten: {'acts': [...], 'sigma': [...],
    'gespielt': kind, 'expl': float} — None wenn Navigation/Combo scheitert."""
    out: list[dict | None] = [None] * len(spots)
    gruppen: dict[float, list[int]] = {}
    for i, s in enumerate(spots):
        gruppen.setdefault(s.geometrie(), []).append(i)
    for geo, idxs in gruppen.items():
        for start in range(0, len(idxs), max_batch):
            teil = idxs[start:start + max_batch]
            boards = [spots[i].board for i in teil]
            r_oop = torch.stack([
                range_vector(_injiziere(spots[i].hero_w, spots[i].hero_hole)
                             if spots[i].hero_oop else spots[i].vill_w)
                for i in teil])
            r_ip = torch.stack([
                range_vector(spots[i].vill_w if spots[i].hero_oop
                             else _injiziere(spots[i].hero_w, spots[i].hero_hole))
                for i in teil])
            cfr = RiverCFRBatch(boards, r_oop, r_ip, pot=POT_NORM,
                                eff_stack=geo * POT_NORM, **baum_kw)
            cfr.solve(iters=iters)
            expl = cfr.exploitability()
            ev_gruppen: dict[int, list] = {}     # id(node) -> [(b_idx, i, node, reach)]
            for b_idx, i in enumerate(teil):
                nav = _navigiere(cfr, spots[i], b_idx)
                if nav is None:
                    continue
                node, _ = nav
                hero_rolle = 0 if spots[i].hero_oop else 1
                if node.actor != hero_rolle:
                    continue                     # Sequenz-Desync — ehrlich auslassen
                sig = cfr.avg_sigma(node)[b_idx]            # [1326, n_acts]
                ci = combo_index(*spots[i].hero_hole)
                # Zusatz-Einsatz je Arm in POT_NORM-Einheiten (fuer Size-Ausgabe:
                # real = zusatz_norm / POT_NORM * pot_river)
                zusatz = [k.invest[node.actor] - node.invest[node.actor]
                          for k in node.kids]
                out[i] = {"acts": list(node.acts),
                          "sigma": [float(x) for x in sig[ci]],
                          "zusatz_norm": [float(z) for z in zusatz],
                          "expl": float(expl[b_idx]),
                          "gespielt": spots[i].seq[-1][1],
                          "tag": spots[i].tag}
                if mit_evs:
                    gr = 1 - hero_rolle
                    grange = cfr.r[gr][b_idx]
                    navr = _navigiere_mit_reach(cfr, spots[i], b_idx, grange)
                    if navr is not None:
                        ev_gruppen.setdefault(id(navr[0]), []).append(
                            (b_idx, i, navr[0], navr[1]))
            # EV-Abfragen knoten-gruppiert: EIN _ev-Traversal je distinktem Knoten
            for eintraege in ev_gruppen.values():
                node = eintraege[0][2]
                hero_rolle = node.actor
                reach_b = torch.zeros(cfr.B, N_COMBOS, device=DEVICE)
                for b_idx, _i, _n, reach in eintraege:
                    reach_b[b_idx] = reach
                av = cfr.action_values(node, reach_b, hero_rolle)   # [B,1326,n]
                for b_idx, i, _n, _r in eintraege:
                    ci = combo_index(*spots[i].hero_hole)
                    # Chips der POT_NORM-Skala; NUR DIFFERENZEN verwenden
                    # (Zentrierungs-Konstante kuerzt sich je Combo heraus).
                    out[i]["ev_je_akt"] = [float(x) for x in av[b_idx, ci]]
    return out


def _selbsttest() -> None:
    import itertools
    import random
    import sys
    from pokerbot.engine.cards import make_deck
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rng = random.Random(9)
    deck = make_deck()
    board = rng.sample(deck, 5)
    rest = [c for c in deck if c not in board]
    combos = list(itertools.combinations(rest, 2))
    hero_w = {c: 1.0 for c in rng.sample(combos, 300)}
    vill_w = {c: 1.0 for c in rng.sample(combos, 300)}
    hero_hole = next(iter(hero_w))
    # Spot: Hero OOP checkt, Villain bettet 75% Pot, Hero muss entscheiden (call?)
    spot = RiverSpot(board, hero_w, vill_w, pot_river=2000.0, eff_stack=6000.0,
                     hero_oop=True,
                     seq=[("hero", "check", 0.0), ("vill", "bet", 1500.0),
                          ("hero", "call", 1500.0)],
                     hero_hole=hero_hole, tag="selbsttest")
    res = solve_spots([spot], iters=250)[0]
    assert res is not None, "Navigation fehlgeschlagen"
    sigsum = sum(res["sigma"])
    print(f"Spot geloest: acts={res['acts']} sigma={['%.3f' % s for s in res['sigma']]} "
          f"(Summe {sigsum:.4f}) expl={res['expl']:.2f}%Pot gespielt={res['gespielt']}")
    assert abs(sigsum - 1.0) < 1e-3, "Sigma-Summe != 1"
    print("Selbsttest OK.")


if __name__ == "__main__":
    _selbsttest()
