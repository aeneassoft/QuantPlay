"""GPU-EVAL — vektorisierter 7-Karten-Evaluator (torch/CUDA), der Kern des GPU-Bots.

Zweck: die heissen Schleifen des Bots (MC-Equity, Range-vs-Range, Flop-Runout-
Enumeration) als EINE Batch-Tensor-Op. Der Flop-Resolver brauchte 75-121s,
weil jede Evaluation einzeln durch Python/treys laeuft; auf der GPU ist
hero x 1326 Combos x 1081 Runouts EIN Kernel-Aufruf.

DESIGN
  Karten-Encoding: int64 0..51, karte = rank*4 + suit, rank 0='2' .. 12='A'.
  Eingabe: Tensor [N, 7] (long) — sieben Karten je Zeile.
  Ausgabe: Tensor [N] (long) — SCORE, groesser = besser. Kompatibel zur
  treys-ORDNUNG (nicht zu den treys-Zahlen): fuer alle Haende a, b gilt
  score(a) > score(b)  <=>  treys_rank(a) < treys_rank(b).

  Score-Aufbau: kategorie * 13^5 + k1*13^4 + k2*13^3 + k3*13^2 + k4*13 + k5
  mit kategorie 8=Straight Flush .. 0=High Card und k1..k5 den Tiebreak-
  Raengen in treys-identischer Reihenfolge.

VERIFIKATION: verify_vs_reference() prueft N Zufallshaende byte-genau gegen
pokerbot.engine.evaluator (Ordnungs-Isomorphie). Kein Einsatz im Bot, bevor
diese Pruefung nicht 100% ist — sie ist Teil der Gate-Kette.

ADDITIV: dieses Modul aendert NICHTS am bestehenden Pfad. Die CPU-Referenz
bleibt die Wahrheit; die GPU ist ein Beschleuniger mit Identitaetsbeweis.

  python -m pokerbot.engine.gpu_eval            # Verifikation + Benchmark
"""
from __future__ import annotations

import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 13^0 .. 13^5 als Gewichte fuer den Score
_P13 = [13 ** i for i in range(6)]

# Straight-Masken: fuer jede der 10 Strassen (A-hoch .. 5-hoch/Wheel) die
# 13-bit-Rangmaske; Index = Rang der HOECHSTEN Karte der Strasse.
_STRAIGHT_MASKS = []
for hi in range(12, 2, -1):                      # 12 = Ace-high .. 3 = 5-high? nein:
    pass
# sauber: Strassen enden auf hi in {12..3} fuer normale, plus Wheel (hi=3 -> A2345)
_STRAIGHTS: list[tuple[int, int]] = []           # (maske, top_rank)
for top in range(12, 3, -1):                     # 12..4: A-hoch bis 6-hoch; Wheel gesondert
    m = 0
    for r in range(top - 4, top + 1):
        m |= 1 << r
    _STRAIGHTS.append((m, top))
_WHEEL = (1 << 12) | 0b1111                      # A,2,3,4,5 -> top_rank 3 (die 5)
_STRAIGHTS.append((_WHEEL, 3))


def _highest_bit(m: torch.Tensor) -> torch.Tensor:
    """Hoechstes gesetztes Bit einer 13-bit-Maske — INTEGER-ONLY.
    Kein log2: CUDA-log2 darf 1 ulp danebenliegen und lieferte bei exakten
    Zweierpotenzen floor(2.9999...) = falschen Rang (gemessener Einzelfehler)."""
    hi = torch.zeros_like(m)
    for r in range(13):
        hi = torch.where((m >> r) & 1 == 1, torch.full_like(m, r), hi)
    return hi


def _topk_ranks(mask: torch.Tensor, k: int) -> list[torch.Tensor]:
    """Die k hoechsten gesetzten Bits einer 13-bit-Maske, als Rang-Tensoren.
    Vektorisiert ueber den Batch; k Iterationen a O(13) Tensor-Ops."""
    ranks = []
    m = mask.clone()
    for _ in range(k):
        hi = _highest_bit(m)
        ranks.append(hi)
        m = m & ~(1 << hi)
    return ranks


