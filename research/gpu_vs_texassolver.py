"""GPU-CFR vs TexasSolver — Kreuzvalidierung auf identischem River-Spot.

Baum-Matching exakt erzwungen: eff_stack = 0.75*Pot -> bei BEIDEN Solvern
kollabieren Bet-Size und Jam zum selben einzigen Arm (OOP/IP: check oder
allin=0.75-Pot-Bet; facing: fold/call). Identische Klassen-Ranges beidseitig.

Vergleich: (1) Root-Bet-Frequenz OOP (rangegewichtet), (2) IP-Bet-Frequenz
nach Check, (3) Call-Frequenzen facing Bet, (4) per-Combo-Korrelation der
Bet-Politik. Erwartung (vorregistriert): Frequenzen +-3pp, Korrelation > 0.9
— zwei unabhaengige Solver desselben Spiels muessen auf dasselbe
Gleichgewichts-SET zeigen (per-Combo-Mixing darf abweichen, wo indifferent).

Run: python -m research.gpu_vs_texassolver
"""
from __future__ import annotations

import sys

import torch

from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gpu_cfr import RiverCFR, combo_index, range_vector
from pokerbot.strategy.ranges import combos_for_classes

BOARD = ["Qs", "7h", "2d", "Th", "3c"]      # trockener River
OOP_CLASSES = ["AA", "KK", "QQ", "TT", "77", "AQs", "AQo", "KQs", "A5s", "A4s",
               "76s", "65s", "K9s", "J9s"]
IP_CLASSES = ["AA", "KK", "QQ", "JJ", "99", "AQs", "AQo", "KJs", "QJs", "A8s",
              "A7s", "98s", "87s", "K8s"]
POT, EFF = 100.0, 75.0                       # eff = 0.75*Pot -> Ein-Arm-Kollaps


def klassen_range_str(classes: list[str]) -> str:
    return ",".join(classes)


