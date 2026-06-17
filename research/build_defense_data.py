"""MVP B2 (+ pull-forward): build the FACING-BET DEFENSE advisor's training data from the EXISTING caches (no
new solving). The floor's #1 leak (Opus 4.6) is facing-bet defense — today a pure heuristic (`call_thresh =
req + MDF`); the advisors only model P(bet). The solved trees ALREADY contain the facing-bet nodes one ply deeper:
  - OOP defends vs IP bet:  root -> CHECK (IP node) -> BET s  (OOP chooses FOLD/CALL/RAISE per combo)
  - IP  defends vs OOP donk: root -> BET s             (IP  chooses FOLD/CALL/RAISE per combo)
Extracted from BOTH the flop cache (3-card boards, SPR~5) AND the river-subgame cache (5-card boards) — so the
defense advisor covers the TWO biggest defense streets (Opus ranks river #1), $0, no pod. (Turn + more sizes/SPRs
still need the scaled solve.) Per (street, board, defender, size-faced, combo): X = features + strength + texture +
size_faced + street; y = (P_fold, P_call, P_raise). -> data/defense_data.jsonl for B3 (train).
Run: python -m extraction.build_defense_data
"""
from __future__ import annotations

import json
import statistics

from pokerbot import config
from pokerbot.benchmark.gto_benchmark import _CACHE, texture
from pokerbot.engine.evaluator import evaluate
from pokerbot.strategy.features import hand_features

FEAT = ["tier", "flush_draw", "backdoor_flush", "nut_flush_blocker", "made_straight",
        "oesd", "gutshot", "overcards", "has_draw"]
START_POT = 20.0   # both caches solve at pot=20 -> size_faced = bet_chips / 20
RIVER_CACHE = config.DATA_DIR / "_gto_river_cache"
TURN_CACHE = config.DATA_DIR / "_gto_turn_cache"   # 4-card boards (mass_solve STREET=4) — the keystone street


def _defense_rows(defender, node, board, tex, st, street, size_faced):
    """Per-combo (fold/call/raise) distribution at a facing-bet node -> rows."""
    s = node.get("strategy") or {}
    actions, strat = s.get("actions", []), s.get("strategy") or {}
    if not actions or not strat:
        return []
    fold_i = [i for i, a in enumerate(actions) if a.split()[0] == "FOLD"]
    call_i = [i for i, a in enumerate(actions) if a.split()[0] == "CALL"]
    raise_i = [i for i, a in enumerate(actions) if a.split()[0] in ("RAISE", "ALLIN", "BET")]
    if not (fold_i or call_i or raise_i):
        return []
    rows = []
    for combo, probs in strat.items():
        hole = [combo[:2], combo[2:4]]
        f = hand_features(hole, board)
        row = {"board": st, "role": defender, "street": street, "tex": tex,
               "size_faced": round(size_faced, 3),
               "y_fold": round(sum(probs[i] for i in fold_i), 4),
               "y_call": round(sum(probs[i] for i in call_i), 4),
               "y_raise": round(sum(probs[i] for i in raise_i), 4),
               "strength": round(1.0 - evaluate(board, hole) / 7462.0, 4)}
        for k in FEAT:
            row[k] = f[k]
        rows.append(row)
    return rows


def _bet_children(node):
    out = []
    for lbl, ch in (node.get("childrens") or {}).items():
        head = lbl.split()
        if head and head[0] in ("BET", "ALLIN") and ch is not None:
            chips = float(head[1]) if len(head) > 1 else START_POT
            out.append((ch, chips))
    return out


def _process_cache(cache_dir, street, nboard, cap=None):
    """Walk a cache dir; extract OOP-defends-vs-bet + IP-defends-vs-donk rows. Root = OOP first-to-act node."""
    rows, used = [], 0
    if not cache_dir.exists():
        return rows, 0
    files = sorted(cache_dir.glob("*.json"))
    if cap:
        files = files[:cap]                # balance the dataset (we over-generated turn boards)
    for cf in files:
        try:
            node = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        bs = cf.stem.split("_")[0]
        if len(bs) < nboard * 2:
            continue
        board = [bs[i:i + 2] for i in range(0, nboard * 2, 2)]
        tex = texture(board[:3])               # texture keyed on the flop (advisor._texture matches this)
        got = False
        for ch, chips in _bet_children(node):                       # IP defends vs OOP donk
            r = _defense_rows("IP", ch, board, tex, cf.stem, street, chips / START_POT)
            rows.extend(r); got = got or bool(r)
        ip = next((v for k, v in (node.get("childrens") or {}).items() if k.split()[0] == "CHECK"), None)
        if ip is not None:
            for ch, chips in _bet_children(ip):                      # OOP defends vs IP bet
                r = _defense_rows("OOP", ch, board, tex, cf.stem, street, chips / START_POT)
                rows.extend(r); got = got or bool(r)
        used += int(got)
    return rows, used


def main() -> None:
    rows = []
    for cache_dir, street, nboard, cap in ((_CACHE, "flop", 3, None), (TURN_CACHE, "turn", 4, 2500),
                                           (RIVER_CACHE, "river", 5, None)):
        r, used = _process_cache(cache_dir, street, nboard, cap)
        rows.extend(r)
        print(f"{street}: {len(r)} rows from {used} boards ({cache_dir.name})")
    out = config.DATA_DIR / "defense_data.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    print(f"TOTAL {len(rows)} defense rows -> {out}")
    for street in ("flop", "turn", "river"):
        sr = [r for r in rows if r["street"] == street]
        if not sr:
            continue
        print(f"  [{street}] fold {statistics.mean(r['y_fold'] for r in sr):.2f} | "
              f"call {statistics.mean(r['y_call'] for r in sr):.2f} | "
              f"raise {statistics.mean(r['y_raise'] for r in sr):.2f}  (n={len(sr)})")
        for sz in sorted({r["size_faced"] for r in sr}):
            ss = [r for r in sr if r["size_faced"] == sz]
            if len(ss) >= 200:
                print(f"      size {sz:.2f}-pot (n={len(ss)}): mean fold {statistics.mean(r['y_fold'] for r in ss):.2f}")


if __name__ == "__main__":
    main()
