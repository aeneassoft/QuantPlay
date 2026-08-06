"""BOLTZMANN-TEMPERATUR-FIT (User: 'beweise das', 2026-08-05) — der QRE-Test am 683k-Korpus.

These (statistische Mechanik / Quantal Response): ein Poker-Pool ist ein thermisches Ensemble;
P(Aktion) ~ exp(lambda * EV). Skill = niedrige Temperatur (hohes lambda). Kern-Vorhersage,
falsifizierbar: eine NUR aus Entscheidungs-Frequenzen gefittete Temperatur (nie aus Ergebnissen)
sagt die echte Winrate OUT-OF-SAMPLE voraus.

Design:
  * Tages-Paritaets-Split (ungerade/gerade Kalendertage): Temperatur wird auf Haelfte A gefittet,
    Winrate auf Haelfte B gemessen — dieselben Haende beruehren sich nie.
  * Temperatur-Proxy aus zwei unabhaengigen dominierten Kanaelen (nur oeffentliche Infos):
      theta1 = logit(Open-Limps / First-in-Gelegenheiten)      [dominierte Aktion Klasse 1]
      theta2 = logit(Limp-Calls / Limps)                        [dominierte Aktion Klasse 2]
    Boltzmann-Form => log-odds ~ -lambda * dEV_klasse: EIN lambda je Spieler muss BEIDE Kanaele
    tragen -> Konsistenztest corr(theta1, theta2).
  * Kontroll-Prädiktor VPIP (plumpe Looseness) zum Vergleich.

  python -m research.boltzmann_fit
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import research.coinpoker_ecology as E
from research.gg_nl2_pop import _configure_gg, _iter_all

BB = 0.02
MIN_HANDS = 800
_DAY_RE = re.compile(r"- \d{4}/\d{2}/(\d{2}) \d{2}:")
_ACT_Q = re.compile(r"^(.+?): (folds|checks|calls|bets|raises)", re.M)


def _day_parity(hand: str) -> int | None:
    m = _DAY_RE.search(hand[:120])
    return int(m.group(1)) % 2 if m else None


def population_by_parity(parity: int) -> dict:
    """parse_population (validierter Parser) nur ueber Haende der gewuenschten Tages-Paritaet."""
    _configure_gg(eu_only=False)

    def _iter():
        for hand in _iter_all():
            if _day_parity(hand) == parity:
                yield hand

    E._iter_hands = _iter
    return E.parse_population()


def channels_by_parity(parity: int) -> dict:
    """Limp- und Limp-Call-Zaehler je Spieler (Zensus-Logik), nur Paritaet A."""
    C = defaultdict(lambda: {"first_in": 0, "limp": 0, "limp_call": 0})
    for hand in _iter_all():
        if _day_parity(hand) != parity:
            continue
        pre = hand.split("*** FLOP ***")[0]
        raises_seen = 0
        limped: set[str] = set()
        acted: set[str] = set()
        for m in _ACT_Q.finditer(pre):
            who, verb = m.group(1), m.group(2)
            if who not in acted and raises_seen == 0 and verb in ("folds", "calls", "raises"):
                C[who]["first_in"] += 1
            if verb == "calls":
                if raises_seen == 0 and who not in acted:
                    C[who]["limp"] += 1
                    limped.add(who)
                elif raises_seen >= 1 and who in limped:
                    C[who]["limp_call"] += 1
            if verb == "raises":
                raises_seen += 1
            acted.add(who)
    return C


def logit(k: int, n: int) -> float:
    p = (k + 1.0) / (n + 2.0)                  # Laplace
    return math.log(p / (1.0 - p))


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return cov / (vx * vy) if vx and vy else 0.0


def main() -> None:
    print("Parse Haelfte A (ungerade Tage) ...")
    pop_a = population_by_parity(1)
    print(f"  {pop_a['n_hands']} Haende")
    print("Parse Haelfte B (gerade Tage) ...")
    pop_b = population_by_parity(0)
    print(f"  {pop_b['n_hands']} Haende")
    print("Kanal-Zaehler auf Haelfte A ...")
    ch_a = channels_by_parity(1)

    rows = []
    for nm, sa in pop_a["players"].items():
        sb = pop_b["players"].get(nm)
        c = ch_a.get(nm)
        if not sb or not c or sa["hands"] < MIN_HANDS or sb["hands"] < MIN_HANDS:
            continue
        theta1 = logit(c["limp"], c["first_in"])
        theta2 = logit(c["limp_call"], c["limp"]) if c["limp"] >= 10 else None
        wr_b = sb["net"] / BB / sb["hands"] * 100.0
        vpip_a = sa["vpip"] / sa["hands"]
        rows.append({"nm": nm, "t1": theta1, "t2": theta2, "wr_b": wr_b, "vpip_a": vpip_a})
    print(f"Spieler mit >= {MIN_HANDS} Haenden in BEIDEN Haelften: {len(rows)}")

    t1 = [r["t1"] for r in rows]
    wr = [r["wr_b"] for r in rows]
    vp = [r["vpip_a"] for r in rows]
    print(f"T2-HAUPTTEST  Spearman(Temperatur theta1 [A], Winrate [B]) = {spearman(t1, wr):+.3f}")
    print(f"KONTROLLE     Spearman(VPIP [A],            Winrate [B]) = {spearman(vp, wr):+.3f}")
    both = [r for r in rows if r["t2"] is not None]
    if len(both) >= 20:
        print(f"T1-FORMTEST   Spearman(theta1, theta2) ueber {len(both)} Spieler = "
              f"{spearman([r['t1'] for r in both], [r['t2'] for r in both]):+.3f} "
              f"(eine Temperatur, zwei Kanaele)")
        lam = [-(r["t1"] + r["t2"]) / 2 for r in both]
        print(f"KOMBINIERT    Spearman(lambda_hat, Winrate [B]) = "
              f"{spearman(lam, [r['wr_b'] for r in both]):+.3f}  (Vorhersage: POSITIV)")
    # Kohorten-Anschauung
    rows.sort(key=lambda r: r["t1"])
    k = len(rows) // 3
    for label, grp in (("KALT (unterstes theta1-Drittel)", rows[:k]),
                      ("MITTE", rows[k:2 * k]),
                      ("HEISS (oberstes Drittel)", rows[2 * k:])):
        m = sum(r["wr_b"] for r in grp) / max(1, len(grp))
        print(f"  {label:32s}: mittlere Out-of-Sample-Winrate {m:+6.1f} bb/100 (n={len(grp)})")


if __name__ == "__main__":
    main()
