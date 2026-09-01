"""TIEFEN-REPLAY — die Nacht-2-Haende mit vielfachem Rechenbudget neu durchdacht.

User-Auftrag (2026-09-01): die echten v4-vs-GTOW-Haende nochmal 'spielen', mit
viel mehr Rechenzeit; ALLE Entscheidungen + Zwischenwerte tracken; ZWEI Fragen:
(1) Wo verlieren wir gegen GTOW und warum? (2) Wo LASSEN WIR EV LIEGEN (die nie
gestellte Umkehr-Frage)? Dazu Muster-Kategorisierung.

METHODE: Fuer jede Hero-RIVER-Entscheidung beider Arme wird das Subgame in drei
Konfigurationen geloest (RiverCFRBatch, geometrie-gebatcht):
  A) iters=600, Tracker-Ranges   — die 'viel mehr Zeit'-Referenz
  B) iters=150, Tracker-Ranges   — das Produktions-Budget (Kipp-Rate = Rauschen)
  C) iters=600, PREFLOP-Ranges   — Range-Nullhypothese (ist das Postflop-Bayes
     ueberhaupt Wert oder Schaden? Board-Blocker maskiert der Solver selbst.)
Je Entscheidung werden die AKTIONS-EVs der Hero-Combo extrahiert (action_values,
beide Seiten avg_sigma; nur EV-DIFFERENZEN sind bedeutungsvoll) und die
historisch gespielte Aktion dem naechsten Baum-Arm zugeordnet.

KATEGORIEN (auf Basis A, Schwelle INDIFF_BB):
  VERLUST_CALL   gespielt call,   best fold            -> bezahlte Fehler-Calls
  VERLUST_AGGRO  gespielt bet/raise, best passiver     -> Spew/Fehl-Value
  OVERFOLD       gespielt fold,   best call/raise      -> weggeworfenes EV
  VERPASST_VALUE gespielt passiv, best bet/raise, Hand stark (Two Pair+)
  VERPASST_BLUFF gespielt passiv, best bet/raise, Hand schwach
  SIZE           gespielt bet/raise, best ANDERER bet/raise-Arm
  OK             ev_diff < Schwelle (indifferent — kein Befund)

Ausgabe: data/runs/tiefen_replay_<ts>.jsonl (jede Entscheidung eine Zeile,
alle Werte) + aggregierter Konsolen-Report. $0, deterministisch, GPU-gebatcht.

Run: POKERB_TRACKER_ALPHA=0.5 POKERB_TRACKER_CONF_SLOPE=0.7 python -m research.tiefen_replay
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.gpu_resolver import POT_NORM, RiverSpot, solve_spots
from pokerbot.strategy.range_tracker import RangeTracker
from research.gtow_tree_census import BB, hero_seat_of, replay
from research.hh_luecken_mine import ARME, SESS, replay_voll
from research.river_bill_replay import spot_state

INDIFF_BB = 0.25            # EV-Differenzen darunter gelten als indifferent
ITERS_TIEF, ITERS_PROD = 600, 150

try:
    from treys import Evaluator as _TE
    _klasse = _TE().get_rank_class          # 1=SF .. 7=Two Pair, 8=Pair, 9=High
except Exception:  # noqa: BLE001
    _klasse = None


def _range_am_schnitt(st0: dict, schnitt_street: str | None) -> tuple[dict, dict]:
    """Tracker-Ranges mit History geschnitten: None = voller River-Beginn-Build
    (st0 kommt schon geschnitten); 'preflop' = nur Preflop-Aktionen."""
    st = st0
    if schnitt_street == "preflop":
        hist = st0.get("history", []) or []
        cut = next((i for i, h in enumerate(hist) if h.get("action") == "deal"), None)
        st = dict(st0)
        st["history"] = hist[:cut] if cut is not None else hist
    t = RangeTracker().build(st)
    return t.range.get(st0["to_act"], {}), t.range.get(1 - st0["to_act"], {})


def extrahiere(arm: str, dateien: list[str]) -> list[dict]:
    """Je Hero-River-Entscheidung ein Eintrag mit BEIDEN Range-Saetzen."""
    eintraege = []
    for name in dateien:
        for line in open(SESS / name, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            hand = json.loads(line)
            if hand.get("aivat") is None:
                continue
            _, net, folder, _ = replay(hand)
            hs = hero_seat_of(hand, net, folder)
            if hs is None:
                continue
            acts, _ = replay_voll(hand)
            riv = [(i, a) for i, a in enumerate(acts) if a["street"] == "river"]
            if not riv:
                continue
            st0 = spot_state(hand, hs, riv[0][0], acts)
            if st0 is None:
                continue
            st0["to_act"] = hs
            hero_w, vill_w = _range_am_schnitt(st0, None)
            hero_p, vill_p = _range_am_schnitt(st0, "preflop")
            if not hero_w or not vill_w:
                continue
            pot_river = st0["pot"]
            eff = min(p["stack"] for p in st0["players"])
            if eff <= 0:
                continue
            btn = st0["button"]
            hero_hole = tuple(st0["players"][hs]["hole"])
            lvl = {0: 0.0, 1: 0.0}
            seq_alle = []
            for _i, a in riv:
                s = a["seat"]
                wer = "hero" if s == hs else "vill"
                if a["kind"] in ("bet", "raise"):
                    z = a["to"] - lvl[s]
                    lvl[s] = a["to"]
                    seq_alle.append((wer, a["kind"], z))
                elif a["kind"] == "call":
                    need = max(lvl.values()) - lvl[s]
                    lvl[s] = max(lvl.values())
                    seq_alle.append((wer, "call", need))
                else:
                    seq_alle.append((wer, a["kind"], 0.0))
            for k, (wer, kind, zusatz) in enumerate(seq_alle):
                if wer != "hero":
                    continue
                kl = _klasse(evaluate(st0["board"], list(hero_hole))) if _klasse else 9
                basis = dict(board=st0["board"], pot_river=pot_river, eff=eff,
                             hero_oop=(hs != btn), seq=seq_alle[:k + 1],
                             hero_hole=hero_hole)
                eintraege.append({
                    "arm": arm, "hand": hand["hand_id"], "entsch_idx": k,
                    "gespielt": kind, "zusatz": zusatz, "pot_bb": pot_river / BB,
                    "hole": "".join(hero_hole), "board": hand.get("board", ""),
                    "handklasse": kl, "win_bb": float(hand.get("winnings") or 0) / BB,
                    "aivat_bb": hand["aivat"] / BB,
                    "n_range_tracker": len(vill_w), "n_range_preflop": len(vill_p),
                    "_basis": basis, "_ranges": (hero_w, vill_w, hero_p, vill_p),
                })
    return eintraege


def _spots(eintraege: list[dict], preflop_ranges: bool) -> list[RiverSpot]:
    out = []
    for e in eintraege:
        b = e["_basis"]
        hw, vw, hp, vp = e["_ranges"]
        h, v = (hp, vp) if preflop_ranges else (hw, vw)
        out.append(RiverSpot(b["board"], h, v, b["pot_river"], b["eff"],
                             b["hero_oop"], b["seq"], b["hero_hole"]))
    return out


def _gespielt_arm(res: dict, gespielt: str, zusatz: float, pot: float) -> int | None:
    """Index des Baum-Arms, der der historischen Aktion entspricht."""
    acts = res["acts"]
    if gespielt in ("check", "call", "fold"):
        return acts.index(gespielt) if gespielt in acts else None
    kand = [i for i, a in enumerate(acts) if a.startswith(("bet", "raise"))]
    if not kand:
        return None
    ziel = zusatz * POT_NORM / max(pot, 1e-9)
    return min(kand, key=lambda i: abs(res["zusatz_norm"][i] - ziel))


def kategorisiere(res: dict, e: dict) -> dict:
    evs = res.get("ev_je_akt")
    if not evs:
        return {"kat": "KEIN_EV"}
    acts = res["acts"]
    gi = _gespielt_arm(res, e["gespielt"], e["zusatz"], e["_basis"]["pot_river"])
    if gi is None:
        return {"kat": "UNMAPPBAR"}
    bi = max(range(len(evs)), key=lambda i: evs[i])
    # POT_NORM-Chips -> bb der echten Hand
    faktor = e["_basis"]["pot_river"] / POT_NORM / BB
    ev_diff_bb = (evs[bi] - evs[gi]) * faktor
    g, b = acts[gi], acts[bi]
    aggro = lambda a: a.startswith(("bet", "raise"))  # noqa: E731
    if ev_diff_bb < INDIFF_BB:
        kat = "OK"
    elif g == "call" and b == "fold":
        kat = "VERLUST_CALL"
    elif aggro(g) and not aggro(b):
        kat = "VERLUST_AGGRO"
    elif g == "fold" and (b == "call" or aggro(b)):
        kat = "OVERFOLD"
    elif not aggro(g) and aggro(b):
        kat = "VERPASST_VALUE" if e["handklasse"] <= 7 else "VERPASST_BLUFF"
    elif aggro(g) and aggro(b) and g != b:
        kat = "SIZE"
    else:
        kat = "SONST"
    return {"kat": kat, "gespielt_arm": g, "best_arm": b,
            "ev_diff_bb": round(ev_diff_bb, 3),
            "p_gespielt": round(res["sigma"][gi], 3),
            "p_best": round(res["sigma"][bi], 3), "expl": round(res["expl"], 2)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t0 = time.perf_counter()
    eintraege = []
    for arm, dateien in ARME.items():
        eintraege += extrahiere(arm, dateien)
    print(f"Hero-River-Entscheidungen: {len(eintraege)}  "
          f"(Extraktion {time.perf_counter()-t0:.0f}s)")

    laeufe = {}
    for name, (it, pre) in {"A_tief": (ITERS_TIEF, False),
                            "B_prod": (ITERS_PROD, False),
                            "C_preflopR": (ITERS_TIEF, True)}.items():
        t1 = time.perf_counter()
        laeufe[name] = solve_spots(_spots(eintraege, pre), iters=it, mit_evs=True)
        print(f"Lauf {name}: iters={it} preflopR={pre}  "
              f"{time.perf_counter()-t1:.0f}s")

    ts = time.strftime("%Y%m%d_%H%M%S")
    pfad = Path(f"data/runs/tiefen_replay_{ts}.jsonl")
    kat_summe: dict[tuple, list] = defaultdict(list)
    kipp_konv = kipp_range = vergleichbar_konv = vergleichbar_range = 0
    with pfad.open("w", encoding="utf-8") as f:
        for j, e in enumerate(eintraege):
            zeile = {k: v for k, v in e.items() if not k.startswith("_")}
            for name in laeufe:
                r = laeufe[name][j]
                zeile[name] = kategorisiere(r, e) if r else None
            a, b, c = zeile["A_tief"], zeile["B_prod"], zeile["C_preflopR"]
            if a and b and "best_arm" in a and "best_arm" in b:
                vergleichbar_konv += 1
                if a["best_arm"] != b["best_arm"]:
                    kipp_konv += 1
            if a and c and "best_arm" in a and "best_arm" in c:
                vergleichbar_range += 1
                if a["best_arm"] != c["best_arm"]:
                    kipp_range += 1
            if a and "kat" in a and a["kat"] not in ("OK", "KEIN_EV", "UNMAPPBAR"):
                kat_summe[(e["arm"], a["kat"])].append(
                    (a["ev_diff_bb"], e["hand"], e["hole"], zeile["board"],
                     e["pot_bb"], a["gespielt_arm"], a["best_arm"]))
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")

    print(f"\nTrackliste: {pfad}")
    print(f"\n=== KONVERGENZ-SENSITIVITAET (150 vs 600 Iter): Best-Arm kippt in "
          f"{kipp_konv}/{vergleichbar_konv} = {100*kipp_konv/max(1,vergleichbar_konv):.1f}% ===")
    print(f"=== RANGE-SENSITIVITAET (Tracker vs Preflop-Nullhypothese): Best-Arm kippt in "
          f"{kipp_range}/{vergleichbar_range} = {100*kipp_range/max(1,vergleichbar_range):.1f}% ===")

    print(f"\n=== KATEGORIEN (Lauf A: 600 Iter, Tracker-Ranges; Schwelle {INDIFF_BB}bb) ===")
    for arm in ARME:
        print(f"\n--- ARM {arm} ---")
        rangliste = sorted(((k, v) for k, v in kat_summe.items() if k[0] == arm),
                           key=lambda kv: -sum(x[0] for x in kv[1]))
        for (_, kat), rows in rangliste:
            s = sum(x[0] for x in rows)
            print(f"  {kat:15s}: n={len(rows):3d}  Summe EV-Diff {s:8.1f}bb")
            for ev, hid, hole, brd, pot, g, b in sorted(rows, key=lambda x: -x[0])[:3]:
                print(f"      #{hid} {hole} {brd} Pot {pot:.0f}bb: {g}->{b}  {ev:+.1f}bb")


if __name__ == "__main__":
    main()
