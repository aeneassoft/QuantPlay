"""G2 LATENZ — Live-Kanal-Latenz beider v10-Arme auf ECHTEN River-Zustaenden (docs/plans/V10_BUILD_CARD.md E10).

Gate (E10): Plan-Pot-Entscheidungen p99 < 8 s UND Gesamt-p99 v10 <= Gesamt-p99 v5-H UND kein Aufruf >= 30 s.

Quelle der Zustaende: data/runs/v10/k3_roots_entwicklung.jsonl (Nacht-2-HH, research/k3_roots.py) — je Root der
live-treue Engine-State am River-Beginn + die gespielte River-Sequenz. Je HERO-River-Entscheidung wird der Zustand
VOR der Aktion mit research.policy_oracle.zustand_nach_pfad (Engine-Chip-Buchhaltung, legal_fuer) rekonstruiert und
auf Hero=Sitz 0 gespiegelt (der GTOW-Adapter gtow_to_state zwingt Hero auf Index 0; wickle_decide wickelt Sitz 0).

Messung: je Arm EIN FRISCHER Subprozess mit Live-Env (POKERB_PRINCE=1, POKERB_AUSLESE_STACK=r8_stack|r10_stack,
POKERB_ERWARTE_PROFIL, alle Shell-POKERB_* gestrippt; Resolver-Default ON; exploit OFF ueber das PRINCE-Profil).
Der Worker baut pokerbot.benchmark.gtowizard.PokerBotAgent DIREKT (Fingerprint + K4-Gatter laufen mit) und misst
die Wandzeit von self._decide(state) unter _decide_lock — exakt der Pfad von PokerBotAgent.act_dict ohne die
gsr-Uebersetzung. Kaltstart (Agent-Konstruktion inkl. K2-Aufwaermen; erste Entscheidung) wird getrennt ausgewiesen.
K2-Trace (POKERB_K2_TRACE) liefert fallback_status/offtree/deadline_status/zeiten_ms je Plan-Pot-Entscheidung.

Schichten: Pot-Klasse (pot_river < 1500 | >= 1500 = Plan-Pot), Position (IP|OOP), Facing (check|bet).
Stichprobe: --n je Arm, alle Plan-Pot-Haende zuerst (Ziel >= 50 Plan-Pot-Entscheidungen), Rest deterministisch
(seed) aus den Nicht-Plan-Haenden; Entscheidungen einer Hand bleiben zusammen und in Spielreihenfolge (Plan-Cache).

  python -m research.v10_latenz --bau                       # Zustandsliste -> data/runs/v10/G2_latenz_zustaende.json
  python -m research.v10_latenz --probe 10                  # 10 Entscheidungen je Arm, frische Prozesse, Hochrechnung
  python -m research.v10_latenz --messe --n 150             # Vollmessung beide Arme -> G2_latenz.json + .md
  python -m research.v10_latenz --bericht                   # nur Auswertung vorhandener Roh-JSONL
Kein Strategie-Code wird veraendert; das Modul liest und misst.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

RUNS = Path("data/runs/v10")
ROOTS = RUNS / "k3_roots_entwicklung.jsonl"
ZUSTAENDE = RUNS / "G2_latenz_zustaende.json"
PLAN_POT_CHIPS = 1500                      # Karte K2 / river_plan.DEFAULT_MIN_POT_CHIPS
GATE_PLAN_P99_S = 8.0                      # E10
GATE_MAX_S = 30.0                          # E10
ARME = {                                   # identisch zu research.gtow_nacht_v10.ARME (Live-Env der K5-Arme)
    "A": {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r8_stack", "POKERB_ERWARTE_PROFIL": "v5-H"},
    "B": {"POKERB_PRINCE": "1", "POKERB_AUSLESE_STACK": "r10_stack", "POKERB_ERWARTE_PROFIL": "v10"},
}
ARM_NAMEN = {"A": "v5-H", "B": "v10"}


# ================================================================ Zustaende (Treiber)
def _pfad_aus_seq(seq: list, k: int, hero_seat: int) -> list[dict]:
    """River-Aktionen VOR der k-ten Sequenzposition als policy_oracle-Pfad [{player, action, to?}].
    seq = [(wer, kind, zusatz_chips)] (k3_roots.river_sequenz): zusatz = Level-Differenz -> Raise-TO = laufendes Level."""
    lvl = {0: 0.0, 1: 0.0}
    pfad = []
    for wer, kind, zusatz in seq[:k]:
        s = hero_seat if wer == "hero" else 1 - hero_seat
        if kind in ("bet", "raise"):
            lvl[s] += float(zusatz)
            pfad.append({"player": s, "action": kind, "to": int(round(lvl[s]))})
        elif kind == "call":
            lvl[s] = max(lvl.values())
            pfad.append({"player": s, "action": "call"})
        elif kind == "check":
            pfad.append({"player": s, "action": "check"})
        else:
            return None   # fold vor Heros Entscheidung -> keine Entscheidung
    return pfad


def spiegle_hero_auf_0(st: dict, hero_seat: int) -> dict:
    """Sitzspiegelung: Hero -> Index 0 (Adapter-Konvention gtow_to_state). Identitaet bei hero_seat == 0."""
    if hero_seat == 0:
        return st
    st2 = json.loads(json.dumps(st))
    p = st2["players"]
    st2["players"] = [dict(p[1], idx=0), dict(p[0], idx=1)]
    for h in st2["history"]:
        if "player" in h:
            h["player"] = 1 - int(h["player"])
    st2["button"] = 1 - int(st2["button"])
    st2["to_act"] = 0
    st2["legal"]["to_act"] = 0
    return st2


def baue_zustaende() -> dict:
    """Alle Hero-River-Entscheidungszustaende aus den K3-Roots, mit Schicht-Metadaten."""
    from research.policy_oracle import zustand_nach_pfad
    zeilen = [json.loads(l) for l in ROOTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    kopf, roots = zeilen[0], zeilen[1:]
    haende, fehler = [], {"pfad_fold": 0, "hero_allin": 0, "keine_hero_aktion": 0, "rekonstruktion": 0}
    for r in roots:
        hs = int(r["hero_seat"])
        seq = [tuple(x) for x in r["seq_river"]]
        entsch = []
        for k, (wer, kind, _z) in enumerate(seq):
            if wer != "hero":
                continue
            pfad = _pfad_aus_seq(seq, k, hs)
            if pfad is None:
                fehler["pfad_fold"] += 1
                break
            try:
                st = zustand_nach_pfad(r["root_state"], pfad, hs)
            except Exception as e:  # noqa: BLE001
                fehler["rekonstruktion"] += 1
                break
            if st["players"][hs]["all_in"] or st["players"][hs]["stack"] <= 0:
                fehler["hero_allin"] += 1
                break
            st = {k2: v for k2, v in st.items() if not k2.startswith("_")}
            st = spiegle_hero_auf_0(st, hs)
            entsch.append({
                "hand_id": r["hand_id"], "root_hash": r["root_hash"], "entsch_idx": k, "gespielt": kind,
                "pot_river": float(r["pot_river"]), "pot_klasse": "plan" if r["pot_river"] >= PLAN_POT_CHIPS else "klein",
                "position": "OOP" if r["hero_oop"] else "IP",
                "facing": "bet" if st["legal"]["to_call"] > 0 else "check",
                "pot_bei_entscheidung": st["pot"], "hero_k1_status": r["hero_k1_status"],
                "provenienz": r["provenienz"], "state": st,
            })
        if not entsch:
            fehler["keine_hero_aktion"] += 1
            continue
        haende.append({"hand_id": r["hand_id"], "pot_klasse": entsch[0]["pot_klasse"], "entscheidungen": entsch})
    n_e = sum(len(h["entscheidungen"]) for h in haende)
    meta = {"quelle": str(ROOTS), "quelle_kopf": kopf, "n_haende": len(haende), "n_entscheidungen": n_e,
            "n_plan_haende": sum(1 for h in haende if h["pot_klasse"] == "plan"),
            "n_plan_entscheidungen": sum(len(h["entscheidungen"]) for h in haende if h["pot_klasse"] == "plan"),
            "ausschluss": fehler, "erzeugt": time.strftime("%Y-%m-%d %H:%M:%S")}
    RUNS.mkdir(parents=True, exist_ok=True)
    ZUSTAENDE.write_text(json.dumps({"meta": meta, "haende": haende}, ensure_ascii=False), encoding="utf-8")
    return meta


def waehle_stichprobe(haende: list[dict], n_ziel: int, seed: int, plan_min: int) -> list[dict]:
    """Plan-Pot-Haende zuerst (bis >= plan_min Entscheidungen oder alle), dann Nicht-Plan-Haende bis n_ziel.
    Deterministisch (seed); Hand-Reihenfolge gemischt, Entscheidungen je Hand in Spielreihenfolge."""
    rng = random.Random(seed)
    plan = [h for h in haende if h["pot_klasse"] == "plan"]
    klein = [h for h in haende if h["pot_klasse"] != "plan"]
    rng.shuffle(plan)
    rng.shuffle(klein)
    auswahl, n = [], 0
    for h in plan:
        if n >= plan_min and n >= n_ziel:
            break
        auswahl.append(h)
        n += len(h["entscheidungen"])
    for h in klein:
        if n >= n_ziel:
            break
        auswahl.append(h)
        n += len(h["entscheidungen"])
    rng.shuffle(auswahl)                     # Plan- und Kleinpots gemischt -> kein Warm-/Kalt-Bias je Klasse
    return auswahl


# ================================================================ Worker (frischer Subprozess je Arm)
def _worker(arm: str, eingabe: Path, ausgabe: Path) -> int:
    """Laeuft im Subprozess mit gesetzter Live-Env. Importiert den GTOW-Adapter ZUERST (PRINCE-/Auslese-Flags vor
    dem bot-Import, K4-Fingerprint + Gatter) und misst _decide(state) je Entscheidung."""
    import threading
    try:
        import psutil
    except Exception:  # noqa: BLE001
        psutil = None
    t_imp0 = time.perf_counter()
    from pokerbot.benchmark.gtowizard import PokerBotAgent   # noqa: PLC0415 — Import-Reihenfolge ist Teil des Pfads
    t_imp = time.perf_counter() - t_imp0
    t_k0 = time.perf_counter()
    agent = PokerBotAgent(seed=7)                             # exploit folgt POKERB_EXPLOIT=0 aus dem PRINCE-Profil
    t_konstruktion = time.perf_counter() - t_k0
    fp = agent.fingerprint
    daten = json.loads(eingabe.read_text(encoding="utf-8"))
    haende = daten["haende"]
    n_ges = sum(len(h["entscheidungen"]) for h in haende)
    kopf = {"kopf": True, "arm": arm, "arm_name": ARM_NAMEN[arm], "pid": os.getpid(),
            "import_s": round(t_imp, 3), "konstruktion_s": round(t_konstruktion, 3),
            "fingerprint_hash": agent.fingerprint_hash, "stack": fp.get("stack"), "exploit": fp.get("exploit"),
            "use_resolver": fp.get("use_resolver"), "use_turn_resolver": fp.get("use_turn_resolver"),
            "prince": fp.get("prince"), "prince_geladen": fp.get("prince_geladen"), "git": fp.get("git"),
            "river_plan": fp.get("river_plan"), "private_seed_quelle": fp.get("private_seed_quelle"),
            "env": {k: v for k, v in os.environ.items() if k.startswith("POKERB_")}, "n_geplant": n_ges}
    with ausgabe.open("w", encoding="utf-8") as f:
        f.write(json.dumps(kopf, ensure_ascii=False) + "\n")
    print(f"[{ARM_NAMEN[arm]}] import {t_imp:.2f}s konstruktion {t_konstruktion:.2f}s stack={fp.get('stack')} "
          f"exploit={fp.get('exploit')} resolver={fp.get('use_resolver')} fp={agent.fingerprint_hash[:12]} n={n_ges}",
          flush=True)
    i, t_lauf0 = 0, time.perf_counter()
    for h in haende:
        for e in h["entscheidungen"]:
            st = e["state"]
            with agent._decide_lock:
                agent.bot.hero_idx = 0
                t0 = time.perf_counter()
                try:
                    dec = agent._decide(st)
                    fehler = None
                except Exception as ex:  # noqa: BLE001 — ein Absturz ist ein Befund, kein Messabbruch
                    dec, fehler = {}, f"{type(ex).__name__}: {ex}"
                dt = time.perf_counter() - t0
            rat = dec.get("rationale") if isinstance(dec.get("rationale"), dict) else {}
            zeile = {"i": i, "kalt": i == 0, "hand_id": e["hand_id"], "entsch_idx": e["entsch_idx"],
                     "pot_klasse": e["pot_klasse"], "position": e["position"], "facing": e["facing"],
                     "pot_river": e["pot_river"], "pot_bei_entscheidung": e["pot_bei_entscheidung"],
                     "gespielt_hist": e["gespielt"], "aktion": dec.get("action"), "amount": dec.get("amount"),
                     "auslese_guard": bool(dec.get("auslese_guard")), "texassolver": bool(rat.get("resolver")),
                     "fehler": fehler, "decide_s": round(dt, 4), "t_seit_start_s": round(time.perf_counter() - t_lauf0, 2)}
            with ausgabe.open("a", encoding="utf-8") as f:
                f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            i += 1
            if i % 5 == 0 or dt >= GATE_PLAN_P99_S:
                print(f"[{ARM_NAMEN[arm]}] {i}/{n_ges} {e['pot_klasse']:5s} {e['position']} {e['facing']:5s} "
                      f"decide {dt:6.2f}s  gesamt {time.perf_counter()-t_lauf0:7.1f}s", flush=True)
        agent.hand_end(None)
    ress = {}
    if psutil is not None:
        mi = psutil.Process().memory_info()
        ress = {"rss_mb": round(mi.rss / 2**20, 1), "peak_wset_mb": round(getattr(mi, "peak_wset", 0) / 2**20, 1)}
    try:
        import torch
        if torch.cuda.is_available():
            ress["cuda_max_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
            ress["cuda_max_reserved_mb"] = round(torch.cuda.max_memory_reserved() / 2**20, 1)
    except Exception:  # noqa: BLE001
        pass
    ress["threads"] = threading.active_count()
    with ausgabe.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"fuss": True, "ressourcen": ress, "lauf_s": round(time.perf_counter() - t_lauf0, 1)},
                           ensure_ascii=False) + "\n")
    print(f"[{ARM_NAMEN[arm]}] fertig {i} Entscheidungen in {time.perf_counter()-t_lauf0:.1f}s; {ress}", flush=True)
    return 0


def starte_arm(arm: str, eingabe: Path, ausgabe: Path, trace: Path, log: Path) -> dict:
    """Frischer Subprozess mit hygienischer Live-Env (Muster gtow_nacht_v10: alle POKERB_* gestrippt)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("POKERB_")}
    env.update(ARME[arm])
    env.update({"PYTHONUTF8": "1", "POKERB_ARM": ARM_NAMEN[arm], "POKERB_K2_TRACE": str(trace),
                "POKERB_LEDGER_PFAD": str(RUNS / f"G2_latenz_ledger_{arm}.jsonl")})
    cmd = [sys.executable, "-u", "-m", "research.v10_latenz", "--worker", arm, "--eingabe", str(eingabe),
           "--ausgabe", str(ausgabe)]
    t0 = time.perf_counter()
    with log.open("a", encoding="utf-8") as lf:
        lf.write(f"# {time.strftime('%H:%M:%S')} {' '.join(cmd)}\n")
        lf.flush()
        rc = subprocess.run(cmd, env=env, stdout=lf, stderr=subprocess.STDOUT, encoding="utf-8").returncode
    return {"arm": arm, "rc": rc, "wandzeit_s": round(time.perf_counter() - t0, 1), "kommando": " ".join(cmd),
            "env_arm": ARME[arm]}


