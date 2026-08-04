"""ICM — das Independent Chip Model (Malmuth-Harville), exakt per Bitmask-DP.

Turnier-Chips sind kein Geld: der $-Wert eines Stacks ist konkav (der verdoppelte Stack verdoppelt
NICHT die Auszahlung), und daraus folgt das ganze Turnier-Spiel — Risk Premium, Bubble-Faktor,
engere Call-Ranges. Dieses Modul liefert die exakten Groessen; die DOKTRIN (wann welcher Aufschlag)
lebt in tournament.py.

Malmuth-Harville: P(Spieler i wird Erster) = s_i / Σs. P(i wird Zweiter | j Erster) = s_i / (Σs − s_j),
rekursiv fuer alle Plaetze. Exakt aufsummiert ueber die Platz-Rekursion; die Bitmask-Memoisierung
macht 9-10 Spieler billig (2^n Zustaende statt n! Pfade).

Referenzen: die klassischen ICM-Rechner (poker-apprentice/icm-calculator u.a.) implementieren genau
dieses Modell; unsere Tests pruefen gegen eine unabhaengige Permutations-Enumeration.
"""
from __future__ import annotations

from functools import lru_cache

MC_THRESHOLD = 12          # ab so vielen Spielern wird die exakte Rekursion teuer -> (spaeter) MC


def icm_equities(stacks: list[float], payouts: list[float]) -> list[float]:
    """$-Equity je Spieler nach Malmuth-Harville. len(payouts) <= len(stacks); Rest zahlt 0.

    Exakt fuer kleine Felder (Bitmask-DP: 2^n Zustaende). Fuer >MC_THRESHOLD Spieler ist die
    Rekursion noch korrekt, aber teuer — Turniertische haben <=10 Sitze, das reicht exakt.
    """
    n = len(stacks)
    if n == 0:
        return []
    pay = list(payouts) + [0.0] * max(0, n - len(payouts))
    # Plaetze ueber die letzte bezahlte Position hinaus tragen 0 — die Rekursion darf dort abbrechen.
    depth_cut = min(n, len(payouts))
    full_mask = (1 << n) - 1

    @lru_cache(maxsize=None)
    def rec(mask: int) -> tuple[float, ...]:
        """Equity-Vektor fuer die noch im Rennen befindlichen Spieler (mask), beginnend beim
        Platz-Index n - popcount(mask)."""
        place = n - bin(mask).count("1")
        if mask == 0 or place >= depth_cut:
            return tuple(0.0 for _ in range(n))
        s_total = sum(stacks[i] for i in range(n) if mask & (1 << i))
        if s_total <= 0:
            # alle Rest-Stacks 0 (theoretisch): Preisgeld gleichmaessig — praktisch unerreichbar,
            # aber die Rekursion darf nie durch 0 teilen
            share = pay[place] / bin(mask).count("1")
            return tuple(share if mask & (1 << i) else 0.0 for i in range(n))
        out = [0.0] * n
        for i in range(n):
            if not mask & (1 << i):
                continue
            p_first = stacks[i] / s_total
            out[i] += p_first * pay[place]
            sub = rec(mask & ~(1 << i))
            for j in range(n):
                out[j] += p_first * sub[j]
        return tuple(out)

    rec.cache_clear()
    return list(rec(full_mask))


