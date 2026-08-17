"""WS5: GTO Wizard AI Benchmark adapter. Maps the researcher API (GameServiceResponse<->ActRequest) to our
engine so the unified MVP (PokerBot exploit-primary) can be benchmarked vs GTO Wizard AI (HUNL 200bb,
AIVAT-scored). GTO Wizard beat Slumbot +19.4 bb/100 -> this is the TRUE-opponent, definitive measurement.

VERIFIED against the cloned client (tools/gtow_client/src/models.py, June 2026):
  GameState : street, common_pot, total_pot, board_cards(str), is_hand_over, players[{name,stack,position,
              hole_cards:str|None}], legal_actions[{f,c,k,b}], raise_range{min,max}|None,
              action_history[str], has_gto_wizard_folded, winnings, aivat_score
  - HERO = the player whose hole_cards is not None (villain's is None).
  - action_history tokens: 'f' fold, 'c' call, 'k' check, 'bX' bet-to-X (CUMULATIVE on the round), '_' round end.
  - to_call = the committed-delta max(0, max(c_h,c_v)-c_h) (total_pot-common_pot INFLATED preflop — fixed 2026-06-21,
    env POKERB_TOCALL_FIX=0 restores the old buggy form for the A/B). HU: SB = button. winnings/aivat on the final state.
  ActRequest: action in {f,c,k,b}, amount:int|None (REQUIRED for 'b'; cumulative street bet).

PokerBotAgent.act_dict(gsr_dict) is the pure mapping (the client wraps it in async + Pydantic). A final legality
guard guarantees we never emit an illegal action. Run offline self-test (no key): python -m pokerbot.benchmark.gtowizard
"""
from __future__ import annotations

import os

from pokerbot import config
from pokerbot.strategy.gto_mode import apply as _apply_gto_mode

# GTOW mode (S1, plan 2026-07-04): POKERB_GTO_MODE=1 expands the anti-exploitability profile BEFORE any
# pokerbot.strategy import (postflop/advisor read their flags at import time; PokerBot is imported lazily below).
_apply_gto_mode()

_STREETS = ["preflop", "flop", "turn", "river"]


def parse_cards(s: str | None) -> list[str]:
    """'AsKdQh' -> ['As','Kd','Qh']; None/'' -> []."""
    s = (s or "").strip()
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def _parse_history(action_history, button_seat, blinds):
    """Reconstruct our engine history + per-street committed from the flat action_history. Players alternate
    from the street's first actor (preflop=button/SB, postflop=non-button); '_' ends a round. 'bX' is the
    CUMULATIVE bet on the round. Returns (history, committed_hero, committed_villain, current_street_idx)."""
    hist = []
    committed = {0: 0.0, 1: 0.0}
    # AUDIT FIX (2026-07-05, confirmed 3x): the live API returns blinds=[BB,SB]=[100,50] (thrice-documented
    # by the earlier 2x-bb fix) but this positional unpack assumed [SB,BB] -> the preflop blind init was
    # INVERTED in every live run (BB-facing-open to_call 175 instead of 125 = +7pp required equity).
    # Unpack by MAGNITUDE — order-agnostic, correct for both the live API and older [SB,BB] fixtures.
    sb, bb = (min(blinds), max(blinds)) if blinds else (0, 0)
    committed[button_seat] = float(sb)            # HU blinds (preflop)
    committed[1 - button_seat] = float(bb)
    si, actor = 0, button_seat                    # preflop first to act = button (SB)
    bet_made = False                              # has an aggressive action opened this round
    for tok in action_history:
        if tok == "_":                            # round end -> advance street, reset committed + first actor
            hist.append({"action": "deal", "street": _STREETS[min(si + 1, 3)]})
            si += 1
            committed = {0: 0.0, 1: 0.0}
            actor = 1 - button_seat               # postflop first to act = non-button (BB)
            bet_made = False
            continue
        st = _STREETS[min(si, 3)]
        if tok == "f":
            hist.append({"player": actor, "action": "fold", "street": st})
        elif tok == "c":
            committed[actor] = max(committed.values())
            hist.append({"player": actor, "action": "call", "street": st})
        elif tok == "k":
            hist.append({"player": actor, "action": "check", "street": st})
        elif tok and tok[0] == "b":
            try:
                committed[actor] = float(tok[1:]) if tok[1:] else committed[actor]
            except ValueError:
                pass
            # BUG-HUNT FIX (major, PRE-EXISTING): the entry carried NO amount, so resolver._match_label got
            # amount=None -> "(amount or 0)" -> nearest-to-ZERO -> it navigated EVERY villain bet/raise onto the
            # SMALLEST tree arm (defending vs a 1.5x overbet as if it were 0.35x). Also made the L2b size
            # injection a silent no-op vs GTOW. `to` = the cumulative street bet-to, matching the engine's history.
            hist.append({"player": actor, "action": ("raise" if (bet_made or si == 0) else "bet"),
                         "street": st, "to": committed[actor]})
            bet_made = True
        actor = 1 - actor                         # turn passes to the other player
    return hist, committed[0], committed[1], si


