"""Session-Report ueber die EIGENEN Trainer-Logs (P1-E).

WHY: Nach einer Trainings-Session braucht der Mensch EINEN warmen, ehrlichen Blick zurueck:
wie viele Entscheidungen, welche Grade-Verteilung (ok/teuer/leak — NIE Ergebnisse graden,
docs/doctrine/TRAINER_DESIGN.md par.1), wo das wiederkehrende Leck sitzt, und der beste Moment EXPLIZIT
gefeiert (par.1.5). Format ist kontrolliert (session_log.build_hand_record + das P0
decision-Schema aus docs/doctrine/TRAINER_DESIGN.md par.4) — kein Parser noetig.

Input-Vertrag (key-tolerant via .get — P0-Drift-Panzerung):
- session JSONL: build_hand_record-Schema (session_log.py:8-32)
  {hand_no, button, sb, bb, human_seat, positions, hole, board,
   actions[{street, seat, action, amount, is_human}], result, net}
- decisions JSONL: trainer.decision.v1 (TRAINER_PLAN P0-1/P0-4)
  {hand_id, ts, street, human_action{action,amount}, legal{pot,...}, obs{bb,...},
   grade in {ok,teuer,leak}, grade_typ, erklaerung_kurz, oracle{action}|oracle_action, mode}

Run: python -m pokerbot.coach.trainer_report   (fuehrt _selftest aus, exit 1 bei FAIL)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

GRADES = ("ok", "teuer", "leak")          # pinned vocabulary (TRAINER_DESIGN par.1.2)
ERROR_GRADES = frozenset({"teuer", "leak"})
LEAK_TOP_N = 3                            # top grade_typ buckets shown in the report
LEARN_BAND = (0.10, 0.20)                 # adaptive error-rate band (TRAINER_DESIGN par.5)
DEFAULT_BB = 100                          # chips per bb (repo convention, CLAUDE.md)

def _de_num(x: float, nachkomma: int = 1) -> str:
    """Number formatting for the narrative (English decimal point since the 2026-09 translation;
    the name is kept for API stability — the selftest's sentence counter skips digit-adjacent dots)."""
    return f"{x:.{nachkomma}f}"


# street phrase as used after an action verb: "Call preflop" / "Call on the flop"
STREET_DE = {"preflop": "preflop", "flop": "on the flop", "turn": "on the turn", "river": "on the river"}
ACTION_DE = {"fold": "Fold", "check": "Check", "call": "Call", "bet": "Bet",
             "raise": "Raise", "allin": "All-in"}


# ---------------------------------------------------------------- loading

def _load_jsonl(path) -> list[dict]:
    recs: list[dict] = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a torn tail line must never kill the report
    except OSError:
        pass
    return recs


# ---------------------------------------------------------------- hand stats

def _matches_session_schema(rec: dict) -> bool:
    """Verify the compute_stats input contract (session_analysis.py:32-58 uses
    a['is_human']/a['street']/a['action'] unguarded) before delegating."""
    acts = rec.get("actions")
    if not isinstance(acts, list) or rec.get("human_seat") is None or "net" not in rec:
        return False
    return all(isinstance(a, dict) and {"is_human", "street", "action"} <= a.keys()
               for a in acts)


def _fallback_stats(recs: list[dict]) -> dict:
    """Direct vpip/pfr/wtsd/net_bb when the JSONL drifted from build_hand_record."""
    hands = len(recs)
    if not hands:
        return {"hands": 0}
    vpip = pfr = wtsd = 0
    net_bb = 0.0
    for rec in recs:
        hs = str(rec.get("human_seat", ""))
        bb = rec.get("bb") or DEFAULT_BB
        net = rec.get("net", {}) or {}
        net_bb += float(net.get(hs, 0)) / bb
        h_pf = [a for a in rec.get("actions", []) if isinstance(a, dict)
                and a.get("is_human") and a.get("street") == "preflop"]
        vpip += any(a.get("action") in ("call", "bet", "raise") for a in h_pf)
        pfr += any(a.get("action") in ("bet", "raise") for a in h_pf)
        folded = any(a.get("is_human") and a.get("action") == "fold"
                     for a in rec.get("actions", []) if isinstance(a, dict))
        if (rec.get("result") or {}).get("reason") == "showdown" and not folded:
            wtsd += 1
    return {"hands": hands,
            "vpip_pct": round(100 * vpip / hands, 1),
            "pfr_pct": round(100 * pfr / hands, 1),
            "went_to_showdown_pct": round(100 * wtsd / hands, 1),
            "net_bb": round(net_bb, 1)}


def _session_stats(recs: list[dict]) -> dict:
    if recs and all(_matches_session_schema(r) for r in recs):
        try:
            from pokerbot.analysis.session_analysis import compute_stats
            return compute_stats(recs)
        except Exception as e:  # noqa: BLE001 — stats must degrade, never crash the report
            print(f"trainer_report: compute_stats failed ({e!r}), fallback", file=sys.stderr)
    return _fallback_stats(recs)


# ---------------------------------------------------------------- decision digest

def _pot_bb(dec: dict) -> float:
    """Pot at decision time in bb (legal.pot is chips, table.py:131-149)."""
    pot = ((dec.get("legal") or {}).get("pot")
           or (dec.get("spot") or {}).get("pot")
           or (dec.get("obs") or {}).get("pot") or 0)
    bb = (dec.get("obs") or {}).get("bb") or DEFAULT_BB
    try:
        return float(pot) / float(bb)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _oracle_action(dec: dict) -> str:
    return dec.get("oracle_action") or (dec.get("oracle") or {}).get("action") or ""


def _grade_dist(decisions: list[dict]) -> dict:
    counts = Counter(d.get("grade") for d in decisions)
    return {g: counts.get(g, 0) for g in GRADES}


def _leak_top(decisions: list[dict]) -> list[dict]:
    """Top grade_typ buckets over non-ok decisions, count desc (ties alphabetical
    for determinism), each with one example erklaerung_kurz."""
    bad = [d for d in decisions if d.get("grade") in ERROR_GRADES]
    counts = Counter(d.get("grade_typ") or "unknown" for d in bad)
    beispiel = {}
    for d in bad:  # first occurrence in log order = deterministic example
        beispiel.setdefault(d.get("grade_typ") or "unknown",
                            d.get("erklaerung_kurz") or "")
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"grade_typ": typ, "count": n, "erklaerung_kurz": beispiel.get(typ, "")}
            for typ, n in ordered[:LEAK_TOP_N]]


