"""G4-AUSWERTUNG — Holdout-Pruefstand (Karte docs/plans/V10_BUILD_CARD.md K3/G4) aus den Pruefstand-Reports.

Liest die JSON-Reports von research/river_br_pruefstand.py (Hauptlauf Villain 'tracker' + Sensitivitaet Villain
'preflop', optional den A/A-Kontrolllauf) und schreibt data/runs/v10/G4_holdout.{json,md}.

Kennzahlen je Root: Delta E_H = w(A) - w(B) [bb], Delta R = R(A) - R(B) [bb]. bb/100 = Mittel je Root x 100 x
Auswahlgewicht (Roots >= 1500 Chips / alle Haende des Splits; Nenner je Quellhand, Karte K3).
Einseitige 95 %-Obergrenze per BOOTSTRAP ueber Roots (>= 2000 Resamples, Perzentil-Methode, geseedet) — zusaetzlich
die t-Obergrenze des Pruefstands zum Vergleich.

STATUS-REGEL (VOR der Auswertung festgelegt, Auftrag Gate-Laeufer G4 2026-09-07):
  * Kriterium (Karte): OG(Delta E_H) <= +0,5 UND OG(Delta R) <= +0,5 bb/100 UND mindestens eine OG < 0.
  * n_bewertet >= 20 und Kriterium erfuellt        -> BESTANDEN
  * n_bewertet <  20                                -> UNVOLLSTAENDIG (auch wenn das Kriterium erfuellt ist), ABER:
    liegt bereits der PUNKTSCHAETZER einer Kennzahl ueber +0,5 bb/100 oder ist keine der beiden PUNKTSCHAETZUNGEN
    negativ, wird zusaetzlich 'kriterium_punkt_verfehlt' ausgewiesen (kein Nachjustieren, keine Beschoenigung).
  * n_bewertet >= 20 und Kriterium verfehlt         -> VERFEHLT
Tail-Faelle: Roots mit |Delta E_H| > 20 bb oder |Delta R| > 20 bb werden separat gelistet.

Run:
    python -m research.g4_auswertung --haupt data/runs/v10/G4_pruefstand_holdout_tracker.json \
        --sens data/runs/v10/G4_pruefstand_holdout_preflop.json --aa data/runs/v10/G4_kontrolle_identisch.json
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

AUSGABE = Path("data/runs/v10")
BOOT_N = 4000
BOOT_SEED = 20260907
GATE_OG = 0.5                 # bb/100, Karte K3 Kandidaten-Gate
MIN_ROOTS_VOLL = 20           # Auftrag: unter 20 Roots UNVOLLSTAENDIG
TAIL_BB = 20.0                # Auftrag: |Delta| > 20 bb je Root separat


def lade(pfad: str | None) -> dict | None:
    if not pfad:
        return None
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def bootstrap_og(x: list[float], faktor: float, n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Einseitige 95 %-Obergrenze des Mittels (x faktor -> bb/100) per Perzentil-Bootstrap ueber Roots."""
    n = len(x)
    if n == 0:
        return {"n": 0}
    rng = random.Random(seed)
    mittel = sum(x) / n
    boots = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += x[rng.randrange(n)]
        boots.append(s / n)
    boots.sort()
    q95 = boots[min(n_boot - 1, int(0.95 * n_boot))]
    q05 = boots[int(0.05 * n_boot)]
    var = sum((v - mittel) ** 2 for v in x) / max(1, n - 1)
    se = (var / n) ** 0.5
    return {"n": n, "mittel_bb_je_root": mittel, "se_bb_je_root": se,
            "bb100": mittel * faktor, "se_bb100": se * faktor,
            "boot_og95_bb100": q95 * faktor, "boot_ug95_bb100": q05 * faktor,
            "boot_resamples": n_boot, "boot_seed": seed}