def nvidia_lage() -> dict:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip()
        return {"gpu": out}
    except Exception as e:  # noqa: BLE001
        return {"gpu": f"unbekannt ({type(e).__name__})"}


# ================================================================ Auswertung
def quantil(xs: list[float], q: float) -> float | None:
    """Empirisches Quantil (naechster Rang, konservativ nach oben: ceil) — bei kleinen n = obere Ordnungsstatistik."""
    if not xs:
        return None
    s = sorted(xs)
    k = min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))
    return s[k]


def zusammenfassung(zeilen: list[dict]) -> dict:
    xs = [z["decide_s"] for z in zeilen]
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "p50_s": round(quantil(xs, 0.50), 3), "p90_s": round(quantil(xs, 0.90), 3),
            "p99_s": round(quantil(xs, 0.99), 3), "max_s": round(max(xs), 3), "mittel_s": round(sum(xs) / len(xs), 3),
            "n_ge_8s": sum(1 for x in xs if x >= GATE_PLAN_P99_S), "n_ge_30s": sum(1 for x in xs if x >= GATE_MAX_S),
            "texassolver_anteil": round(sum(1 for z in zeilen if z.get("texassolver")) / len(xs), 3),
            "guard_anteil": round(sum(1 for z in zeilen if z.get("auslese_guard")) / len(xs), 3),
            "fehler": sum(1 for z in zeilen if z.get("fehler"))}


