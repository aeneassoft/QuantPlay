"""The DATA REGISTRY — the single source of truth for "the gold".

Every training-data asset (DSL shards, the trained postflop advisors, the Qwen models, the big data/ training files, key
knowledge_base artifacts) gets a stable key, a ROLE, an honest one-line description, its schema, provenance, and a
`current` flag.

WHY: the data was opaque — ambiguous shard names (`solver_mass` vs `c_decide`), undocumented `.pt` nets, hardcoded shard
lists scattered in the training pipeline — so you had to open files or grep code to know what anything was. Now the
training pipeline asks THIS registry for data by ROLE (e.g. `sft_gold()`), not by hardcoded path → the data is
structured for the AI's training logic, and `dataset/build_manifest.py` renders a never-stale CATALOG.md from it.

$0, no torch/trl: pure path + jsonl-stat, safe to import anywhere (the training pipeline imports `sft_gold`).
HARD RULE (CLAUDE.md): the `.pt` advisors + knowledge_base paths are hard-referenced by config.py + strategy/* — this
registry DESCRIBES them; it never physically renames/moves them.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pokerbot import config

ROLES = ("sft_gold", "raw_shard", "kb_advisor", "kb_playbook", "kb_ranges",
         "kb_math", "model", "train_data", "eval")

_ROWCOUNT_MAX_BYTES = 64 * 1024 * 1024   # above this, stats() reports bytes only (don't iterate ~845MB defense_data)


@dataclass(frozen=True)
class Asset:
    """One data asset. `role` is HOW the training logic consumes it (the pipeline queries by role, not by path).
    `current=False` = superseded / empty / deprecated: still shown in the manifest (with `note`) but excluded from the
    active-role queries like `sft_gold()`."""
    key: str                       # stable id, e.g. "shard.a_contract"
    path: Path
    role: str                      # one of ROLES
    desc: str                      # one honest line: what it IS
    schema: str = ""               # record/format, e.g. "DSL decision (spot->program)"
    provenance: str = ""           # how it was made, e.g. "from_selfplay (advisor-wired)"
    stage: str = ""                # SFT/curriculum stage or street, e.g. "a_contract" / "turn"
    current: bool = True
    note: str = ""


_S, _M, _K, _P = config.SHARDS_DIR, config.MODELS_DIR, config.KNOWLEDGE_DIR, config.POSTFLOP_DIR

ASSETS: list[Asset] = [
    # --- SFT GOLD: the frac_bad-fixed reasoning-loop + solver DSL shards the pod SFT trains on -------------------
    Asset("shard.a_contract", _S / "a_contract.jsonl", "sft_gold",
          "highest-clarity reasoning-loop decisions; ~57% drive the trained advisor (api.solver_freq)",
          "DSL decision (spot->program)", "dataset.build.from_selfplay (advisor-wired)", "a_contract"),
    Asset("shard.c_decide", _S / "c_decide.jsonl", "sft_gold",
          "reasoning-loop decisions + opponent-read conditioning",
          "DSL decision (spot->program)", "from_pokerbench + from_selfplay", "c_decide"),
    Asset("shard.solver", _S / "solver.jsonl", "sft_gold",
          "TexasSolver GTO mixed-frequency decisions (curated board set)",
          "DSL decision (decide_mix)", "dataset.build.from_solver", "solver"),
    Asset("shard.solver_mass", _S / "solver_mass.jsonl", "sft_gold",
          "TexasSolver mass-solve GTO mixes (the local CPU mass_solve gold)",
          "DSL decision (decide_mix)", "dataset.build.from_solver --mass", "solver", current=False,
          note="EXCLUDED from sft_gold 2026-06-20 (plan #3): 25.6k non-line-aware SRP-flop solves (~-47 quality) DROWN "
               "the 2.2k Claude-teacher postflop gold 13:1 in the re-SFT -> Claude can't lead the postflop policy. "
               "Re-enable (current=True) for a 6-max / broad-coverage run."),
    Asset("shard.hu_blueprint", _S / "hu_blueprint.jsonl", "sft_gold",
          "HU 200bb near-Nash BLUEPRINT preflop (api.preflop_solve, decide_mix literals) + HU postflop — the flywheel "
          "fix for the GTOW HU preflop over-fold leak (the −43.30→? lever)",
          "DSL decision (decide_mix)", "dataset.build.from_hu", "hu_blueprint"),
    Asset("shard.teacher", _S / "teacher.jsonl", "sft_gold",
          "distilled frontier-teacher DSL (gated; present only AFTER a teacher run)",
          "DSL decision", "pipeline.distill_teacher", "teacher"),
    Asset("shard.claude_study", _S / "claude_study.jsonl", "sft_gold",
          "EV-gated GOOD decisions distilled from the Claude-Code-vs-GTOW thought_log study (the closed learning loop)",
          "DSL decision (# reasoning + decide)", "research.study_distill (EVFilter-gated)", "claude_study",
          note="warm-start shard (~hundreds of rows): MY own GTO-matching HU play, reconstructed spots + reasoning, "
               "EVFilter G1-G6 passed, built INCLUDE_MADE_HAND ON (train==serve). Honest cap: NOT a lift above my play. "
               "Decisions whose reasoning cited the inflated decision-time required_equity are excluded (math_ok gate)."),

    # --- other shards (NOT in the active SFT gold) -------------------------------------------------------------
    Asset("shard.decisions", _S / "decisions.jsonl", "raw_shard",
          "from_selfplay default sample output (a_contract/c_decide are the staged gold)",
          "DSL decision", "from_selfplay main()"),
    Asset("shard.local_kb", _S / "local_kb.jsonl", "raw_shard",
          "OLD blended KB shard (math+exploit+concepts) — the original frac_bad=0.97 cause; NOT the gold",
          "mixed comment/decision", "dataset.build.run", current=False,
          note="superseded for SFT by the reasoning-loop shards; kept for reference"),
    Asset("shard.sample", _S / "sample.jsonl", "raw_shard", "253-row verification downsample of local_kb",
          "mixed", "manual", current=False),
    Asset("shard.b_ground", _S / "b_ground.jsonl", "raw_shard", "EMPTY placeholder (curriculum stage b)",
          "", "curriculum.py", "b_ground", current=False, note="0 rows — from_calc/from_math not wired into the stage"),
    Asset("shard.d_exploit", _S / "d_exploit.jsonl", "raw_shard", "EMPTY placeholder (curriculum stage d)",
          "", "curriculum.py", "d_exploit", current=False, note="0 rows"),

    # --- the trained POSTFLOP ADVISORS (the underused gold; api.solver_freq drives these) ----------------------
    # HARD-REFERENCED by config.py + strategy/advisor.py -> DESCRIBE only; never physically rename/move (CLAUDE.md).
    Asset("advisor.flop", _P / "advisor.pt", "kb_advisor", "trained flop GTO bet-frequency MLP (+63% vs strength-only)",
          "torch MLP", "solver-imitation (strategy/advisor.py)", "flop"),
    Asset("advisor.turn", _P / "turn_advisor.pt", "kb_advisor", "trained turn GTO bet-frequency MLP (+46%)",
          "torch MLP", "solver-imitation", "turn"),
    Asset("advisor.river", _P / "river_advisor.pt", "kb_advisor", "trained river GTO bet-frequency MLP (+18%)",
          "torch MLP", "solver-imitation", "river"),
    Asset("advisor.defense", _P / "defense_advisor.pt", "kb_advisor", "trained defense-frequency net (facing aggression)",
          "torch MLP", "research/build_defense_data.py", "defense", note="verify live wiring"),
    Asset("net.deepcfr_hunl", _P / "deepcfr_hunl.pt", "model", "Deep-CFR HUNL value net (SHELVED — the -212 fcpa era)",
          "torch net", "research/train_cfv_net.py", current=False, note="superseded per CLAUDE.md history"),

    # --- key KNOWLEDGE_BASE artifacts (training-relevant; curated) ---------------------------------------------
    Asset("kb.playbook", _K / "exploit" / "playbook.jsonl", "kb_playbook",
          "the exploit playbook — opponent-leak directives (large)", "jsonl directives", "research/exploit_playbook.py"),
    Asset("kb.postflop_playbook", _P / "openai_strategy.json", "kb_playbook",
          "the 62-rule postflop strategy playbook", "json rules", "OpenAI distill (gated)"),
    Asset("kb.preflop_blueprint", _K / "ranges" / "preflop_blueprint.json", "kb_ranges",
          "near-Nash 6-max preflop blueprint (RFI / vs-raise)", "json ranges", "research/preflop_*"),
    Asset("kb.pushfold", _K / "cfr" / "preflop_pushfold.json", "kb_ranges",
          "Nash push-fold blueprint (HU endgame)", "json ranges", "cfr solve"),
    Asset("kb.formulas", _K / "math" / "formulas.py", "kb_math",
          "engine-verified poker formulas = the DSL math primitives (pot-odds, MDF, SPR, outs)", "python", "verified"),
    Asset("kb.scorecard", _K / "scorecard.json", "eval",
          "latest grounded scorecard (gto_gap / exploit_edge bb/100)", "json metrics", "research/bot_audit.py"),

    # --- the big data/ TRAINING FILES (feed the advisor nets; gitignored) --------------------------------------
    Asset("data.defense", config.DATA_DIR / "defense_data.jsonl", "train_data",
          "defense-strategy training sequences (feeds advisor.defense)", "jsonl sequences",
          "research/build_defense_data.py", note="~845MB, gitignored"),
    Asset("data.advisor", config.DATA_DIR / "advisor_data.jsonl", "train_data",
          "turn/river advisor training sequences", "jsonl sequences", "research/build_advisor_data.py", note="gitignored"),
    Asset("data.river", config.DATA_DIR / "river_data.jsonl", "train_data",
          "river advisor training sequences", "jsonl sequences", "research/build_river_data.py", note="gitignored"),
    Asset("data.sd_advisor", config.DATA_DIR / "sd_advisor_data.jsonl", "train_data",
          "short-deck advisor training sequences", "jsonl sequences", "research/build_sd_advisor_data.py", note="gitignored"),

    # --- the Qwen MODELS (the brain) --------------------------------------------------------------------------
    Asset("model.local_sft", _M / "qwen_local_sft", "model", "Qwen3-1.7B SFT adapter (the local frac_bad-fix proof)",
          "LoRA adapter", "training.qwen_sft", note="6 checkpoints"),
    Asset("model.local_grpo", _M / "qwen_local_grpo", "model", "Qwen3-1.7B GRPO adapter (local RL proof)",
          "LoRA adapter", "training.qwen_grpo"),
    Asset("model.poker_ckpt500", _M / "qwen_poker_ckpt500", "model", "early 8B LoRA checkpoint (historical)",
          "LoRA adapter", "training.qwen_sft", current=False),
    Asset("model.smoke", _M / "qwen_smoke", "model", "smoke-test adapter", "LoRA adapter", "smoke", current=False),
    Asset("model.combined_sft", _M / "qwen_combined_sft", "model", "EMPTY placeholder dir", "", "",
          current=False, note="empty"),
    Asset("model.sft_aligned", _M / "qwen_local_sft_aligned", "model",
          "EMPTY (aligned re-SFT was killed; the pod run superseded it)", "", "training.qwen_sft",
          current=False, note="empty"),
]

_BY_KEY: dict[str, Asset] = {a.key: a for a in ASSETS}


# --- queries the TRAINING PIPELINE calls (data discovered by ROLE, not path) ----------------------------------
def get(key: str) -> Asset:
    return _BY_KEY[key]


def by_role(role: str, current_only: bool = True) -> list[Asset]:
    return [a for a in ASSETS if a.role == role and (a.current or not current_only)]


def sft_gold() -> list[Path]:
    """The SFT gold shards to train on — the ONE source of this list (replaces the hardcoded `_candidates` in
    runpod_rl_campaign + any duplicated list). Only `current` shards that exist on disk."""
    return [a.path for a in by_role("sft_gold") if a.path.exists()]


def advisor(street: str) -> Path | None:
    """The trained street bet-frequency advisor `.pt` for 'flop'/'turn'/'river'/'defense' — api.solver_freq's gold."""
    for a in by_role("kb_advisor"):
        if a.stage == street:
            return a.path
    return None