def werte_report(rep: dict, label: str) -> dict:
    agg, roots = rep["aggregat"], rep["roots"]
    ok = [r for r in roots if r["status"] == "ok"]
    faktor = 100.0 * agg["auswahlgewicht"]
    de = [r["delta_e_h_bb"] for r in ok]
    dr = [r["delta_regret_bb"] for r in ok]
    out = {"label": label, "konfig": rep["konfig"], "n_bewertet": len(ok),
           "n_unsupported": agg["n_unsupported"], "unsupported_gruende": agg.get("unsupported_gruende", []),
           "n_haende": agg["n_haende"], "n_roots_ge_schwelle": agg["n_roots_ge_schwelle"],
           "auswahlgewicht": agg["auswahlgewicht"], "abgebrochen": agg.get("abgebrochen"),
           "sekunden_gesamt": agg.get("sekunden_gesamt"), "oracle_statistik": agg.get("oracle_statistik"),
           "delta_e_h": bootstrap_og(de, faktor), "delta_regret": bootstrap_og(dr, faktor, seed=BOOT_SEED + 1),
           # VORZEICHEN (Befund G4): der Pruefstand definiert delta_e_h = w(A) - w(B) = E_H(B) - E_H(A) (B-NACHTEIL
           # als Verlustdifferenz: negativ = B besser), aber delta_regret = R(A) - R(B) (positiv = B besser). 'Delta R
           # analog' (Karte/Auftrag) im Sinne des Gates = B-Nachteil = R(B) - R(A). Beide Lesarten werden ausgewiesen.
           "delta_regret_nachteil_b": bootstrap_og([-v for v in dr], faktor, seed=BOOT_SEED + 1),
           "t_og95_delta_e_h_bb100": agg.get("delta_e_h_obergrenze95_bb100"),
           "t_og95_delta_regret_bb100": agg.get("delta_regret_obergrenze95_bb100"),
           "t_quantil": agg.get("quantil_art"),
           "w_a_mittel_bb": agg["w_a_bb"]["mittel_bb_je_root"], "w_b_mittel_bb": agg["w_b_bb"]["mittel_bb_je_root"],
           "regret_a_mittel_bb": agg["regret_a_bb"]["mittel_bb_je_root"],
           "regret_b_mittel_bb": agg["regret_b_bb"]["mittel_bb_je_root"],
           "zusatz_arme_gesamt": agg.get("zusatz_arme_gesamt"), "roots_mit_zusatzarmen": agg.get("roots_mit_zusatzarmen"),
           "max_abw_w_b_eval_vs_k2_bb": agg.get("max_abw_w_b_eval_vs_k2_bb"),
           "tail_faelle": [{"hand_id": r["hand_id"], "delta_e_h_bb": r["delta_e_h_bb"], "delta_regret_bb": r["delta_regret_bb"],
                            "pot_river_bb": r["pot_river_bb"], "hero_oop": r["hero_oop"]}
                           for r in ok if abs(r["delta_e_h_bb"]) > TAIL_BB or abs(r["delta_regret_bb"]) > TAIL_BB],
           "roots": [{k: r.get(k) for k in ("hand_id", "pot_river_bb", "eff_bb", "hero_oop", "n_hero_range", "hero_range",
                                            "w_a_bb", "w_b_bb", "delta_e_h_bb", "L_bb", "U_bb", "regret_a_bb",
                                            "regret_b_bb", "delta_regret_bb", "expl_b_pct_pot", "n_zusatz_arme",
                                            "sekunden", "status", "grund")} for r in roots]}
    return out


def _kriterium(og_e, og_r, pt_e, pt_r) -> dict:
    krit = og_e <= GATE_OG and og_r <= GATE_OG and (og_e < 0 or og_r < 0)
    punkt_verfehlt = (pt_e > GATE_OG or pt_r > GATE_OG) or not (pt_e < 0 or pt_r < 0)
    return {"og95_delta_e_h_bb100": og_e, "og95_delta_regret_bb100": og_r, "punkt_delta_e_h_bb100": pt_e,
            "punkt_delta_regret_bb100": pt_r, "kriterium_obergrenzen_erfuellt": krit, "kriterium_punkt_verfehlt": punkt_verfehlt}


def status_regel(h: dict) -> tuple[str, dict]:
    """Primaere Lesart = B-NACHTEIL fuer beide Kennzahlen (Delta E_H = E_H(B)-E_H(A) = w(A)-w(B) wie der Pruefstand;
    Delta R = R(B)-R(A)); die woertliche Pruefstand-Lesart (delta_regret = R(A)-R(B)) wird daneben ausgewiesen."""
    n = h["n_bewertet"]
    if n == 0 or h["delta_e_h"].get("boot_og95_bb100") is None:
        return "UNVOLLSTAENDIG", {"grund": "keine bewerteten Roots"}
    e, rB, rTool = h["delta_e_h"], h["delta_regret_nachteil_b"], h["delta_regret"]
    prim = _kriterium(e["boot_og95_bb100"], rB["boot_og95_bb100"], e["bb100"], rB["bb100"])
    woertlich = _kriterium(e["boot_og95_bb100"], rTool["boot_og95_bb100"], e["bb100"], rTool["bb100"])
    krit = prim["kriterium_obergrenzen_erfuellt"]
    detail = {"lesart_primaer": "B-Nachteil: dE_H = w(A)-w(B), dR = R(B)-R(A)", **prim,
              "lesart_woertlich_pruefstand": {"dR = R(A)-R(B)": woertlich},
              "n_bewertet": n, "n_min_voll": MIN_ROOTS_VOLL}
    if n < MIN_ROOTS_VOLL:
        return "UNVOLLSTAENDIG", detail
    return ("BESTANDEN" if krit else "VERFEHLT"), detail