def lese_roh(pfad: Path) -> tuple[dict, list[dict], dict]:
    zeilen = [json.loads(l) for l in pfad.read_text(encoding="utf-8").splitlines() if l.strip()]
    kopf = next((z for z in zeilen if z.get("kopf")), {})
    fuss = next((z for z in zeilen if z.get("fuss")), {})
    return kopf, [z for z in zeilen if "decide_s" in z], fuss


def lese_trace(pfad: Path) -> dict:
    """K2-Trace-Zaehler (Plan-Pot-Entscheidungen des r10-Arms): fallback_status, offtree, deadline_status, flags,
    zeiten_ms-Quantile (queue/ranges/solve/gesamt)."""
    if not pfad.exists():
        return {"vorhanden": False}
    tr = [json.loads(l) for l in pfad.read_text(encoding="utf-8").splitlines() if l.strip()]
    z = {"vorhanden": True, "n": len(tr), "fallback_status": {}, "deadline_status": {}, "flags": {},
         "offtree": sum(1 for t in tr if t.get("offtree")), "range_herkunft": {}}
    for t in tr:
        z["fallback_status"][t.get("fallback_status")] = z["fallback_status"].get(t.get("fallback_status"), 0) + 1
        z["deadline_status"][t.get("deadline_status")] = z["deadline_status"].get(t.get("deadline_status"), 0) + 1
        z["range_herkunft"][t.get("range_herkunft")] = z["range_herkunft"].get(t.get("range_herkunft"), 0) + 1
        for fl in t.get("flags") or []:
            z["flags"][fl] = z["flags"].get(fl, 0) + 1
    for feld in ("queue", "ranges", "solve", "gesamt"):
        xs = [t["zeiten_ms"][feld] / 1000.0 for t in tr if t.get("zeiten_ms") and t["zeiten_ms"].get(feld) is not None]
        if xs:
            z[f"{feld}_s"] = {"n": len(xs), "p50": round(quantil(xs, 0.5), 3), "p99": round(quantil(xs, 0.99), 3),
                              "max": round(max(xs), 3)}
    lat = [t["latenz_ms"] / 1000.0 for t in tr if t.get("latenz_ms") is not None]
    if lat:
        z["latenz_s"] = {"n": len(lat), "p50": round(quantil(lat, 0.5), 3), "p99": round(quantil(lat, 0.99), 3),
                         "max": round(max(lat), 3)}
    return z