def gtow_to_state(gsr: dict) -> dict:
    """Full GameServiceResponse dict -> our engine state (hero forced to index 0). gsr has 'game' + 'game_state'."""
    game = gsr.get("game") or {}
    gs = gsr.get("game_state") or gsr             # tolerate being handed game_state directly
    blinds = [int(x) for x in (game.get("blinds") or [50, 100])]
    bb = max(blinds) if blinds else 100        # the BIG blind = max (GTOW returns [BB, SB]=[100,50]; blinds[1]=SB=50 was a 2x-bb bug)
    start = int(game.get("starting_stack") or 20000)
    players = gs.get("players") or []
    # HERO = the seat with hole_cards populated (villain's is None)
    hseat = next((i for i, p in enumerate(players) if p.get("hole_cards")), 0)
    hero = players[hseat] if players else {}
    vill = players[1 - hseat] if len(players) > 1 else {}
    hero_is_button = str(hero.get("position", "")).upper() in ("SB", "BTN", "BU", "D")
    button_eng = 0 if hero_is_button else 1       # engine: hero=0

    board = parse_cards(gs.get("board_cards", ""))
    street = gs.get("street") or (_STREETS[min(len(board) - 2, 3)] if len(board) >= 3 else "preflop")
    common_pot = int(gs.get("common_pot") or 0)
    total_pot = int(gs.get("total_pot") or common_pot)

    # Reconstruct history in ENGINE seat space (hero=0). The actual play order is button-first preflop /
    # non-button-first postflop, which _parse_history replicates via button_seat -> the flat action_history
    # attributes correctly (first preflop token = the button = engine seat `button_eng`). c_h/c_v = the per-street
    # committed (incl. the preflop blinds).
    hist_eng, c_h, c_v, _si = _parse_history(gs.get("action_history") or [], button_seat=button_eng, blinds=blinds)
    # to_call = the UNMATCHED delta from the committed amounts, NOT total_pot - common_pot. The latter INFLATED
    # preflop to_call to the WHOLE pot (GTOW's common_pot excludes the blinds during active preflop betting), so the
    # logged required_equity ran ~0.22 too high in 100% of preflop facing-bet spots (study_grade audit 2026-06-21 — a
    # co-cause of the GLM preflop over-fold; it's why blueprint-routing fixed it = bypasses this input). The
    # committed-delta is correct on EVERY street (postflop common_pot already matched it, so this is a no-op there).
    # POKERB_TOCALL_FIX=0 restores the old buggy form (the paired GTOW A/B that measures this fix's bb/100 effect).
    if os.environ.get("POKERB_TOCALL_FIX", "1") == "1":
        to_call = max(0, int(max(c_h, c_v)) - int(c_h))
    else:
        to_call = max(0, total_pot - common_pot)

    la_codes = [a.lower() for a in (gs.get("legal_actions") or [])]
    rr = gs.get("raise_range") or {}
    rmin = rr.get("min") if isinstance(rr, dict) else None
    rmax = rr.get("max") if isinstance(rr, dict) else None
    hero_stack = int(hero["stack"]) if hero.get("stack") is not None else start  # NOT `or start`: a legit all-in 0 must stay 0
    legal = {"to_act": 0, "to_call": int(to_call), "pot": int(total_pot),
             "can_fold": "f" in la_codes, "can_check": "k" in la_codes, "can_call": "c" in la_codes,
             "call_amount": int(to_call), "can_raise": "b" in la_codes, "is_bet": ("k" in la_codes),
             "raise_min": int(rmin) if rmin is not None else None,
             "raise_max": int(rmax) if rmax is not None else hero_stack + int(c_h)}  # all-in raise-TO = behind + already-in
    vill_stack = int(vill["stack"]) if vill.get("stack") is not None else start  # 0 = all-in; the old `or start` hid it
    return {
        "street": street, "board": board, "pot": int(total_pot), "bb": int(bb),
        "current_bet": int(max(c_h, c_v)) if to_call > 0 else 0, "button": button_eng,
        # hand_id: keys the L2a per-hand line-draw (H1 fix) — 8 concurrent hands share ONE bot instance
        "hand_id": gsr.get("hand_id"),
        "hand_no": 0, "history": hist_eng, "to_act": 0, "hand_over": bool(gs.get("is_hand_over")),
        "players": [
            {"idx": 0, "hole": parse_cards(hero.get("hole_cards")), "stack": hero_stack,
             "committed_street": int(c_h), "committed_total": int(start - hero_stack),
             "folded": False, "all_in": hero_stack == 0, "is_button": button_eng == 0},
            {"idx": 1, "hole": ["??", "??"], "stack": vill_stack,
             "committed_street": int(c_v), "committed_total": int(start - vill_stack),
             "folded": False, "all_in": vill_stack == 0, "is_button": button_eng == 1},
        ],
        "legal": legal,
    }


