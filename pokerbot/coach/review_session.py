"""Personal GTO coaching over the user's OWN CoinPoker hands (docs/ROADMAP.md §B — the MVP).

Pipeline: CoinPoker HH -> per-Hero-decision Spots (pokerbot/coach/coinpoker.py) -> engine grounding (format_spot +
understanding.strategic_read + api equity) -> Claude coaches each decision, GTO-anchored + personalized to the user's
tracked leaks -> a Markdown report + a leak rollup. Claude = PC-hub only; hands stay local; cite the engine's exact
numbers, no hollow praise (per CLAUDE.md). Per-session bb/100 is noise — the value is the per-decision grading + the
cross-session leak trend.

  python -m pokerbot.coach.review_session --hh "<path>" --stakes 2,5 --limit 25 --out data/coach/report.md
"""
from __future__ import annotations

import argparse
import os
from collections import Counter

import pokerbot.brain.format_spot as _F
from pokerbot.brain import api
from pokerbot.brain.format_spot import format_spot
from pokerbot.coach import coinpoker

# EXPLOIT-AWARE coaching. GTO is the BASELINE/insurance, NOT the verdict — a deviation is GOOD when it is +EV vs THIS
# pool, a LEAK only when -EV vs any reasonable range. The coach names the pool/villain read + the sticky-villain boundary.
_SYSTEM = (
    "You are a world-class poker coach reviewing a student's OWN hands for a SPECIFIC player pool, one decision at a "
    "time. You reason GTO-FIRST (the baseline/insurance) but you GRADE THE ACTUAL ACTION AS AN EXPLOIT vs the pool: a "
    "deviation from GTO is GOOD when it is +EV against this population, a LEAK only when it loses EV against ANY "
    "reasonable range. NEVER flag a profitable exploit as a leak; NEVER praise a true -EV play.\n\n"
    "You get the engine's EXACT numbers (the STRATEGIC READ: SPR, position, pot-odds, required equity, MDF, made-hand, "
    "texture) + an equity figure — cite them. INFER THE VILLAIN TYPE from their actions IN THIS HAND (passive/"
    "fit-or-fold vs sticky/aggressive) and judge the exploit against it.\n\n"
    "THE POOL (CoinPoker NL200/NL500): predominantly LOOSE-PASSIVE + FIT-OR-FOLD — over-folds to big bets/barrels "
    "(fears stacking off light), calls too wide preflop, rarely bluff-raises. A MINORITY are 'frantic'/STICKY (call/jam "
    "light, don't fold) — against THOSE, big sizing + barrels BACKFIRE. The student's EDGE is exploiting the fit-or-fold "
    "majority; his TAIL losses come from running the same aggression into the sticky minority.\n\n"
    "THE STUDENT (Princedarkness): a winning NL200/NL500 reg, adaptive exploit style — barrels scare cards, uses big "
    "sizing to leverage fold equity + fold out the field, plays speculative hands deep. His over-sizing/barrelling IS "
    "+EV vs the fit-or-fold majority (classify it as such!) — but flag the read-dependent / sticky-villain risk. His "
    "TRUE leaks (-EV vs anyone): dominated OUT-OF-POSITION offsuit preflop calls/3-bets (Q5s, JTo OOP), and "
    "'I'll win it back' loose calling. Be HONEST: no hollow praise, and no flagging a real edge as a leak. Write `why`, "
    "`vs_sticky` and `lesson` in GERMAN; keep the enum as given."
)
_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "gto_baseline": {"type": "string", "description": "What a GTO solver does here (the reference action + size/freq)."},
        "pool_read": {"type": "string", "description": "What the inferred villain TYPE (from their in-hand actions) likely does vs the student's action."},
        "classification": {"type": "string",
                           "enum": ["gto_optimal", "profitable_exploit", "read_dependent", "true_leak", "blunder"]},
        "why": {"type": "string", "description": "German, 1-3 sentences citing the engine numbers + the pool/villain read."},
        "vs_sticky": {"type": "string", "description": "German: does this BACKFIRE vs a sticky/frantic villain? (the boundary / the risk)."},
        "lesson": {"type": "string", "description": "One concrete German takeaway."},
    },
    "required": ["gto_baseline", "pool_read", "classification", "why", "vs_sticky", "lesson"],
}


def _equity_context(spot) -> str:
    """A grounded equity figure for the prompt: postflop = hero's hand vs a ~top-40% continuing range on this board."""
    if spot.street == "preflop" or len(spot.board) < 3:
        return ""
    try:
        eq = api.equity(spot.hero_hole, api.range_top(0.40), spot.board, iters=600)
        return f"\nEngine equity (your hand vs a ~top-40% range on this board): {eq * 100:.0f}%."
    except Exception:                                          # noqa: BLE001 — grounding is best-effort
        return ""