def auswerte_arm(roh: Path, trace: Path) -> dict:
    kopf, zeilen, fuss = lese_roh(roh)
    warm = [z for z in zeilen if not z["kalt"]]
    out = {"kopf": kopf, "ressourcen": fuss.get("ressourcen"), "lauf_s": fuss.get("lauf_s"),
           "gesamt_inkl_kalt": zusammenfassung(zeilen), "gesamt_warm": zusammenfassung(warm),
           "kalt": next((z for z in zeilen if z["kalt"]), None),
           "je_pot_klasse": {k: zusammenfassung([z for z in zeilen if z["pot_klasse"] == k]) for k in ("plan", "klein")},
           "je_position": {k: zusammenfassung([z for z in zeilen if z["position"] == k]) for k in ("IP", "OOP")},
           "je_facing": {k: zusammenfassung([z for z in zeilen if z["facing"] == k]) for k in ("check", "bet")},
           "je_zelle": {}, "trace": lese_trace(trace),
           "langsamste": sorted(zeilen, key=lambda z: -z["decide_s"])[:8]}
    for pk in ("plan", "klein"):
        for pos in ("IP", "OOP"):
            for fc in ("check", "bet"):
                sel = [z for z in zeilen if z["pot_klasse"] == pk and z["position"] == pos and z["facing"] == fc]
                if sel:
                    out["je_zelle"][f"{pk}/{pos}/{fc}"] = zusammenfassung(sel)
    return out