def decision_to_act(decision: dict, leg: dict, la_codes: list[str]) -> dict:
    """Our {action,amount} -> ActRequest dict, clamped to raise_range, with a LEGALITY GUARD (never emit an
    action not in legal_actions; 'b' always carries an int amount as the API requires)."""
    act, amt = decision.get("action"), decision.get("amount")
    lo, hi = leg.get("raise_min"), leg.get("raise_max")
    code = {"fold": "f", "check": "k", "call": "c"}.get(act, "b")  # bet/raise/allin -> b
    if act == "allin" or (code == "b" and amt is None):
        amt = hi
    if code == "b" and amt is not None:
        if lo is not None:
            amt = max(int(lo), int(amt))
        if hi is not None:
            amt = min(int(hi), int(amt))
        amt = int(amt)
    # legality guard: fall back through k -> c -> f -> b if our chosen code isn't offered
    if code not in la_codes:
        for alt in ("k", "c", "f", "b"):
            if alt in la_codes:
                code = alt
                break
    if code == "b":
        if amt is None:
            amt = int(lo if lo is not None else (hi or 0))
        return {"action": "b", "amount": amt}
    return {"action": code, "amount": None}


class PokerBotAgent:
    """The unified MVP wrapped for the GTO Wizard PokerAgent protocol. The client's poker_agent.py does:
        class MyAgent(PokerBotAgent):
            async def act(self, gsr): return ActRequest(**self.act_dict(gsr.model_dump()))
    and feeds the final (is_hand_over) state to hand_end() so live-learning sees the river responses."""

    def __init__(self, seed: int = 7, exploit: bool = True, use_resolver: bool | None = None,
                 use_turn_resolver: bool | None = None):
        import os
        from pokerbot.strategy.bot import PokerBot
        # env A/B toggles (default ON): POKERB_RESOLVER=0 / POKERB_TURN_RESOLVER=0 -> off (e.g. the floor baseline)
        if os.environ.get("POKERB_EXPLOIT", "1") == "0":   # A/B: OFF -> pure GTO discipline (no exploit-primary deviation;
            exploit = False                                # ~the pre-exploit chassis -- hypothesis: better vs near-Nash GTOW)
        if use_resolver is None:
            use_resolver = os.environ.get("POKERB_RESOLVER", "1") != "0"
        if use_turn_resolver is None:
            use_turn_resolver = os.environ.get("POKERB_TURN_RESOLVER", "1") != "0"
        self.bot = PokerBot(0, seed=seed, exploit=exploit)
        self.bot.use_resolver = use_resolver             # MVP#2 P1: real-time river re-solving
        self.bot.use_turn_resolver = use_turn_resolver   # MVP#2 P2: real-time turn re-solving
        if os.environ.get("POKERB_GTO_MODE", "0") == "1":  # GTOW mode: no off-tree probing vs a near-GTO opponent
            self.bot.use_probe = False
        if os.environ.get("POKERB_DEEPCFR", "0") == "1":  # our from-scratch HUNL Deep CFR net IS the strategy
            self.bot.use_deepcfr = True
        if os.environ.get("POKERB_BLUEPRINT", "1") == "0":  # A/B: OFF -> heuristic preflop (the -72 baseline)
            self.bot.use_blueprint = False
        if os.environ.get("POKERB_RANGE_TRACKER", "1") == "0":  # A/B: OFF -> floor uses _narrow (pre-keystone villain range)
            self.bot.use_range_tracker = False
        # AUSLESE-ADAPTER (2026-08-18, Armee-Befund 'v4-Wrapper fehlt im Harness'):
        # POKERB_AUSLESE_STACK=r6_button legt die Guard-Kette um decide. Default
        # leer = byte-identisch. ARM-DISZIPLIN: mit Stack gehoert der Lauf in den
        # resolver-OFF-Kanal ODER ohne RAISE_NARROW (v8-K3-Kontraindikation).
        self._decide = self.bot.decide
        _stack = os.environ.get("POKERB_AUSLESE_STACK", "")
        if _stack:
            from pokerbot.strategy.auslese import wickle_decide
            self._decide = wickle_decide(self.bot, _stack)

    def act_dict(self, gsr: dict) -> dict:
        state = gtow_to_state(gsr)
        self.bot.hero_idx = 0
        decision = self._decide(state)
        gs = gsr.get("game_state") or gsr
        la_codes = [a.lower() for a in (gs.get("legal_actions") or [])]
        return decision_to_act(decision, state["legal"], la_codes)

    def hand_end(self, final_gsr: dict | None = None):
        try:
            self.bot.observe_hand_end(gtow_to_state(final_gsr) if final_gsr else None)
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------- offline self-test (no key)
def _gsr(street, common, total, board, la, rr, hist, hole="QcQd", pos="SB", hstack=19700, vstack=19700, over=False):
    return {"hand_id": 1, "game": {"game_id": 1, "game_name": "HUNL 200BB", "game_format": "nlh",
                                   # LIVE order [BB,SB]=[100,50] — the fixture must match production, or the
                                   # locked to_call asserts test a schema the API never sends (the audit catch)
                                   "starting_stack": 20000, "blinds": [100, 50], "stack_reset_per_hand": True},
            "game_state": {"street": street, "common_pot": common, "total_pot": total, "board_cards": board,
                           "is_hand_over": over, "legal_actions": la, "raise_range": rr, "action_history": hist,
                           "has_gto_wizard_folded": False, "winnings": None, "aivat_score": None,
                           "players": [{"name": "hero", "stack": hstack, "position": pos, "hole_cards": hole},
                                       {"name": "GTO Wizard", "stack": vstack, "position": "BB" if pos == "SB" else "SB",
                                        "hole_cards": None}]}}


