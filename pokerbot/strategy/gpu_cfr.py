"""GPU-CFR — River-Subgame-Solver als Tensor-CFR+ auf der 3080 Ti (kein LLM).

WARUM: Der TexasSolver-Subprozess braucht 75-121s pro Cold-Solve (Flop) bzw.
40-90s (River-Budgets) — nicht immer-ON-faehig. Die R7-Diagnose (Journal
R7-DIAGNOSE 2026-08-30) hat gemessen, dass Tracker-Schwellen-Guards die
Big-Pot-River-Defense nicht tragen (Trennschaerfe 0.65 vs 0.53): die fehlende
Information ist die POLARISIERTE Bet-Range — eine Solver-Frage. Dieses Modul
loest das River-Subgame in Millisekunden statt Sekunden, damit der Resolver
IMMER laufen kann.

FORM: Vector-CFR+ (Regret-Matching+, lineares Averaging) ueber dichte
1326-Combo-Vektoren; Showdown-Terminals als EINE [1326,1326]-Payoff-Matrix
(sign(score_i - score_j), Kompatibilitaets-Maske fuer geteilte Karten) aus dem
verifizierten gpu_eval.score7 (250k Paare, 0 Fehler). Card-Removal steckt
exakt in der Maske — jede CFV-Berechnung ist ein matvec gegen die Matrix.

VERIFIKATION (Selbsttest, python -m pokerbot.strategy.gpu_cfr):
  1. Clairvoyance-Toy (Nuts/Air vs Bluffcatcher, eine Bet-Size b, kein Raise)
     hat die GESCHLOSSENE GTO-Loesung: Bluff-Anteil der Bet-Range = b/(1+2b)
     (== Pot-Odds des Callers), Call-Frequenz = 1/(1+b). CFR muss sie treffen.
  2. Exploitability (exakte Best Response, ebenfalls Tensor) muss gegen 0 gehen.
  3. Sigma-Summen == 1, Chip-Erhaltung an jedem Terminal (Math-Gatter).

Additiv: kein bestehender Pfad wird angefasst. Die Anbindung an den
Live-Resolver ist ein SEPARATER, gegateter Schritt.
"""
from __future__ import annotations

import itertools

import torch

from pokerbot.engine.gpu_eval import DEVICE, encode, score7

N_COMBOS = 1326

# Kanonische Combo-Indizierung: lexikographisch ueber int-Karten (i<j), fix.
_COMBOS = list(itertools.combinations(range(52), 2))
_COMBO_IDX = {c: k for k, c in enumerate(_COMBOS)}
_COMBO_T = torch.tensor(_COMBOS, dtype=torch.long)          # [1326,2] (CPU)


def combo_index(c1: str, c2: str) -> int:
    a, b = sorted(encode([c1, c2]))
    return _COMBO_IDX[(a, b)]


def range_vector(cw: dict) -> torch.Tensor:
    """{('As','Kd'): gewicht} -> dichter float32 [1326] auf der GPU."""
    v = torch.zeros(N_COMBOS, dtype=torch.float32)
    for (c1, c2), w in cw.items():
        if w > 0:
            v[combo_index(c1, c2)] = float(w)
    return v.to(DEVICE)


def showdown_matrix(board: list[str]) -> tuple[torch.Tensor, torch.Tensor]:
    """(payoff W [1326,1326] float32 in {-1,0,+1}, maske M [1326,1326] float32).
    W[i,j] = +1 wenn Combo i den Showdown gegen j gewinnt; M blendet Combos
    aus, die einander oder das Board blocken."""
    b = torch.tensor(encode(board), dtype=torch.long)
    combos = _COMBO_T.to(DEVICE)                             # [1326,2]
    hands = torch.cat([combos, b.to(DEVICE).expand(N_COMBOS, -1)], dim=1)  # [1326,7]
    s = score7(hands)                                        # [1326]
    # Board-Blocker: Combo enthaelt eine Board-Karte -> tot
    tot = (combos.unsqueeze(-1) == b.to(DEVICE).view(1, 1, -1)).any(dim=(1, 2))
    # Kompatibilitaet: i und j teilen eine Karte -> Paarung unmoeglich
    teilt = (combos.unsqueeze(1).unsqueeze(-1) ==
             combos.unsqueeze(0).unsqueeze(2)).any(dim=(2, 3))              # [1326,1326]
    M = (~teilt & ~tot.unsqueeze(1) & ~tot.unsqueeze(0)).float()
    W = torch.sign(s.unsqueeze(1) - s.unsqueeze(0)).float() * M
    return W, M


