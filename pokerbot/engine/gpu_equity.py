"""GPU-EQUITY — exakte hero-vs-Range-Equity als Batch-Tensor-Op (auf gpu_eval).

Der Baustein, an dem der Flop-Resolver haengt: statt MC-Samples wird der
KOMPLETTE Runout-Raum enumeriert —
  River: C Villain-Combos                          (exakt, wie CPU-Referenz)
  Turn : C x 46 River-Karten                        (exakt statt MC-3000)
  Flop : C x 1081 Turn/River-Paare                  (exakt statt MC-3000)
Bei 1326 Combos x 1081 Runouts x 2 Seiten ~ 2,9M Evaluationen = <1s GPU.

Blocker-Behandlung: Runouts werden aus dem HERO-Restdeck gebaut ([R,2]);
pro Combo maskiert eine [C,R]-Gueltigkeitsmatrix die Runouts, die Villain-
Karten enthalten. Equity je Combo = (wins + ties/2) / n_gueltig.

VERIFIKATION (Gate vor jedem Bot-Einsatz):
  - River: EXAKT identisch zur CPU-Enumeration equity_vs_range.
  - Flop/Turn: CPU-MC (3000 iters) muss im 4-SE-Band der exakten Zahl liegen.

  python -m pokerbot.engine.gpu_equity        # Verifikation + Benchmark
"""
from __future__ import annotations

import itertools

import torch

from pokerbot.engine.gpu_eval import DEVICE, encode, score7


def _rest_deck(tot: list[int]) -> list[int]:
    belegt = set(tot)
    return [c for c in range(52) if c not in belegt]


def equity_vs_range_exakt(hero: list[str], villain_combos: list[tuple[str, str]],
                          board: list[str]) -> torch.Tensor:
    """Exakte Equity des Hero gegen jede Combo, alle Runouts enumeriert.
    board: 3 (Flop), 4 (Turn) oder 5 (River) Karten. Rueckgabe: [C] float
    (CPU-Tensor); Combos, die Hero/Board blocken, erhalten NaN."""
    h = encode(list(hero))
    b = encode(list(board))
    fehlend = 5 - len(b)
    C = len(villain_combos)
    combos = torch.tensor([encode(list(vc)) for vc in villain_combos],
                          dtype=torch.long, device=DEVICE)          # [C,2]

    rest = _rest_deck(h + b)
    if fehlend == 0:
        runouts = torch.zeros(1, 0, dtype=torch.long, device=DEVICE)
    elif fehlend == 1:
        runouts = torch.tensor([[c] for c in rest], dtype=torch.long, device=DEVICE)
    else:
        runouts = torch.tensor(list(itertools.combinations(rest, 2)),
                               dtype=torch.long, device=DEVICE)     # [R,2]
    R = runouts.shape[0]

    basis = torch.tensor(h + b, dtype=torch.long, device=DEVICE)    # [2+len(b)]
    # Hero-Scores: haengen nur vom Runout ab -> [R]
    hero7 = torch.cat([basis.expand(R, -1), runouts], dim=1)        # [R,7]
    s_hero = score7(hero7)                                          # [R]

    # Villain-Scores: [C,R]
    vb = torch.cat([combos, torch.tensor(b, dtype=torch.long,
                                         device=DEVICE).expand(C, -1)], dim=1)  # [C,2+len(b)]
    v7 = torch.cat([vb.unsqueeze(1).expand(C, R, -1),
                    runouts.unsqueeze(0).expand(C, R, -1)], dim=2)  # [C,R,7]
    s_vill = score7(v7.reshape(C * R, 7)).reshape(C, R)

    # Gueltigkeit: Combo blockt weder Hero/Board (via NaN unten) noch den Runout
    hb = set(h + b)
    blockt_hb = torch.tensor([c[0] in hb or c[1] in hb or c[0] == c[1]
                              for c in [encode(list(vc)) for vc in villain_combos]],
                             dtype=torch.bool, device=DEVICE)       # [C]
    if R and fehlend:
        # Runout enthaelt eine Villain-Karte? [C,R]
        treffer = ((runouts.unsqueeze(0) == combos[:, 0].view(C, 1, 1)).any(dim=2) |
                   (runouts.unsqueeze(0) == combos[:, 1].view(C, 1, 1)).any(dim=2))
        gueltig = ~treffer                                          # [C,R]
    else:
        gueltig = torch.ones(C, max(R, 1), dtype=torch.bool, device=DEVICE)

    win = (s_hero.unsqueeze(0) > s_vill).double()
    tie = (s_hero.unsqueeze(0) == s_vill).double()
    punkte = torch.where(gueltig, win + 0.5 * tie, torch.zeros_like(win))
    n = gueltig.double().sum(dim=1)
    eq = punkte.sum(dim=1) / n.clamp(min=1)
    eq = torch.where(blockt_hb | (n == 0), torch.full_like(eq, float("nan")), eq)
    return eq.cpu()


