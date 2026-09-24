"""GATE G3 -- K1-Orakel-Abnahme, stratifizierter Lauf (Gate-Laeufer, 2026-09-07). Karte docs/plans/V10_BUILD_CARD.md K1:
mittlere TV <= 0,02, p95 <= 0,05, max <= 0,10; >= 64 Vorgeschichten, jede Guard-Klasse >= 16x.

Nutzt AUSSCHLIESSLICH die Bausteine von research/k1_oracle.py (Phase 1 Spielen, Orakel-Pakete, Auswertung) und
aendert keinen Strategie-Code. Neu ist nur die STICHPROBEN-ZIEHUNG: die Karte verlangt jede Guard-Klasse >= 16x,
die natuerliche Rate (Zensus data/runs/v10/g3_census_20260907_221523.json: turn_wert 32 / sel_m15 45 /
button_disziplin 16 in 300 Vorgeschichten) braeuchte dafuer ~300 Vorgeschichten (Orakel-Hochrechnung ~3 h) --
deshalb: die ersten `--je-klasse` Vorgeschichten (Deck-Reihenfolge) jeder Guard-Klasse + Auffuellen mit
'keine' auf `--n`. Das Gesamt-Mittel ist damit ein STRATIFIZIERTES Mittel (Guard-Klassen ueberrepraesentiert),
die Klassen-Kennzahlen sind unverzerrt je Klasse. Zeitbudget (--zeitbudget-s) fuer die Orakel-Phase: bei
Ueberschreitung wird der Pool beendet und NUR ueber vollstaendig gerechnete Vorgeschichten ausgewertet
(Reduktion im Report ausgewiesen, nie stillschweigend).

  python -u -m research.g3_k1_gate --zensus-n 300 --n 64 --je-klasse 16 --seeds 12 --workers 8
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

REPORT_DIR = Path("data/runs/v10")
WORKER_S_JE_PAKET_SEED = 0.8   # Pilot S=64 w12: 1123,7 s * 12 / (262 Pakete * 64 Seeds) = 0,80 (k1_oracle_20260907_190257.json)


def waehle(vgs: list[dict], n: int, je_klasse: int, klassen: tuple[str, ...]) -> tuple[list[int], dict]:
    """Erste `je_klasse` Vorgeschichten jeder Guard-Klasse (Deck-Reihenfolge), Union, dann 'keine' auffuellen."""
    gewaehlt: list[int] = []
    je: dict[str, list[int]] = {}
    for kl in klassen:
        idx = [i for i, v in enumerate(vgs) if kl in v["guards_real"]][:je_klasse]
        je[kl] = idx
        for i in idx:
            if i not in gewaehlt:
                gewaehlt.append(i)
    keine = [i for i, v in enumerate(vgs) if not v["guards_real"]]
    fuell = keine[:max(0, n - len(gewaehlt))]
    je["keine"] = fuell
    gewaehlt = sorted(gewaehlt + fuell)
    return gewaehlt, {k: len(v) for k, v in je.items()}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--zensus-n", type=int, default=300)
    ap.add_argument("--n", type=int, default=64)
    ap.add_argument("--je-klasse", type=int, default=16)
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--deck-seed", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stack", default="r6_button")
    ap.add_argument("--zeitbudget-s", type=float, default=4200.0, help="Orakel-Phase; danach Abbruch + Teilauswertung")
    ap.add_argument("--zensus-datei", default="data/runs/v10/g3_census_20260907_221523.json")
    args = ap.parse_args()
    from research import k1_oracle as ko
    from pokerbot.strategy import hero_range as hr
    from pokerbot.strategy import range_tracker as rt
    from pokerbot.strategy.contracts import combo_kanonisch
    ko._worker_env()

    t0 = time.time()
    alle = ko.spiele_vorgeschichten(args.zensus_n, args.deck_seed, args.seed, args.stack)
    t_spiel = time.time() - t0
    zensus_pfad = Path(args.zensus_datei)
    zensus = json.loads(zensus_pfad.read_text(encoding="utf-8")) if zensus_pfad.exists() else None
    zensus_identisch = None
    if zensus is not None:
        zensus_identisch = (ko._zaehle_guard_klassen(alle) == zensus["guard_klassen_real"]
                            and sum(len(v["knoten_states"]) for v in alle) == zensus["n_knoten"])
    gewaehlt, je_klasse_n = waehle(alle, args.n, args.je_klasse, hr.STANDARD_GUARDS)
    vgs = [alle[i] for i in gewaehlt]
    n_knoten = sum(len(v["knoten_states"]) for v in vgs)
    print(f"Zensus {len(alle)} Vorgeschichten in {t_spiel:.1f}s (identisch zum Zensus-Report: {zensus_identisch}); "
          f"gewaehlt {len(vgs)} | Knoten {n_knoten} | je Klasse {je_klasse_n} | "
          f"real gefeuert {ko._zaehle_guard_klassen(vgs)}", flush=True)

    seeds = list(range(args.seed, args.seed + args.seeds))
    pakete = ko._pakete(vgs, seeds, args.stack)
    pakete_je_vg = [0] * len(vgs)
    for p in pakete:
        pakete_je_vg[p[0]] += 1
    print(f"Orakel: {len(pakete)} Pakete x {ko.COMBO_CHUNK} Combos x {len(seeds)} Seeds auf {args.workers} Workern; "
          f"Hochrechnung {len(pakete) * len(seeds) * WORKER_S_JE_PAKET_SEED / args.workers / 60:.1f} min "
          f"({WORKER_S_JE_PAKET_SEED} Worker-s je Paket-Seed aus dem Pilot S=64 w12)", flush=True)

    t2 = time.time()
    treffer: dict[tuple, dict] = {}
    histo: dict[tuple, dict] = {}
    fertig_je_vg = [0] * len(vgs)
    abgebrochen = False
    t_k1 = 0.0
    pool = mp.Pool(args.workers)
    try:
        it = pool.imap_unordered(ko._orakel_paket, pakete)
        # K1 im Hauptprozess, waehrend die Worker rechnen (Rekonstruktion ~4 s je Vorgeschichte fuer 3 Arme)
        t1 = time.time()
        k1 = [hr.rekonstruiere(v["st0"], hero=v["hero"]) for v in vgs]
        k1_par = [hr.rekonstruiere(v["st0"], hero=v["hero"], konvention=hr.TRACKER_PARITAET) for v in vgs]
        ohne = [hr.rekonstruiere(v["st0"], guards=(), hero=v["hero"]) for v in vgs]
        t_k1 = time.time() - t1
        print(f"K1 gerechnet: {t_k1:.1f}s ({t_k1 / max(1, len(vgs)):.1f}s je Vorgeschichte, 3 Arme)", flush=True)
        for k, (vi, ki, tr, hist) in enumerate(it, 1):
            treffer.setdefault((vi, ki), {}).update(tr)
            h = histo.setdefault((vi, ki), {})
            for lab, n in hist.items():
                h[lab] = h.get(lab, 0) + n
            fertig_je_vg[vi] += 1
            el = time.time() - t2
            if k % 25 == 0 or k == len(pakete):
                voll = sum(int(f == p) for f, p in zip(fertig_je_vg, pakete_je_vg))
                print(f"  [{k}/{len(pakete)}] {el / 60:.1f} min | ETA {el / k * (len(pakete) - k) / 60:.1f} min | "
                      f"vollstaendige VG {voll}/{len(vgs)}", flush=True)
            if el > args.zeitbudget_s and k < len(pakete):
                abgebrochen = True
                print(f"ZEITBUDGET {args.zeitbudget_s:.0f}s ueberschritten nach {k}/{len(pakete)} Paketen -> Abbruch, "
                      f"Teilauswertung", flush=True)
                break
    finally:
        pool.terminate()
        pool.join()
    t_orakel = time.time() - t2

    vollst = [vi for vi in range(len(vgs)) if fertig_je_vg[vi] == pakete_je_vg[vi]]
    faelle = []
    for vi in vollst:
        vg = vgs[vi]
        treffer_v = {ki: treffer[(vi, ki)] for ki in range(len(vg["knoten_states"])) if (vi, ki) in treffer}
        f = ko._fall(vi, vg, k1[vi], k1_par[vi], ohne[vi], treffer_v, histo, len(seeds))
        hole = combo_kanonisch(*vg["hero_hole"])
        f["hero_hole_in_k1_support"] = k1[vi].hero_range.get(hole, 0.0) > 0.0
        f["hero_hole_k1_masse"] = k1[vi].hero_range.get(hole, 0.0)
        try:
            f["hero_injiziert"] = bool(k1[vi].range_state(vg["st0"]["board"]).hero_injiziert)
        except Exception as e:  # noqa: BLE001
            f["hero_injiziert"] = f"nicht ermittelbar: {type(e).__name__}"
        faelle.append(f)

    def klassen_tabelle(feld: str) -> dict:
        kl: dict[str, list] = {}
        for f in faelle:
            for c in (f["guards_real"] or ["keine"]):
                if f.get(feld) is not None:
                    kl.setdefault(c, []).append(f[feld])
        return {k: ko._zusammenfassung(v) for k, v in sorted(kl.items())}

    gesamt = ko._zusammenfassung(ko._sammle(faelle, "tv_k1_vs_orakel"))
    floor = ko._zusammenfassung(ko._sammle(faelle, "tv_floor_orakel_ab"))
    vgs_ausgewertet = [vgs[vi] for vi in vollst]
    stich = ko.stichprobe_pruefen(len(vgs_ausgewertet), sum(len(v["knoten_states"]) for v in vgs_ausgewertet),
                                  ko._zaehle_guard_klassen(vgs_ausgewertet))
    floor_mittel = floor["mittel"] if floor["n"] > 0 else None
    status_z: dict[str, int] = {}
    for vi in range(len(vgs)):
        status_z[k1[vi].status] = status_z.get(k1[vi].status, 0) + 1
    report = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "gate": "G3", "kanal": ko.KANAL_GYM,
        "orakel_version": ko.ORAKEL_VERSION, "k1_version": hr.K1_VERSION, "k1_versions_hash": hr.versions_hash(),
        "kanal_flags": {"exploit": True, "prince": False, "resolver": False,
                        "tracker_alpha": rt.TRACKER_ALPHA, "aggro_full": rt.TRACKER_AGGRO_FULL,
                        "raise_narrow": rt.RAISE_NARROW, "audit_fix": rt.AUDIT_FIX},
        "konfig": vars(args), "seeds": seeds, "stack": args.stack,
        "stichprobe_design": "stratifiziert: erste je_klasse Vorgeschichten je Guard-Klasse (Deck-Reihenfolge) + 'keine' aufgefuellt",
        "zensus_identisch": zensus_identisch, "gewaehlte_vg_indizes": gewaehlt, "je_klasse_gezogen": je_klasse_n,
        "n_vorgeschichten_geplant": len(vgs), "n_vorgeschichten_ausgewertet": len(faelle),
        "n_knoten_geplant": n_knoten, "n_knoten_ausgewertet": sum(f["n_knoten"] for f in faelle),
        "n_pakete": len(pakete), "n_pakete_fertig": sum(fertig_je_vg), "zeitbudget_abbruch": abgebrochen,
        "zeit_s": {"spiel": round(t_spiel, 1), "k1": round(t_k1, 1), "orakel": round(t_orakel, 1)},
        "tv_budget": ko.TV_BUDGET, "floor_anteil_budget": ko.FLOOR_ANTEIL_BUDGET,
        "stichprobe": stich, "guard_klassen_real": ko._zaehle_guard_klassen(vgs_ausgewertet),
        "k1_status_zaehler": status_z,
        "rekonstruktions_fehler": status_z.get(hr.STATUS_FEHLGESCHLAGEN, 0),
        "hero_injiziert_anzahl": sum(int(f["hero_injiziert"] is True) for f in faelle),
        "hero_hole_ausserhalb_k1_support": sum(int(not f["hero_hole_in_k1_support"]) for f in faelle),
        "tv_k1_vs_orakel": gesamt, "tv_floor_orakel_ab": floor,
        "tv_k1_korrigiert_untere_schranke": ko._zusammenfassung(ko._sammle(faelle, "tv_k1_korrigiert_untere_schranke")),
        "urteil_roh": ko._urteil_roh(gesamt), "urteil_budget": ko._budget_urteil(gesamt, floor_mittel, stich),
        "tv_k1_vs_orakel_klasse": ko._zusammenfassung(ko._sammle(faelle, "tv_k1_vs_orakel_klasse")),
        "tv_paritaet_vs_orakel": ko._zusammenfassung(ko._sammle(faelle, "tv_paritaet_vs_orakel")),
        "tv_ohne_guards_vs_orakel": ko._zusammenfassung(ko._sammle(faelle, "tv_ohne_guards_vs_orakel")),
        "je_guard_klasse_real": klassen_tabelle("tv_k1_vs_orakel"),
        "je_guard_klasse_floor": klassen_tabelle("tv_floor_orakel_ab"),
        "je_guard_klasse_untere_schranke": klassen_tabelle("tv_k1_korrigiert_untere_schranke"),
        "je_guard_klasse_klassenebene": klassen_tabelle("tv_k1_vs_orakel_klasse"),
        "je_kanal_flag": {ko.KANAL_GYM: gesamt,
                          "live": "nicht messbar (k1_oracle --kanal gtow nicht verdrahtet, E3)"},
        "faelle": faelle,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    pfad = REPORT_DIR / f"g3_k1_gate_{time.strftime('%Y%m%d_%H%M%S')}.json"
    pfad.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    ko._drucke(report, faelle, pfad)
    for name in ("je_guard_klasse_floor", "je_guard_klasse_untere_schranke", "je_guard_klasse_klassenebene"):
        print(name, json.dumps(report[name], ensure_ascii=False))
    print(f"Rekonstruktions-Fehler {report['rekonstruktions_fehler']} | Status {status_z} | hero_injiziert "
          f"{report['hero_injiziert_anzahl']} | Hero-Hole ausserhalb K1-Support "
          f"{report['hero_hole_ausserhalb_k1_support']}/{len(faelle)}")


if __name__ == "__main__":
    main()