def gate_urteil(a: dict, b: dict) -> dict:
    plan_b = b["je_pot_klasse"]["plan"]
    ges_a, ges_b = a["gesamt_inkl_kalt"], b["gesamt_inkl_kalt"]
    krit = {
        "plan_p99_unter_8s": (plan_b.get("p99_s") is not None and plan_b["p99_s"] < GATE_PLAN_P99_S),
        "gesamt_p99_v10_le_v5H": (ges_b.get("p99_s") is not None and ges_a.get("p99_s") is not None
                                  and ges_b["p99_s"] <= ges_a["p99_s"]),
        "kein_aufruf_ge_30s": (ges_a.get("n_ge_30s", 0) == 0 and ges_b.get("n_ge_30s", 0) == 0),
    }
    n_plan_ok = plan_b.get("n", 0) >= 50
    status = "BESTANDEN" if all(krit.values()) else "VERFEHLT"
    if not n_plan_ok or ges_a.get("n", 0) < 150 or ges_b.get("n", 0) < 150:
        status = status + "_REDUZIERTE_STICHPROBE"
    return {"kriterien": krit, "werte": {"plan_p99_v10_s": plan_b.get("p99_s"), "plan_n_v10": plan_b.get("n"),
                                         "gesamt_p99_v10_s": ges_b.get("p99_s"), "gesamt_p99_v5H_s": ges_a.get("p99_s"),
                                         "max_v10_s": ges_b.get("max_s"), "max_v5H_s": ges_a.get("max_s")},
            "stichprobe_voll": n_plan_ok and ges_a.get("n", 0) >= 150 and ges_b.get("n", 0) >= 150, "status": status}


