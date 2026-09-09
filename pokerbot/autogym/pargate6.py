"""pargate6 — das gepaarte 6-max-Gate (Duplicate-Prinzip ueber ALLE Sitze).

Ein Deck = 6 Hole-Paare + Board aus EINEM Deck-Seed. Jedes Deck wird 6x gespielt, der Held rotiert ueber alle
Sitze (Button fest auf Sitz 0 -> der Held sieht jede Position genau einmal), die 5 Villains der festen Liga
fuellen die uebrigen Sitze zyklisch: Sitz s traegt in Rotation r das Profil LIGA[(s - r - 1) % 6] -> jedes
Hole-Paar wird einmal vom Helden und einmal von jedem Profil gespielt. Villain-RNGs sind je (Deck, Rotation,
Sitz) geseedet; ihre OppModels leben ueber den Job-Block (Reads brauchen Beobachtungen — gleiche --workers =
gleiche Lern-Fenster). Kandidat und Incumbent spielen IDENTISCHE Decks in getrennten frischen Prozessen (Env je
Arm, Import-Zeit-Flags) -> per-Deck-Differenz der Helden-Chips ueber die 6 Rotationen; A/A muss EXAKT 0 sein.

  python -m pokerbot.autogym.pargate6 --kandidat hybrid_r8 --incumbent tag --decks 3000 --workers 8

Die Arena ist ueber n_seats generisch (n=2 = HU mit Button-Tausch); pokerbot/autogym/exploit_gate.py nutzt sie
mit eigenen Helden-Fabriken (fabrik_spec 'modul:funktion').
"""
from __future__ import annotations

import argparse
import importlib
import multiprocessing as mp
import random
import sys
import time

from pokerbot.benchmark.duplicate import HAND_ID_STRIDE_JE_DECKSEED

N_SEATS = 6
LIGA = ("tag", "lag", "nit", "station", "maniac")   # der Liga-Kern (sixmax_export --villains Default)
START_STACK, SB, BB = 10000, 50, 100                # 100bb Cash, jede Hand zurueckgesetzt (Export-Geometrie)
MAX_AKTIONEN_JE_HAND = 400                          # Schleifen-Wache wie sixmax_export.play_hand
ROTATIONS_STRIDE = 8                                # Seed-Adressraum: deck_id*64 + rot*8 + seat (n_seats <= 8)
SEED_OFFSET = 10 ** 12                              # --seed verschiebt den RNG-Adressraum (Replikationslauf)
KANDIDATEN = ("tag", "tag_reads", "tag_flatfix", "hybrid", "hybrid_r8", "hybrid_r10")
JOBS_JE_WORKER = 2                                  # feinere Bloecke = laufender Fortschritt + ETA
# Env je Arm (VOR den Imports im frischen Prozess): die AUSLESE-Kette braucht ihre Import-Zeit-Flags
# (resolver-OFF-Variante inkl. RAISE_NARROW, wie das HU-Gate); der nackte Prince nur das PRINCE-Profil.
_PRINCE_ENV = {"POKERB_PRINCE": "1"}


def arm_env(name: str) -> dict:
    from pokerbot.strategy.auslese import AUSLESE_ENV_RESOLVER_OFF
    if name in ("hybrid_r8", "hybrid_r10"):
        return {**_PRINCE_ENV, **AUSLESE_ENV_RESOLVER_OFF}
    if name == "hybrid":
        return dict(_PRINCE_ENV)
    return {}


# ------------------------------------------------------------------ Decks
def gen_decks6(n: int, seed: int, n_seats: int = N_SEATS) -> list:
    """n feste Deals: (holes[n_seats], board[5]) ohne Zuruecklegen aus je einer frischen Mischung."""
    from pokerbot.engine.cards import make_deck
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        d = make_deck()
        rng.shuffle(d)
        holes = [d[2 * i:2 * i + 2] for i in range(n_seats)]
        out.append((holes, d[2 * n_seats:2 * n_seats + 5]))
    return out


def _setze_deck(table, holes, board) -> None:
    """Feste Karten in einen frischen Tisch: Button auf Sitz 0 (start_hand rueckt um eins vor), Stacks
    auf 100bb, Hole-Paare nach SITZ, das Board als Rest-Deck (deal() poppt vom Ende)."""
    table.button = table.n - 1
    for s in table.seats:
        s.stack = START_STACK
    table.start_hand()
    for i, h in enumerate(holes):
        table.seats[i].hole = list(h)
    table.deck.cards = list(reversed(board))


def _seed(deck_id: int, rot: int, seat: int, seed: int = 0) -> int:
    return seed * SEED_OFFSET + deck_id * (ROTATIONS_STRIDE * ROTATIONS_STRIDE) + rot * ROTATIONS_STRIDE + seat