def kosten(h: dict) -> dict:
    ok_s = [r["sekunden"] for r in h["roots"] if r.get("sekunden") is not None]
    n = len(ok_s)
    if n == 0:
        return {}
    mittel = sum(ok_s) / n
    voll = h["n_roots_ge_schwelle"]
    return {"sekunden_je_root_mittel": mittel, "sekunden_je_root_max": max(ok_s), "n_roots_gemessen": n,
            "roots_holdout_gesamt": voll, "hochrechnung_voller_holdout_h": mittel * voll / 3600.0,
            "hochrechnung_rest_h": mittel * max(0, voll - n) / 3600.0,
            "hinweis": "kalt (Oracle-Cache leer); die ersten Roots der Datei sind nicht notwendig repraesentativ"}


def md_zeilen(res: dict) -> list[str]:
    h, s, aa = res["haupt"], res.get("sensitivitaet"), res.get("kontrolle_aa")
    z = [f"# G4 — Holdout-Pruefstand (K3) — {res['status']}", "",
         f"Erzeugt {res['erzeugt']}. Karte: docs/plans/V10_BUILD_CARD.md K3/G4. Status-Regel: siehe research/g4_auswertung.py Docstring.", "",
         "## Kennzahlen (Hauptlauf, Villain = Tracker)", "",
         f"- Roots bewertet: **{h['n_bewertet']}** (UNSUPPORTED {h['n_unsupported']}); Nenner {h['n_roots_ge_schwelle']} Roots >= 1500 von "
         f"{h['n_haende']} Holdout-Haenden -> Auswahlgewicht {h['auswahlgewicht']:.4f}",
         f"- Delta E_H = w(A) - w(B): {h['delta_e_h']['mittel_bb_je_root']:+.3f} +- {h['delta_e_h']['se_bb_je_root']:.3f} bb/Root = "
         f"**{h['delta_e_h']['bb100']:+.3f} +- {h['delta_e_h']['se_bb100']:.3f} bb/100**; Bootstrap-OG95 **{h['delta_e_h']['boot_og95_bb100']:+.3f}** "
         f"(t-OG95 {h['t_og95_delta_e_h_bb100']:+.3f}, {h['t_quantil']})",
         f"- Delta R (Pruefstand-Konvention R(A) - R(B)): {h['delta_regret']['mittel_bb_je_root']:+.3f} +- {h['delta_regret']['se_bb_je_root']:.3f} bb/Root = "
         f"**{h['delta_regret']['bb100']:+.3f} +- {h['delta_regret']['se_bb100']:.3f} bb/100**; Bootstrap-OG95 **{h['delta_regret']['boot_og95_bb100']:+.3f}** "
         f"(t-OG95 {h['t_og95_delta_regret_bb100']:+.3f})",
         f"- Delta R als B-NACHTEIL (R(B) - R(A), analog zu dE_H = E_H(B)-E_H(A)): **{h['delta_regret_nachteil_b']['bb100']:+.3f} +- "
         f"{h['delta_regret_nachteil_b']['se_bb100']:.3f} bb/100**; Bootstrap-OG95 **{h['delta_regret_nachteil_b']['boot_og95_bb100']:+.3f}**",
         f"- w(A) Mittel {h['w_a_mittel_bb']:+.3f} bb, w(B) {h['w_b_mittel_bb']:+.3f} bb; R(A) {h['regret_a_mittel_bb']:.3f}, R(B) {h['regret_b_mittel_bb']:.3f} bb",
         f"- Zusatzarme (Schliessung): {h['zusatz_arme_gesamt']} in {h['roots_mit_zusatzarmen']} Roots; Selbstkontrolle max|w_B(eval)-w_B(K2)| = {h['max_abw_w_b_eval_vs_k2_bb']:.2e} bb",
         f"- Tail-Faelle (|Delta| > {TAIL_BB:.0f} bb): {len(h['tail_faelle'])} -> {h['tail_faelle']}",
         f"- Abbruch: {h['abgebrochen']}; Laufzeit {h['sekunden_gesamt']} s; Oracle-Statistik {h['oracle_statistik']}",
         "", f"**Gate-Kriterium:** OG(dE_H) <= +0,5 UND OG(dR) <= +0,5 UND eine < 0 -> {res['status_detail']}", ""]
    if s:
        z += ["## Sensitivitaet (Villain = Preflop-Nullhypothese, gleiche Roots)", "",
              f"- Roots {s['n_bewertet']} (UNSUPPORTED {s['n_unsupported']}); Delta E_H {s['delta_e_h']['bb100']:+.3f} +- {s['delta_e_h']['se_bb100']:.3f} bb/100, "
              f"OG95 {s['delta_e_h']['boot_og95_bb100']:+.3f}; Delta R (R(A)-R(B)) {s['delta_regret']['bb100']:+.3f} +- {s['delta_regret']['se_bb100']:.3f}, OG95 {s['delta_regret']['boot_og95_bb100']:+.3f}; "
              f"B-Nachteil (R(B)-R(A)) {s['delta_regret_nachteil_b']['bb100']:+.3f}, OG95 {s['delta_regret_nachteil_b']['boot_og95_bb100']:+.3f}",
              f"- Oracle-Statistik (Cache-Treffer erwartet: Arm A haengt nicht von der Villain-Familie ab): {s['oracle_statistik']}",
              f"- Tail-Faelle: {s['tail_faelle']}", ""]
    if aa:
        z += ["## Kontrolle A/A (Arm A == Arm B, Solve-Pfad)", "",
              f"- Roots {aa['n_bewertet']}: Delta E_H {aa['delta_e_h']['mittel_bb_je_root']:.3e} bb, Delta R {aa['delta_regret']['mittel_bb_je_root']:.3e} bb (exakt 0 erwartet)", ""]
    k = res.get("kosten") or {}
    if k:
        z += ["## Kosten / Power", "",
              f"- {k['sekunden_je_root_mittel']:.0f} s je Root im Mittel (max {k['sekunden_je_root_max']:.0f} s), kalt; voller Holdout "
              f"({k['roots_holdout_gesamt']} Roots) hochgerechnet **{k['hochrechnung_voller_holdout_h']:.1f} h**, Rest ab hier {k['hochrechnung_rest_h']:.1f} h (Cache setzt fort)",
              f"- Power: n = {h['n_bewertet']} Roots; SE(Delta E_H) {h['delta_e_h']['se_bb100']:.3f} bb/100, SE(Delta R) {h['delta_regret']['se_bb100']:.3f} bb/100 (Nenner alle Haende)", ""]
    z += ["## Roots (Hauptlauf)", "",
          "| hand_id | pot bb | eff bb | OOP | Range | n | w_A | w_B | dE_H | [L,U] | R_A | R_B | dR | +Arme | s | Status |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in h["roots"]:
        if r["status"] == "ok":
            z.append(f"| {r['hand_id']} | {r['pot_river_bb']:.1f} | {r['eff_bb']:.0f} | {int(r['hero_oop'])} | {r['hero_range']} | {r['n_hero_range']} | "
                     f"{r['w_a_bb']:+.2f} | {r['w_b_bb']:+.2f} | {r['delta_e_h_bb']:+.3f} | [{r['L_bb']:+.2f},{r['U_bb']:+.2f}] | "
                     f"{r['regret_a_bb']:.3f} | {r['regret_b_bb']:.3f} | {r['delta_regret_bb']:+.3f} | {r['n_zusatz_arme']} | {r['sekunden']} | ok |")
        else:
            z.append(f"| {r['hand_id']} | {r['pot_river_bb']:.1f} | {r['eff_bb']:.0f} | {int(r['hero_oop'])} | | | | | | | | | | | {r.get('sekunden')} | UNSUPPORTED: {str(r.get('grund'))[:70]} |")
    return z


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--haupt", required=True)
    ap.add_argument("--sens", default=None)
    ap.add_argument("--aa", default=None)
    ap.add_argument("--name", default="G4_holdout")
    ap.add_argument("--notizen", default="", help="Freitext (Kanal-Kennzeichnung, Reduktionen) fuer den Report")
    args = ap.parse_args()
    haupt = werte_report(lade(args.haupt), "haupt_tracker")
    status, detail = status_regel(haupt)
    res = {"gate": "G4 Holdout-Pruefstand (K3)", "status": status, "status_detail": detail,
           "erzeugt": time.strftime("%Y-%m-%d %H:%M:%S"), "notizen": args.notizen,
           "quellen": {"haupt": args.haupt, "sens": args.sens, "aa": args.aa}, "haupt": haupt, "kosten": kosten(haupt)}
    if args.sens:
        res["sensitivitaet"] = werte_report(lade(args.sens), "sens_preflop")
    if args.aa:
        res["kontrolle_aa"] = werte_report(lade(args.aa), "kontrolle_identisch")
    AUSGABE.mkdir(parents=True, exist_ok=True)
    pj, pm = AUSGABE / f"{args.name}.json", AUSGABE / f"{args.name}.md"
    pj.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    zeilen = md_zeilen(res)
    if args.notizen:
        zeilen[2:2] = ["", f"Notizen: {args.notizen}"]
    pm.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, **detail}, indent=1))
    print(f"-> {pj}\n-> {pm}")


if __name__ == "__main__":
    main()