def score7(cards: torch.Tensor) -> torch.Tensor:
    """[N,7] long (0..51) -> [N] long Score, groesser = besser."""
    if cards.device != DEVICE:
        cards = cards.to(DEVICE)
    N = cards.shape[0]
    rank = cards // 4                                     # [N,7] 0..12
    suit = cards % 4                                      # [N,7] 0..3

    # rank_counts [N,13], suit_counts [N,4]
    one = torch.ones_like(rank)
    rank_counts = torch.zeros(N, 13, dtype=torch.long, device=DEVICE)
    rank_counts.scatter_add_(1, rank, one)
    suit_counts = torch.zeros(N, 4, dtype=torch.long, device=DEVICE)
    suit_counts.scatter_add_(1, suit, one)

    # Rang-Maske aller Karten und je Suit
    rank_bit = (1 << rank)                                # [N,7]
    mask_all = torch.zeros(N, dtype=torch.long, device=DEVICE)
    for i in range(7):
        mask_all = mask_all | rank_bit[:, i]
    # Flush-Suit (max. eine moeglich bei 7 Karten)
    flush_suit = torch.argmax(suit_counts, dim=1)         # [N]
    has_flush = suit_counts.gather(1, flush_suit.unsqueeze(1)).squeeze(1) >= 5
    suit_match = suit == flush_suit.unsqueeze(1)          # [N,7]
    mask_flush = torch.zeros(N, dtype=torch.long, device=DEVICE)
    for i in range(7):
        mask_flush = mask_flush | torch.where(suit_match[:, i], rank_bit[:, i],
                                              torch.zeros_like(mask_all))

    # Strassen (auf beliebiger Maske): liefert top_rank oder -1
    def straight_top(mask: torch.Tensor) -> torch.Tensor:
        top = torch.full_like(mask, -1)
        for m, t in _STRAIGHTS:
            hit = (mask & m) == m
            top = torch.where(hit & (top < 0), torch.full_like(top, t), top)
        return top

    st_all = straight_top(mask_all)
    st_fl = straight_top(mask_flush)

    # Vielfache
    quads_rank = torch.argmax((rank_counts == 4).long() *
                              torch.arange(1, 14, device=DEVICE), dim=1) - 0
    has_quads = (rank_counts == 4).any(dim=1)
    quads_rank = torch.where(has_quads, torch.argmax(
        (rank_counts == 4).long() * torch.arange(1, 14, device=DEVICE), dim=1),
        torch.zeros_like(quads_rank))
    trips_mask = (rank_counts == 3)
    pairs_mask = (rank_counts == 2)
    n_trips = trips_mask.sum(dim=1)
    n_pairs = pairs_mask.sum(dim=1)
    rangeidx = torch.arange(13, device=DEVICE)
    # hoechster Trip / hoechstes & zweites Paar
    trip_hi = torch.where(n_trips > 0,
                          torch.argmax(trips_mask.long() * (rangeidx + 1), dim=1),
                          torch.full((N,), -1, dtype=torch.long, device=DEVICE))
    # zweiter Trip (fuer Fullhouse Trips+Trips)
    trips_wo_hi = trips_mask.clone()
    trips_wo_hi.scatter_(1, trip_hi.clamp(min=0).unsqueeze(1), False)
    trip_2nd = torch.where(trips_wo_hi.any(dim=1),
                           torch.argmax(trips_wo_hi.long() * (rangeidx + 1), dim=1),
                           torch.full((N,), -1, dtype=torch.long, device=DEVICE))
    pair_hi = torch.where(n_pairs > 0,
                          torch.argmax(pairs_mask.long() * (rangeidx + 1), dim=1),
                          torch.full((N,), -1, dtype=torch.long, device=DEVICE))
    pairs_wo_hi = pairs_mask.clone()
    pairs_wo_hi.scatter_(1, pair_hi.clamp(min=0).unsqueeze(1), False)
    pair_2nd = torch.where(pairs_wo_hi.any(dim=1),
                           torch.argmax(pairs_wo_hi.long() * (rangeidx + 1), dim=1),
                           torch.full((N,), -1, dtype=torch.long, device=DEVICE))

    Z = torch.zeros(N, dtype=torch.long, device=DEVICE)
    score = Z.clone()
    fertig = torch.zeros(N, dtype=torch.bool, device=DEVICE)

    def setze(bedingung, kat, k1=None, k2=None, k3=None, k4=None, k5=None):
        nonlocal score, fertig
        neu = bedingung & ~fertig
        s = torch.full_like(Z, kat) * _P13[5]
        for w, k in zip((_P13[4], _P13[3], _P13[2], _P13[1], _P13[0]),
                        (k1, k2, k3, k4, k5)):
            if k is not None:
                s = s + k.clamp(min=0) * w
        score = torch.where(neu, s, score)
        fertig = fertig | neu

    # 8 Straight Flush
    setze(st_fl >= 0, 8, st_fl)
    # 7 Quads: quads_rank + bester Kicker aus Restmaske
    rest_q = mask_all & ~(1 << quads_rank.clamp(min=0))
    kick_q = _topk_ranks(rest_q, 1)[0]
    setze(has_quads, 7, quads_rank, kick_q)
    # 6 Fullhouse: Trip + (2. Trip als Paar ODER hoechstes Paar)
    fh_pair = torch.where(trip_2nd >= 0, torch.maximum(trip_2nd, pair_hi), pair_hi)
    setze((trip_hi >= 0) & (fh_pair >= 0), 6, trip_hi, fh_pair)
    # 5 Flush: Top-5 der Flush-Maske
    f5 = _topk_ranks(mask_flush, 5)
    setze(has_flush, 5, *f5)
    # 4 Straight
    setze(st_all >= 0, 4, st_all)
    # 3 Trips: trip + 2 Kicker
    rest_t = mask_all & ~(1 << trip_hi.clamp(min=0))
    kt = _topk_ranks(rest_t, 2)
    setze(trip_hi >= 0, 3, trip_hi, kt[0], kt[1])
    # 2 Two Pair: 2 Paare + 1 Kicker
    rest_2p = mask_all & ~(1 << pair_hi.clamp(min=0)) & ~(1 << pair_2nd.clamp(min=0))
    k2p = _topk_ranks(rest_2p, 1)[0]
    setze((pair_hi >= 0) & (pair_2nd >= 0), 2, pair_hi, pair_2nd, k2p)
    # 1 One Pair: Paar + 3 Kicker
    rest_1p = mask_all & ~(1 << pair_hi.clamp(min=0))
    k1p = _topk_ranks(rest_1p, 3)
    setze(pair_hi >= 0, 1, pair_hi, k1p[0], k1p[1], k1p[2])
    # 0 High Card: Top-5
    h5 = _topk_ranks(mask_all, 5)
    setze(torch.ones_like(fertig), 0, *h5)
    return score


