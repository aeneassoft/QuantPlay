"""AUTOGYM HU — Prince-HU-Self-Play mit Buchfuehrung, auf gepaarten Decks.

Jedes Deck wird VIERMAL gespielt: Holes x Button voll gekreuzt (Review-Befund
2026-08-16: bei blossem Button-Tausch kuerzt sich nur die Position heraus, nicht
die Karten — der Symmetrie-Check waere praktisch machtlos). Im 4er-Block kuerzen
sich Karten UND Position exakt. Die informativen Groessen sind nicht
"gewinnt er?", sondern:
  1. der Positions-Spread (Button-Netto): der gemessene Wert der Position,
  2. jede Entscheidung, gegen das Orakel gehalten,
  3. die HARTE Chip-Erhaltung pro Hand.
"""
from __future__ import annotations

import random

from pokerbot.benchmark.duplicate import _setup_fixed, gen_decks
from pokerbot.engine.game import HeadsUpGame

from . import oracle as orc


def _make_bot(seat: int, seed: int, exploit: bool, eq_iters: int):
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = eq_iters
    from pokerbot.strategy.bot import PokerBot
    return PokerBot(seat, seed=seed, exploit=exploit)


def _play_recorded(g: HeadsUpGame, bots, start: int, rep: orc.OracleReport,
                   ledger: dict, hand_id: str) -> int:
    # Blinds sind beim Aufruf schon gepostet -> committed zaehlt zur Summe dazu.
    before = sum(p.stack + p.committed_total for p in g.players)
    guard = 0
    while not g.hand_over:
        st = g.state()
        seat = st["to_act"]
        bots[seat].hero_idx = seat
        dec = bots[seat].decide(st)
        action, amount = dec["action"], dec.get("amount")
        me, opp = st["players"][seat], st["players"][1 - seat]
        to_call = max(0, st["current_bet"] - me["committed_street"])
        orc.grade_decision(rep, {
            "street": st["street"], "pot": st["pot"], "to_call": to_call,
            "action": action, "amount": amount,
            "hero_hole": me["hole"], "board": st["board"],
            "villain_hole": opp["hole"],
            "call_closes_action": opp["all_in"] or to_call >= me["stack"],
            "effective_stack": min(me["stack"], opp["stack"]),
            "n_opponents": 1,
        }, bb=g.bb)
        g.act(action, amount)
        guard += 1
        if guard > 500:
            break
    if not g.hand_over:
        # Haenger-Abbruch: KEIN Chip-Erhaltungs-Urteil (committed liegt noch im
        # Pot — das waere ein falscher HART-Befund) und keine Ledger-Buchung.
        ledger["abbrueche"] += 1
        return 0
    orc.grade_hand_conservation(rep, before, g.players[0].stack + g.players[1].stack,
                                hand_id, bb=g.bb)
    net0 = g.players[0].stack - start
    btn = g.button
    ledger["button_net"] += (net0 if btn == 0 else -net0)
    ledger["hands"] += 1
    return net0


def run(n_pairs: int = 200, seed: int = 7, exploit: bool = True,
        eq_iters: int = 120, start: int = 20000, bb: int = 100) -> dict:
    decks = gen_decks(n_pairs, seed=seed)
    g = HeadsUpGame(names=("S0", "S1"), starting_stack=start, sb=bb // 2, bb=bb, seed=0)
    bots = {0: _make_bot(0, seed, exploit, eq_iters), 1: _make_bot(1, seed + 1, exploit, eq_iters)}
    rep = orc.OracleReport()
    ledger = {"hands": 0, "button_net": 0, "abbrueche": 0}
    pair_edges = []
    for i, (h0, h1, board) in enumerate(decks):
        # 4er-Block: (Holes, Button) voll gekreuzt. Der Sitz-0-Bot sieht jede
        # (Karten, Position)-Kombination genau einmal -> in der Blocksumme
        # kuerzen sich Karten UND Position exakt; der Button-Ledger haelt als
        # BTN h0,h1,h1,h0 und bleibt ebenfalls kartenbalanciert.
        block = 0
        for holes, btn, tag in (((h0, h1), 0, "a"), ((h0, h1), 1, "b"),
                                ((h1, h0), 0, "c"), ((h1, h0), 1, "d")):
            _setup_fixed(g, holes[0], holes[1], board, btn, start)
            block += _play_recorded(g, bots, start, rep, ledger, f"{i}{tag}")
        pair_edges.append(block)
    orc.finalize_frequencies(rep)

    n = len(pair_edges)
    mean = sum(pair_edges) / n
    var = sum((e - mean) ** 2 for e in pair_edges) / max(1, n - 1)
    return {
        "disziplin": "HU", "haende": ledger["hands"], "abbrueche": ledger["abbrueche"],
        "button_netto_bb100": ledger["button_net"] / max(1, ledger["hands"]) / bb * 100,
        "paar_drift_bb100": mean / 4 / bb * 100,       # 4 Haende je Block; Soll ~0
        "paar_drift_se": (var ** 0.5 / n ** 0.5) / 4 / bb * 100,
        "orakel": rep.counts(),
        "orakel_report": rep,
    }
