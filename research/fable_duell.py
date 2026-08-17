"""Fable-5 spielt HU gegen den vollen AUSLESE-v4-Stack (stateful via Replay).

Der Agent ist KEIN PokerBot — die v4-Env-Flags faerben im Prozess nur die Bot-Seite.
Zustand = Aktions-Log auf Platte; jede Invokation rebaut Game+Bot deterministisch und
replayt (Bot-Entscheidungen sind seed-deterministisch). Kommandos:
  python -m research.fable_duell --neu            (Session zuruecksetzen, erste Hand)
  python -m research.fable_duell --akt call       (fold|check|call|allin|bet:300|raise:600)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("POKERB_TURN_DEFENSE", "0.07")
os.environ.setdefault("POKERB_SLOWPLAY", "0.25")
os.environ.setdefault("POKERB_RAISE_NARROW", "1.0")

D = Path("data/runs/fable_duell")
LOG = D / "aktionen.json"
AGENT = 0                      # Agent sitzt immer Seat 0; Button wechselt je Hand
N_DECKS = 200


def _spiel(bis_aktion: int):
    """Rebaut alles und replayt die ersten bis_aktion Agenten-Aktionen. Gibt (game, bot_d, log, netto) zurueck."""
    import pokerbot.strategy.bot as botmod
    botmod.EQUITY_ITERS = 300
    from pokerbot.autogym.pargate import _baue_fabrik
    from pokerbot.benchmark.duplicate import _setup_fixed, gen_decks
    from pokerbot.engine.game import HeadsUpGame
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    log = log[:bis_aktion]
    decks = gen_decks(N_DECKS, seed=4242)
    g = HeadsUpGame(names=("FABLE", "V4"), starting_stack=20000, sb=50, bb=100, seed=0)
    import os as _os
    bot_d = _baue_fabrik(_os.environ.get("FABLE_STACK", "turn_wert"), 7)(1)
    netto, hand_i, k = 0, 0, 0
    while True:
        h0, h1, board = decks[hand_i % N_DECKS]
        _setup_fixed(g, h0, h1, board, hand_i % 2, 20000)
        while not g.hand_over:
            st = g.state()
            if st["to_act"] == AGENT:
                if k >= len(log):
                    return g, bot_d, log, netto, hand_i
                a = log[k]; k += 1
                g.act(a[0], a[1])
            else:
                g.act(*bot_d(st))
        netto += g.players[AGENT].stack - 20000
        hand_i += 1


def _zeig(g, netto, hand_i):
    st = g.state()
    me = st["players"][AGENT]
    to_call = max(0, st["current_bet"] - me["committed_street"])
    la = g.legal_actions()
    if g.hand_over:
        print("HAND VORBEI (interner Fehler)"); return
    print(json.dumps({
        "hand_nr": hand_i + 1, "score_agent_bb": round(netto / 100, 1),
        "street": st["street"], "deine_karten": me["hole"], "board": st["board"],
        "pot": st["pot"], "to_call": to_call, "dein_stack": me["stack"],
        "bot_stack": st["players"][1]["stack"], "du_bist_button": g.button == AGENT,
        "legal": {"check": la.get("can_check"), "call": la.get("can_call"),
                  "raise_min": la.get("raise_min"), "raise_max": la.get("raise_max")},
        "history_der_hand": [h for h in g.history if h.get("street")],
    }, ensure_ascii=False))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--neu", action="store_true")
    ap.add_argument("--akt", default="")
    a = ap.parse_args()
    D.mkdir(parents=True, exist_ok=True)
    if a.neu:
        LOG.write_text("[]")
    log = json.loads(LOG.read_text()) if LOG.exists() else []
    if a.akt:
        teile = a.akt.split(":")
        akt = (teile[0], int(teile[1]) if len(teile) > 1 else None)
        log.append(akt)
        LOG.write_text(json.dumps(log))
    g, bot_d, log2, netto, hand_i = _spiel(len(log))
    _zeig(g, netto, hand_i)


if __name__ == "__main__":
    main()
