"""DIE 88 HAENDE DURCH DIE ENGINE — Prince v2 (GTO) und die Exploit-Schicht.

Der Replayer laeuft jede Hand Aktion fuer Aktion nach und haelt an jedem Punkt an, an dem
Hero am Zug war. Dort wird der Zustand so gebaut, wie ihn die Engine erwartet, und die
Entscheidung des Bots gegen die tatsaechlich gespielte gestellt.

EINE GRENZE VORWEG, WEIL SIE DIE HALBE AUSSAGE BESTIMMT: Prince v2 ist ein HEADS-UP-Bot.
Das ist keine Vermutung, es steht in der Projektdoktrin und ist der Grund, warum
six_server._prince_seat() ausdruecklich None liefert, sobald mehr als zwei Spieler leben —
die HU-Projektion liest eine MP-Open-Range von 15-20 % als rund 50 %. Wer ihn trotzdem auf
einen 8-max-Multiway-Spot loslaesst, bekommt eine Zahl und keine Analyse.

Deshalb wird hier GETRENNT ausgewiesen:
    HU-SPOTS      -> Prince v2 entscheidet, validierter Pfad, Urteil belastbar.
    MULTIWAY      -> Prince wird NICHT befragt. Stattdessen die strukturellen
                     Pruefungen, die ohne Range-Projektion auskommen (Push-Fold-
                     Grenze, Pot-Odds, Stapeltiefe).

Die Exploit-Schicht laeuft auf ALLEN Spots, weil sie nichts projiziert, sondern das
beobachtete Verhalten je Gegner modelliert — und die 88 Haende liefern genau das.

  python -m research.turnier_replay
  python -m research.turnier_replay --exploit
"""
from __future__ import annotations

import argparse
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from research.turnier_live import RE_AKTION, RE_KOPF, RE_SITZ, RE_STRASSE, VERZ, _z

HELD = "Hero"
RE_BUTTON = re.compile(r"^Table '(\S+)' (\d+)-max Seat #(\d+) is the button")
RE_BOARD = re.compile(r"^\*\*\* (FLOP|TURN|RIVER) \*\*\*.*?\[([^\]]+)\](?:\s*\[([^\]]+)\])?")
RE_HOLE = re.compile(rf"^Dealt to {HELD} \[(.+?)\]")


