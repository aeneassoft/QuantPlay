"""ICM-Tests: die exakte Rekursion gegen eine UNABHAENGIGE Permutations-Enumeration + Invarianten.

Der Pruefer ist bewusst ein ANDERER Algorithmus (naive Enumeration aller Platzierungs-Pfade) —
stimmen beide ueberein, ist ein gemeinsamer Denkfehler nahezu ausgeschlossen (Malmuth-Harville
ist einfach genug, dass zwei Implementierungen nur ueber die Formel selbst korrelieren).
"""
from itertools import permutations

from pokerbot.strategy.icm import bubble_factor, icm_call_threshold, icm_equities


def naive_icm(stacks, payouts):
    n = len(stacks)
    eq = [0.0] * n
    for perm in permutations(range(n)):
        p = 1.0
        rem = list(range(n))
        total = sum(stacks)
        s = dict(enumerate(stacks))
        t = total
        for i in perm:
            p *= s[i] / t
            t -= s[i]
        for place, i in enumerate(perm):
            if place < len(payouts):
                eq[i] += p * payouts[place]
    return eq


def close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def run():
    # 1) Zwei Spieler: geschlossene Form P(1.) = s/T
    st, pay = [7000.0, 3000.0], [60.0, 40.0]
    got = icm_equities(st, pay)
    want = [0.7 * 60 + 0.3 * 40, 0.3 * 60 + 0.7 * 40]
    assert close(got, want), (got, want)

    # 2) Drei + fuenf Spieler gegen die unabhaengige Enumeration
    for st, pay in ([[50.0, 30.0, 20.0], [50.0, 30.0, 20.0]],
                    [[40.0, 25.0, 20.0, 10.0, 5.0], [45.0, 27.0, 18.0, 10.0]],
                    [[9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0], [50.0, 30.0, 20.0]]):
        got = icm_equities(st, pay)
        want = naive_icm(st, pay)
        assert close(got, want, 1e-7), (st, got, want)

    # 3) Invarianten: Summe = ausgezahltes Geld; Gleichstand = Gleichteilung; Monotonie
    st, pay = [30.0, 30.0, 30.0], [50.0, 30.0, 20.0]
    got = icm_equities(st, pay)
    assert abs(sum(got) - 100.0) < 1e-9
    assert max(got) - min(got) < 1e-9
    a = icm_equities([50.0, 30.0, 20.0], pay)
    assert a[0] > a[1] > a[2]
    assert a[0] < 50.0 - 1e-12          # Konkavitaet: der Chipleader ist WENIGER wert als sein Chip-Anteil
    assert a[2] > 20.0 + 1e-12          # ... und der Shortstack MEHR (der ICM-Kern in einer Zeile)

    # 4) Bubble: 4 Spieler, 3 bezahlt — gegen den Gleich-Stack ist das Risiko am hoechsten
    st, pay = [40.0, 30.0, 20.0, 10.0], [50.0, 30.0, 20.0]
    bf_equal = bubble_factor(st, pay, 1, 0)      # 30 vs 40 (voll gedeckt)
    bf_short = bubble_factor(st, pay, 1, 3)      # 30 vs 10
    assert bf_equal > bf_short > 1.0, (bf_equal, bf_short)

    # 5) Call-Schwelle: im Cash-Aequivalent (alle gleich bezahlt = keine Konkavitaet) -> Pot-Odds
    st = [100.0, 100.0]
    flat = [50.0, 50.0]                          # Payout unabhaengig vom Platz -> Chips wertlos
    thr = icm_call_threshold(st, flat, 0, 1, to_call=50.0, pot_before=100.0)
    # flache Payouts: ICM-Gradient 0 -> natuerliche Grenze = Chip-Pot-Odds
    assert abs(thr - 50.0 / 150.0) < 1e-9, thr
    winner_take_all = [100.0, 0.0]
    thr2 = icm_call_threshold([100.0, 100.0], winner_take_all, 0, 1, to_call=50.0, pot_before=100.0)
    # Winner-take-all = lineares Chip-EV -> Schwelle == Pot-Odds = 50/(100+50)
    assert abs(thr2 - 50.0 / 150.0) < 1e-9, thr2
    # Bubble-Fall: 3 Spieler, 2 bezahlt, Hero mittel vs Chipleader -> Schwelle KLAR ueber Pot-Odds
    st3, pay3 = [50.0, 100.0, 20.0], [60.0, 40.0]
    thr3 = icm_call_threshold(st3, pay3, 0, 1, to_call=50.0, pot_before=60.0)
    assert thr3 > 50.0 / 110.0 + 0.05, thr3
    print("ICM: alle Tests bestanden")
    print(f"  Beispiel 50/30/20 -> {[round(x,2) for x in a]} (Chip-Anteile 50/30/20)")
    print(f"  Bubble-Faktor 30v40: {bf_equal:.2f} | 30v10: {bf_short:.2f}")
    print(f"  Call-Schwelle Bubble: {thr3*100:.1f}% (Pot-Odds waeren {50/110*100:.1f}%)")


if __name__ == "__main__":
    run()
