"""AUTOGYM 6-MAX — Self-Play des sixmax-Kerns mit Buchfuehrung.

Frischer Tisch pro Hand (deterministischer Seed je Hand, rebuy-frei), damit die
HARTE Chip-Erhaltung sauber pruefbar bleibt. Multiway kennt keine eindeutige
Rueckschau-Gegnerhand -> die L-Stufe des Orakels bleibt hier aus; gemessen
werden P, F, HART und der Positions-Ledger (Netto je Positionslabel).
"""
from __future__ import annotations

from pokerbot.arena.sixmax import PROFILES, SixMaxBot
from pokerbot.engine.table import Table

from . import oracle as orc


def run(n_hands: int = 300, seed: int = 7, n_players: int = 6,
        profile: str = "tag", start: int = 10000, bb: int = 100) -> dict:
    rep = orc.OracleReport()
    pos_net: dict[str, int] = {}
    pos_hands: dict[str, int] = {}
    abbrueche = 0
    # Bots PERSISTENT ueber die Haende (Review-Befund: pro Hand neu erzeugte Bots
    # koennen ihre OppModels nie fuellen — die Reads waeren strukturell tot).
    bots = {s: SixMaxBot(s, PROFILES[profile]) for s in range(n_players)}
    for h in range(n_hands):
        names = [f"B{i}" for i in range(n_players)]
        t = Table(names, starting_stack=start, sb=bb // 2, bb=bb,
                  seed=seed * 100003 + h, human_seat=-1, rebuy=False)
        t.start_hand()
        # Das SixMaxBot-Protokoll (wie six_server): ohne new_hand() bleibt
        # pf_aggressor=None -> jeder Bot spielte postflop als Nicht-Aggressor,
        # der ganze C-Bet-Zweig waere unerreichbar (Review-Befund, gemessen:
        # cbet_policy 0x in 300 Haenden ohne, 143x mit Protokoll).
        for b in bots.values():
            b.new_hand(list(range(n_players)))
        before = sum(p.stack + p.committed_total for p in t.seats)
        positions = {s: t.position_label(s) for s in range(n_players)}
        guard = 0
        while not t.hand_over:
            seat = t.to_act
            obs = t.obs_for(seat)
            dec = bots[seat].decide(obs)
            action, amount = dec["action"], dec.get("amount")
            orc.grade_decision(rep, {
                "street": obs["street"], "pot": obs["pot"], "to_call": obs["to_call"],
                "action": action, "amount": amount,
                "hero_hole": obs["hole"], "board": obs["board"],
                "villain_hole": None,           # multiway: keine eindeutige Gegenhand
            }, bb=bb)
            t.act(action, amount)
            act_name = "raise" if action == "allin" else action
            for b in bots.values():
                b.observe(seat, obs["street"], act_name, obs["to_call"],
                          obs["preflop_raises"])
            guard += 1
            if guard > 600:
                break
        if not t.hand_over:
            abbrueche += 1          # Haenger: kein HART-Urteil, keine Buchung
            continue
        after = sum(p.stack for p in t.seats)
        orc.grade_hand_conservation(rep, before, after, h, bb=bb)
        for s in range(n_players):
            lab = positions[s]
            pos_net[lab] = pos_net.get(lab, 0) + (t.seats[s].stack - start)
            pos_hands[lab] = pos_hands.get(lab, 0) + 1
    orc.finalize_frequencies(rep)
    return {
        "disziplin": f"{n_players}-max", "haende": n_hands, "abbrueche": abbrueche,
        "position_bb100": {k: pos_net[k] / pos_hands[k] / bb * 100
                           for k in sorted(pos_net)},
        "orakel": rep.counts(),
        "orakel_report": rep,
    }