def icm_equities_mc(stacks: list[float], payouts: list[float], iters: int = 20_000,
                    rng=None) -> list[float]:
    """Monte-Carlo-ICM fuer GROSSE Felder (n > MC_THRESHOLD, z.B. 54-Spieler-MTT).

    Sampelt Finish-Reihenfolgen sequenziell mit P(naechster Platz) ∝ Stack — exakt die
    Harville-Annahme der DP, nur gesampelt statt aufsummiert. Fuer Turnier-Diagnosen
    (Druck-Hebel im MTT) reicht das; Entscheidungen an der FT (<=12) rechnen weiter exakt.
    """
    import random as _random
    r = rng or _random.Random(0)
    n = len(stacks)
    depth = min(n, len(payouts))
    eq = [0.0] * n
    idx = [i for i in range(n) if stacks[i] > 0]
    for _ in range(iters):
        pool = list(idx)
        weights = [stacks[i] for i in pool]
        for place in range(depth):
            if not pool:
                break
            total = sum(weights)
            x = r.random() * total
            acc = 0.0
            for j, w in enumerate(weights):
                acc += w
                if x <= acc:
                    eq[pool[j]] += payouts[place]
                    pool.pop(j)
                    weights.pop(j)
                    break
    return [e / iters for e in eq]


def icm_equity(stacks: list[float], payouts: list[float], hero: int) -> float:
    return icm_equities(stacks, payouts)[hero]


def bubble_factor(stacks: list[float], payouts: list[float], hero: int, villain: int) -> float:
    """Wie viel teurer verlorene Chips sind als gewonnene, gegen DIESEN Gegner (>= 1.0 im Turnier).

    Definition (Endgame-Poker-Strategy-Konvention): BF = |ΔEq(verlieren)| / ΔEq(gewinnen) fuer den
    Flip des effektiven Stacks gegen den Gegner. BF 1.0 = Cash-Game; 2.0 heisst: ein verlorener
    Chip kostet doppelt so viel $-Equity, wie ein gewonnener bringt -> required_equity steigt von
    50% (Flip) auf BF/(BF+1).
    """
    eff = min(stacks[hero], stacks[villain])
    if eff <= 0:
        return 1.0
    base = icm_equities(stacks, payouts)[hero]
    win_st = list(stacks)
    win_st[hero] += eff
    win_st[villain] -= eff
    lose_st = list(stacks)
    lose_st[hero] -= eff
    lose_st[villain] += eff
    gain = icm_equities(win_st, payouts)[hero] - base
    loss = base - icm_equities(lose_st, payouts)[hero]
    if gain <= 0:
        return float("inf")
    return max(1.0, loss / gain)


def icm_call_threshold(stacks: list[float], payouts: list[float], hero: int, villain: int,
                       to_call: float, pot_before: float) -> float:
    """Exakte Equity-Schwelle fuer einen ALL-IN-Call unter ICM (statt Pot-Odds).

    KONVENTION (Chip-Erhaltung, im ersten Wurf verletzt und beim Gegenlesen gefangen):
    stacks = BEHIND-Stacks im Entscheidungsmoment; pot_before = kompletter Pot INKLUSIVE des
    Gegner-Shoves und Heros bisherigem Einsatz; to_call = was Hero noch zuzahlen muss.
      folden    -> der Gegner gewinnt pot_before, Heros Stack bleibt.
      gewinnen  -> Hero zahlt to_call ein und gewinnt den Gesamtpot: netto +pot_before.
      verlieren -> Hero -to_call; der Gegner nimmt pot_before + to_call.
    threshold = (E_fold − E_lose) / (E_win − E_lose).
    """
    fold_st = list(stacks)
    fold_st[villain] += pot_before
    win_st = list(stacks)
    win_st[hero] += pot_before
    lose_st = list(stacks)
    lose_st[hero] -= to_call
    lose_st[villain] += pot_before + to_call
    e_fold = icm_equities(fold_st, payouts)[hero]
    e_win = icm_equities(win_st, payouts)[hero]
    e_lose = icm_equities(lose_st, payouts)[hero]
    if abs(e_win - e_lose) < 1e-12:
        # entarteter Fall (flache Payouts): ICM-Gradient = 0 -> die natuerliche Grenze ist Chip-EV
        return to_call / max(1e-9, pot_before + to_call)
    if e_win < e_lose:
        return 1.01                        # Call kann nie richtig sein (Payout-Sprung dominiert)
    return max(0.0, (e_fold - e_lose) / (e_win - e_lose))
