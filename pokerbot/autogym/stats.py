"""Robuste Statistik fuer gepaarte Deck-Edges (Fat-Tail-Befund 2026-08-17).

Die per-Deck-Edges sind FETTRANDIG (3-sigma-Heterogenitaet identischer Laeufe
gemessen) -> die klassische 2SE-Entscheidung ist zu optimistisch. Vorregistrierte
Loesung (STATE-Schritt 1): getrimmter Mittelwert (Tukey/McLaughlin) mit
winsorisierter SE als ENTSCHEIDUNGS-Statistik; die rohen Werte bleiben im
Ergebnis (Vergleichbarkeit mit allen Alt-Laeufen).

Skalierung wie duplicate_ab: edge = Chips ueber die 2 gespiegelten Haende eines
Decks -> bb/100 = mean / 2 / bb * 100.
"""
from __future__ import annotations

TRIM = 0.05          # Anteil je Rand, der fuer den getrimmten Mittelwert faellt


def robust_stats(edges: list, bb: int = 100, trim: float = TRIM) -> dict:
    """Rohe + robuste Lage/Streuung der per-Deck-Edges, beides in bb/100.

    ESTIMATOR v2 (2026-08-17 abend, vorregistriert VOR der Replikations-Runde,
    Journal R5): die Runde-5-Messung zeigte, dass Guard-Kanaele DUENN sind
    (turn_wert 8,4% / raise_narrow 1% divergente Decks) — die 5%-Trimmung
    entfernt dann exakt die Signal-Decks (trim=0,0 bei raw +1,64). Seit dem
    Seeding-Fix ist die Lauf-Heterogenitaet (der urspruengliche Trim-Grund)
    beseitigt (A/A exakt 0). Entscheidung daher auf dem ROHEN Mittel +- 2*SE;
    dazu SPARSE-Diagnostik: nonzero-Anteil, VORZEICHEN-Test auf den
    divergenten Decks (tail-robust; nicht EV-gewichtet -> stuetzt, ersetzt
    nie das Chips-Mittel), nz-Median. Trim bleibt als Diagnose-Feld."""
    n = len(edges)
    if n == 0:
        return {"n_decks": 0}
    skala = 1.0 / 2.0 / bb * 100.0
    mean = sum(edges) / n
    var = sum((e - mean) ** 2 for e in edges) / max(1, n - 1)
    s = sorted(edges)
    k = int(trim * n)
    core = s[k:n - k] if n - 2 * k > 0 else s
    tmean = sum(core) / len(core)
    nz = [e for e in edges if e != 0]
    nz_pos = sum(1 for e in nz if e > 0)
    if nz:
        sn = sorted(nz)
        nz_median = sn[len(sn) // 2]
        # Vorzeichen-z: (pos - n/2) / sqrt(n/4) auf den divergenten Decks.
        z = (nz_pos - len(nz) / 2) / max(1e-9, (len(nz) / 4) ** 0.5)
    else:
        nz_median, z = 0, 0.0
    return {
        "n_decks": n,
        "bb100": round(mean * skala, 2), "se": round((var ** 0.5 / n ** 0.5) * skala, 2),
        "bb100_trim": round(tmean * skala, 2),
        "median_bb100": round(s[n // 2] * skala, 2), "trim": trim,
        "nonzero": len(nz), "nonzero_anteil": round(len(nz) / n, 4),
        "nz_pos": nz_pos, "vorzeichen_z": round(z, 2),
        "nz_median_chips": nz_median,
    }


def verdikt(st: dict) -> str:
    """Vorregistrierte Entscheidungsregel v2 (2026-08-17 abend): das rohe Mittel
    traegt das Verdikt (ANWENDEN bei bb100 - 2*se > 0; VERWERFEN bei
    bb100 + 2*se < -1); der Vorzeichen-Test ist Stuetz-Evidenz im Journal."""
    t, se = st.get("bb100", 0.0), st.get("se", float("inf"))
    if t - 2 * se > 0:
        return "ANWENDEN"
    if t + 2 * se < -1.0:
        return "VERWERFEN"
    return "NEUTRAL"