def coach_decision(dec, provider: str = "claude") -> tuple[dict, tuple]:
    """Ground one decision + ask a frontier model for a structured coaching verdict. Returns (verdict, (in, out)).
    Claude is the default; falls back to OpenAI (same coaching, the project's other frontier provider)."""
    _F.INCLUDE_UNDERSTANDING = True                            # the strategic read is the grounding the coach reasons on
    acted = dec.action + (f" to {dec.amount_bb}bb" if dec.amount_bb else "")
    user = (f"{format_spot(dec.spot)}{_equity_context(dec.spot)}\n\n"
            f"THE STUDENT ACTUALLY CHOSE: {acted}.\nReview this exact decision.")
    if provider == "openai":
        from research.llm import openai_json
        return openai_json(_SYSTEM, user, _SCHEMA, "coach_verdict", max_tokens=4000)
    from research.llm import claude_json
    v, (ti, to, _) = claude_json(_SYSTEM, user, _SCHEMA, max_tokens=2000, thinking=True)
    return v, (ti, to)


def _select(hands, stakes: set, limit: int, dates: set | None = None) -> list:
    """Curate the most instructive decisions: A-game stakes, biggest pots + postflop play first, capped at `limit`.
    If `dates` is given (a set of 'YYYY/MM/DD' strings), only hands from those days are considered."""
    scored = []
    for h in hands:
        if h.bb not in stakes or h.hero_seat is None:
            continue
        if dates and h.date not in dates:
            continue
        ds = coinpoker.hero_decisions(h)
        ds = [d for d in ds if not (d.action == "fold" and d.street == "preflop")]   # skip preflop auto-folds
        if not ds:
            continue
        maxpot = max(d.spot.pot for d in ds)
        postflop = any(d.street != "preflop" for d in ds)
        scored.append((postflop, maxpot, h.hid, ds))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)       # postflop-containing + biggest pots first
    out = []
    for _, _, hid, ds in scored:
        for d in ds:
            if len(out) >= limit:
                return out
            out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hh", required=True)
    ap.add_argument("--stakes", default="2,5", help="comma BB list (NL200=2, NL500=5)")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--provider", default="claude", choices=["claude", "openai"])
    ap.add_argument("--dates", default="", help="comma 'YYYY/MM/DD' list; empty = all days")
    ap.add_argument("--out", default="data/coach/report.md")
    a = ap.parse_args()

    hands = coinpoker.parse_file(a.hh)
    stakes = {float(x) for x in a.stakes.split(",")}
    dates = {d.strip() for d in a.dates.split(",") if d.strip()} or None
    decs = _select(hands, stakes, a.limit, dates)
    print(f"Coaching {len(decs)} decisions (stakes BB={sorted(stakes)}) ...")

    rows, tok_in, tok_out = [], 0, 0
    klass = Counter()
    for i, d in enumerate(decs):
        v, (ti, to) = coach_decision(d, a.provider)
        tok_in += ti; tok_out += to
        klass[v["classification"]] += 1
        rows.append((d, v))
        print(f"  [{i + 1}/{len(decs)}] hand #{d.hid} {d.street} {d.action}: {v['classification']}")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"# Coaching-Report — {len(decs)} Entscheidungen (exploit-bewusst)\n\n")
        f.write("## Klassifikation (GTO-Abweichung ≠ Leak)\n\n")
        for tag, n in klass.most_common():
            f.write(f"- **{tag}**: {n}\n")
        f.write(f"\n_Tokens: {tok_in} in / {tok_out} out._\n\n---\n\n")
        for d, v in rows:
            f.write(f"## Hand #{d.hid} — {d.street}: du {d.action}"
                    + (f" auf {d.amount_bb}bb" if d.amount_bb else "") + f"  →  **{v['classification'].upper()}**\n\n")
            f.write(f"- **GTO-Baseline:** {v['gto_baseline']}\n- **Pool/Villain-Read:** {v['pool_read']}\n")
            f.write(f"- **Warum:** {v['why']}\n- **Vs. sticky:** {v['vs_sticky']}\n- **Lektion:** {v['lesson']}\n\n")
    print(f"\nReport -> {a.out}\nKlassifikation: {dict(klass)}\nTokens: {tok_in} in / {tok_out} out")


if __name__ == "__main__":
    main()
