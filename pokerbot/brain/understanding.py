"""The consolidated POKER-UNDERSTANDING layer — ONE coherent strategic read of ANY spot, so the brain reasons well
even on spots the solver never solved.

WHY (the project's core gap): the brain (Claude or GLM) drives the engine via program-of-thought, but its *judgment*
is only as good as what it UNDERSTANDS about the spot. Solved spots are rare (TexasSolver covers ~15-40%, 6-76s each);
the vast majority of real decisions are UNSOLVED, and there the brain must generalize from poker first principles. Those
principles already live in the engine — but scattered: `api.spr`/`pot_odds`/`mdf`/`required_equity` (geometry),
`api.board_texture` + `api.hand_rank` (texture + the made-hand read), the line (initiative), and the MEASURED GTO
heuristics (river bets skew small, c-bet small-and-often on dry boards, defend to MDF, jam-discipline). This module
FUSES them into a single engine-computed NL block — no solve required — so the brain has the full strategic frame on
every spot. It is the shared seam: `format_spot` appends it (gated `POKERB_UNDERSTANDING`, default OFF), so BOTH brains
benefit and the baseline stays byte-identical + A/B-able.

Public API: `strategic_read(spot) -> str`. Everything is a deterministic function of the engine primitives.
"""
from __future__ import annotations

from pokerbot.brain import api

# --- Measured GTO heuristics as NAMED priors (grounded by this repo's GTOW/solver measurements; tunable) ----------
RIVER_BET_MEDIAN_X = 0.33     # measured 2026-06-29: solver OOP river-lead bet median ~0.33x pot (0.25x most common)
RIVER_CHECK_RATE = 0.58       # measured 2026-06-29: solver checks ~58% of OOP river decisions (5 boards x 2 pot-types)
SPR_COMMITTED = 1.0           # SPR <= this -> stack-committed; get-it-in math dominates, fold equity is gone
SPR_DEEP = 6.0                # SPR >= this -> deep; implied odds + maneuverability matter, avoid bloating marginal pots
STRONG_MADE = 0.62            # hand_rank strength (= 1 - treys/7462): ~0.62+ is two-pair-or-better -> value territory
MEDIUM_MADE = 0.40            # ~0.40-0.62 is a decent pair/marginal made hand -> bluff-catch / thin value, pot control

# Postflop action order, first..last to act. The LAST active player to act is most in position (the BTN).
_POSTFLOP_ORDER = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]


def strategic_read(spot) -> str:
    """The consolidated understanding block (NL, engine-computed). Always returns a non-empty frame for a live spot."""
    parts = [_geometry(spot), _hand_read(spot), _initiative(spot), _principle(spot)]
    parts = [p for p in parts if p]
    body = "\n".join("- " + p for p in parts)
    return "STRATEGIC READ (engine-computed — reason from this even where no solve exists):\n" + body


# ---------------------------------------------------------------- helpers (each small + single-purpose)
def _in_position(spot) -> bool:
    """Hero is IP iff every still-active villain acts BEFORE hero postflop (hero is last to act)."""
    rank = {p: i for i, p in enumerate(_POSTFLOP_ORDER)}
    hero = rank.get(spot.hero_pos, 0)
    others = [rank.get(s["pos"], -1) for s in spot.seats if not s["folded"] and s["seat"] != spot.hero_seat]
    return all(hero > o for o in others) if others else True


def _effective_stack_bb(spot) -> float:
    """Effective stack (bb) = min(hero, the largest active villain) — the stack that actually governs SPR/commitment."""
    hero = next((s for s in spot.seats if s["seat"] == spot.hero_seat), None)
    if hero is None:
        return 0.0
    villains = [s["stack"] for s in spot.seats if not s["folded"] and s["seat"] != spot.hero_seat]
    eff = min(hero["stack"], max(villains)) if villains else hero["stack"]
    return round(eff / spot.bb, 1)


def _commitment(spr: float) -> str:
    if spr <= SPR_COMMITTED:
        return "committed: get-it-in math, no fold equity"
    if spr >= SPR_DEEP:
        return "deep: implied odds + maneuver, don't bloat marginal pots"
    return "medium: one big bet commits"