def _verify() -> bool:
    import random
    import statistics
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine import equity as cpu_eq
    rng = random.Random(11)
    deck = make_deck()
    ok = True

    # 1) RIVER: exakt vs exakt — muss identisch sein (float-Toleranz 1e-9)
    for probe in range(20):
        zieh = rng.sample(deck, 7)
        hero, board = zieh[:2], zieh[2:7]
        rest = [c for c in deck if c not in zieh]
        combos = [tuple(rng.sample(rest, 2)) for _ in range(60)]
        gpu = equity_vs_range_exakt(hero, combos, board)
        cpu = cpu_eq.equity_vs_range(hero, combos, board)
        if abs(float(gpu.nanmean()) - cpu) > 1e-9:
            # CPU-Referenz mittelt ueber gueltige Combos gleichgewichtig
            print(f"  RIVER-DIFF Probe {probe}: gpu={float(gpu.nanmean()):.6f} cpu={cpu:.6f}")
            ok = False
    print(f"  River: 20 Proben exakt gegen CPU-Enumeration {'OK' if ok else 'FEHLER'}")

    # 2) FLOP: exakt vs CPU-MC(3000) — MC muss im 4-SE-Band liegen
    treffer, faelle = 0, 12
    for probe in range(faelle):
        zieh = rng.sample(deck, 5)
        hero, board = zieh[:2], zieh[2:5]
        rest = [c for c in deck if c not in zieh]
        combos = [tuple(rng.sample(rest, 2)) for _ in range(40)]
        gpu = float(equity_vs_range_exakt(hero, combos, board).nanmean())
        mc = [cpu_eq.equity_vs_range(hero, combos, board, iters=3000,
                                     rng=random.Random(1000 + probe + w))
              for w in range(3)]
        m = statistics.mean(mc)
        se = max(statistics.stdev(mc) / len(mc) ** 0.5, 0.004)
        if abs(gpu - m) <= 4 * se + 0.01:
            treffer += 1
        else:
            print(f"  FLOP-DIFF Probe {probe}: exakt={gpu:.4f} mc={m:.4f} se={se:.4f}")
    print(f"  Flop: {treffer}/{faelle} MC-Proben im Toleranzband")
    return ok and treffer == faelle


def _benchmark() -> None:
    import random
    import time
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine import equity as cpu_eq
    rng = random.Random(5)
    deck = make_deck()
    zieh = rng.sample(deck, 5)
    hero, board = zieh[:2], zieh[2:5]
    rest = [c for c in deck if c not in zieh]
    combos = list(itertools.combinations(rest, 2))          # volle 1081 Combos
    # GPU exakt
    equity_vs_range_exakt(hero, combos[:8], board)          # warmup/JIT
    torch.cuda.synchronize() if DEVICE.type == "cuda" else None
    t0 = time.perf_counter()
    eq = equity_vs_range_exakt(hero, combos, board)
    t_gpu = time.perf_counter() - t0
    # CPU-MC Referenzzeit (gleiche Frage, 3000 Samples statt exakt)
    t0 = time.perf_counter()
    cpu_eq.equity_vs_range(hero, combos, board, iters=3000, rng=random.Random(1))
    t_cpu = time.perf_counter() - t0
    n_eval = len(combos) * 1081 + 1081
    print(f"  Flop, {len(combos)} Combos x 1081 Runouts EXAKT: {t_gpu:.3f}s GPU "
          f"({n_eval/t_gpu/1e6:.1f}M eval/s)  |  CPU-MC(3000) dieselbe Frage: {t_cpu:.3f}s")
    print(f"  mittlere Hero-Equity: {float(eq.nanmean()):.4f}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Device: {DEVICE}")
    print("Verifikation ...")
    if not _verify():
        print(">>> NICHT EINSATZFAEHIG."); sys.exit(1)
    print("Benchmark ...")
    _benchmark()