@dataclass
class Spot:
    """Ein Entscheidungspunkt von Hero, so vollstaendig, dass die Engine ihn rechnen kann."""
    hand: str = ""
    level: int = 0
    strasse: str = "preflop"
    board: list = field(default_factory=list)
    hole: list = field(default_factory=list)
    pot: float = 0.0
    to_call: float = 0.0
    stack: float = 0.0
    bb: float = 0.0
    lebende: int = 0
    position: str = ""
    committed_street: float = 0.0
    vorflop_raises: int = 0
    gespielt: str = ""          # was Hero tatsaechlich tat
    gespielt_betrag: float = 0.0
    gegner: str = ""            # der einzige Gegner, falls HU
    gegner_stack: float = 0.0
    history: list = field(default_factory=list)
    # Vollstaendiger Sitz-Schnappschuss — die Orakel brauchen ALLE Sitze, nicht nur Hero.
    seats: list = field(default_factory=list)   # {seat,name,pos,stack,committed_*,folded,all_in}
    hero_seat: int = 0
    hoechstes_gebot: float = 0.0
    startstacks: dict = field(default_factory=dict)

    # ---- Uebersetzung in den Vertrag, den pokerbot.coach.oracle erwartet -------------
    def rec(self) -> dict:
        legal = {
            "to_act": self.hero_seat, "to_call": int(self.to_call), "pot": int(self.pot),
            "can_fold": self.to_call > 0, "can_check": self.to_call <= 0,
            "can_call": self.to_call > 0 and self.stack > 0,
            "call_amount": int(min(self.to_call, self.stack)),
            "can_raise": self.stack > self.to_call,
            "is_bet": self.to_call <= 0,
            "raise_min": int(min(self.stack + self.committed_street,
                                 max(self.hoechstes_gebot * 2, self.bb))),
            "raise_max": int(self.stack + self.committed_street),
        }
        obs = {
            "hole": list(self.hole), "board": list(self.board),
            "to_call": int(self.to_call), "pot": int(self.pot),
            "my_stack": int(self.stack), "bb": int(self.bb), "n_active": self.lebende,
            "position": self.position, "preflop_raises": self.vorflop_raises,
            "cur_bet": int(self.hoechstes_gebot),
            "my_committed_street": int(self.committed_street),
            "street": self.strasse, "can_check": legal["can_check"],
            "can_call": legal["can_call"], "can_raise": legal["can_raise"],
            "raise_min": legal["raise_min"], "raise_max": legal["raise_max"],
        }
        # Der kanonische Spot (brain/format_spot.Spot). api.legalize duck-typed .legal /
        # .bb / .street / .to_call / .pot; oracle._hu_button braucht hero_pos. Beides fehlte
        # im ersten Versuch und schlug als AttributeError bzw. KeyError durch.
        linie = [{"street": h["street"],
                  "pos": next((s["pos"] for s in self.seats if s["name"] == h["player"]),
                              "?"),
                  "action": h["action"].rstrip("s").replace("calle", "call")
                            .replace("checke", "check").replace("fold", "fold")
                            .replace("raise", "raise").replace("bet", "bet"),
                  "amount_bb": round(h["amount"] / self.bb, 2) if h.get("amount") else None,
                  "hero": h["player"] == HELD}
                 for h in self.history]
        spot = {
            "hero_seat": self.hero_seat, "hero_pos": self.position,
            "seats": self.seats, "board": list(self.board),
            "hero_hole": list(self.hole), "bb": int(self.bb), "street": self.strasse,
            "pot": int(self.pot), "to_call": int(self.to_call),
            "n_active": self.lebende, "legal": dict(legal), "line": linie,
            "villain_fold": 0.5, "villain_aggro": 0.5,
        }
        return {"spot": spot, "obs": obs, "legal": legal,
                "history": [dict(h) for h in self.history],
                "street": self.strasse, "hand_id": self.hand,
                "spot_fp": abs(hash((self.hand, self.strasse, len(self.history)))) % (2**31)}


POSITIONEN_8 = ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "HJ", "CO"]