# ------------------------------------------------------------------ Helden
def held_fabrik(name: str):
    """Standard-Helden: SixMaxBot-Kern (Reads AUS = GTO-Modus-Paritaet / AN) oder der Hybrid-Verbund."""
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot
    if name in ("tag", "tag_reads", "tag_flatfix"):
        bot = SixMaxBot(0, PROFILES["tag_flatfix" if name == "tag_flatfix" else "tag"])
        if name != "tag_reads":
            bot._read = lambda obs: {}
        return bot
    from pokerbot.arena.hybrid import HybridHero
    from pokerbot.strategy.auslese import FINAL_STACK, RC_STACK
    stack = {"hybrid": None, "hybrid_r8": FINAL_STACK, "hybrid_r10": RC_STACK}[name]
    return HybridHero(0, stack=stack, kanal="gym")


def _setze_sitz(held, seat: int) -> None:
    if hasattr(held, "setze_sitz"):
        held.setze_sitz(seat)
    else:
        held.seat = seat


def _kern_rng(held):
    """Die RNG des Multiway-Kerns (SixMaxBot direkt oder HybridHero.bot) — je (Deck, Sitz) neu geseedet."""
    return getattr(held, "bot", held)


def _spiele_hand(table, bots: dict, held_seat: int, held, hand_id: str) -> tuple[int, int]:
    """Eine Hand am gesetzten Tisch; Rueckgabe (Helden-Netto-Chips, illegale Fallbacks)."""
    n = table.n
    for b in bots.values():
        b.new_hand(list(range(n)))
    if hasattr(held, "bind_table"):
        held.bind_table(table)
        held.hand_id = hand_id
    fallbacks = 0
    for _ in range(MAX_AKTIONEN_JE_HAND):
        if table.hand_over or table.to_act is None:
            break
        i = table.to_act
        obs = table.obs_for(i)
        dec = bots[i].decide(obs)
        action, amount = dec["action"], dec.get("amount")
        try:
            table.act(action, amount)
        except Exception:  # noqa: BLE001 — illegal -> sicherer Zug (die Engine ist die Wahrheit)
            fallbacks += 1
            la = table.legal_actions()
            table.act("check" if la.get("can_check") else ("call" if la.get("can_call") else "fold"))
        act_name = "raise" if action == "allin" else action
        for b in bots.values():
            b.observe(i, obs["street"], act_name, obs["to_call"], obs["preflop_raises"])
    return table.seats[held_seat].stack - START_STACK, fallbacks


def spiele_block(held, decks: list, deck_id0: int, n_seats: int = N_SEATS, liga: tuple = LIGA,
                 seed: int = 0) -> dict:
    """Ein Held spielt jedes Deck n_seats-mal (Rotation ueber alle Sitze). Rueckgabe: chips je Deck (Summe
    ueber die Rotationen), Prince-Zaehler, Fallbacks. Villains je Rotations-Slot persistent (OppModels)."""
    from pokerbot.arena.sixmax import PROFILES, SixMaxBot, seed_modul_rng
    from pokerbot.engine.table import Table
    villains = {rot: {s: SixMaxBot(s, PROFILES[liga[(s - rot - 1) % n_seats]])
                      for s in range(n_seats) if s != rot} for rot in range(n_seats)}
    names = [f"S{i}" for i in range(n_seats)]
    chips, fallbacks = [], 0
    for idx, (holes, board) in enumerate(decks):
        deck_id = deck_id0 + idx
        summe = 0
        for rot in range(n_seats):
            seed_modul_rng(_seed(deck_id, rot, n_seats, seed))   # zustandslose Pfade ebenfalls reproduzierbar
            table = Table(names, starting_stack=START_STACK, sb=SB, bb=BB, seed=deck_id, human_seat=-1)
            _setze_deck(table, holes, board)
            _setze_sitz(held, rot)
            _kern_rng(held).rng = random.Random(_seed(deck_id, rot, rot, seed))
            bots = dict(villains[rot])
            for s, b in bots.items():
                b.rng = random.Random(_seed(deck_id, rot, s, seed))
            bots[rot] = held
            netto, fb = _spiele_hand(table, bots, rot, held, f"pg6-{deck_id}-{rot}")
            summe += netto
            fallbacks += fb
        chips.append(summe)
    return {"chips": chips, "prince_decisions": getattr(held, "prince_decisions", 0),
            "kern_fallbacks": getattr(held, "kern_fallbacks", 0), "illegal_fallbacks": fallbacks,
            "fingerprint": getattr(held, "fingerprint", None)}   # K4-Nachweis der Arm-Konfig (exploit_gate)


# ------------------------------------------------------------------ Worker
def _env_hygiene(env: dict) -> None:
    """Frischer Prozess: BLAS/Torch auf 1 Thread, alle geerbten POKERB_* weg, dann NUR die Arm-Flags."""
    import os
    for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[v] = "1"
    for k in [k for k in os.environ if k.startswith("POKERB_")]:
        os.environ.pop(k, None)
    os.environ.update(env)
    try:
        import torch
        torch.set_num_threads(1)
    except Exception:  # noqa: BLE001
        pass