def _selftest():
    assert parse_cards("AsKdQh") == ["As", "Kd", "Qh"] and parse_cards("") == []
    assert parse_cards("2c2d4h5d8d") == ["2c", "2d", "4h", "5d", "8d"]
    leg = {"raise_min": 200, "raise_max": 20000}
    assert decision_to_act({"action": "fold"}, leg, ["f", "c", "b"]) == {"action": "f", "amount": None}
    assert decision_to_act({"action": "check"}, leg, ["k", "b"]) == {"action": "k", "amount": None}
    assert decision_to_act({"action": "bet", "amount": 50}, leg, ["k", "b"]) == {"action": "b", "amount": 200}
    assert decision_to_act({"action": "raise", "amount": 9 ** 9}, leg, ["f", "c", "b"]) == {"action": "b", "amount": 20000}
    assert decision_to_act({"action": "allin"}, leg, ["f", "c", "b"]) == {"action": "b", "amount": 20000}
    # legality guard: our 'check' but only f/c/b offered -> must NOT emit 'k'
    assert decision_to_act({"action": "check"}, leg, ["f", "c", "b"])["action"] in ("c", "f")

    # to_call derivation + hero identification + a legal ActRequest end-to-end across spots
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 60
    agent = PokerBotAgent(seed=7, exploit=True)
    spots = [
        ("preflop SB open", _gsr("preflop", 150, 150, "", ["f", "c", "b"], {"min": 300, "max": 19950},
                                 [], hole="AsKd", pos="SB", hstack=19950, vstack=19900)),
        ("flop check spot", _gsr("flop", 600, 600, "AsKd7h", ["k", "b"], {"min": 100, "max": 19700},
                                 ["b300", "c", "_"], hole="QcQd")),
        ("river facing bet", _gsr("river", 1800, 3000, "AsKd7h2c9d", ["f", "c", "b"], {"min": 2400, "max": 18000},
                                  ["b300", "c", "_", "k", "k", "_", "k", "k", "_", "b1200"], hole="QcJd", hstack=18000, vstack=17400)),
    ]
    for name, gsr in spots:
        st = gtow_to_state(gsr)
        ar = agent.act_dict(gsr)
        assert ar["action"] in ("f", "c", "k", "b"), ar
        assert ar["action"] in [a.lower() for a in gsr["game_state"]["legal_actions"]], (name, ar)
        if ar["action"] == "b":
            rr = gsr["game_state"]["raise_range"]
            assert rr["min"] <= ar["amount"] <= rr["max"], (name, ar, rr)
        print(f"  {name:18s}: to_call={st['legal']['to_call']:5d} pot={st['pot']:5d} -> ActRequest {ar}")
    # LOCK the to_call fix (study_grade audit 2026-06-21 — committed-delta, NOT total_pot-common_pot). The BB case
    # uses common=0,total=325 so the OLD formula would yield 325 (the inflated bug) and FAIL this assert.
    assert gtow_to_state(_gsr("preflop", 0, 325, "", ["f", "c", "b"], {"min": 450, "max": 19900}, ["b225"],
                              hole="Ts9s", pos="BB"))["legal"]["to_call"] == 125, "BB vs 2.25bb open must be 1.25bb"
    assert gtow_to_state(_gsr("preflop", 150, 150, "", ["f", "c", "b"], {"min": 300, "max": 19950}, [],
                              hole="AsKd", pos="SB"))["legal"]["to_call"] == 50, "SB to open faces the BB (0.5bb)"
    print("to_call fix locked: BB-vs-open=125 (was 325), SB-open=50 (was 0)")
    print("OK - adapter maps the REAL schema to legal ActRequests. Key present:", bool(config.GTOWIZARD_API_KEY))


if __name__ == "__main__":
    _selftest()