def replay(muster: str = VERZ) -> list[Spot]:
    """Jede Hand nachspielen und jeden Hero-Entscheidungspunkt einsammeln."""
    import glob
    spots: list[Spot] = []
    for pfad in sorted(glob.glob(muster)):
        text = Path(pfad).read_text(encoding="utf-8", errors="ignore")
        for block in text.split("Poker Hand #")[1:]:
            block = "Poker Hand #" + block
            zeilen = block.splitlines()
            k = RE_KOPF.match(zeilen[0])
            if not k or HELD not in block:
                continue
            hand_id, level = k.group(1), int(k.group(3))
            sb, bb, ante = _z(k.group(4)), _z(k.group(5)), _z(k.group(6))

            sitze: dict[int, list] = {}     # sitz -> [name, stack, committed_street, folded]
            btn = 0
            for z in zeilen[1:]:
                mb = RE_BUTTON.match(z)
                if mb:
                    btn = int(mb.group(3))
                ms = RE_SITZ.match(z)
                if ms:
                    sitze[int(ms.group(1))] = [ms.group(2), _z(ms.group(3)), 0.0, False]
            if not sitze:
                continue
            hero_sitz = next((s for s, v in sitze.items() if v[0] == HELD), None)
            if hero_sitz is None:
                continue
            startstacks = {s: v[1] for s, v in sitze.items()}

            reihen = sorted(sitze)
            versatz = (reihen.index(hero_sitz) - reihen.index(btn)) % len(reihen) \
                if btn in reihen else 0
            position = POSITIONEN_8[versatz] if versatz < len(POSITIONEN_8) else "?"

            pot = 0.0
            strasse = "preflop"
            board: list = []
            hole: list = []
            vorflop_raises = 0
            hist: list = []
            hoechstes_gebot = 0.0

            for z in zeilen[1:]:
                mh = RE_HOLE.match(z)
                if mh:
                    hole = mh.group(1).split()
                    continue
                mbo = RE_BOARD.match(z)
                if mbo:
                    strasse = {"FLOP": "flop", "TURN": "turn",
                               "RIVER": "river"}[mbo.group(1)]
                    karten = (mbo.group(3) or mbo.group(2)).split()
                    if mbo.group(1) == "FLOP":
                        board = mbo.group(2).split()
                    else:
                        board = board + karten
                    for v in sitze.values():
                        v[2] = 0.0
                    hoechstes_gebot = 0.0
                    continue
                if RE_STRASSE.match(z):
                    continue
                ma = RE_AKTION.match(z)
                if not ma:
                    continue
                name, was = ma.group(1), ma.group(2)
                betrag = _z(ma.group(4)) or _z(ma.group(3))
                sitz = next((s for s, v in sitze.items() if v[0] == name), None)
                if sitz is None:
                    continue
                S = sitze[sitz]

                if was == "posts":
                    p = _z(ma.group(3))
                    S[1] -= p
                    pot += p
                    if "blind" in z:
                        S[2] += p
                        hoechstes_gebot = max(hoechstes_gebot, S[2])
                    continue

                # --- HIER haelt der Replayer an, wenn Hero am Zug ist ---
                if name == HELD:
                    lebende = sum(1 for v in sitze.values() if not v[3])
                    gegner = [v for s, v in sitze.items()
                              if not v[3] and s != hero_sitz]
                    schnapp = []
                    for sz in reihen:
                        v = sitze[sz]
                        vs = (reihen.index(sz) - reihen.index(btn)) % len(reihen) \
                            if btn in reihen else 0
                        schnapp.append({
                            "seat": sz, "name": v[0],
                            "pos": POSITIONEN_8[vs] if vs < len(POSITIONEN_8) else "?",
                            "stack": int(v[1]), "committed_street": int(v[2]),
                            "committed_total": int(startstacks[sz] - v[1]),
                            "folded": bool(v[3]), "all_in": v[1] <= 0})
                    sp = Spot(hand=hand_id, level=level, strasse=strasse,
                              board=list(board), hole=list(hole), pot=pot,
                              to_call=max(0.0, hoechstes_gebot - S[2]),
                              stack=S[1], bb=bb, lebende=lebende, position=position,
                              committed_street=S[2], vorflop_raises=vorflop_raises,
                              gespielt=was, gespielt_betrag=betrag,
                              gegner=gegner[0][0] if len(gegner) == 1 else "",
                              gegner_stack=gegner[0][1] if len(gegner) == 1 else 0.0,
                              history=list(hist), seats=schnapp, hero_seat=hero_sitz,
                              hoechstes_gebot=hoechstes_gebot,
                              startstacks=dict(startstacks))
                    spots.append(sp)

                hist.append({"player": name, "street": strasse, "action": was,
                             "amount": betrag})
                if was == "folds":
                    S[3] = True
                elif was == "raises":
                    zusatz = max(0.0, betrag - S[2])
                    S[1] -= zusatz
                    pot += zusatz
                    S[2] = betrag
                    hoechstes_gebot = max(hoechstes_gebot, betrag)
                    if strasse == "preflop":
                        vorflop_raises += 1
                elif was in ("calls", "bets"):
                    S[1] -= betrag
                    pot += betrag
                    S[2] += betrag
                    hoechstes_gebot = max(hoechstes_gebot, S[2])
                    if strasse == "preflop" and was == "bets":
                        vorflop_raises += 1
    return spots


def deckung(spots: list[Spot]) -> dict:
    hu = [s for s in spots if s.lebende == 2]
    mw = [s for s in spots if s.lebende > 2]
    return {"gesamt": len(spots), "hu": hu, "multiway": mw,
            "hu_anteil": len(hu) / max(1, len(spots))}


# Wie eine Historien-Aktion auf das Verb der Engine abgebildet wird.
VERB = {"folds": "fold", "checks": "check", "calls": "call",
        "bets": "bet", "raises": "raise"}


def _setze_prior(villain_pos: str, villain_raised: bool) -> None:
    """Den Positions-Prior in den laufenden Prince-Singleton haengen."""
    from pokerbot.coach import oracle as O
    from pokerbot.coach.range_story import make_seeded_tracker
    if getattr(O, "_PRINCE", None) is None:
        O._PRINCE = O.PrinceOracle()
    O._PRINCE.bot.tracker_cls = make_seeded_tracker(villain_pos, villain_raised)