def _fabrik_aus_spec(spec: str):
    modul, funk = spec.split(":")
    return getattr(importlib.import_module(modul), funk)


def _worker(args: tuple) -> tuple:
    job_idx, arm, spec, env, deck_seed, n_decks, n_seats, liga, seed = args
    _env_hygiene(env)
    decks = gen_decks6(n_decks, seed=deck_seed, n_seats=n_seats)
    held = _fabrik_aus_spec(spec)(arm)
    res = spiele_block(held, decks, deck_seed * HAND_ID_STRIDE_JE_DECKSEED, n_seats, tuple(liga), seed)
    return job_idx, arm, res


# ------------------------------------------------------------------ Gate
def par_gate6(kandidat: str, incumbent: str, n_decks: int, workers: int, seed: int = 1,
              deck_seed0: int = 5000, n_seats: int = N_SEATS, liga: tuple = LIGA,
              fabrik_spec: str = "pokerbot.autogym.pargate6:held_fabrik",
              env_fn=arm_env) -> dict:
    """Gepaartes Gate: beide Arme auf identischen Deck-Bloecken, je Job ein FRISCHER Prozess
    (maxtasksperchild=1 — Import-Zeit-Flags je Arm koennen sich nie ueber einen Pool-Prozess vermischen)."""
    n_jobs = max(1, workers * JOBS_JE_WORKER)
    chunk = max(1, n_decks // n_jobs)
    jobs = [(i, arm, fabrik_spec, env_fn(arm), deck_seed0 + i, chunk, n_seats, list(liga), seed)
            for i in range(n_jobs) for arm in (kandidat, incumbent)]
    t0 = time.time()
    ergebnis: dict[tuple, dict] = {}
    with mp.Pool(workers, maxtasksperchild=1) as pool:
        for k, (idx, arm, res) in enumerate(pool.imap_unordered(_worker, jobs), 1):
            ergebnis[(idx, arm)] = res
            el = time.time() - t0
            print(f"  [{k}/{len(jobs)}] Block {idx} {arm}: {len(res['chips'])} Decks | {el/60:.1f} min | "
                  f"ETA {el/k*(len(jobs)-k)/60:.1f} min", flush=True)
    kand = [c for i in range(n_jobs) for c in ergebnis[(i, kandidat)]["chips"]]
    inc = [c for i in range(n_jobs) for c in ergebnis[(i, incumbent)]["chips"]]
    edges = [a - b for a, b in zip(kand, inc)]
    from pokerbot.autogym.stats import bootstrap_ci, robust_stats, verdikt
    rs = robust_stats(edges, bb=BB, haende_je_deck=n_seats)
    rs.update(bootstrap_ci(edges, bb=BB, haende_je_deck=n_seats))
    skala = 1.0 / n_seats / BB * 100.0
    zaehler = {arm: {k: sum(ergebnis[(i, arm)][k] for i in range(n_jobs))
                     for k in ("prince_decisions", "kern_fallbacks", "illegal_fallbacks")}
               for arm in {kandidat, incumbent}}
    fingerprints = {arm: ergebnis[(0, arm)]["fingerprint"] for arm in {kandidat, incumbent}}
    return {"kandidat": kandidat, "incumbent": incumbent, "kanal": "pargate6", "n_seats": n_seats,
            "liga": list(liga), **rs,
            "bb100_kandidat": round(sum(kand) / max(1, len(kand)) * skala, 2),
            "bb100_incumbent": round(sum(inc) / max(1, len(inc)) * skala, 2),
            "aa_exakt_null": kandidat == incumbent and all(e == 0 for e in edges),
            "zaehler": zaehler, "fingerprints": fingerprints, "workers": workers, "sekunden": round(time.time() - t0, 1),
            "verdict": verdikt(rs), "edges": edges}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kandidat", choices=KANDIDATEN, default="hybrid_r8")
    ap.add_argument("--incumbent", choices=KANDIDATEN, default="tag")
    ap.add_argument("--decks", type=int, default=600)
    ap.add_argument("--workers", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--deck-seed0", type=int, default=5000)
    args = ap.parse_args()
    from pokerbot.autogym import runs
    d = runs.neuer_run(f"pargate6_{args.kandidat}", vars(args))
    res = par_gate6(args.kandidat, args.incumbent, args.decks, args.workers, args.seed, args.deck_seed0)
    edges = res.pop("edges")
    import json
    (d / "edges.json").write_text(json.dumps(edges), encoding="utf-8")
    runs.schliesse_run(d, res)
    print(res)
    print(f"Run-Ablage: {d}")


if __name__ == "__main__":
    main()