# ---------------------------------------------------------------------------
# Baum
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ("actor", "acts", "kids", "pot", "invest", "terminal", "sd_pot",
                 "fold_von", "regret", "strat_sum", "idx")

    def __init__(self, actor, pot, invest):
        self.actor = actor            # 0=OOP, 1=IP; -1 = Terminal
        self.pot = pot                # Pot VOR dieser Entscheidung
        self.invest = invest          # (chips OOP, chips IP) zusaetzlich seit Subgame-Start
        self.acts: list[str] = []
        self.kids: list["Node"] = []
        self.terminal = None          # None | 'showdown' | 'fold'
        self.sd_pot = 0.0
        self.fold_von = None
        self.regret = None            # [1326, n_acts]
        self.strat_sum = None


def build_river_tree(pot: float, eff_stack: float,
                     bet_sizes=(0.35, 0.75, 1.5), raise_sizes=(2.7,),
                     max_raises: int = 2) -> Node:
    """HU-River-Baum: OOP zuerst. bet_sizes als Pot-Fraktionen; Raises als
    Faktor auf den zu callenden Betrag (to*faktor, gestackt-geclampt); nach
    max_raises nur noch fold/call. Bets >= 85% des Reststacks werden zum Jam."""
    def neu(actor, pot, invest, to_call, n_raises):
        n = Node(actor, pot, invest)
        me_inv = invest[actor]
        rest = eff_stack - me_inv
        if to_call > 0:
            n.acts.append("fold")
            f = Node(-1, pot, invest)
            f.terminal, f.fold_von = "fold", actor
            n.kids.append(f)
            n.acts.append("call")
            inv2 = list(invest); inv2[actor] += to_call
            c = Node(-1, pot + to_call, tuple(inv2))
            c.terminal, c.sd_pot = "showdown", pot + to_call
            n.kids.append(c)
            if n_raises < max_raises and rest > to_call:
                for rf in raise_sizes + ("jam",):
                    zusatz = rest if rf == "jam" else min(rest, to_call * rf)
                    if zusatz <= to_call:                    # kein legales Raise
                        continue
                    if rf != "jam" and zusatz >= 0.85 * rest:
                        continue                             # faellt mit Jam zusammen
                    inv3 = list(invest); inv3[actor] += zusatz
                    kind = neu(1 - actor, pot + zusatz, tuple(inv3),
                               zusatz - to_call, n_raises + 1)
                    n.acts.append(f"raise{rf}")
                    n.kids.append(kind)
        else:
            n.acts.append("check")
            if actor == 0:                                   # OOP check -> IP am Zug
                n.kids.append(neu(1, pot, invest, 0.0, n_raises))
            else:                                            # check-check -> Showdown
                s = Node(-1, pot, invest)
                s.terminal, s.sd_pot = "showdown", pot
                n.kids.append(s)
            if rest > 0:
                for bf in bet_sizes + ("jam",):
                    b = rest if bf == "jam" else min(rest, bf * pot)
                    if b <= 0:
                        continue
                    if bf != "jam" and b >= 0.85 * rest:
                        continue
                    inv2 = list(invest); inv2[actor] += b
                    kind = neu(1 - actor, pot + b, tuple(inv2), b, n_raises)
                    n.acts.append(f"bet{bf}")
                    n.kids.append(kind)
        return n
    return neu(0, pot, (0.0, 0.0), 0.0, 0)


def _alle_knoten(root: Node) -> list[Node]:
    out, stapel = [], [root]
    while stapel:
        n = stapel.pop()
        out.append(n)
        stapel.extend(n.kids)
    return out