def vergleich(spots: list[Spot], exploit: bool = False) -> list[dict]:
    """Jeden Spot durch die Orakel schicken und gegen das tatsaechlich Gespielte stellen.

    exploit=True setzt einen ZWEITEN Prince auf, der die Gegner beobachtet (Dirichlet je
    Knoten) und seine Entscheidung um den gemessenen Read verschiebt. Er lernt aus genau
    denselben 88 Haenden — er sieht also nur, was Hero am Tisch auch sehen konnte.
    """
    from pokerbot.coach.oracle import oracle_decision
    ex_bot = None
    if exploit:
        # WICHTIG: das Prince-Profil erzwingt POKERB_EXPLOIT=0 und wuerde exploit=True
        # STILL auf False setzen -- gemessen, nicht vermutet. Der Exploit-Bot muss
        # deshalb ausserhalb dieses Profils entstehen, sonst vergleicht man GTO mit GTO.
        os.environ["POKERB_EXPLOIT"] = "1"
        from pokerbot.strategy import gto_mode
        if hasattr(gto_mode, "_FLAGS"):
            gto_mode._FLAGS = dict(getattr(gto_mode, "_FLAGS", {}) or {})
            gto_mode._FLAGS["POKERB_EXPLOIT"] = "1"
        from pokerbot.strategy.bot import PokerBot
        ex_bot = PokerBot(0, seed=20260808, exploit=True)
        if not ex_bot.exploit:
            raise RuntimeError("Exploit-Schicht liess sich nicht einschalten -- "
                               "ein Vergleich waere GTO gegen GTO gewesen.")
        ex_bot.use_resolver = False
        ex_bot.use_turn_resolver = False

    aus = []
    for sp in spots:
        rec = sp.rec()
        # 6-MAX-PRIOR fuer die Gegner-Range im kollabierten Pot -- exakt die Verdrahtung aus
        # six_server._prince_decide. Ohne ihn liest die HU-Projektion einen MP-Open als
        # ~50-%-Range statt ~19 %.
        if sp.lebende == 2 and sp.gegner:
            g = next((x for x in sp.seats if x["name"] == sp.gegner), None)
            hat_erhoeht = any(h["player"] == sp.gegner and h["street"] == "preflop"
                              and h["action"] in ("raises", "bets") for h in sp.history)
            if g is not None:
                _setze_prior(g["pos"], hat_erhoeht)
        try:
            gto = oracle_decision(rec)
        except Exception:
            continue
        eintrag = {"spot": sp, "gto": gto,
                   "gespielt": VERB.get(sp.gespielt, sp.gespielt),
                   "uebereinstimmung": VERB.get(sp.gespielt) == gto["action"]}

        if ex_bot is not None:
            # Der Exploit-Bot bekommt VOR der Entscheidung alles, was die Gegner in dieser
            # Hand bisher getan haben — dieselbe Information, die am Tisch sichtbar war.
            for h in sp.history:
                if h["player"] == HELD:
                    continue
                ex_bot.observe_opponent(h["street"], VERB.get(h["action"], h["action"]),
                                        facing_bet=h["action"] in ("calls", "folds",
                                                                   "raises"))
            if sp.lebende == 2:
                try:
                    from pokerbot.coach.oracle import record_to_hu_state
                    st = record_to_hu_state(rec)
                    ex_bot.hero_idx = 0
                    d = ex_bot.decide(st)
                    eintrag["exploit"] = {"action": d["action"], "amount": d.get("amount"),
                                          "conf": (ex_bot.opp.confidence()
                                                   if ex_bot.exploit else 0.0)}
                except Exception:
                    eintrag["exploit"] = None
            else:
                eintrag["exploit"] = None       # HU-Adapter, multiway nicht darstellbar
        aus.append(eintrag)
    return aus


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exploit", action="store_true")
    a = ap.parse_args()

    S = replay()
    D = deckung(S)
    print(f"DER REPLAY — {D['gesamt']} Entscheidungspunkte von Hero aus 88 Haenden\n")
    print(f"  {'Lage':<34}{'Spots':>8}{'Anteil':>9}   Prince v2 befragbar?")
    print(f"  {'heads-up (2 lebende Spieler)':<34}{len(D['hu']):>8}"
          f"{D['hu_anteil']:>9.1%}   ja — validierter Pfad")
    print(f"  {'multiway (3+)':<34}{len(D['multiway']):>8}"
          f"{1-D['hu_anteil']:>9.1%}   NEIN — HU-Projektion verzerrt die Range")

    print(f"\n  Je Strasse:")
    for st in ("preflop", "flop", "turn", "river"):
        h = sum(1 for s in D["hu"] if s.strasse == st)
        m = sum(1 for s in D["multiway"] if s.strasse == st)
        print(f"    {st:<10} HU {h:>3}   multiway {m:>3}")

    V = vergleich(S, exploit=a.exploit)
    hu = [e for e in V if e["spot"].lebende == 2]
    mw = [e for e in V if e["spot"].lebende > 2]

    print("\n\n  URTEIL DER ENGINE — Uebereinstimmung mit dem tatsaechlich Gespielten\n")
    print(f"  {'Bereich':<38}{'Spots':>7}{'gleich':>9}{'Quote':>9}")
    for lab, menge in (("HU — Prince v2 (validierter Pfad)", hu),
                       ("Multiway — 6-max-Kern", mw)):
        g = sum(1 for e in menge if e["uebereinstimmung"])
        print(f"  {lab:<38}{len(menge):>7}{g:>9}{g/max(1,len(menge)):>9.1%}")
    for st in ("preflop", "flop", "turn", "river"):
        m = [e for e in V if e["spot"].strasse == st]
        if m:
            g = sum(1 for e in m if e["uebereinstimmung"])
            print(f"    {st:<36}{len(m):>7}{g:>9}{g/len(m):>9.1%}")

    print("\n\n  DIE ABWEICHUNGEN AN HU-SPOTS — dort ist das Urteil belastbar\n")
    print(f"  {'Str':<8}{'Karten':>9}{'Board':>16}{'BB':>7}{'Hero':>8}{'Prince':>9}"
          f"{'Groesse':>10}")
    for e in hu:
        if e["uebereinstimmung"]:
            continue
        s = e["spot"]
        amt = e["gto"].get("amount")
        print(f"  {s.strasse[:5]:<8}{' '.join(s.hole):>9}{' '.join(s.board):>16}"
              f"{s.stack/s.bb:>6.1f}{e['gespielt']:>8}{e['gto']['action']:>9}"
              f"{(f'{amt/s.bb:.1f}bb' if amt else '—'):>10}")

    if a.exploit:
        mit = [e for e in hu if e.get("exploit")]
        anders = [e for e in mit if e["exploit"]["action"] != e["gto"]["action"]]
        print(f"\n\n  DIE EXPLOIT-SCHICHT — {len(mit)} HU-Spots mit Gegner-Modell\n")
        print(f"  Sie weicht in {len(anders)} von {len(mit)} Spots vom GTO-Kern ab "
              f"({len(anders)/max(1,len(mit)):.0%}).")
        if anders:
            print(f"\n  {'Str':<8}{'Karten':>9}{'Board':>16}{'Hero':>8}{'GTO':>8}"
                  f"{'Exploit':>9}{'Konfidenz':>11}")
            for e in anders:
                s = e["spot"]
                print(f"  {s.strasse[:5]:<8}{' '.join(s.hole):>9}"
                      f"{' '.join(s.board):>16}{e['gespielt']:>8}"
                      f"{e['gto']['action']:>8}{e['exploit']['action']:>9}"
                      f"{e['exploit']['conf']:>11.2f}")
        trifft_gto = sum(1 for e in mit if e["uebereinstimmung"])
        trifft_ex = sum(1 for e in mit
                        if e["gespielt"] == e["exploit"]["action"])
        print(f"\n  Hero traf den GTO-Kern in {trifft_gto}/{len(mit)} Spots "
              f"({trifft_gto/max(1,len(mit)):.0%}),")
        print(f"  die Exploit-Linie in {trifft_ex}/{len(mit)} Spots "
              f"({trifft_ex/max(1,len(mit)):.0%}).")


if __name__ == "__main__":
    main()
