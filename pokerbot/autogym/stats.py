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
    """Rohe + robuste Lage/Streuung der per-Deck-Edges, beides in bb/100."""
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
    # Winsorisierte Varianz: Raender auf die Trim-Grenzwerte geklemmt; SE des
    # getrimmten Mittels = sd_win / ((1-2g) * sqrt(n))  (Tukey/McLaughlin).
    wins = ([s[k]] * k + list(core) + [s[n - k - 1]] * k) if k > 0 else list(s)
    wmean = sum(wins) / n
    wvar = sum((e - wmean) ** 2 for e in wins) / max(1, n - 1)
    se_trim = (wvar ** 0.5) / max(1e-12, (1 - 2 * trim)) / n ** 0.5
    return {
        "n_decks": n,
        "bb100": round(mean * skala, 2), "se": round((var ** 0.5 / n ** 0.5) * skala, 2),
        "bb100_trim": round(tmean * skala, 2), "se_trim": round(se_trim * skala, 2),
        "median_bb100": round(s[n // 2] * skala, 2), "trim": trim,
    }


def verdikt(st: dict) -> str:
    """Vorregistrierte Entscheidungsregel auf der ROBUSTEN Statistik (2026-08-17):
    ANWENDEN nur bei trim - 2*se_trim > 0; VERWERFEN bei trim + 2*se_trim < -1."""
    t, se = st.get("bb100_trim", 0.0), st.get("se_trim", float("inf"))
    if t - 2 * se > 0:
        return "ANWENDEN"
    if t + 2 * se < -1.0:
        return "VERWERFEN"
    return "NEUTRAL"