def gewichte(classes: list[str], board) -> dict:
    return {c: 1.0 for c in combos_for_classes(classes, dead=board)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not O.available():
        print("TexasSolver-Binary fehlt — Kreuzvalidierung nicht moeglich."); sys.exit(1)

    oop_w = gewichte(OOP_CLASSES, BOARD)
    ip_w = gewichte(IP_CLASSES, BOARD)
    print(f"Ranges: OOP {len(oop_w)} Combos, IP {len(ip_w)} Combos, Board {''.join(BOARD)}")

    # --- GPU-CFR ---------------------------------------------------------
    cfr = RiverCFR(BOARD, range_vector(oop_w), range_vector(ip_w),
                   pot=POT, eff_stack=EFF, bet_sizes=(0.75,), raise_sizes=(),
                   max_raises=0)
    cfr.solve(iters=600)
    expl = cfr.exploitability()
    root = cfr.root
    sig_oop = cfr.avg_sigma(root)                       # [1326, n]
    bet_i = next(i for i, a in enumerate(root.acts) if a.startswith("bet"))
    r_oop = cfr.r[0]
    oop_bet_freq = float((sig_oop[:, bet_i] * r_oop).sum() / r_oop.sum())
    check_node = root.kids[root.acts.index("check")]
    sig_ip = cfr.avg_sigma(check_node)
    bet_j = next(i for i, a in enumerate(check_node.acts) if a.startswith("bet"))
    r_ip = cfr.r[1]
    ip_bet_freq = float((sig_ip[:, bet_j] * r_ip).sum() / r_ip.sum())
    # OOP facing IP-Bet: Call-Frequenz
    fb = check_node.kids[bet_j]
    sig_fb = cfr.avg_sigma(fb)
    call_k = fb.acts.index("call")
    oop_call_freq = float((sig_fb[:, call_k] * r_oop).sum() / r_oop.sum())
    print(f"\nGPU-CFR   (expl {expl:.3f}%Pot): OOP-Bet {oop_bet_freq:.3f}  "
          f"IP-Bet-nach-Check {ip_bet_freq:.3f}  OOP-Call-vs-Bet {oop_call_freq:.3f}")

    # --- TexasSolver -----------------------------------------------------
    bets = [
        "set_bet_sizes oop,river,bet,75", "set_bet_sizes oop,river,allin",
        "set_bet_sizes ip,river,bet,75", "set_bet_sizes ip,river,allin",
    ]
    wurzel = O.solve(BOARD, klassen_range_str(OOP_CLASSES), klassen_range_str(IP_CLASSES),
                     pot=POT, eff_stack=EFF, bets=bets, accuracy=0.1, max_iter=400,
                     threads=8, dump_rounds=3, timeout=300, tag="gpu_xval")

    def ts_freq(node: dict, combos: dict, aggro: bool) -> float:
        """Rangegewichtete Frequenz der aggressiven (bet/allin) bzw. call-Aktion."""
        z = n = 0.0
        for (c1, c2) in combos:
            s = O.strategy_for(node, c1, c2)
            if not s:
                continue
            p = sum(v for a, v in s.items()
                    if (aggro and (a.upper().startswith(("BET", "ALLIN", "RAISE"))))
                    or (not aggro and a.upper().startswith("CALL")))
            z += p; n += 1.0
        return z / max(n, 1.0)

    oop_bet_ts = ts_freq(wurzel, oop_w, aggro=True)
    # IP-Knoten nach OOP-Check + OOP-facing-bet-Knoten aus dem Dump navigieren
    def kind(node: dict, label_teil: str) -> dict | None:
        ca = node.get("childrens") or {}
        for k, v in ca.items():
            if label_teil.upper() in k.upper():
                return v
        return None

    ip_node = kind(wurzel, "CHECK")
    ip_bet_ts = ts_freq(ip_node, ip_w, aggro=True) if ip_node else float("nan")
    fb_ts = None
    if ip_node:
        for lbl in ("BET", "ALLIN"):
            fb_ts = kind(ip_node, lbl)
            if fb_ts:
                break
    oop_call_ts = ts_freq(fb_ts, oop_w, aggro=False) if fb_ts else float("nan")
    print(f"TexasSolver             : OOP-Bet {oop_bet_ts:.3f}  "
          f"IP-Bet-nach-Check {ip_bet_ts:.3f}  OOP-Call-vs-Bet {oop_call_ts:.3f}")

    # --- per-Combo-Vergleich der OOP-Root-Bet-Politik --------------------
    xs, ys = [], []
    for (c1, c2) in oop_w:
        s = O.strategy_for(wurzel, c1, c2)
        if not s:
            continue
        p_ts = sum(v for a, v in s.items() if a.upper().startswith(("BET", "ALLIN")))
        p_gpu = float(sig_oop[combo_index(c1, c2), bet_i])
        xs.append(p_ts); ys.append(p_gpu)
    if len(xs) > 5:
        x = torch.tensor(xs); y = torch.tensor(ys)
        vx, vy = x - x.mean(), y - y.mean()
        korr = float((vx * vy).sum() / (vx.norm() * vy.norm() + 1e-12))
        mad = float((x - y).abs().mean())
        print(f"\nper-Combo OOP-Bet-Politik: n={len(xs)}  Korrelation {korr:.3f}  "
              f"mittl. |Diff| {mad:.3f}")
    d1 = abs(oop_bet_freq - oop_bet_ts)
    d2 = abs(ip_bet_freq - ip_bet_ts)
    d3 = abs(oop_call_freq - oop_call_ts)
    print(f"\nFrequenz-Deltas: OOP-Bet {d1:.3f}  IP-Bet {d2:.3f}  OOP-Call {d3:.3f}")
    ok = max(d1, d2, d3) < 0.05
    print("KREUZVALIDIERUNG " + ("BESTANDEN (alle Deltas < 0.05)" if ok
                                  else "NICHT bestanden — Abweichungen analysieren"))


if __name__ == "__main__":
    main()
