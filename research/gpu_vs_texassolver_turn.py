"""TurnCFR vs TexasSolver — Kreuzvalidierung auf identischem TURN-Spot.

Baum-Matching erzwungen wie beim River-Pendant: eff_stack = 0.75*Pot ->
Turn-Bet 0.75 == Jam (ein Arm); nach Bet+Call sind die Stacks leer (Run-out);
nach check-check bleibt am River wieder genau der eine 0.75(=Jam)-Arm.
TexasSolver: bet,75 + allin auf Turn und River (kollabiert identisch).

Vergleich: OOP-Turn-Bet-Frequenz, IP-Bet-nach-Check, OOP-Call-vs-Bet +
per-Combo-Korrelation der Turn-Bet-Politik. Vorregistriert: Deltas < 0.05,
Korrelation > 0.9.

Run: python -m research.gpu_vs_texassolver_turn
"""
from __future__ import annotations

import sys
import time

import torch

from pokerbot.strategy import gto_oracle as O
from pokerbot.strategy.gpu_cfr import TurnCFR, combo_index, range_vector
from pokerbot.strategy.ranges import combos_for_classes

BOARD4 = ["Qs", "7h", "2d", "Th"]
OOP_CLASSES = ["AA", "KK", "QQ", "TT", "77", "AQs", "AQo", "KQs", "A5s", "A4s",
               "76s", "65s", "K9s", "J9s"]
IP_CLASSES = ["AA", "KK", "QQ", "JJ", "99", "AQs", "AQo", "KJs", "QJs", "A8s",
              "A7s", "98s", "87s", "K8s"]
POT, EFF = 100.0, 75.0


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not O.available():
        print("TexasSolver-Binary fehlt."); sys.exit(1)
    oop_w = {c: 1.0 for c in combos_for_classes(OOP_CLASSES, dead=BOARD4)}
    ip_w = {c: 1.0 for c in combos_for_classes(IP_CLASSES, dead=BOARD4)}
    print(f"Ranges: OOP {len(oop_w)} / IP {len(ip_w)} Combos, Turn-Board {''.join(BOARD4)}")

    t0 = time.perf_counter()
    cfr = TurnCFR(BOARD4, range_vector(oop_w), range_vector(ip_w), pot=POT,
                  eff_stack=EFF, turn_bets=(0.75,), raise_sizes=(),
                  max_raises=0, river_kw={"bet_sizes": (0.75,), "raise_sizes": (),
                                          "max_raises": 0})
    cfr.solve(iters=400)
    t_solve = time.perf_counter() - t0
    expl = cfr.exploitability()
    root = cfr.root
    sig_oop = cfr.avg_sigma(root)[0]
    bet_i = next(i for i, a in enumerate(root.acts) if a.startswith("bet"))
    r_oop, r_ip = cfr.r[0], cfr.r[1]
    oop_bet = float((sig_oop[:, bet_i] * r_oop).sum() / r_oop.sum())
    check_node = root.kids[root.acts.index("check")]
    sig_ip = cfr.avg_sigma(check_node)[0]
    bet_j = next(i for i, a in enumerate(check_node.acts) if a.startswith("bet"))
    ip_bet = float((sig_ip[:, bet_j] * r_ip).sum() / r_ip.sum())
    fb = check_node.kids[bet_j]
    sig_fb = cfr.avg_sigma(fb)[0]
    call_k = fb.acts.index("call")
    oop_call = float((sig_fb[:, call_k] * r_oop).sum() / r_oop.sum())
    print(f"\nTurnCFR ({t_solve:.0f}s, expl {expl:.3f}%Pot): OOP-Bet {oop_bet:.3f}  "
          f"IP-Bet-n-Check {ip_bet:.3f}  OOP-Call {oop_call:.3f}")

    bets = ["set_bet_sizes oop,turn,bet,75", "set_bet_sizes oop,turn,allin",
            "set_bet_sizes ip,turn,bet,75", "set_bet_sizes ip,turn,allin",
            "set_bet_sizes oop,river,bet,75", "set_bet_sizes oop,river,allin",
            "set_bet_sizes ip,river,bet,75", "set_bet_sizes ip,river,allin"]
    wurzel = O.solve(BOARD4, ",".join(OOP_CLASSES), ",".join(IP_CLASSES),
                     pot=POT, eff_stack=EFF, bets=bets, accuracy=0.1,
                     max_iter=400, threads=8, dump_rounds=3, timeout=600,
                     tag="gpu_xval_turn")

    def kind(node, teil):
        for k, v in (node.get("childrens") or {}).items():
            if teil.upper() in k.upper():
                return v
        return None

    def ts_freq(node, combos, aggro):
        z = n = 0.0
        for (c1, c2) in combos:
            s = O.strategy_for(node, c1, c2)
            if not s:
                continue
            p = sum(v for a, v in s.items()
                    if (aggro and a.upper().startswith(("BET", "ALLIN", "RAISE")))
                    or (not aggro and a.upper().startswith("CALL")))
            z += p; n += 1.0
        return z / max(n, 1.0)

    oop_bet_ts = ts_freq(wurzel, oop_w, True)
    ipn = kind(wurzel, "CHECK")
    ip_bet_ts = ts_freq(ipn, ip_w, True) if ipn else float("nan")
    fbn = kind(ipn, "BET") or kind(ipn, "ALLIN") if ipn else None
    oop_call_ts = ts_freq(fbn, oop_w, False) if fbn else float("nan")
    print(f"TexasSolver             : OOP-Bet {oop_bet_ts:.3f}  "
          f"IP-Bet-n-Check {ip_bet_ts:.3f}  OOP-Call {oop_call_ts:.3f}")

    xs, ys = [], []
    for (c1, c2) in oop_w:
        s = O.strategy_for(wurzel, c1, c2)
        if not s:
            continue
        xs.append(sum(v for a, v in s.items() if a.upper().startswith(("BET", "ALLIN"))))
        ys.append(float(sig_oop[combo_index(c1, c2), bet_i]))
    x, y = torch.tensor(xs), torch.tensor(ys)
    vx, vy = x - x.mean(), y - y.mean()
    korr = float((vx * vy).sum() / (vx.norm() * vy.norm() + 1e-12))
    print(f"per-Combo Turn-Bet: n={len(xs)}  Korrelation {korr:.3f}  "
          f"mittl.|Diff| {float((x - y).abs().mean()):.3f}")
    ds = [abs(oop_bet - oop_bet_ts), abs(ip_bet - ip_bet_ts), abs(oop_call - oop_call_ts)]
    print(f"Frequenz-Deltas: {ds[0]:.3f} / {ds[1]:.3f} / {ds[2]:.3f}")
    print("TURN-KREUZVALIDIERUNG " + ("BESTANDEN" if max(ds) < 0.05 and korr > 0.9
                                       else "NICHT bestanden — analysieren"))


if __name__ == "__main__":
    main()