# ---------------------------------------------------------------------------
# Bruecke zum bestehenden Encoding ('As', 'Td', ...)
# ---------------------------------------------------------------------------
_RANKS = "23456789TJQKA"
_SUITS = "shdc"                      # Zuordnung egal, solange konsistent


def encode(cards: list[str]) -> list[int]:
    return [_RANKS.index(c[0]) * 4 + _SUITS.index(c[1]) for c in cards]


def verify_vs_reference(n: int = 200_000, seed: int = 7) -> tuple[int, int]:
    """Ordnungs-Isomorphie gegen die CPU-Referenz auf n Zufalls-PAAREN.
    Rueckgabe: (geprueft, fehler)."""
    import random
    from pokerbot.engine.cards import make_deck
    from pokerbot.engine.evaluator import evaluate
    rng = random.Random(seed)
    deck = make_deck()
    a = torch.empty(n, 7, dtype=torch.long)
    b = torch.empty(n, 7, dtype=torch.long)
    ref = torch.empty(n, dtype=torch.long)     # -1: a<b(treys: a besser), 0: tie, 1: b besser
    for i in range(n):
        zieh = rng.sample(deck, 9)             # 2 hero, 2 villain, 5 board -> 2 Haende a/b
        board, ha, hb = zieh[:5], zieh[5:7], zieh[7:9]
        a[i] = torch.tensor(encode(board + ha))
        b[i] = torch.tensor(encode(board + hb))
        ra, rb = evaluate(board, ha), evaluate(board, hb)
        ref[i] = -1 if ra < rb else (0 if ra == rb else 1)
    sa, sb = score7(a), score7(b)
    got = torch.where(sa > sb, -1, torch.where(sa == sb, 0, 1)).cpu()
    fehler = int((got != ref).sum())
    return n, fehler


def benchmark(n: int = 2_000_000) -> dict:
    import time
    g = torch.Generator().manual_seed(3)
    # zufaellige 7 aus 52 je Zeile (via argsort-Trick)
    r = torch.rand(n, 52, generator=g)
    cards = r.argsort(dim=1)[:, :7].long()
    if DEVICE.type == "cuda":
        cards_gpu = cards.to(DEVICE)
        torch.cuda.synchronize()
        t0 = time.perf_counter(); score7(cards_gpu); torch.cuda.synchronize()
        t_gpu = time.perf_counter() - t0
    else:
        t_gpu = float("nan")
    return {"n": n, "gpu_s": t_gpu, "gpu_pro_s": n / t_gpu if t_gpu else 0}


if __name__ == "__main__":
    import sys, time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Device: {DEVICE}")
    print("Verifikation gegen CPU-Referenz (Ordnungs-Isomorphie) ...")
    t0 = time.perf_counter()
    n, fehler = verify_vs_reference(50_000)
    print(f"  {n:,} Paare, {fehler} Fehler  ({time.perf_counter()-t0:.1f}s)")
    if fehler:
        print("  >>> NICHT EINSATZFAEHIG — Fehler analysieren."); sys.exit(1)
    b = benchmark()
    print(f"Benchmark: {b['n']:,} Haende in {b['gpu_s']:.3f}s  = {b['gpu_pro_s']:,.0f} Haende/s")