def _geometry(spot) -> str:
    """SPR + position + the exact price to continue (required equity + MDF) — the spot's hard numbers."""
    eff, pot_bb = _effective_stack_bb(spot), spot.b(spot.pot)
    bits = ["in position" if _in_position(spot) else "out of position", f"effective {eff}bb"]
    if eff <= 0:                                                # facing/holding an all-in -> no SPR, stacks are committed
        bits.append("all-in decision (stacks committed)")
    elif pot_bb > 0:
        s = api.spr(eff, pot_bb)
        bits.append(f"SPR {s:.1f} ({_commitment(s)})")
    if spot.to_call > 0:
        req = api.required_equity(spot.to_call, spot.pot)
        bits.append(f"facing {spot.b(spot.to_call)}bb -> need {req * 100:.0f}% equity to call")
        pot_pre = spot.pot - spot.to_call                       # MDF is vs the bet into the PRE-bet pot
        if pot_pre > 0:
            bits.append(f"MDF {api.mdf(spot.to_call, pot_pre) * 100:.0f}% (don't over-fold)")
    return "Geometry: " + ", ".join(bits) + "."


def _hand_tier(strength: float) -> str:
    if strength >= STRONG_MADE:
        return "strong (value)"
    if strength >= MEDIUM_MADE:
        return "marginal (bluff-catch / thin value)"
    return "weak (bluff or give-up)"


def _draw_note(tex: dict, complete: bool) -> str:
    """Coordination note. On the river (complete board) draws are MADE, not 'live' — word it honestly."""
    suffix = "possible" if complete else "draws live"
    notes = []
    if tex.get("monotone") or tex.get("twotone"):
        notes.append(f"flush {suffix}")
    if tex.get("connected"):
        notes.append(f"straight {suffix}")
    return ", ".join(notes)


def _hand_read(spot) -> str:
    """The made-hand strength vs the board texture — anchored on the EXACT engine evaluation (api.hand_rank)."""
    if spot.street == "preflop" or len(spot.board) < 3:
        return ""
    cat, strength = api.hand_rank(spot.hero_hole, spot.board)
    tex = api.board_texture(spot.board)
    wet = tex.get("monotone") or tex.get("twotone") or tex.get("connected")
    out = f"Hand vs board: {cat} (strength {strength:.2f} = {_hand_tier(strength)}) on a {'wet/dynamic' if wet else 'dry/static'} board"
    draws = _draw_note(tex, len(spot.board) >= 5)
    return out + (f"; {draws}." if draws else ".")


def _initiative(spot) -> str:
    """Who holds the preflop lead + the rough range-advantage read (aggressor favored on high/dry boards)."""
    pre = [a for a in spot.line if a["street"] == "preflop" and a["action"] in ("bet", "raise")]
    if not pre:
        return ""
    who = "you hold" if pre[-1].get("hero") else "villain holds"
    fav = ""
    if len(spot.board) >= 3:
        tex = api.board_texture(spot.board)
        if tex.get("high") and not (tex.get("connected") or tex.get("monotone")):
            fav = " — the aggressor's range is favored here (bet small, high-frequency)"
        else:
            fav = " — the board favors the caller (more two-pair/sets); size down / check more"
    return f"Initiative: {who} the preflop lead{fav}."


def _principle(spot) -> str:
    """The MEASURED GTO heuristic for THIS spot type — the generalization that survives where no solve exists."""
    if spot.to_call > 0:
        return ("Facing a bet: continue by equity vs the required price, defend toward MDF with your bluff-catchers; "
                "vs an all-in decide by the math (api.preflop_mix / equity >= required), never reflex-call a premium.")
    if spot.street == "river":
        return (f"River lead: solver river bets skew SMALL (median ~{RIVER_BET_MEDIAN_X:.2f}x pot, check "
                f"~{RIVER_CHECK_RATE * 100:.0f}%) — value-bet thin and small; size up only when polarized (nuts / air).")
    if spot.street in ("flop", "turn"):
        return ("With the lead: bet small + high-frequency on dry boards (range advantage), polarize on wet boards; "
                "without it, check more and realize equity in position rather than bloating the pot.")
    return "Preflop: play the exact blueprint (api.preflop_mix) when covered; position + initiative drive postflop EV."