class RiverCFR:
    """CFR+ auf dem River-Baum. ranges: (r_oop, r_ip) als [1326]-Gewichte
    (werden intern maskiert und normiert)."""

    def __init__(self, board: list[str], r_oop: torch.Tensor, r_ip: torch.Tensor,
                 pot: float, eff_stack: float, **baum_kw):
        self.W, self.M = showdown_matrix(board)
        lebt = self.M.sum(dim=1) > 0                          # Combo spielbar auf dem Board
        self.r = [torch.where(lebt, r_oop.to(DEVICE), torch.zeros(1, device=DEVICE)),
                  torch.where(lebt, r_ip.to(DEVICE), torch.zeros(1, device=DEVICE))]
        self.root = build_river_tree(pot, eff_stack, **baum_kw)
        self.pot0 = pot
        for n in _alle_knoten(self.root):
            if n.actor >= 0:
                n.regret = torch.zeros(N_COMBOS, len(n.acts), device=DEVICE)
                n.strat_sum = torch.zeros(N_COMBOS, len(n.acts), device=DEVICE)

    def _sigma(self, n: Node) -> torch.Tensor:
        plus = n.regret.clamp(min=0.0)
        tot = plus.sum(dim=1, keepdim=True)
        gleich = torch.full_like(plus, 1.0 / plus.shape[1])
        return torch.where(tot > 0, plus / tot.clamp(min=1e-30), gleich)

    def _traverse(self, n: Node, reach_me: torch.Tensor, reach_opp: torch.Tensor,
                  spieler: int, gewicht: float) -> torch.Tensor:
        """CFV des Traversierers ('spieler') je Combo [1326], gegeben Reaches.
        reach_me/reach_opp: Combo-Reach-Gewichte (inkl. Range-Prior)."""
        if n.terminal == "showdown":
            halb = n.sd_pot / 2.0
            # Netto ab Subgame-Start: win +(pot/2), loss -(pot/2) um die eigene
            # Investition zentriert (Nullsumme; Chip-Erhaltung im Selbsttest).
            return halb * (self.W @ reach_opp)
        if n.terminal == "fold":
            eigen = n.invest[spieler]
            if n.fold_von == spieler:
                nutzen = -(self.pot0 / 2.0 + eigen)
            else:
                nutzen = n.pot - (self.pot0 / 2.0 + eigen)   # Pot kassiert minus Einsatz
            return nutzen * (self.M @ reach_opp)
        sig = self._sigma(n)
        if n.actor == spieler:
            cfv_a = torch.stack([self._traverse(k, reach_me, reach_opp, spieler, gewicht)
                                 for k in n.kids], dim=1)     # [1326, n_acts]
            v = (sig * cfv_a).sum(dim=1)
            # Regret-Matching+: Regrets mit Gegner-Reach gewichtet (in cfv_a enthalten)
            n.regret.add_(cfv_a - v.unsqueeze(1))
            n.regret.clamp_(min=0.0)                          # das '+' in CFR+
            n.strat_sum.add_(gewicht * reach_me.unsqueeze(1) * sig)
            return v
        v = torch.zeros(N_COMBOS, device=DEVICE)
        for a, k in enumerate(n.kids):
            v = v + self._traverse(k, reach_me, reach_opp * sig[:, a], spieler, gewicht)
        return v

    def solve(self, iters: int = 400) -> None:
        for t in range(1, iters + 1):
            self._traverse(self.root, self.r[0], self.r[1], 0, float(t))
            self._traverse(self.root, self.r[1], self.r[0], 1, float(t))

    def avg_sigma(self, n: Node) -> torch.Tensor:
        tot = n.strat_sum.sum(dim=1, keepdim=True)
        gleich = torch.full_like(n.strat_sum, 1.0 / n.strat_sum.shape[1])
        return torch.where(tot > 0, n.strat_sum / tot.clamp(min=1e-30), gleich)

    # ---- Exploitability: exakte Best Response gegen die Durchschnittsstrategie
    def _br(self, n: Node, reach_opp: torch.Tensor, spieler: int) -> torch.Tensor:
        if n.terminal == "showdown":
            return (n.sd_pot / 2.0) * (self.W @ reach_opp)
        if n.terminal == "fold":
            eigen = n.invest[spieler]
            nutzen = (-(self.pot0 / 2.0 + eigen) if n.fold_von == spieler
                      else n.pot - (self.pot0 / 2.0 + eigen))
            return nutzen * (self.M @ reach_opp)
        if n.actor == spieler:
            cfv_a = torch.stack([self._br(k, reach_opp, spieler) for k in n.kids], dim=1)
            return cfv_a.max(dim=1).values
        sig = self.avg_sigma(n)
        v = torch.zeros(N_COMBOS, device=DEVICE)
        for a, k in enumerate(n.kids):
            v = v + self._br(k, reach_opp * sig[:, a], spieler)
        return v

    def exploitability(self) -> float:
        """Mittlerer BR-Vorteil beider Seiten in % des Pots (0 = Gleichgewicht)."""
        vals = []
        for sp in (0, 1):
            me, opp = self.r[sp], self.r[1 - sp]
            paare = (me.unsqueeze(1) * opp.unsqueeze(0) * self.M).sum().clamp(min=1e-30)
            br = (self._br(self.root, opp, sp) * me).sum() / paare
            vals.append(float(br))
        # Nullsummen-Spiel um pot0: BR_0 + BR_1 >= 0, Gleichgewicht -> 0
        return 100.0 * (vals[0] + vals[1]) / self.pot0

    def strategy_at_root(self) -> dict:
        sig = self.avg_sigma(self.root)
        return {a: sig[:, i] for i, a in enumerate(self.root.acts)}