def _pick_moments(decisions: list[dict]) -> tuple[dict | None, dict | None]:
    """best = the biggest-pot 'ok' decision (celebrated, par.1.5);
    teuerstes = the biggest-pot leak, else the biggest-pot teuer decision."""
    oks = [d for d in decisions if d.get("grade") == "ok"]
    leaks = [d for d in decisions if d.get("grade") == "leak"]
    teure = [d for d in decisions if d.get("grade") == "teuer"]
    best = max(oks, key=_pot_bb) if oks else None
    worst_pool = leaks or teure
    worst = max(worst_pool, key=_pot_bb) if worst_pool else None
    return best, worst


def _moment_satz(dec: dict) -> str:
    """Ein deterministischer Halbsatz, der einen Entscheidungs-Moment benennt."""
    street = STREET_DE.get(dec.get("street"), str(dec.get("street") or "?"))
    act = (dec.get("human_action") or {}).get("action") or "?"
    return f"{ACTION_DE.get(act, act)} {street} with {_de_num(_pot_bb(dec))} bb in the pot"


# ---------------------------------------------------------------- narrative

def _band_satz(error_rate: float, n: int) -> str:
    lo, hi = LEARN_BAND
    if n == 0:
        return "No graded decisions yet — the next session will deliver the data."
    pct = _de_num(100 * error_rate) + "%"
    if error_rate < lo:
        return (f"Your error rate is {pct} — below the 10–20% learning band, "
                "feel free to take on tougher opponents.")
    if error_rate <= hi:
        return f"Your error rate is {pct} — right in the 10–20% learning sweet spot."
    return (f"Your error rate is {pct} — above the learning band; no drama, "
            "we'll dial the difficulty down a notch.")


def _narrative_de(n_hands: int, n_decisions: int, dist: dict, error_rate: float,
                  leak_top: list[dict], best: dict | None, worst: dict | None) -> str:
    """Deterministische 4-6 Saetze: warm, progress-orientiert, nie Ergebnis-gradend."""
    saetze = [f"Nice session — {n_hands} hands played and {n_decisions} "
              "decisions graded honestly",
              f"Of those, {dist['ok']} were solid, {dist['teuer']} costly "
              f"and {dist['leak']} real leaks",
              _band_satz(error_rate, n_decisions).rstrip(".")]
    if best is not None:
        saetze.append(f"Your best moment: {_moment_satz(best)} — keep it up")
    if leak_top:
        top = leak_top[0]
        grund = f" ({top['erklaerung_kurz'].rstrip('.')})" if top["erklaerung_kurz"] else ""
        saetze.append(f"Most frequent theme: {top['grade_typ']} "
                      f"({top['count']}x){grund}".rstrip("."))
    elif worst is None:
        saetze.append("No recurring costly mistake this session — strong")
    if worst is not None:
        alt = _oracle_action(worst)
        alt_txt = f" — alternative: {ACTION_DE.get(alt, alt)}" if alt else ""
        saetze.append(f"The most expensive mistake was {_moment_satz(worst)}{alt_txt}")
    return ". ".join(saetze[:6]) + "."