def model(name: str) -> Asset:
    """A Qwen model asset by short name, e.g. model('local_sft')."""
    return _BY_KEY[f"model.{name}"]


# --- stats + content-search (navigation; $0, no torch) --------------------------------------------------------
def _iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def stats(asset: Asset) -> dict:
    """Cheap on-disk facts: existence, bytes, and for jsonl decision shards the row-count + action-mix (the
    pipeline/inspect_teacher pattern). No torch — safe for the manifest."""
    p = asset.path
    if not p.exists():
        return {"exists": False}
    if p.is_dir():
        files = [f for f in p.rglob("*") if f.is_file()]
        return {"exists": True, "is_dir": True, "n_files": len(files),
                "bytes": sum(f.stat().st_size for f in files)}
    out: dict = {"exists": True, "bytes": p.stat().st_size}
    if p.suffix == ".jsonl" and out["bytes"] <= _ROWCOUNT_MAX_BYTES:
        rows, acts = 0, Counter()
        for row in _iter_jsonl(p):
            rows += 1
            act = row.get("action")
            if isinstance(act, dict) and act.get("action"):
                acts[act["action"]] += 1
        out["rows"] = rows
        if acts:
            out["action_mix"] = dict(acts)
    elif p.suffix == ".jsonl":
        out["rows_uncounted"] = True   # too large to row-count cheaply (e.g. the ~845MB defense_data.jsonl)
    return out


def grep(term: str, roles: tuple = ("sft_gold", "raw_shard", "kb_playbook"), limit: int = 20) -> list[dict]:
    """Content-search ('find the data about X'): records whose spot/completion contains `term`, ACROSS all cataloged
    jsonl assets in `roles`. Returns [{key, line, snippet}]."""
    needle = term.lower()
    hits: list[dict] = []
    for a in ASSETS:
        if a.role not in roles or a.path.suffix != ".jsonl" or not a.path.exists():
            continue
        for i, row in enumerate(_iter_jsonl(a.path)):
            blob = (str(row.get("spot", "")) + " " + str(row.get("completion", ""))).lower()
            if needle in blob:
                hits.append({"key": a.key, "line": i, "snippet": str(row.get("spot", ""))[:120]})
                if len(hits) >= limit:
                    return hits
    return hits


if __name__ == "__main__":  # quick sanity: print the active SFT gold + role counts
    from collections import Counter as _C
    print("SFT gold:", [p.name for p in sft_gold()])
    print("roles:", dict(_C(a.role for a in ASSETS if a.current)))
    print("advisors:", {s: (advisor(s).name if advisor(s) else None) for s in ("flop", "turn", "river", "defense")})