def _md_tabelle(titel: str, d: dict) -> str:
    z = [f"### {titel}", "", "| Schicht | n | p50 | p90 | p99 | max | Mittel | >=8s | >=30s | TexasSolver | Guard | Fehler |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, s in d.items():
        if not s or not s.get("n"):
            z.append(f"| {k} | 0 | | | | | | | | | | |")
            continue
        z.append(f"| {k} | {s['n']} | {s['p50_s']:.2f} | {s['p90_s']:.2f} | {s['p99_s']:.2f} | {s['max_s']:.2f} | "
                 f"{s['mittel_s']:.2f} | {s['n_ge_8s']} | {s['n_ge_30s']} | {s['texassolver_anteil']:.2f} | "
                 f"{s['guard_anteil']:.2f} | {s['fehler']} |")
    return "\n".join(z) + "\n"


def schreibe_bericht(ergebnis: dict, md: Path) -> None:
    g = ergebnis["gate"]
    t = [f"# G2 LATENZ — Live-Kanal, beide Arme ({ergebnis['erzeugt']})", "",
         f"**Status: {g['status']}** — Kriterien E10: {json.dumps(g['kriterien'])}", "",
         f"Werte: {json.dumps(g['werte'])}", "",
         f"Stichprobe: {json.dumps(ergebnis['stichprobe'])}", "",
         f"Maschine: {json.dumps(ergebnis['maschine'])}", ""]
    for arm in ("A", "B"):
        e = ergebnis["arme"][arm]
        k = e["kopf"]
        t += [f"## Arm {arm} = {ARM_NAMEN[arm]} (stack {k.get('stack')}, exploit {k.get('exploit')}, resolver "
              f"{k.get('use_resolver')}, fp {str(k.get('fingerprint_hash'))[:12]}, rc {ergebnis['laeufe'][arm]['rc']})", "",
              f"Kaltstart: Import {k.get('import_s')} s, Konstruktion (inkl. K2-Aufwaermen) {k.get('konstruktion_s')} s, "
              f"erste Entscheidung {e['kalt'] and e['kalt']['decide_s']} s "
              f"({e['kalt'] and e['kalt']['pot_klasse']}/{e['kalt'] and e['kalt']['position']}/{e['kalt'] and e['kalt']['facing']})",
              f"Ressourcen: {json.dumps(e['ressourcen'])}; Lauf {e['lauf_s']} s", "",
              _md_tabelle("Gesamt", {"inkl. Kaltstart": e["gesamt_inkl_kalt"], "warm": e["gesamt_warm"]}),
              _md_tabelle("Pot-Klasse", e["je_pot_klasse"]), _md_tabelle("Position", e["je_position"]),
              _md_tabelle("Facing", e["je_facing"]), _md_tabelle("Zellen", e["je_zelle"]),
              f"K2-Trace: {json.dumps(e['trace'], ensure_ascii=False)}", "",
              "Langsamste Aufrufe: " + "; ".join(f"{z['decide_s']:.2f}s ({z['pot_klasse']}/{z['position']}/{z['facing']}, "
                                                 f"hand {z['hand_id']}, {z['aktion']})" for z in e["langsamste"]), ""]
    if ergebnis.get("hochrechnung"):
        t += ["## Hochrechnung (Probe)", "", json.dumps(ergebnis["hochrechnung"], ensure_ascii=False), ""]
    t += ["## Kommandos", ""] + [f"- `{l['kommando']}` (rc {l['rc']}, {l['wandzeit_s']} s)" for l in ergebnis["laeufe"].values()]
    md.write_text("\n".join(t) + "\n", encoding="utf-8")


# ================================================================ Treiber
def messe(n: int, plan_min: int, seed: int, tag: str, arme: tuple[str, ...] = ("A", "B")) -> dict:
    daten = json.loads(ZUSTAENDE.read_text(encoding="utf-8"))
    auswahl = waehle_stichprobe(daten["haende"], n, seed, plan_min)
    eingabe = RUNS / f"G2_latenz_{tag}_stichprobe.json"
    eingabe.write_text(json.dumps({"haende": auswahl}, ensure_ascii=False), encoding="utf-8")
    n_e = sum(len(h["entscheidungen"]) for h in auswahl)
    n_plan = sum(len(h["entscheidungen"]) for h in auswahl if h["pot_klasse"] == "plan")
    stich = {"n_haende": len(auswahl), "n_entscheidungen": n_e, "n_plan_entscheidungen": n_plan, "seed": seed,
             "n_ziel": n, "plan_min": plan_min, "verfuegbar": {k: daten["meta"][k] for k in
                                                                ("n_haende", "n_entscheidungen", "n_plan_haende",
                                                                 "n_plan_entscheidungen")}}
    print(f"[{tag}] Stichprobe: {stich}", flush=True)
    maschine_vor = nvidia_lage()
    laeufe, ausw = {}, {}
    log = RUNS / f"G2_latenz_{tag}.log"
    for arm in arme:
        roh, trace = RUNS / f"G2_latenz_{tag}_roh_{arm}.jsonl", RUNS / f"G2_latenz_{tag}_k2trace_{arm}.jsonl"
        for p in (roh, trace):
            if p.exists():
                p.unlink()
        print(f"[{tag}] starte Arm {arm} ({ARM_NAMEN[arm]}) ...", flush=True)
        laeufe[arm] = starte_arm(arm, eingabe, roh, trace, log)
        ausw[arm] = auswerte_arm(roh, trace)
        print(f"[{tag}] Arm {arm} rc={laeufe[arm]['rc']} {laeufe[arm]['wandzeit_s']}s gesamt={ausw[arm]['gesamt_inkl_kalt']}",
              flush=True)
    ergebnis = {"gate": "G2 Latenz (E10)", "erzeugt": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": tag,
                "stichprobe": stich, "maschine": {"vor": maschine_vor, "nach": nvidia_lage(),
                                                  "cpu_kerne": os.cpu_count()},
                "laeufe": laeufe, "arme": ausw}
    if all(a in ausw for a in ("A", "B")):
        ergebnis["gate_urteil"] = gate_urteil(ausw["A"], ausw["B"])
        ergebnis["gate"] = ergebnis["gate_urteil"]
    return ergebnis


def hochrechnung(ergebnis: dict, n_ziel: int) -> dict:
    """Aus den Probe-Mitteln: Sekunden je Entscheidung je Arm -> Wandzeit fuer n_ziel je Arm (+ Kaltstart)."""
    out = {}
    for arm, e in ergebnis["arme"].items():
        g = e["gesamt_warm"] if e["gesamt_warm"].get("n") else e["gesamt_inkl_kalt"]
        k = e["kopf"]
        fix = float(k.get("import_s") or 0) + float(k.get("konstruktion_s") or 0)
        out[arm] = {"mittel_s_je_entscheidung": g.get("mittel_s"), "p99_probe_s": g.get("p99_s"),
                    "fixkosten_s": round(fix, 1), "wandzeit_fuer_n_min": round((fix + n_ziel * (g.get("mittel_s") or 0)) / 60, 1),
                    "n_ziel": n_ziel}
    out["summe_min"] = round(sum(v["wandzeit_fuer_n_min"] for v in out.values() if isinstance(v, dict)), 1)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bau", action="store_true")
    ap.add_argument("--probe", type=int, default=None, help="Entscheidungen je Arm fuer die Hochrechnung")
    ap.add_argument("--messe", action="store_true")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--plan-min", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260908)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--arme", default="AB")
    ap.add_argument("--bericht", action="store_true")
    ap.add_argument("--worker", default=None, choices=tuple(ARME))
    ap.add_argument("--eingabe", default=None)
    ap.add_argument("--ausgabe", default=None)
    a = ap.parse_args(argv)
    if a.worker:
        return _worker(a.worker, Path(a.eingabe), Path(a.ausgabe))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.bau:
        print(json.dumps(baue_zustaende(), ensure_ascii=False, indent=1))
        return 0
    arme = tuple(c for c in a.arme if c in ARME)
    if a.probe:
        tag = a.tag or f"probe{a.probe}"
        erg = messe(a.probe, plan_min=max(1, a.probe // 2), seed=a.seed + 1, tag=tag, arme=arme)
        erg["hochrechnung"] = hochrechnung(erg, a.n)
        (RUNS / f"G2_latenz_{tag}.json").write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"hochrechnung": erg["hochrechnung"], "gate": erg.get("gate_urteil")}, ensure_ascii=False, indent=1))
        return 0
    if a.messe:
        tag = a.tag or "voll"
        erg = messe(a.n, a.plan_min, a.seed, tag, arme=arme)
        (RUNS / f"G2_latenz_{tag}.json").write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
        if len(arme) == 2:
            (RUNS / "G2_latenz.json").write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
            schreibe_bericht(erg, RUNS / "G2_latenz.md")
        print(json.dumps(erg.get("gate_urteil"), ensure_ascii=False, indent=1))
        return 0
    if a.bericht:
        tag = a.tag or "voll"
        erg = json.loads((RUNS / f"G2_latenz_{tag}.json").read_text(encoding="utf-8"))
        for arm in erg["arme"]:
            erg["arme"][arm] = auswerte_arm(RUNS / f"G2_latenz_{tag}_roh_{arm}.jsonl",
                                            RUNS / f"G2_latenz_{tag}_k2trace_{arm}.jsonl")
        erg["gate_urteil"] = gate_urteil(erg["arme"]["A"], erg["arme"]["B"])
        (RUNS / "G2_latenz.json").write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
        schreibe_bericht(erg, RUNS / "G2_latenz.md")
        print(json.dumps(erg["gate_urteil"], ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