# ---------------------------------------------------------------- public API

def report(session_path, decisions_path) -> dict:
    """Kompletter Session-Report ueber session_<sid>.jsonl + decisions_<sid>.jsonl."""
    hands = _load_jsonl(session_path)
    decisions = _load_jsonl(decisions_path)
    graded = [d for d in decisions if d.get("grade") in GRADES]
    dist = _grade_dist(graded)
    n_err = dist["teuer"] + dist["leak"]
    error_rate = n_err / len(graded) if graded else 0.0
    leak_top = _leak_top(graded)
    best, worst = _pick_moments(graded)
    return {
        "n_hands": len(hands),
        "n_decisions": len(graded),
        "grade_dist": dist,
        "error_rate": round(error_rate, 4),
        "leak_top": leak_top,
        "stats": _session_stats(hands),
        "best_moment": best,
        "teuerstes_moment": worst,
        "narrative_de": _narrative_de(len(hands), len(graded), dist, error_rate,
                                      leak_top, best, worst),
    }


def format_report_text(rep: dict) -> str:
    """Der Report als schlichter deutscher Textblock (Panel/Konsole/Log)."""
    dist = rep.get("grade_dist", {})
    stats = rep.get("stats", {})
    lines = ["=== Session Report ===",
             f"Hands: {rep.get('n_hands', 0)} · graded decisions: "
             f"{rep.get('n_decisions', 0)}",
             f"Grades: {dist.get('ok', 0)} ok · {dist.get('teuer', 0)} costly · "
             f"{dist.get('leak', 0)} leak "
             f"(error rate {100 * rep.get('error_rate', 0.0):.1f}%)"]
    stat_teile = [f"{label} {stats[key]}" for key, label in
                  (("vpip_pct", "VPIP%"), ("pfr_pct", "PFR%"),
                   ("went_to_showdown_pct", "WTSD%"), ("net_bb", "Net bb"),
                   ("bb_per_100", "bb/100"))
                  if stats.get(key) is not None]
    if stat_teile:
        lines.append("Stats: " + " · ".join(stat_teile))
    if rep.get("leak_top"):
        lines.append("Most expensive patterns:")
        for item in rep["leak_top"]:
            bsp = f" — {item['erklaerung_kurz']}" if item.get("erklaerung_kurz") else ""
            lines.append(f"  {item['count']}x {item['grade_typ']}{bsp}")
    if rep.get("best_moment"):
        lines.append(f"Best moment: {_moment_satz(rep['best_moment'])}")
    if rep.get("teuerstes_moment"):
        lines.append(f"Most expensive mistake: {_moment_satz(rep['teuerstes_moment'])}")
    lines.append("")
    lines.append(rep.get("narrative_de", ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- selftest

def _synth_hand(hand_no: int, human_pf: str, showdown: bool, net_h: int) -> dict:
    """One build_hand_record-shaped fixture hand (session_log.py:8-32)."""
    actions = [{"street": "preflop", "seat": 1, "pos": "BTN", "action": "raise",
                "amount": 300, "is_human": False},
               {"street": "preflop", "seat": 0, "pos": "BB", "action": human_pf,
                "amount": 300 if human_pf == "call" else None, "is_human": True}]
    if human_pf != "fold":
        actions.append({"street": "flop", "seat": 0, "pos": "BB", "action": "check",
                        "amount": None, "is_human": True})
    return {"hand_no": hand_no, "button": 1, "sb": 50, "bb": 100, "human_seat": 0,
            "positions": {"0": "BB", "1": "BTN"},
            "hole": {"0": ["As", "Kd"], "1": ["??", "??"]},
            "board": ["7h", "8d", "2c"] if human_pf != "fold" else [],
            "actions": actions,
            "result": {"reason": "showdown" if showdown else "fold"},
            "net": {"0": net_h, "1": -net_h}}


def _synth_decision(hand_no: int, street: str, action: str, grade: str,
                    grade_typ: str, pot: int) -> dict:
    return {"schema": "trainer.decision.v1", "session_id": "selftest",
            "hand_id": f"selftest-{hand_no}", "ts": float(hand_no), "mode": "gto",
            "street": street, "human_action": {"action": action, "amount": None},
            "legal": {"pot": pot, "to_call": 0}, "obs": {"bb": 100, "pot": pot},
            "grade": grade, "grade_typ": grade_typ,
            "erklaerung_kurz": f"Beispiel-{grade_typ}" if grade != "ok" else "",
            "oracle": {"action": "fold"}, "spot_fp": hand_no}


def _selftest() -> None:
    import tempfile
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        sess = Path(td) / "session_selftest.jsonl"
        decs = Path(td) / "decisions_selftest.jsonl"
        hands = [_synth_hand(1, "call", True, 650), _synth_hand(2, "fold", False, -100),
                 _synth_hand(3, "raise", False, 150), _synth_hand(4, "call", True, -400),
                 _synth_hand(5, "fold", False, -100)]
        # 8 graded: 5 ok, 2 teuer(pot_odds), 1 leak(pot_odds->no: mix typs) -> err 3/8
        ds = [_synth_decision(1, "preflop", "call", "ok", "", 250),
              _synth_decision(1, "flop", "check", "ok", "", 650),
              _synth_decision(2, "preflop", "fold", "ok", "", 250),
              _synth_decision(3, "preflop", "raise", "ok", "", 250),
              _synth_decision(4, "preflop", "call", "ok", "", 250),
              _synth_decision(4, "flop", "call", "teuer", "pot_odds", 800),
              _synth_decision(4, "turn", "call", "teuer", "pot_odds", 1600),
              _synth_decision(4, "river", "call", "leak", "mdf", 3200),
              {"grade": "???", "street": "flop"}]  # unknown grade -> ignored
        sess.write_text("".join(json.dumps(h) + "\n" for h in hands), encoding="utf-8")
        decs.write_text("".join(json.dumps(d) + "\n" for d in ds), encoding="utf-8")

        rep = report(sess, decs)
        check("n_hands == 5", rep["n_hands"] == 5)
        check("n_decisions == 8 (unknown grade ignored)", rep["n_decisions"] == 8)
        check("grade_dist", rep["grade_dist"] == {"ok": 5, "teuer": 2, "leak": 1})
        check("error_rate == 0.375 (3 Dezimalen)",
              round(rep["error_rate"], 3) == 0.375)
        counts = [item["count"] for item in rep["leak_top"]]
        check("leak_top absteigend sortiert", counts == sorted(counts, reverse=True))
        check("leak_top[0] = pot_odds x2",
              rep["leak_top"][0] == {"grade_typ": "pot_odds", "count": 2,
                                     "erklaerung_kurz": "Beispiel-pot_odds"})
        check("stats via compute_stats (hands/vpip)",
              rep["stats"].get("hands") == 5 and rep["stats"].get("vpip_pct") == 60.0)
        check("best_moment = groesster ok-Pot",
              (rep["best_moment"] or {}).get("legal", {}).get("pot") == 650)
        check("teuerstes_moment = leak vor teuer",
              (rep["teuerstes_moment"] or {}).get("grade") == "leak")
        nar = rep["narrative_de"]
        check("narrative_de nicht leer", bool(nar.strip()))
        # sentence boundary = punctuation followed by whitespace/end ("12.5 bb" is not a boundary)
        n_saetze = len([s for s in re.split(r"[.!?]+(?=\s|$)", nar) if s.strip()])
        check(f"narrative_de 4-6 Saetze (ist {n_saetze})", 4 <= n_saetze <= 6)
        check("narrative_de englisch/warm ('Nice session')", "Nice session" in nar)
        check("deterministisch (2 Laeufe identisch)", rep == report(sess, decs))

        txt = format_report_text(rep)
        check("format_report_text nicht leer + Header",
              txt.startswith("=== Session Report ===") and "error rate 37.5%" in txt)

        # drifted schema -> fallback stats, no crash
        bad = Path(td) / "session_drift.jsonl"
        bad.write_text(json.dumps({"hand_no": 1, "actions": [{"weird": 1}]}) + "\n",
                       encoding="utf-8")
        rep2 = report(bad, Path(td) / "missing.jsonl")
        check("Schema-Drift -> Fallback-Stats, keine Exception",
              rep2["stats"].get("hands") == 1 and rep2["n_decisions"] == 0)
        check("leere decisions -> narrative trotzdem vorhanden",
              bool(rep2["narrative_de"].strip()))

    print(("SELFTEST FAIL: " + ", ".join(fails)) if fails else "SELFTEST OK")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    _selftest()
