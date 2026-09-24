"""Autotest-Harness (P4-A): Liga-Bots spielen den Menschen-Sitz durch den KOMPLETTEN Trainer-Stack.

WHY (docs/doctrine/TRAINER_DESIGN.md par.7, verbindlich vor Menschen-Einsatz): der volle Pfad Logger -> Grader ->
Renderer -> Report muss N Haende ohne Crash ueberleben, die Latenz-Budgets halten und eine plausible
Grade-Verteilung liefern (station wird schlechter benotet als tag — die Sanity des Graders selbst).
Der Treiber normalisiert SixMaxBot-'bet' zu 'raise' und klemmt amounts in [raise_min, raise_max]
aus view.legal (BINDING, docs/plans/TRAINER_PLAN.md P4-A) — sonst 400t der Harness und zero_crash scheitert
faelschlich. Ein persistenter injizierter rng pro Arm (KEIN per-Spot-Reseed — der Fake-Mixing-Trap,
arena/sixmax.py:96-97).

Mid-Integration-Verhalten: der Server wird parallel verdrahtet — fehlt ein GEPLANTER Endpoint
(/api/feedback/last bzw. /api/feedback, /api/replay/last, /api/report) oder das P0-Decision-Log
KOMPLETT, degradiert der jeweilige Check zu WARN (Exit bleibt 0). Vorhandene, aber kaputte
Artefakte (Records ohne grade/erklaerung_kurz, Latenz ueber Budget, station<=tag) -> FAIL, Exit 1.

Deliberate-failure probe (dev-only): einen Grader so monkeypatchen, dass Records ohne 'grade'
geschrieben werden -> decisions_schema FAIL + Exit 1 (der Harness ERKENNT, er laeuft nicht nur).

Run:  python -m pokerbot.coach.autotest [hands] [--hands N] [--deep] [--json PATH] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

DEFAULT_HANDS = 60
DEEP_HANDS = 300                      # the pre-release bar (P4-A acceptance)
DRIVER_PROFILES = ("tag", "station")  # sanity pair: disciplined vs call-station
MODES = ("gto", "exploit")            # the two trainer modes (P0-0)
ARM_SEEDS = {"tag": 42, "station": 43}   # fixed seeds per the plan (statistical honesty)
MEDIAN_GRADE_MS_BUDGET = 250          # gate: median per-decision grading latency
# Floor per profile for the station-vs-tag sanity check. MEASURED: at ~120 graded decisions/profile the two
# error rates sit within noise of each other (station .057 vs tag .059 — a coin flip); at ~500 they separate
# cleanly. Below the floor the check WARNs instead of failing — a noisy criterion must not hard-fail a build.
MIN_GRADED_FOR_SANITY = 300           # default-run floor per profile; --deep uses the plan's 200+
MIN_GRADED_FOR_SANITY_DEEP = 500
MAX_ITERS_PER_HAND = 80               # runaway guard for the drive loop
GRADE_VOCAB = {"ok", "teuer", "leak"}

CHECKS: list[tuple[str, object]] = []  # (name, fn) — fn returns None (pass) / 'WARN: ...' / failure str
RESULTS: dict = {}                     # filled by run_all(); checks read it


def check(name: str):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


def _bootstrap() -> None:
    """PRINCE v2.2 flags BEFORE any strategy import — flags are read at import time (gto_mode.py:6)."""
    os.environ.setdefault("POKERB_PRINCE", "1")
    from pokerbot.strategy import gto_mode
    gto_mode.apply()


def normalize_action(dec: dict, legal: dict) -> tuple[str, int | None]:
    """BINDING (P4-A): SixMaxBot.decide kann 'bet' liefern; POST /api/action akzeptiert nur
    fold|check|call|raise|allin. bet->raise; raise-amount in [raise_min, raise_max] geklemmt
    (commit-TO totals); nicht-legale Aktionen degradieren sicher check > call > fold."""
    action = dec.get("action", "check")
    amount = dec.get("amount")
    if action == "bet":
        action = "raise"
    if action in ("raise", "allin") and not legal.get("can_raise"):
        action = "check" if legal.get("can_check") else ("call" if legal.get("can_call") else "fold")
    if action == "raise":
        lo, hi = legal.get("raise_min"), legal.get("raise_max")
        amount = int(amount) if amount is not None else int(lo or 0)
        if lo is not None:
            amount = max(int(lo), amount)
        if hi is not None:
            amount = min(int(hi), amount)
        return action, amount
    if action == "check" and not legal.get("can_check"):
        action = "call" if legal.get("can_call") else "fold"
    elif action == "call" and not legal.get("can_call"):
        action = "check" if legal.get("can_check") else "fold"
    return action, None


def _safe_json(resp) -> dict:
    try:
        d = resp.json()
        return d if isinstance(d, dict) else {"_": d}
    except Exception:  # noqa: BLE001 — a non-JSON body is diagnostic data, not a crash of ours
        return {}


def _probe(client, candidates: list[tuple[str, str]]) -> dict | None:
    """Try (method, url) pairs; return the first response that is not 404/405 (endpoint exists),
    else None (planned endpoint not wired yet -> the caller degrades to WARN)."""
    for method, url in candidates:
        try:
            r = client.request(method, url)
        except Exception as e:  # noqa: BLE001 — a raising probe is itself a finding
            return {"method": method, "url": url, "status": -1, "error": repr(e), "json": {}}
        if r.status_code not in (404, 405):
            return {"method": method, "url": url, "status": r.status_code, "json": _safe_json(r)}
    return None


def _decisions_path_of(six_server) -> Path:
    """The P0-1 planned contract: decisions_<sid>.jsonl next to session_<sid>.jsonl."""
    sess = six_server.SESSION
    explicit = getattr(sess, "decisions_path", None)
    if explicit is not None:
        return Path(explicit)
    p = Path(sess.path)
    return p.with_name("decisions_" + p.stem.removeprefix("session_") + ".jsonl")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def run_arm(client, six_server, profile: str, mode: str, hands: int, seed: int,
            used_paths: set[str]) -> dict:
    """Drive `hands` hands of one (profile, mode) arm through the real HTTP routes."""
    import random
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot

    arm = {"profile": profile, "mode": mode, "hands": 0, "crashes": [],
           "mode_seen": "__absent__", "coach_seen": False, "feedback": None, "replay": None,
           "session_path": None, "decisions_path": None, "decisions": []}

    # fresh session; the sid is second-resolution — avoid path collisions between fast arms
    view = None
    for _ in range(6):
        r = client.post("/api/new_session", json={"stack_bb": 100, "mode": mode})
        if r.status_code != 200:
            arm["crashes"].append(("/api/new_session", r.status_code, r.text[:200]))
            return arm
        if str(six_server.SESSION.path) not in used_paths:
            view = r.json()
            break
        time.sleep(0.55)
    if view is None:
        arm["crashes"].append(("/api/new_session", 0, "no fresh session path after retries"))
        return arm
    used_paths.add(str(six_server.SESSION.path))
    arm["session_path"] = str(six_server.SESSION.path)
    arm["decisions_path"] = str(_decisions_path_of(six_server))
    arm["mode_seen"] = view.get("mode", "__absent__")

    driver = SixMaxBot(0, PROFILES[profile])
    driver.rng = random.Random(seed)   # ONE persistent rng per arm (solver_policy.py idiom)

    iters = 0
    while arm["hands"] < hands and iters < hands * MAX_ITERS_PER_HAND:
        iters += 1
        if view.get("hand_over"):
            arm["hands"] += 1
            if isinstance(view.get("coach"), dict):
                arm["coach_seen"] = True
            if arm["feedback"] is None:            # probe the planned feedback route once per arm
                arm["feedback"] = _probe(client, [("POST", "/api/feedback/last"),
                                                  ("GET", "/api/feedback/last"),
                                                  ("POST", "/api/feedback")])
            if arm["replay"] is None:
                arm["replay"] = _probe(client, [("GET", "/api/replay/last")])
            if arm["hands"] >= hands:
                break
            r = client.post("/api/hand")
            if r.status_code != 200:
                arm["crashes"].append(("/api/hand", r.status_code, r.text[:200]))
                break
            view = r.json()
            driver.new_hand(list(range(6)))        # per-hand state hygiene (opp models stay)
            continue
        legal = view.get("legal") or {}
        if legal.get("to_act") != 0:
            arm["crashes"].append(("view", 0, f"unexpected to_act={legal.get('to_act')} while hand live"))
            break
        obs = six_server.SESSION.table.obs_for(0)  # verified real: six_server.py:30 self.table
        dec = driver.decide(obs)
        action, amount = normalize_action(dec, legal)
        r = client.post("/api/action", json={"action": action, "amount": amount})
        if r.status_code != 200:
            arm["crashes"].append(("/api/action", r.status_code,
                                   f"{action}/{amount} -> {r.text[:160]}"))
            rs = client.get("/api/state")          # resync once, then force the safe fallback
            if rs.status_code != 200:
                break
            view = rs.json()
            lg = view.get("legal") or {}
            if lg.get("to_act") == 0:
                safe = "check" if lg.get("can_check") else ("call" if lg.get("can_call") else "fold")
                r2 = client.post("/api/action", json={"action": safe, "amount": None})
                if r2.status_code != 200:
                    break
                view = r2.json()
            continue
        view = r.json()
    arm["decisions"] = _read_jsonl(Path(arm["decisions_path"]))
    return arm


def run_all(hands: int) -> dict:
    _bootstrap()
    from fastapi.testclient import TestClient
    from pokerbot.web import six_server

    # raise_server_exceptions=False: a route crash must register as a 500 (counted), not kill the harness
    client = TestClient(six_server.app, raise_server_exceptions=False)
    used_paths: set[str] = set()
    arms = []
    for profile in DRIVER_PROFILES:
        for mode in MODES:
            arms.append(run_arm(client, six_server, profile, mode, hands,
                                ARM_SEEDS[profile], used_paths))
    # report probes while the LAST session is still live
    report_ep = _probe(client, [("POST", "/api/report"), ("GET", "/api/report")])
    analyze = _probe(client, [("POST", "/api/analyze")])
    report_direct = _report_direct(arms)
    RESULTS.update({"arms": arms, "hands_requested": hands, "report_ep": report_ep,
                    "analyze": analyze, "report_direct": report_direct,
                    "bot_fallbacks": getattr(six_server, "BOT_FALLBACKS", None)})
    return RESULTS


def _report_direct(arms) -> dict:
    """trainer_report.report() (P1-E, parallel builder) — import guarded: absent -> WARN later."""
    try:
        from pokerbot.coach import trainer_report
    except Exception as e:  # noqa: BLE001 — module is built in parallel; absence is a WARN, not a crash
        return {"status": "absent", "detail": repr(e)}
    last = next((a for a in reversed(arms) if a["session_path"]), None)
    if last is None:
        return {"status": "absent", "detail": "no session played"}
    try:
        import inspect
        n_params = len(inspect.signature(trainer_report.report).parameters)
        args = [Path(last["session_path"])]
        if n_params >= 2:                       # shipped signature: report(session_path, decisions_path)
            args.append(Path(last["decisions_path"]))
        rep = trainer_report.report(*args)
        ok = isinstance(rep, dict) and bool(rep)
        return {"status": "ok" if ok else "fail", "detail": f"keys={sorted(rep)[:8]}" if ok else "empty"}
    except Exception as e:  # noqa: BLE001 — a raising report() is exactly what this gate must catch
        return {"status": "fail", "detail": repr(e)}


def _graded(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("grade") in GRADE_VOCAB]


def _error_rate(records: list[dict]) -> float | None:
    """teuer+leak share of graded decisions. Prefers the planned P3-D helper when it exists
    (shipped signature: error_rate(records) -> (rate, n))."""
    try:
        from pokerbot.coach.difficulty import error_rate  # planned sibling module (P3-D)
        res = error_rate(records)
        return float(res[0]) if isinstance(res, tuple) else float(res)
    except Exception:  # noqa: BLE001 — parallel build; local definition is the documented fallback
        g = _graded(records)
        if not g:
            return None
        return sum(1 for r in g if r["grade"] != "ok") / len(g)


# --------------------------------------------------------------------------- checks (gate criteria)
@check("zero_crash")
def _zero_crash():
    arms = RESULTS["arms"]
    crashes = [c for a in arms for c in a["crashes"]]
    if crashes:
        return f"{len(crashes)} non-200/driver failures, first: {crashes[0]}"
    short = [a for a in arms if a["hands"] < RESULTS["hands_requested"]]
    if short:
        a = short[0]
        return f"arm {a['profile']}/{a['mode']} completed only {a['hands']}/{RESULTS['hands_requested']} hands"
    fb = RESULTS.get("bot_fallbacks")
    if fb not in (None, 0):    # BOT_FALLBACKS counter is server-side instrumentation (may not exist yet)
        return f"BOT_FALLBACKS={fb} (bots silently degraded to check/call)"
    return None


@check("decisions_schema")
def _decisions_schema():
    all_recs = [r for a in RESULTS["arms"] for r in a["decisions"]]
    if not all_recs:
        return "WARN: kein Decision-Log gefunden (P0 noch nicht verdrahtet) — Check uebersprungen"
    bad = [r for r in all_recs
           if r.get("grade") not in GRADE_VOCAB or not str(r.get("erklaerung_kurz") or "").strip()]
    if bad:
        return (f"{len(bad)}/{len(all_recs)} records ohne gueltiges grade/erklaerung_kurz, "
                f"z.B. hand_id={bad[0].get('hand_id')} grade={bad[0].get('grade')!r}")
    missing_soft = [k for k in ("hand_id", "ts", "street", "spot_fp", "human_action", "mode")
                    if any(k not in r for r in all_recs)]
    if missing_soft:
        return f"WARN: grade/erklaerung_kurz ok, aber Plan-Keys fehlen teils: {missing_soft}"
    return None


@check("grade_latency")
def _grade_latency():
    ms = [float(r["grade_ms"]) for a in RESULTS["arms"] for r in a["decisions"]
          if isinstance(r.get("grade_ms"), (int, float))]
    if not ms:
        return "WARN: keine grade_ms-Felder (Grader noch nicht verdrahtet) — Check uebersprungen"
    med = statistics.median(ms)
    RESULTS["latency"] = {"grade_p50_ms": round(med, 1),
                          "grade_p95_ms": round(sorted(ms)[max(0, int(0.95 * len(ms)) - 1)], 1),
                          "n": len(ms)}
    if med >= MEDIAN_GRADE_MS_BUDGET:
        return f"median grade_ms {med:.0f} >= Budget {MEDIAN_GRADE_MS_BUDGET}"
    return None


@check("grade_distribution_sanity")
def _grade_distribution_sanity():
    per_profile: dict[str, list[dict]] = {p: [] for p in DRIVER_PROFILES}
    for a in RESULTS["arms"]:
        per_profile[a["profile"]].extend(a["decisions"])
    floor = RESULTS.get("min_graded", MIN_GRADED_FOR_SANITY)
    rates = {}
    for p, recs in per_profile.items():
        g = _graded(recs)
        if len(g) < floor:
            return (f"WARN: nur {len(g)} graded decisions fuer '{p}' (< {floor}) — "
                    "Sanity nicht belastbar, --hands erhoehen")
        rates[p] = _error_rate(recs)
    RESULTS["error_rates"] = {p: round(v, 4) for p, v in rates.items() if v is not None}
    if rates["station"] <= rates["tag"]:
        return (f"error_rate(station)={rates['station']:.3f} <= error_rate(tag)={rates['tag']:.3f} "
                "— Grader-Sanity verletzt (station muss schlechter benotet werden)")
    return None


@check("feedback_nonempty")
def _feedback_nonempty():
    arms = RESULTS["arms"]
    probes = [a["feedback"] for a in arms if a["feedback"] is not None]
    if not probes and not any(a["coach_seen"] for a in arms):
        return "WARN: kein Feedback-Endpoint und kein view.coach (P1 noch nicht verdrahtet)"
    for pr in probes:
        if pr["status"] == 200:
            body = pr["json"]
            if not (str(body.get("html") or "").strip() or str(body.get("text") or "").strip()):
                return f"{pr['url']} liefert 200 aber leeres html/text"
        elif pr["status"] not in (400,):
            return f"{pr['method']} {pr['url']} -> {pr['status']}"
    if probes and all(pr["status"] == 400 for pr in probes) and not any(a["coach_seen"] for a in arms):
        return "WARN: Feedback-Endpoint existiert, liefert aber nach Handende nur 400 (Grader-Wiring pruefen)"
    return None


@check("report_builds")
def _report_builds():
    direct = RESULTS["report_direct"]
    if direct["status"] == "fail":
        return f"trainer_report.report() failed: {direct['detail']}"
    an = RESULTS["analyze"]
    if an is None or an["status"] != 200:
        return f"/api/analyze -> {an['status'] if an else 'absent'} (existierende Route muss 200 liefern)"
    stats = (an["json"] or {}).get("stats") or {}
    if not stats.get("hands"):
        return f"/api/analyze stats.hands leer: {stats}"
    if direct["status"] == "absent":
        return f"WARN: trainer_report (P1-E) noch nicht importierbar ({direct['detail'][:80]})"
    rep = RESULTS.get("report_ep")
    if rep is None:
        return "WARN: /api/report noch nicht verdrahtet (Analyze-Fallback ist gruen)"
    return None


@check("mode_toggle")
def _mode_toggle():
    arms = RESULTS["arms"]
    if all(a["mode_seen"] == "__absent__" for a in arms):
        return "WARN: view.mode fehlt (P0-0 Modus-Umschalter noch nicht verdrahtet)"
    wrong = [a for a in arms if a["mode_seen"] != "__absent__" and a["mode_seen"] != a["mode"]]
    if wrong:
        a = wrong[0]
        return f"mode angefragt '{a['mode']}' aber view.mode='{a['mode_seen']}'"
    return None


@check("replay_reconstructs")
def _replay_reconstructs():
    probes = [a["replay"] for a in RESULTS["arms"] if a["replay"] is not None]
    if not probes:
        return "WARN: /api/replay/last noch nicht verdrahtet (P2-5)"
    for pr in probes:
        if pr["status"] == 200:
            steps = (pr["json"] or {}).get("steps")
            if not steps:
                return "/api/replay/last 200 aber keine steps"
        elif pr["status"] != 400:
            return f"GET /api/replay/last -> {pr['status']}"
    return None


# --------------------------------------------------------------------------- runner
def _evaluate() -> tuple[dict, int]:
    outcomes = {}
    fails = 0
    for name, fn in CHECKS:
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001 — a crashing check is a FAIL with its traceback repr
            res = f"check crashed: {e!r}"
        if res is None:
            outcomes[name] = "PASS"
            print(f"  PASS  {name}")
        elif isinstance(res, str) and res.startswith("WARN"):
            outcomes[name] = res
            print(f"  WARN  {name}: {res[5:].lstrip(': ')}")
        else:
            outcomes[name] = res
            fails += 1
            print(f"  FAIL  {name}: {res}")
    return outcomes, fails


def _selftest() -> int:
    """3 Haende (tag/gto) durch den echten Stack, falls six_server importierbar — sonst sauberer SKIP.
    Bewusst OHNE Grading-Gates (mid-integration): nur der Treiber + zero-crash."""
    _bootstrap()
    try:
        from fastapi.testclient import TestClient
        from pokerbot.web import six_server
    except Exception as e:  # noqa: BLE001 — selftest must skip cleanly without the server stack
        print(f"SELFTEST SKIP: six_server nicht importierbar ({e!r})")
        return 0
    client = TestClient(six_server.app, raise_server_exceptions=False)
    arm = run_arm(client, six_server, "tag", "gto", 3, ARM_SEEDS["tag"], set())
    assert arm["hands"] == 3, f"expected 3 hands, got {arm['hands']}"
    assert not arm["crashes"], f"crashes: {arm['crashes']}"
    # BINDING normalization is unit-checked here (no server needed for the assert itself)
    a, amt = normalize_action({"action": "bet", "amount": 50},
                              {"can_raise": True, "raise_min": 200, "raise_max": 10000})
    assert (a, amt) == ("raise", 200), f"bet->raise clamp broken: {(a, amt)}"
    a, amt = normalize_action({"action": "raise", "amount": 99999},
                              {"can_raise": True, "raise_min": 200, "raise_max": 10000})
    assert (a, amt) == ("raise", 10000), f"raise_max clamp broken: {(a, amt)}"
    a, amt = normalize_action({"action": "raise", "amount": 400},
                              {"can_raise": False, "can_call": True})
    assert (a, amt) == ("call", None), f"can_raise=False degrade broken: {(a, amt)}"
    print("SELFTEST PASS: 3 Haende, 0 Crashes, Normalisierung ok "
          f"(decisions gefunden: {len(arm['decisions'])})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("hands_pos", nargs="?", type=int, default=None, metavar="hands")
    ap.add_argument("--hands", type=int, default=None)
    ap.add_argument("--deep", action="store_true", help=f"{DEEP_HANDS} Haende pro Arm (Pre-Release-Bar)")
    ap.add_argument("--json", dest="json_path", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    hands = DEEP_HANDS if args.deep else (args.hands or args.hands_pos or DEFAULT_HANDS)
    RESULTS["min_graded"] = MIN_GRADED_FOR_SANITY_DEEP if args.deep else MIN_GRADED_FOR_SANITY
    try:    # measure the WARMED path the user actually experiences (the server prewarms at start, P0-5)
        from pokerbot.coach import grader
        grader.prewarm()
    except Exception:  # noqa: BLE001 — prewarm is an optimization, never a gate
        pass
    t0 = time.perf_counter()
    run_all(hands)
    outcomes, fails = _evaluate()
    n_dec = sum(len(a["decisions"]) for a in RESULTS["arms"])
    summary = {"checks": outcomes, "hands": hands,
               "hands_played": sum(a["hands"] for a in RESULTS["arms"]),
               "decisions_n": n_dec,
               "error_rates": RESULTS.get("error_rates", {}),
               "latency": RESULTS.get("latency", {}),
               "bot_fallbacks": RESULTS.get("bot_fallbacks"),
               "wall_s": round(time.perf_counter() - t0, 1),
               "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    if args.json_path:
        p = Path(args.json_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON -> {p}")
    warns = sum(1 for v in outcomes.values() if isinstance(v, str) and v.startswith("WARN"))
    print(f"AUTOTEST: {len(CHECKS) - fails - warns} PASS / {warns} WARN / {fails} FAIL  "
          f"({summary['hands_played']} Haende, {n_dec} decisions, {summary['wall_s']}s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
