"""RIVER-BR-PRUEFSTAND — beide Hero-Arme im SELBEN River-Root-Spiel bewertet (v10 K3; Karte docs/V10_BUILD_CARD.md
K3 + E3/E9; Fakten docs/V10_FAKTEN.md A6/B10/B13).

Je Quellhand EIN Root (research/k3_roots.py: River-Beginn). Gemeinsames Root-Spiel rho_s = (Hero-Range: K1 falls
vorhanden sonst Tracker [Flag], Villain: Tracker). Zwei Hero-Politiken:
  A = PolicyTable je Hero-Knoten aus research/policy_oracle.py (ausgefuehrte v5-Politik, r8_stack);
  B = gemittelte Strategie eines RiverCFRBatch-Solves auf dem K2-Baum (bet 0.35/0.75/1.5, raise 2.7x to_call,
      max 2 Raises, ECHTER eff, fp32, 150 Iter; gpu_cfr.build_river_tree-Defaults) — hier direkt mit gpu_cfr
      gebaut, unabhaengig von river_plan.py (E7: kein Eingriff in gpu_resolver).

KENNZAHLEN (getrennt):
  * w(pi_H) = min_sigmaV u(pi_H, sigmaV): EXAKTE Villain-Best-Response gegen die FESTE Hero-Politik im Baum
    (br_gegen_fest). Informationsmengen-treu: Villain maximiert je EIGENER Combo ueber die Aktionen gegen die
    Hero-REACH-gewichtete Summe (W @ reach_hero) — er sieht Heros Combo nicht (Kontrolle: Brute-Force-Fixture,
    tests/test_river_br_pruefstand.py). Gepaart: Delta E_H = w(pi_A) - w(pi_B) (Spielwert kuerzt sich).
  * Spielwert-Klammer [L, U]: L = w(pi_B) (Hero garantiert; auf dem Evaluationsbaum), U = max_H u_H(., sigma_V^Q)
    (Hero-BR gegen Villains gemittelte Q-Solverstrategie, 600 Iter, AUF DEM EVALUATIONSBAUM — Review MITTEL
    2026-09-07: ein U vom K2-Baum kann unter v*(eval) liegen, sobald die Schliessung Hero-Arme hinzufuegt).
    E_H(pi) = v* - w(pi) in [L - w, U - w]; L <= v* <= U exakt.
  * Lokaler Regret R(s,h;pi) = max_a Q(s,h,a) - sum_a pi(a|h) Q(s,h,a), Q = RiverCFRBatch.action_values der
    gemittelten Strategie eines 600-Iter-Solves (adaptiv genauer fuer Q-Urteile), gewichtet mit der
    Erreichwahrscheinlichkeit von (s,h) unter (pi_H, sigma_V^Q); Delta R = R(pi_A) - R(pi_B).
  * Nenner je Quellhand; bb/100 = mean_roots(Delta in bb) x 100 x Auswahlgewicht (n_roots>=Schwelle / n_haende).

BAUM-SCHLIESSUNG (Karte: 'finale Sizes beider Arme in den Evaluationsbaum'): Hero-Arme = K2 ∪ EXAKTE Arm-A-
Chipbetraege JE KNOTEN (rollen-spezifischer Baum, Villain-Arme = K2), iterativ bis kein Arm-A-Betrag mehr
off-tree ist (max MAX_SCHLIESSUNGSRUNDEN); sonst Root = UNSUPPORTED (ausgewiesen, NICHT projiziert). Arm-Zuordnung
ueber Chips mit Toleranz SIZE_TOL_CHIPS (= 1 Chip Engine-Truncation-Rauschen, KEIN Snapping auf den naechsten
K2-Arm; Review-Befund HOCH 2026-09-07: 8 % Pot projizierte 0,67-Pot-Bets auf 0,75); Jam = raise_max.
Arm B (auf dem K2-Baum geloest) wird VOR der Bewertung per Label auf den Evaluationsbaum abgebildet
(sigma_auf_baum; Review-Befund BLOCKER 2026-09-07: Spalten-Verschiebung -> IndexError/Unsupported sobald die
Schliessung einen Hero-Arm hinzufuegt). Zusatzarme werden je Root gezaehlt (Kostenfolge im Report).

Solver-Vertraege beachtet (V10_FAKTEN B10): avg_sigma liefert uniform bei Reach 0 -> PolicyTable.undefiniert via
Support-Maske; eff = echter Stack (nicht SPR-Bucket); Villain-Off-Tree existiert hier nicht (Baum-Villain).

ORACLE-ANFRAGE NUR MIT HERO-REACH > 0: an jedem Hero-Knoten fragt die Schliessung den Oracle nur fuer Combos mit
positiver Hero-Reach (Range x eigene Politik entlang des Pfads) — exakt fuer w/E_H/R (Reach-0-Zeilen tragen 0 in
br_gegen_fest und lokaler_regret) und der Kostenhebel des Oracles (policy_oracle.py: ~0,21 s GPU je Combo).
Statistik: einseitige 95 %-Obergrenze mit t-Quantil (n-1 Freiheitsgrade; Review NIEDRIG: 1,645 war bei n=5 zu
optimistisch); Auswahlgewicht = Roots mit pot_river >= --min-pot / alle Haende des Splits.

Run (Pilot B vs purifiziertes B, 5 Entwicklungs-Roots):
    python -m research.river_br_pruefstand --split entwicklung --roots 5 --arm-a purify
Run (Arm A via Oracle):
    python -m research.river_br_pruefstand --split holdout --arm-a oracle --kanal gym --seeds 4
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch

from pokerbot.strategy.contracts import ActionKey, PolicyTable, combo_index
from pokerbot.strategy.gpu_cfr import DEVICE, N_COMBOS, Node, RiverCFRBatch, range_vector, showdown_matrix
from research.policy_oracle import combos_mit_masse, zustand_nach_pfad

K2_BET_SIZES = (0.35, 0.75, 1.5)            # gpu_cfr.build_river_tree Defaults = K2 (Karte K2 'Baum')
K2_RAISE_SIZES = (2.7,)
K2_MAX_RAISES = 2
JAM_KOLLAPS = 0.85                          # gpu_cfr.py:123/143: Arme >= 85 % Reststack fallen mit Jam zusammen
ITERS_STRATEGIE = 150                       # K2: gemittelte Strategie nach 150 Iter (fp32)
ITERS_Q = 600                               # Q-Urteile: adaptiv genauer (tiefen_replay ITERS_TIEF)
SIZE_TOL_CHIPS = 1.0                        # Arm-Zuordnung: |Zusatz_A - Zusatz_Arm| <= 1 Chip (int-Truncation der
                                            # Engine-Betraege in pfad_zu_aktionen; Karte K2 'Sizes exakt')
MAX_SCHLIESSUNGSRUNDEN = 3
EXAKT_TRENNER = "@"                         # Label exakter Zusatzarme: 'bet@1340' / 'raise@3450' (Zusatz-Chips)
JAM_EXAKT_LABEL = "raise@jam"               # exakter Jam-Arm an raise-gekappten Knoten (endet auf 'jam' wie K2-Jams)
REACH_EPS = 1e-9                            # Hero-Knoten mit Reach-Masse darunter werden nicht abgefragt
SCHWELLE_CHIPS = 1500                       # Karte K2: pot_river >= 15 bb
BB = 100
AUSGABE_DIR = Path("data/runs/v10")
DTYPE = torch.float64                       # Bewertung exakt (fp64); die CFR-Solves bleiben fp32


class Unsupported(Exception):
    """Root nicht im Evaluationsbaum darstellbar (wird ausgewiesen, nie projiziert). `meta` = Schliessungs-Meta,
    falls der Abbruch in sigma_arm_a passierte (Pfade, Oracle-Zeiten bleiben im Report)."""

    def __init__(self, grund: str, meta: dict | None = None):
        super().__init__(grund)
        self.meta = meta


# ================================================================ Baum mit rollen-spezifischen Groessen
def exakt_label(art: str, zusatz_chips: int) -> str:
    """Label eines exakten Zusatzarms ('bet@1340'): Art + Zusatz-Chips, damit der Baum-Arm byte-gleich dem
    Oracle-Betrag ist (Karte K3: 'finale Sizes beider Arme in den Evaluationsbaum')."""
    return f"{art}{EXAKT_TRENNER}{int(zusatz_chips)}"


def baue_baum(pot: float, eff: float, bets_je_rolle: tuple[tuple, tuple], raises_je_rolle: tuple[tuple, tuple],
              max_raises: int = K2_MAX_RAISES, zusatz_exakt: dict[tuple[str, ...], set[int]] | None = None) -> Node:
    """gpu_cfr.build_river_tree mit GETRENNTEN Bet-/Raise-Menues je Rolle (0=OOP, 1=IP); Labels, Jam-Kollaps und
    Chip-Logik identisch (Test: mit K2-Menues beidseitig strukturgleich zu build_river_tree).

    zusatz_exakt = {Pfad: {Zusatz-Chips}}: EXAKTE Zusatzarme NUR am genannten Knoten (Schliessung der Arm-A-
    Betraege), nach den Fraktions-Armen und vor dem Jam eingefuegt. Sie unterliegen NICHT dem Jam-Kollaps (der ist
    eine K2-Abstraktionsregel; ein realer 0,9-Reststack-Bet ist eine eigene, exakt darstellbare Aktion), wohl aber
    der Legalitaet (Raise > to_call) und der Jam-Grenze (Zusatz < Reststack, sonst IST es der Jam).
    RAISE-GEKAPPTE KNOTEN (n_raises >= max_raises, K2 bietet nur fold/call): jamt Arm A dort (Zusatz >= Reststack),
    bekommt der Knoten den exakten Jam-Arm 'raise@jam' (Villain danach nur fold/call -> terminal; Pilot-Fund
    2026-09-07: Root 2988445 war sonst UNSUPPORTED 'unmappbar raise_to 19042' = Heros All-in nach zwei Raises)."""
    zusatz_exakt = zusatz_exakt or {}

    def exakte_arme(pfad, actor, invest, to_call, rest):
        """(zusatz, label) der exakten Zusatzarme am Knoten, aufsteigend; illegale/jam-gleiche Betraege entfallen."""
        art = "raise" if to_call > 0 else "bet"
        out = []
        for z in sorted(zusatz_exakt.get(pfad, ())):
            if z <= 0 or z >= rest or (to_call > 0 and z <= to_call):
                continue
            out.append((float(z), exakt_label(art, z)))
        return out

    def neu(actor, pot_n, invest, to_call, n_raises, pfad):
        n = Node(actor, pot_n, invest)
        rest = eff - invest[actor]
        if to_call > 0:
            n.acts.append("fold")
            f = Node(-1, pot_n, invest); f.terminal, f.fold_von = "fold", actor
            n.kids.append(f)
            n.acts.append("call")
            inv2 = list(invest); inv2[actor] += to_call
            c = Node(-1, pot_n + to_call, tuple(inv2)); c.terminal, c.sd_pot = "showdown", pot_n + to_call
            n.kids.append(c)
            if n_raises < max_raises and rest > to_call:
                arme = []
                for rf in tuple(sorted(raises_je_rolle[actor])):
                    zusatz = min(rest, to_call * rf)
                    if zusatz > to_call and zusatz < JAM_KOLLAPS * rest:
                        arme.append((zusatz, f"raise{rf}"))
                arme += exakte_arme(pfad, actor, invest, to_call, rest)
                arme.append((rest, "raisejam"))
                for zusatz, lbl in arme:
                    inv3 = list(invest); inv3[actor] += zusatz
                    n.acts.append(lbl)
                    n.kids.append(neu(1 - actor, pot_n + zusatz, tuple(inv3), zusatz - to_call, n_raises + 1,
                                      pfad + (lbl,)))
            elif rest > to_call and any(z >= rest for z in zusatz_exakt.get(pfad, ())):
                # Schliessung am raise-gekappten Knoten: Arm A geht all-in -> exakter Jam-Arm (Kind: Villain
                # mit n_raises+1 > max_raises -> nur fold/call, terminal)
                inv3 = list(invest); inv3[actor] += rest
                n.acts.append(JAM_EXAKT_LABEL)
                n.kids.append(neu(1 - actor, pot_n + rest, tuple(inv3), rest - to_call, n_raises + 1,
                                  pfad + (JAM_EXAKT_LABEL,)))
        else:
            n.acts.append("check")
            if actor == 0:
                n.kids.append(neu(1, pot_n, invest, 0.0, n_raises, pfad + ("check",)))
            else:
                s = Node(-1, pot_n, invest); s.terminal, s.sd_pot = "showdown", pot_n
                n.kids.append(s)
            if rest > 0:
                arme = []
                for bf in tuple(sorted(bets_je_rolle[actor])):
                    b = min(rest, bf * pot_n)
                    if b > 0 and b < JAM_KOLLAPS * rest:
                        arme.append((b, f"bet{bf}"))
                arme += exakte_arme(pfad, actor, invest, 0.0, rest)
                arme.append((rest, "betjam"))
                for b, lbl in arme:
                    inv2 = list(invest); inv2[actor] += b
                    n.acts.append(lbl)
                    n.kids.append(neu(1 - actor, pot_n + b, tuple(inv2), b, n_raises, pfad + (lbl,)))
        return n
    return neu(0, pot, (0.0, 0.0), 0.0, 0, ())


def zusatzarme(root: Node) -> list[tuple[str, str]]:
    """(Pfad, Label) aller exakten Zusatzarme im Baum — die Kostenfolge der Schliessung, im Report ausgewiesen."""
    return [("/".join(p) or "root", a) for p, n in knoten_mit_pfad(root) for a in n.acts if EXAKT_TRENNER in a]


def knoten_mit_pfad(root: Node) -> list[tuple[tuple[str, ...], Node]]:
    out, stapel = [], [((), root)]
    while stapel:
        pfad, n = stapel.pop()
        out.append((pfad, n))
        stapel.extend((pfad + (a,), k) for a, k in zip(n.acts, n.kids))
    return out


def knoten_am_pfad(root: Node, pfad: tuple[str, ...]) -> Node:
    n = root
    for a in pfad:
        n = n.kids[n.acts.index(a)]
    return n


class CFRAufBaum(RiverCFRBatch):
    """RiverCFRBatch auf einem VORGEGEBENEN Baum (B=1). Nur __init__ ersetzt (gpu_cfr.py:267-292 bis auf die
    Baumquelle identisch); Traversal/avg_sigma/_br/action_values/exploitability sind die geerbten Originale."""

    def __init__(self, board: list[str], r_oop: torch.Tensor, r_ip: torch.Tensor, pot: float, baum: Node):
        self.B, self.half = 1, False
        W, M = showdown_matrix(board)
        self.W, self.M = W.unsqueeze(0), M.unsqueeze(0)
        lebt = self.M.sum(dim=2) > 0
        self.r = [torch.where(lebt, r_oop.to(DEVICE).unsqueeze(0), torch.zeros(1, device=DEVICE)),
                  torch.where(lebt, r_ip.to(DEVICE).unsqueeze(0), torch.zeros(1, device=DEVICE))]
        self.root = baum
        self.pot0 = pot
        for _, n in knoten_mit_pfad(baum):
            if n.actor >= 0:
                n.regret = torch.zeros(1, N_COMBOS, len(n.acts), device=DEVICE)
                n.strat_sum = torch.zeros(1, N_COMBOS, len(n.acts), device=DEVICE)


# ================================================================ Bewertung: feste Politik vs exakte BR
class RiverSpiel:
    """Terminal-Nutzen des River-Subgames in fp64 (Konvention gpu_cfr.py:306-313: zentriert um -pot0/2, nullsummig).
    r[rolle] = Range-Vektoren (Board-maskiert). Nutzen in CHIPS."""

    def __init__(self, board: list[str], pot: float, r_oop, r_ip):
        W, M = showdown_matrix(board)
        self.W, self.M = W.to(DTYPE), M.to(DTYPE)
        lebt = self.M.sum(dim=1) > 0
        null = torch.zeros(1, device=DEVICE, dtype=DTYPE)
        self.r = [torch.where(lebt, r_oop.to(DEVICE).to(DTYPE), null), torch.where(lebt, r_ip.to(DEVICE).to(DTYPE), null)]
        self.pot0 = float(pot)
        self.n_combos = N_COMBOS
        self.paare = float((self.r[0].unsqueeze(1) * self.r[1].unsqueeze(0) * self.M).sum())

    def terminal_nutzen(self, n: Node, reach_opp: torch.Tensor, spieler: int) -> torch.Tensor:
        if n.terminal == "showdown":
            return (n.sd_pot / 2.0) * (self.W @ reach_opp)
        eigen = n.invest[spieler]
        nutzen = -(self.pot0 / 2.0 + eigen) if n.fold_von == spieler else n.pot - (self.pot0 / 2.0 + eigen)
        return nutzen * (self.M @ reach_opp)

    def offset(self) -> float:
        """Terminalwerte = Netto-Chips seit River-Beginn MINUS pot0/2 -> +offset ergibt Netto-Chips."""
        return self.pot0 / 2.0


def br_gegen_fest(spiel, root: Node, sigma_fest: dict, spieler_br: int) -> tuple[float, torch.Tensor]:
    """Exakte Best Response des Spielers `spieler_br` gegen die FESTE Gegner-Politik sigma_fest {pfad: [n,n_acts]}.
    An Gegner-Knoten ohne Eintrag muss die Gegner-Reach 0 sein (sonst Unsupported). Rueckgabe (Wert je
    kompatiblem Paar, BR-Vektor je eigener Combo)."""
    r_me, r_opp = spiel.r[spieler_br], spiel.r[1 - spieler_br]

    def rek(n: Node, pfad: tuple, reach_opp: torch.Tensor) -> torch.Tensor:
        if n.terminal is not None:
            return spiel.terminal_nutzen(n, reach_opp, spieler_br)
        if n.actor == spieler_br:
            return torch.stack([rek(k, pfad + (a,), reach_opp) for a, k in zip(n.acts, n.kids)], dim=1).max(dim=1).values
        sig = sigma_fest.get(pfad)
        if sig is None:
            if float(reach_opp.abs().sum()) == 0.0:
                return torch.zeros(spiel.n_combos, device=reach_opp.device, dtype=reach_opp.dtype)
            raise Unsupported(f"Politik fehlt am erreichbaren Knoten {pfad}")
        v = torch.zeros(spiel.n_combos, device=reach_opp.device, dtype=reach_opp.dtype)
        for a, (lbl, k) in enumerate(zip(n.acts, n.kids)):
            v = v + rek(k, pfad + (lbl,), reach_opp * sig[:, a])
        return v
    vec = rek(root, (), r_opp)
    return float((vec * r_me).sum() / spiel.paare), vec


def garantiewert(spiel, root: Node, sigma_hero: dict, hero_rolle: int) -> float:
    """w(pi_H) = min_sigmaV u_H(pi_H, sigmaV) = -(Villains BR-Wert) im Nullsummenspiel."""
    wert_v, _ = br_gegen_fest(spiel, root, sigma_hero, 1 - hero_rolle)
    return -wert_v


def reach_je_knoten(spiel, root: Node, sigma: dict, rolle: int) -> dict:
    """{pfad: Reach-Vektor der Rolle am Knoten} (Range x eigene Politik entlang des Pfads); fehlende Politik bei
    Reach 0 -> Teilbaum bekommt 0."""
    out = {}

    def rek(n: Node, pfad: tuple, reach: torch.Tensor) -> None:
        out[pfad] = reach
        if n.terminal is not None:
            return
        if n.actor == rolle:
            sig = sigma.get(pfad)
            for a, (lbl, k) in enumerate(zip(n.acts, n.kids)):
                rek(k, pfad + (lbl,), reach * sig[:, a] if sig is not None else torch.zeros_like(reach))
        else:
            for lbl, k in zip(n.acts, n.kids):
                rek(k, pfad + (lbl,), reach)
    rek(root, (), spiel.r[rolle].clone())
    return out


def sigma_aus_cfr(cfr: RiverCFRBatch, root: Node, rolle: int) -> dict:
    """{pfad: avg_sigma [1326, n_acts] (fp64)} fuer alle Knoten der Rolle."""
    return {p: cfr.avg_sigma(n)[0].to(DTYPE) for p, n in knoten_mit_pfad(root) if n.actor == rolle}


def sigma_auf_baum(sigma_quelle: dict, baum_quelle: Node, baum_ziel: Node, rolle: int) -> dict:
    """Politik der Rolle vom Quellbaum auf den Zielbaum abbilden — Spalten per LABEL (n.acts), nie per Index.
    Zielarme ohne Quell-Gegenstueck (die exakten Arm-A-Zusatzarme) bekommen Masse 0; Knoten der Rolle unter
    solchen Armen existieren im Quellbaum nicht und erhalten 0-Zeilen (Reach der Rolle dort = 0). Villain-Arme
    sind in beiden Baeumen K2, daher deckt der Quellpfad jeden Zielpfad, der keinen Zusatzarm enthaelt.
    Exakt: eine Spaltenkopie aendert keinen Wert; ungenutzte Zusatzarme addieren exakt 0 (Test: w_B identisch)."""
    quelle = {p: n for p, n in knoten_mit_pfad(baum_quelle) if n.actor == rolle}
    out = {}
    for pfad, n in knoten_mit_pfad(baum_ziel):
        if n.actor != rolle:
            continue
        nq = quelle.get(pfad)
        if nq is None or pfad not in sigma_quelle:
            out[pfad] = torch.zeros(N_COMBOS, len(n.acts), device=DEVICE, dtype=DTYPE)
            continue
        sq = sigma_quelle[pfad]
        sig = torch.zeros(N_COMBOS, len(n.acts), device=sq.device, dtype=sq.dtype)
        for j, lbl in enumerate(n.acts):
            if lbl in nq.acts:
                sig[:, j] = sq[:, nq.acts.index(lbl)]
        out[pfad] = sig
    fehlend = [lbl for p, nq in quelle.items() for lbl in nq.acts
               if p in sigma_quelle and lbl not in knoten_am_pfad_oder_none(baum_ziel, p)]
    if fehlend:
        raise Unsupported(f"Quellarme ohne Zielarm (Masse ginge verloren): {fehlend[:5]}")
    return out


def knoten_am_pfad_oder_none(root: Node, pfad: tuple[str, ...]) -> list[str]:
    """Aktionslabels am Zielpfad ([] falls der Pfad im Baum nicht existiert)."""
    n = root
    for a in pfad:
        if a not in n.acts:
            return []
        n = n.kids[n.acts.index(a)]
    return n.acts


def purifiziere(sigma: dict) -> dict:
    """Modalaktion je Combo (Purify-Kontrolle: weiche Plausibilitaet, Karte K3)."""
    out = {}
    for p, s in sigma.items():
        idx = s.argmax(dim=1)
        out[p] = torch.zeros_like(s).scatter_(1, idx.unsqueeze(1), 1.0)
    return out


# ================================================================ Lokaler Regret
def lokaler_regret(cfr_q: RiverCFRBatch, root: Node, spiel, sigma_pi: dict, hero_rolle: int) -> tuple[float, dict]:
    """R(pi) = sum_s sum_h P(s,h | pi_H, sigma_V^Q) [max_a Q - sum_a pi Q] in Chips je Wurzel-Hand. Q aus
    action_values der gemittelten Q-Strategie; Villain-Reach am Knoten = Range x avg_sigma^Q entlang des Pfads
    (wie gpu_resolver._navigiere_mit_reach). Knoten ohne pi-Eintrag tragen Reach 0 (nichts zu regrettieren)."""
    sigma_vq = sigma_aus_cfr(cfr_q, root, 1 - hero_rolle)
    reach_h = reach_je_knoten(spiel, root, sigma_pi, hero_rolle)
    reach_v = reach_je_knoten(spiel, root, sigma_vq, 1 - hero_rolle)
    summe, je_knoten = 0.0, {}
    for pfad, n in knoten_mit_pfad(root):
        if n.actor != hero_rolle or pfad not in sigma_pi:
            continue
        rh = reach_h[pfad]
        if float(rh.sum()) <= 0.0:
            continue
        rv = reach_v[pfad].to(torch.float32).unsqueeze(0)
        q = cfr_q.action_values(n, rv, hero_rolle)[0].to(DTYPE)          # [1326, n] normiert je Combo
        masse = spiel.M @ reach_v[pfad]                                   # kompatible Villain-Masse je Hero-Combo
        pi = sigma_pi[pfad]
        regret = q.max(dim=1).values - (pi * q).sum(dim=1)
        gewicht = rh * masse / spiel.paare
        beitrag = float((gewicht * regret).sum())
        je_knoten["/".join(pfad) or "root"] = beitrag
        summe += beitrag
    return summe, je_knoten


# ================================================================ Arm A: PolicyTable -> Baum-Sigma (Schliessung)
def rolle_zu_seat(rolle: int, button: int) -> int:
    return button if rolle == 1 else 1 - button


def pfad_zu_aktionen(root: Node, pfad: tuple[str, ...], button: int, root_state: dict) -> list[dict]:
    """Baumpfad -> konkrete Engine-Aktionen (player, action, to) mit int-Truncation der Baum-Chips."""
    akt, n = [], root
    committed = {0: int(root_state["players"][0]["committed_street"]), 1: int(root_state["players"][1]["committed_street"])}
    for lbl in pfad:
        k = n.kids[n.acts.index(lbl)]
        seat = rolle_zu_seat(n.actor, button)
        if lbl == "check":
            akt.append({"player": seat, "action": "check"})
        elif lbl == "call":
            akt.append({"player": seat, "action": "call"})
            committed[seat] = max(committed.values())
        elif lbl == "fold":
            raise ValueError("fold auf einem Entscheidungspfad")
        else:
            zusatz = int(k.invest[n.actor] - n.invest[n.actor])
            committed[seat] += zusatz
            akt.append({"player": seat, "action": "bet" if lbl.startswith("bet") else "raise", "to": committed[seat]})
        n = k
    return akt


def key_zu_arm(key: ActionKey, n: Node, hero_rolle: int, st: dict, hero_seat: int):
    """(Arm-Index | None, fehlender Zusatz | None). Fehlender Zusatz = ('exakt', Zusatz-Chips) = der EXAKTE
    Betrag, den die Schliessung als eigenen Arm an diesem Knoten einfuegt (keine Fraktion, keine Rundung)."""
    la = st["legal"]
    if key.kind in ("fold", "check", "call"):
        return (n.acts.index(key.kind) if key.kind in n.acts else None), None
    zusatz = key.chips - int(st["players"][hero_seat]["committed_street"])
    if la["to_call"] > 0 and abs(zusatz - la["to_call"]) <= SIZE_TOL_CHIPS and "call" in n.acts:
        # 'Raise' um hoechstens 1 Chip ueber den Call = der Call im Truncation-Fenster (Pilot-Fund 2988445: Villains
        # Baum-Jam kommt im Engine-State 1 Chip kurz an, Hero setzt den letzten Chip 'als Raise' nach)
        return n.acts.index("call"), None
    if key.chips >= la["raise_max"] - SIZE_TOL_CHIPS:                       # Jam = raise_max
        jam = next((i for i, a in enumerate(n.acts) if a.endswith("jam")), None)
        if jam is None and la.get("can_raise"):
            return None, ("exakt", int(zusatz))      # raise-gekappter Knoten: Jam wird als exakter Arm geschlossen
        return jam, None
    best = None
    for i, (a, k) in enumerate(zip(n.acts, n.kids)):
        if not a.startswith(("bet", "raise")):
            continue
        d = abs((k.invest[hero_rolle] - n.invest[hero_rolle]) - zusatz)
        if d <= SIZE_TOL_CHIPS and (best is None or d < best[1]):
            best = (i, d)
    if best is not None:
        return best[0], None
    return None, ("exakt", int(zusatz))


def tabelle_zu_sigma(tab: PolicyTable, n: Node, hero_rolle: int, st: dict, hero_seat: int, gewicht: torch.Tensor):
    """PolicyTable -> [1326, n_acts]-Sigma am Knoten. `gewicht` [1326] = Hero-Reach am Knoten (oder die Range):
    undefinierte Combos mit gewicht>0 -> Unsupported; off-tree Groessen werden gesammelt (Schliessung); Combos ohne
    Zeile und gewicht==0 bleiben 0-Zeilen (sie tragen in keiner Kennzahl)."""
    sig = torch.zeros(N_COMBOS, len(n.acts), device=DEVICE, dtype=DTYPE)
    arm_je_key, schliessbar_je_key, fehlend = {}, {}, set()
    for key in tab.aktionen:
        idx, neu = key_zu_arm(key, n, hero_rolle, st, hero_seat)
        arm_je_key[key], schliessbar_je_key[key] = idx, neu
    rh = gewicht.to(DEVICE)
    for combo, probs in tab.zeilen:
        ci = combo_index(*combo)
        if float(rh[ci]) <= 0.0:
            continue
        for key, p in zip(tab.aktionen, probs):
            if p <= 0:
                continue
            idx = arm_je_key[key]
            if idx is None:
                # Off-Tree-Betrag MIT Masse: schliessbar (('exakt', Zusatz-Chips) -> eigener Arm in der naechsten
                # Runde) oder endgueltig unmappbar (fold/check/call/jam ohne Baum-Arm). Nur Keys, die eine Combo mit
                # Range-Gewicht tatsaechlich nutzt, zaehlen — sonst blaeht jede Phantom-Size den Baum auf. (Pilot
                # smoke_oracle_root1: jede schliessbare Size wurde zusaetzlich als 'unmappbar' gemeldet.)
                neu = schliessbar_je_key[key]
                fehlend.add(neu if neu is not None else ("unmappbar", key.kind, key.chips))
                continue
            sig[ci, idx] += p
    for combo in tab.undefiniert:
        if float(rh[combo_index(*combo)]) > 0.0:
            raise Unsupported(f"Oracle undefiniert fuer Combo {combo} mit Range-Gewicht > 0")
    return sig, fehlend


def sigma_arm_a(orakel, root: dict, spiel, r_hero: torch.Tensor, hero_rolle: int):
    """Schliessungs-Schleife: Baum bauen, A an erreichbaren Hero-Knoten abfragen, off-tree Sizes einarbeiten.
    Rueckgabe (baum, sigma_A, meta)."""
    pot, eff, button, hs = root["pot_river"], root["eff"], root["button"], root["hero_seat"]
    zusatz_exakt: dict[tuple[str, ...], set[int]] = {}
    meta = {"runden": 0, "zusatz_exakt": {}, "n_zusatz_arme": 0, "knoten_abgefragt": 0, "knoten_uebersprungen": 0,
            "oracle_meta": []}
    for runde in range(1, MAX_SCHLIESSUNGSRUNDEN + 1):
        meta["runden"] = runde
        baum = baue_baum(pot, eff, (K2_BET_SIZES, K2_BET_SIZES), (K2_RAISE_SIZES, K2_RAISE_SIZES),
                         zusatz_exakt=zusatz_exakt)
        try:
            _pruefe_zusatzarme(baum, zusatz_exakt, hero_rolle)
        except Unsupported as e:
            raise Unsupported(str(e), meta) from None
        sigma, neu_je_pfad = {}, {}
        # Knoten in Pfad-Reihenfolge (DFS ab Root), damit die A-Reach fuer die Pruning-Entscheidung vorliegt
        for pfad, n in sorted(knoten_mit_pfad(baum), key=lambda pn: len(pn[0])):
            if n.actor != hero_rolle:
                continue
            reach = reach_je_knoten(spiel, baum, sigma, hero_rolle).get(pfad)
            if reach is None or float(reach.sum()) <= REACH_EPS * max(1e-30, float(spiel.r[hero_rolle].sum())):
                meta["knoten_uebersprungen"] += 1
                continue
            st = _zustand(root, baum, pfad, button, hs)
            tab, om = orakel.tabelle(root["root_hash"], st, hs, combos=combos_mit_masse(reach))
            if not om.get("gueltig", True):
                raise Unsupported(f"Oracle-Tabelle ungueltig (GPU-Solve-Fehler {om.get('gpu_solve_fehler')}) am Knoten {pfad}")
            meta["knoten_abgefragt"] += 1
            meta["oracle_meta"].append({"pfad": "/".join(pfad) or "root", "sekunden": om.get("sekunden"),
                                        "herkunft": om.get("herkunft"), "fehler": len(om.get("fehler", []))})
            sig, fehlend = tabelle_zu_sigma(tab, n, hero_rolle, st, hs, reach)
            if fehlend:
                neu_je_pfad[pfad] = fehlend
            sigma[pfad] = sig
        print(f"    [root {root['hand_id']}] Runde {runde}: {meta['knoten_abgefragt']} Knoten abgefragt, "
              f"{meta['knoten_uebersprungen']} ohne Reach, offene Sizes an {len(neu_je_pfad)} Knoten", flush=True)
        unloesbar = [x for f in neu_je_pfad.values() for x in f if x[0] != "exakt"]
        if unloesbar:
            raise Unsupported(f"nicht darstellbare Arm-A-Aktionen: {sorted(map(str, unloesbar))[:5]}", meta)
        if not neu_je_pfad:
            _normiere_sigma(sigma, r_hero)
            meta["n_zusatz_arme"] = len(zusatzarme(baum))
            return baum, sigma, meta
        for pfad, fehlend in neu_je_pfad.items():
            zusatz_exakt.setdefault(pfad, set()).update(z for _, z in fehlend)
        meta["zusatz_exakt"] = {"/".join(p) or "root": sorted(z) for p, z in zusatz_exakt.items()}
    raise Unsupported(f"Schliessung nach {MAX_SCHLIESSUNGSRUNDEN} Runden offen: zusatz_exakt {meta['zusatz_exakt']}", meta)


def _pruefe_zusatzarme(baum: Node, zusatz_exakt: dict, hero_rolle: int) -> None:
    """Jeder verlangte exakte Zusatzarm muss am genannten Hero-Knoten mit EXAKT diesem Zusatz existieren
    (|Arm-Zusatz - Chips| <= SIZE_TOL_CHIPS); fehlt er (Illegal/Jam-gleich), ist der Root UNSUPPORTED statt
    endlos zu schliessen."""
    for pfad, betraege in zusatz_exakt.items():
        n = knoten_am_pfad(baum, pfad)
        if n.actor != hero_rolle:
            raise Unsupported(f"Zusatzarm an Nicht-Hero-Knoten {pfad}")
        arme = {round(k.invest[hero_rolle] - n.invest[hero_rolle]) for a, k in zip(n.acts, n.kids) if EXAKT_TRENNER in a}
        if JAM_EXAKT_LABEL in n.acts:                                          # Jam-Zusatz = Reststack (Test: z >= rest)
            arme.add(round(n.kids[n.acts.index(JAM_EXAKT_LABEL)].invest[hero_rolle] - n.invest[hero_rolle]))
        for z in betraege:
            if not any(abs(z - arm) <= SIZE_TOL_CHIPS for arm in arme):
                raise Unsupported(f"Zusatzarm {z} Chips am Knoten {'/'.join(pfad) or 'root'} nicht darstellbar "
                                  f"(illegal oder jam-gleich; Arme {sorted(arme)})")


def _normiere_sigma(sigma: dict, r_hero: torch.Tensor) -> None:
    """Zeilen mit Masse -> Sigma-Zeilen Σ=1 (Oracle-Zeilen summieren bereits zu 1; Rundung absichern)."""
    for p, s in sigma.items():
        tot = s.sum(dim=1, keepdim=True)
        sigma[p] = torch.where(tot > 0, s / tot.clamp(min=1e-300), s)


def _zustand(root: dict, baum: Node, pfad: tuple, button: int, hs: int) -> dict:
    return zustand_nach_pfad(root["root_state"], pfad_zu_aktionen(baum, pfad, button, root["root_state"]), hs)


# ================================================================ Root-Bewertung
def hero_range_fuer(root: dict, sensitivitaet: str = "tracker") -> tuple[dict, str]:
    """rho_s Hero-Range: K1 falls vorhanden, sonst Tracker (Flag)."""
    rg = root["ranges"]
    if rg.get("hero_k1"):
        return rg["hero_k1"], "k1_likelihood"
    return rg["hero_tracker"], "tracker"


def villain_range_fuer(root: dict, familie: str = "tracker") -> dict:
    """Villain-Range-Familie: 'tracker' (Standard) oder 'preflop' (Nullhypothese: Tracker-Prior ohne Postflop-
    Bayes; tiefen_replay._range_am_schnitt-Semantik)."""
    if familie == "tracker":
        return root["ranges"]["vill_tracker"]
    from pokerbot.strategy.range_tracker import RangeTracker
    st = dict(root["root_state"])
    hist = st.get("history", []) or []
    cut = next((i for i, h in enumerate(hist) if h.get("action") == "deal"), None)
    st["history"] = hist[:cut] if cut is not None else hist
    t = RangeTracker().build(st)
    return t.range.get(1 - root["hero_seat"], {})


def bewerte_root(root: dict, orakel=None, arm_a: str = "purify", villain_familie: str = "tracker") -> dict:
    """Ein Root: B solven (K2, 150 Iter), Q solven (600 Iter, Evaluationsbaum), A aus Oracle ODER Dummy
    (purifiziertes B), w/E_H/Regret berechnen. Alle Chip-Werte -> bb."""
    t0 = time.perf_counter()
    board, pot, eff = root["board"], float(root["pot_river"]), float(root["eff"])
    hero_rolle = 0 if root["hero_oop"] else 1
    hero_w, hero_herkunft = hero_range_fuer(root)
    vill_w = villain_range_fuer(root, villain_familie)
    r_hero, r_vill = range_vector(hero_w), range_vector(vill_w)
    r_oop, r_ip = (r_hero, r_vill) if hero_rolle == 0 else (r_vill, r_hero)
    spiel = RiverSpiel(board, pot, r_oop, r_ip)
    out = {"hand_id": root["hand_id"], "provenienz": root["provenienz"], "split": root["split"],
           "pot_river_bb": pot / BB, "eff_bb": eff / BB, "hero_oop": root["hero_oop"], "board": "".join(board),
           "hero_range": hero_herkunft, "villain_familie": villain_familie, "status": "ok",
           "n_hero_range": len(hero_w), "n_vill_range": len(vill_w)}
    if spiel.paare <= 0:
        out.update(status="UNSUPPORTED", grund="keine kompatiblen Range-Paare")
        return out
    # --- B: K2-Baum, 150 Iter
    baum_k2 = baue_baum(pot, eff, (K2_BET_SIZES, K2_BET_SIZES), (K2_RAISE_SIZES, K2_RAISE_SIZES))
    cfr_b = CFRAufBaum(board, r_oop, r_ip, pot, baum_k2)
    cfr_b.solve(iters=ITERS_STRATEGIE)
    sigma_b = sigma_aus_cfr(cfr_b, baum_k2, hero_rolle)
    out["expl_b_pct_pot"] = float(cfr_b.exploitability()[0])
    # --- A: Oracle (mit Schliessung) oder Dummy
    try:
        if arm_a == "oracle":
            baum_eval, sigma_a, meta_a = sigma_arm_a(orakel, root, spiel, r_hero, hero_rolle)
        elif arm_a == "purify":
            baum_eval, sigma_a, meta_a = baum_k2, purifiziere(sigma_b), {"dummy": "purify(B)"}
        elif arm_a == "identisch":
            baum_eval, sigma_a, meta_a = baum_k2, sigma_b, {"dummy": "A==B"}
        else:
            raise ValueError(arm_a)
        out["arm_a_meta"] = meta_a
        # --- B auf den Evaluationsbaum abbilden (per Label; Zusatzarme = Masse 0). Ohne diesen Schritt sind die
        # Spalten von sigma_b gegen n.acts des Evaluationsbaums verschoben (Review-BLOCKER 2026-09-07).
        sigma_b_eval = sigma_auf_baum(sigma_b, baum_k2, baum_eval, hero_rolle)
        # --- Q: 600 Iter auf dem Evaluationsbaum (Hero-Arme ∪ exakte A-Betraege)
        cfr_q = CFRAufBaum(board, r_oop, r_ip, pot, baum_eval)
        cfr_q.solve(iters=ITERS_Q)
        out["expl_q_pct_pot"] = float(cfr_q.exploitability()[0])
        # --- Kennzahlen (Chips -> bb; +offset = Netto seit River-Beginn)
        w_a = garantiewert(spiel, baum_eval, sigma_a, hero_rolle)
        w_b = garantiewert(spiel, baum_eval, sigma_b_eval, hero_rolle)
        w_b_k2 = garantiewert(spiel, baum_k2, sigma_b, hero_rolle)         # Selbstkontrolle: muss == w_b sein
        # U: Hero-BR vs Villains gemittelte Q-Strategie AUF DEM EVALUATIONSBAUM (Review MITTEL: ein U vom K2-Baum
        # unterschreitet v*(eval), sobald die Schliessung Hero-Arme hinzufuegt -> Band falsch beschriftet)
        sigma_vq = sigma_aus_cfr(cfr_q, baum_eval, 1 - hero_rolle)
        u_eval, _ = br_gegen_fest(spiel, baum_eval, sigma_vq, hero_rolle)
        r_a, _ = lokaler_regret(cfr_q, baum_eval, spiel, sigma_a, hero_rolle)
        r_b, _ = lokaler_regret(cfr_q, baum_eval, spiel, sigma_b_eval, hero_rolle)
        off = spiel.offset()
        out.update(w_a_bb=(w_a + off) / BB, w_b_bb=(w_b + off) / BB, w_b_k2_bb=(w_b_k2 + off) / BB,
                   delta_e_h_bb=(w_a - w_b) / BB, L_bb=(w_b + off) / BB, U_bb=(u_eval + off) / BB,
                   u_baum=f"eval(Q, {ITERS_Q} Iter)",
                   e_h_a_band_bb=[(w_b - w_a) / BB, (u_eval - w_a) / BB], e_h_b_band_bb=[0.0, (u_eval - w_b) / BB],
                   regret_a_bb=r_a / BB, regret_b_bb=r_b / BB, delta_regret_bb=(r_a - r_b) / BB,
                   n_knoten_eval=len(knoten_mit_pfad(baum_eval)), n_zusatz_arme=len(zusatzarme(baum_eval)))
    except Unsupported as e:
        out.update(status="UNSUPPORTED", grund=str(e))
        if e.meta is not None:
            out["arm_a_meta"] = e.meta
    except (IndexError, RuntimeError) as e:
        # Sicherheitsnetz: ein Tensor-/Solver-Fehler an EINEM Root darf den Lauf nicht abbrechen; er wird als
        # UNSUPPORTED mit Typ ausgewiesen (nie still, nie projiziert). CUDA-OOM landet hier ebenfalls sichtbar.
        out.update(status="UNSUPPORTED", grund=f"{type(e).__name__}: {str(e)[:200]}")
    out["sekunden"] = round(time.perf_counter() - t0, 2)
    return out


# ================================================================ Aggregation + Report
def _mittel_se(x: list[float]) -> tuple[float, float]:
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(x) / n
    var = sum((v - m) ** 2 for v in x) / max(1, n - 1)
    return m, math.sqrt(var / n)


def aggregiere(ergebnisse: list[dict], n_haende: int, n_roots_ge_schwelle: int) -> dict:
    ok = [e for e in ergebnisse if e["status"] == "ok"]
    gewicht = n_roots_ge_schwelle / max(1, n_haende)                       # Auswahlgewicht (Karte: ausgewiesen)
    agg = {"n_bewertet": len(ok), "n_unsupported": sum(1 for e in ergebnisse if e["status"] != "ok"),
           "n_haende": n_haende, "n_roots_ge_schwelle": n_roots_ge_schwelle, "auswahlgewicht": gewicht,
           "unsupported_gruende": [e.get("grund") for e in ergebnisse if e["status"] != "ok"]}
    for name in ("delta_e_h_bb", "delta_regret_bb", "w_a_bb", "w_b_bb", "regret_a_bb", "regret_b_bb"):
        m, se = _mittel_se([e[name] for e in ok])
        agg[name] = {"mittel_bb_je_root": m, "se": se,
                     "bb100_alle_haende": m * 100 * gewicht, "se_bb100": se * 100 * gewicht}
    # Kostenfolge der exakten Schliessung (Karte: ausgewiesen, nicht per Toleranz versteckt)
    agg["zusatz_arme_gesamt"] = sum(e.get("n_zusatz_arme", 0) for e in ok)
    agg["roots_mit_zusatzarmen"] = sum(1 for e in ok if e.get("n_zusatz_arme", 0) > 0)
    # Selbstkontrolle der B-Abbildung: w_B auf dem Evaluationsbaum == w_B auf dem K2-Baum (exakt erwartet)
    agg["max_abw_w_b_eval_vs_k2_bb"] = max((abs(e["w_b_bb"] - e["w_b_k2_bb"]) for e in ok), default=0.0)
    q, art = _quantil_95(len(ok))
    agg["quantil_95"], agg["quantil_art"] = q, art
    d = agg["delta_e_h_bb"]
    agg["delta_e_h_obergrenze95_bb100"] = d["bb100_alle_haende"] + q * d["se_bb100"]     # Karte: einseitig 95 %
    r = agg["delta_regret_bb"]
    agg["delta_regret_obergrenze95_bb100"] = r["bb100_alle_haende"] + q * r["se_bb100"]
    return agg


def _quantil_95(n: int) -> tuple[float, str]:
    """Einseitiges 95 %-Quantil fuer die Obergrenze: Student-t mit n-1 Freiheitsgraden (n=5: 2,13 statt 1,645)."""
    if n < 2:
        return float("inf"), "t (n<2: unendlich)"
    try:
        from scipy.stats import t
        return float(t.ppf(0.95, n - 1)), f"t({n - 1})"
    except Exception:  # noqa: BLE001
        return 1.645, "normal (scipy fehlt)"


def schreibe_report(name: str, konfig: dict, ergebnisse: list[dict], agg: dict) -> tuple[Path, Path]:
    AUSGABE_DIR.mkdir(parents=True, exist_ok=True)
    pj = AUSGABE_DIR / f"{name}.json"
    pm = AUSGABE_DIR / f"{name}.md"
    pj.write_text(json.dumps({"konfig": konfig, "aggregat": agg, "roots": ergebnisse}, indent=1, ensure_ascii=False,
                             default=str), encoding="utf-8")
    zeilen = [f"# River-BR-Pruefstand — {name}", "", f"Konfig: `{json.dumps(konfig, default=str)}`", "",
              f"Bewertet {agg['n_bewertet']} Roots, UNSUPPORTED {agg['n_unsupported']}; Haende {agg['n_haende']}, "
              f"Roots >= Schwelle {agg['n_roots_ge_schwelle']} -> Auswahlgewicht {agg['auswahlgewicht']:.3f}"
              + (f"; ABGEBROCHEN: {agg['abgebrochen']}" if agg.get("abgebrochen") else ""), "",
              f"Exakte Zusatzarme (Schliessung): {agg['zusatz_arme_gesamt']} in {agg['roots_mit_zusatzarmen']} Roots; "
              f"Selbstkontrolle max |w_B(eval) - w_B(K2)| = {agg['max_abw_w_b_eval_vs_k2_bb']:.2e} bb", "",
              "| Kennzahl | Mittel bb/Root | SE | bb/100 (alle Haende) | SE bb/100 |", "|---|---|---|---|---|"]
    for k in ("delta_e_h_bb", "delta_regret_bb", "w_a_bb", "w_b_bb", "regret_a_bb", "regret_b_bb"):
        v = agg[k]
        zeilen.append(f"| {k} | {v['mittel_bb_je_root']:+.3f} | {v['se']:.3f} | {v['bb100_alle_haende']:+.3f} | {v['se_bb100']:.3f} |")
    zeilen += ["", f"Einseitige 95%-Obergrenze ({agg['quantil_art']}, q={agg['quantil_95']:.3f}) Delta E_H: "
               f"{agg['delta_e_h_obergrenze95_bb100']:+.3f} bb/100; Delta R: {agg['delta_regret_obergrenze95_bb100']:+.3f} "
               f"bb/100 (Gate: beide <= +0,5, eine < 0)", "",
               "| hand_id | prov | pot bb | eff bb | OOP | w_A | w_B | dE_H | [L,U] | R_A | R_B | dR | expl_B % | +Arme | s | Status |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in ergebnisse:
        if e["status"] == "ok":
            zeilen.append(f"| {e['hand_id']} | {e['provenienz']} | {e['pot_river_bb']:.1f} | {e['eff_bb']:.0f} | {int(e['hero_oop'])} | "
                          f"{e['w_a_bb']:+.2f} | {e['w_b_bb']:+.2f} | {e['delta_e_h_bb']:+.3f} | [{e['L_bb']:+.2f},{e['U_bb']:+.2f}] | "
                          f"{e['regret_a_bb']:.3f} | {e['regret_b_bb']:.3f} | {e['delta_regret_bb']:+.3f} | "
                          f"{e['expl_b_pct_pot']:.2f} | {e.get('n_zusatz_arme', 0)} | {e['sekunden']} | ok |")
        else:
            zeilen.append(f"| {e['hand_id']} | {e['provenienz']} | {e['pot_river_bb']:.1f} | {e['eff_bb']:.0f} | {int(e['hero_oop'])} | "
                          f"| | | | | | | | | {e.get('sekunden', '')} | UNSUPPORTED: {e.get('grund', '')[:60]} |")
    pm.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pj, pm


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="entwicklung", choices=("entwicklung", "holdout"))
    ap.add_argument("--roots", type=int, default=5)
    ap.add_argument("--arm-a", default="purify", choices=("purify", "identisch", "oracle"))
    ap.add_argument("--kanal", default="gym")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--min-pot", type=float, default=SCHWELLE_CHIPS)
    ap.add_argument("--villain", default="tracker", choices=("tracker", "preflop"))
    ap.add_argument("--name", default=None)
    ap.add_argument("--hand-ids", default="", help="Kommaliste konkreter Roots (statt der ersten --roots des Splits)")
    ap.add_argument("--zeitbudget-s", type=float, default=0.0,
                    help="kein neuer Root nach Ablauf (0 = unbegrenzt); der Report weist den Abbruch aus")
    args = ap.parse_args()
    from research.k3_roots import lade_roots
    kopf, roots = lade_roots(args.split, min_pot=args.min_pot)
    if args.hand_ids:
        ids = [int(x) for x in args.hand_ids.split(",") if x.strip()]
        auswahl = [r for r in roots if r["hand_id"] in ids]
        assert len(auswahl) == len(ids), f"hand_ids nicht (alle) im Split >= min_pot: {ids}"
    else:
        auswahl = roots[:args.roots] if args.roots > 0 else roots
    orakel = None
    if args.arm_a == "oracle":
        from research.policy_oracle import PolicyOracle
        orakel = PolicyOracle(args.kanal, args.seeds, args.workers)
    konfig = {**vars(args), "iters_strategie": ITERS_STRATEGIE, "iters_q": ITERS_Q, "k2_bets": K2_BET_SIZES,
              "k2_raises": K2_RAISE_SIZES, "size_tol_chips": SIZE_TOL_CHIPS, "device": str(DEVICE),
              "provenienz_dateien": kopf["dateien"], "hero_k1": kopf.get("hero_k1"),
              "nenner_roots_min_pot": len(roots), "oracle_fingerprint": getattr(orakel, "fingerprint", None)}
    ergebnisse, abgebrochen = [], None
    t0 = time.perf_counter()
    try:
        for i, r in enumerate(auswahl, 1):
            if args.zeitbudget_s and time.perf_counter() - t0 > args.zeitbudget_s:
                abgebrochen = f"Zeitbudget {args.zeitbudget_s:.0f}s erschoepft vor Root {i}/{len(auswahl)}"
                print(f"[{i}/{len(auswahl)}] {abgebrochen}", flush=True)
                break
            print(f"[{i}/{len(auswahl)}] Root {r['hand_id']} pot {r['pot_river'] / BB:.1f}bb eff {r['eff'] / BB:.0f}bb "
                  f"{'OOP' if r['hero_oop'] else 'IP'} Hero-Range {len(r['ranges'].get('hero_k1') or r['ranges']['hero_tracker'])} "
                  f"Combos — Arm A = {args.arm_a} ...", flush=True)
            e = bewerte_root(r, orakel, args.arm_a, args.villain)
            ergebnisse.append(e)
            kurz = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in e.items()
                    if k in ("hand_id", "pot_river_bb", "hero_oop", "w_a_bb", "w_b_bb", "delta_e_h_bb",
                             "regret_a_bb", "regret_b_bb", "expl_b_pct_pot", "sekunden", "status", "grund")}
            print(f"[{i}/{len(auswahl)}] {json.dumps(kurz, ensure_ascii=False)}", flush=True)
    finally:
        if orakel is not None:
            orakel.schliessen()
    agg = aggregiere(ergebnisse, kopf["n_haende"], len(roots))          # Nenner = Roots >= --min-pot des Splits
    agg["sekunden_gesamt"] = round(time.perf_counter() - t0, 1)
    agg["abgebrochen"] = abgebrochen
    if orakel is not None:
        agg["oracle_statistik"] = orakel.statistik
    name = args.name or f"pruefstand_{args.split}_{args.arm_a}_{time.strftime('%Y%m%d_%H%M%S')}"
    pj, pm = schreibe_report(name, konfig, ergebnisse, agg)
    print(json.dumps({k: agg[k] for k in ("n_bewertet", "n_unsupported", "auswahlgewicht", "delta_e_h_bb",
                                          "delta_regret_bb", "sekunden_gesamt")}, indent=1))
    print(f"-> {pj}\n-> {pm}")


if __name__ == "__main__":
    main()