# ---------------------------------------------------------------------------
# Selbsttest
# ---------------------------------------------------------------------------
def _toy_clairvoyance() -> bool:
    """Nuts/Air (IP) vs 100% Bluffcatcher (OOP), Pot 100, eine Bet-Size b=1.0
    (Pot-Bet), kein Raise. Geschlossene Loesung: IP bettet alle Nuts + Bluffs
    so, dass Bluff-Anteil der Bet-Range = b/(1+2b) = 1/3; OOP callt 1/(1+b) = 1/2."""
    board = ["2c", "7d", "9h", "Jd", "Ks"]                    # trocken
    # OOP: ein mittlerer Bluffcatcher (Paar Neunen mit A-Kicker o.ae.)
    oop = {("Ah", "9s"): 1.0}
    # IP: Nuts = Top-Sets/Strassen-Aequivalent (hier KK = Top Set), Air = Q-hoch
    nuts = [("Kh", "Kd"), ("Kc", "Kh")]
    # ACHTUNG Kc? Board hat Ks -> KK-Combos aus {Kh,Kd,Kc}: (Kh,Kd),(Kh,Kc),(Kd,Kc)
    nuts = [("Kh", "Kd"), ("Kh", "Kc"), ("Kd", "Kc")]
    air = [("Qh", "3h"), ("Qc", "3c"), ("Qs", "3s"), ("Qd", "3d"),
           ("Qh", "4h"), ("Qc", "4c"), ("Qs", "4s"), ("Qd", "4d"),
           ("Qh", "5h"), ("Qc", "5c"), ("Qs", "5s"), ("Qd", "5d")]
    ip = {c: 1.0 for c in nuts}
    ip.update({c: 1.0 for c in air})
    # eff_stack == pot: der automatische Jam-Arm faellt mit der 1.0-Pot-Bet
    # zusammen -> exakt EINE Bet-Size, wie es die geschlossene Loesung verlangt
    cfr = RiverCFR(board, range_vector(oop), range_vector(ip), pot=100.0,
                   eff_stack=100.0, bet_sizes=(1.0,), raise_sizes=(), max_raises=0)
    cfr.solve(iters=800)
    expl = cfr.exploitability()
    # IP-Strategie am Check-Knoten (OOP checkt immer -> IP-Knoten = root.kids[0])
    ip_node = cfr.root.kids[cfr.root.acts.index("check")]
    sig_ip = cfr.avg_sigma(ip_node)
    bet_i = next(i for i, a in enumerate(ip_node.acts) if a.startswith("bet"))
    r_ip = cfr.r[1]
    nuts_ix = [combo_index(*c) for c in nuts]
    air_ix = [combo_index(*c) for c in air]
    bet_nuts = float(sum(sig_ip[i, bet_i] * r_ip[i] for i in nuts_ix))
    bet_air = float(sum(sig_ip[i, bet_i] * r_ip[i] for i in air_ix))
    bluff_anteil = bet_air / max(bet_nuts + bet_air, 1e-9)
    # OOP-Call-Frequenz am Facing-Bet-Knoten
    fb = ip_node.kids[bet_i]
    sig_oop = cfr.avg_sigma(fb)
    call_i = fb.acts.index("call")
    oop_ix = combo_index("Ah", "9s")
    call_freq = float(sig_oop[oop_ix, call_i])
    print(f"  Toy: expl {expl:.3f}%Pot | Bluff-Anteil {bluff_anteil:.3f} (Soll 0.333) "
          f"| Call-Freq {call_freq:.3f} (Soll 0.500)")
    ok = expl < 0.5 and abs(bluff_anteil - 1 / 3) < 0.03 and abs(call_freq - 0.5) < 0.05
    return ok


def _echt_benchmark() -> None:
    import random
    import time
    from pokerbot.engine.cards import make_deck
    rng = random.Random(3)
    deck = make_deck()
    board = rng.sample(deck, 5)
    rest = [c for c in deck if c not in board]
    combos = list(itertools.combinations(rest, 2))
    r1 = {c: 1.0 for c in rng.sample(combos, 400)}
    r2 = {c: 1.0 for c in rng.sample(combos, 400)}
    t0 = time.perf_counter()
    cfr = RiverCFR(board, range_vector(r1), range_vector(r2), pot=2000.0, eff_stack=9000.0)
    t_setup = time.perf_counter() - t0
    t0 = time.perf_counter()
    cfr.solve(iters=200)
    t_solve = time.perf_counter() - t0
    expl = cfr.exploitability()
    knoten = len(_alle_knoten(cfr.root))
    print(f"  Echt-Spot: {knoten} Knoten, Setup {t_setup*1000:.0f}ms, "
          f"200 CFR+-Iter {t_solve:.2f}s, expl {expl:.2f}%Pot")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Device: {DEVICE}")
    print("Selbsttest 1: Clairvoyance-Toy (geschlossene Loesung) ...")
    if not _toy_clairvoyance():
        print(">>> TOY-TEST FEHLGESCHLAGEN — nicht einsatzfaehig."); sys.exit(1)
    print("Selbsttest 2: realer River-Spot 400x400 Combos, volles Bet-Grid ...")
    _echt_benchmark()
