# -*- coding: utf-8 -*-
"""G5-Divergenz-Auswertung: K2-Trace der nachgespielten Divergenz-Decks x Deck-Edges.

Liest den K2-Trace (research/g5_deck_replay.py --trace ...) und edges.json/config.json
des Spiegels, ordnet jede Trace-Zeile ueber hand_adresse = deck_seed*Stride + idx dem
globalen Deck zu und zaehlt je Deck die Plan-Entscheidungen des r10_stack nach Status
('keiner' = Plan gespielt; offtree / hand_not_in_range / deadline / fehler = Fallback
auf die NACKTE Basis ohne river_gpu_guard). Ausgewiesen: Edge-Summe der Decks MIT
Fallback vs OHNE vs ohne Plan-Pot (pot_river < 1500 -> Chirurgie-Luecke r8 vs r10).

  python -m research.g5_divergenz_auswertung data/runs/<ts>_pargate_r10_stack data/runs/v10/g5_divergenz_trace.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BB_CHIPS = 100
STRIDE = 1_000_000                   # duplicate.HAND_ID_STRIDE_JE_DECKSEED


def main() -> None:
    run_dir, trace = Path(sys.argv[1]), Path(sys.argv[2])
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    edges = json.loads((run_dir / "edges.json").read_text(encoding="utf-8"))
    chunk = max(1, cfg["decks"] // (cfg["workers"] * 4))
    replays = json.loads((run_dir / "g5_deck_replay.json").read_text(encoding="utf-8")) \
        if (run_dir / "g5_deck_replay.json").exists() else []
    gespielt = {r["deck_global"] for r in replays}
    # Log als Quelle fuer "welche Decks sind schon nachgespielt", falls der JSON noch fehlt
    log = run_dir.parent / "v10" / "g5_divergenz_replay.log"
    if log.exists():
        for zeile in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if zeile.startswith("Deck ") and "identisch=" in zeile:
                gespielt.add(int(zeile.split()[1]))
    status_je_deck: dict[int, Counter] = defaultdict(Counter)
    for zeile in trace.read_text(encoding="utf-8").splitlines():
        z = json.loads(zeile)
        adresse = int(z["hand_adresse"])
        deck_seed, idx = divmod(adresse, STRIDE)
        deck = (deck_seed - cfg["deck_seed0"]) * chunk + idx
        status_je_deck[deck][z.get("fallback_status") or "keiner"] += 1
    klassen = {"mit_fallback": [], "nur_plan": [], "kein_plan_pot": []}
    for d in sorted(gespielt):
        c = status_je_deck.get(d)
        if not c:
            klassen["kein_plan_pot"].append(d)
        elif any(k != "keiner" for k in c):
            klassen["mit_fallback"].append(d)
        else:
            klassen["nur_plan"].append(d)
    gesamt = Counter()
    for c in status_je_deck.values():
        gesamt.update(c)
    print(f"nachgespielte Divergenz-Decks: {len(gespielt)} von {sum(1 for e in edges if e)} | "
          f"K2-Statusverteilung (r10-Entscheidungen): {dict(gesamt)}")
    bericht = {"n_nachgespielt": len(gespielt), "status_gesamt": dict(gesamt), "klassen": {}}
    for name, decks in klassen.items():
        s = sum(edges[d] for d in decks)
        neg = [d for d in decks if edges[d] < 0]
        gross_neg = [d for d in decks if edges[d] <= -10000]
        print(f"  {name:<14} n={len(decks):3d}  Summe {s/BB_CHIPS:+7.0f} bb  negativ {len(neg):3d}  "
              f"<= -100bb: {len(gross_neg)} {[(d, edges[d]//100) for d in gross_neg]}")
        bericht["klassen"][name] = {"n": len(decks), "summe_bb": s / BB_CHIPS, "n_negativ": len(neg),
                                    "decks_unter_minus100bb": [(d, edges[d]) for d in gross_neg]}
    out = run_dir / "g5_divergenz_auswertung.json"
    out.write_text(json.dumps(bericht, indent=1), encoding="utf-8")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
