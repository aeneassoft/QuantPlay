"""Phase 1 WITH the OpenAI API (user instruction): consult gpt-5.1 as the engineer who makes the existing
parts MESH -- NOT add new ones. Carries the EXACT existing exploit channel + the 62 unified rules + the
user's 3 framing comments (esp. "make the engine actually run, don't complicate" + the self-play->floor
question). Output -> docs/phase1_openai.md for hand-synthesis + implementation. Vet for hallucination after.

Run:  python -m extraction.phase1_consult
"""
from __future__ import annotations

import json

from pokerbot import config

SYSTEM = (
    "You are a brutally honest senior ML/poker-AI ENGINEER. The user's framing: the bot is a conceptual "
    "brainstorm sketch of an engine -- the parts fit on paper but it does NOT run smoothly yet. Your job is "
    "to make the EXISTING parts mesh and run PERFECTLY, NOT to add complexity or ingest new data. Computation "
    "(neural net / solver) is allowed ONLY to FIT existing parts precisely (calibration/grounding), not for "
    "new features. Every recommendation MUST name how to VERIFY it (solver TV-gap, held-out metric, duplicate-"
    "poker A/B, LBR). No hype; prefer correctness. Be concrete enough to implement this week."
)


def brief() -> str:
    rules = json.loads((config.KNOWLEDGE_DIR / "exploit" / "unified.json").read_text(encoding="utf-8"))
    return f"""\
GOAL — Phase 1: connect our EXPLOIT layer with our GTO FLOOR so there is NO mismatch, by making the parts we
ALREADY have mesh cleanly. Do not propose new subsystems or new data ingestion. SIMPLIFY where possible.

============ THE EXISTING EXPLOIT CHANNEL (this is what you must integrate INTO, not replace) ============
- `directive_to_nudge(directive)` maps a bounded directive {{adjust:{{action, freq_delta}}, confidence}} to
  small signed nudges on exactly THREE channels: `bluff`, `value`, `foldcatch`. freq_delta clamped [-0.3,0.3],
  scaled by the directive's own confidence.
- action->channel map `_MAP`: bluff_more->(bluff,+), value_bet_thinner->(value,+), call_wider->(foldcatch,+),
  fold_more->(foldcatch,-), raise_more->(bluff,+).
- In `AdaptiveExploiter.decide`: a live LLM `live_directive` (if set) applies at full weight; else the static
  playbook (11,520 Haiku + 240 Opus directives) is a COLD-START prior via nearest-opponent-profile lookup on
  (vpip, fold_to_cbet, af), FADED by (1 - live_confidence) and only when board present & confidence < 0.6.
  The nudge is then CAPPED. This same path is the seam the future LLM strategist writes into.
- The LIVE opponent model currently MEASURES (with Bayesian shrinkage, pseudo-count k=6): vpip, pfr,
  fold_to_bet, aggression_freq, + a confidence(n). It does NOT yet track: call_down_freq, river_bet_freq,
  fold_to_cbet (split by street/size), fold_to_3bet, threebet_pct, wtsd, limp_freq.

============ THE NEW ASSET TO MESH IN: 62 deduped, stat-keyed exploit rules (knowledge_base/exploit/unified.json) ============
Each: {{stat, condition (e.g. ">0.6"), spot, adjustment, delta, magnitude (small/medium/large), confidence, merged}}.
`delta` vocabulary: more_value_bets, thinner_value, more_bluffs, fewer_bluffs, fold_more, call_wider,
raise_more, check_more, overbet, smaller_bet. NOTE the mismatch you must resolve: the channel carries only
FREQUENCY nudges on bluff/value/foldcatch, but several deltas (check_more, overbet, smaller_bet) are SIZING,
and several rule `stat`s are NOT measured live yet. The 62 rules (full):
{json.dumps(rules, ensure_ascii=False)}

============ MEASURED STATUS / HARD-WON LESSONS (do not contradict) ============
- We CRUSH the exploitable field (+300..700 bb/100); vs near-GTO Slumbot ~break-even (you cannot beat GTO,
  only minimize loss). The edge is exploitation; the floor is insurance.
- ONLY a grounded signal gates a change (solver TV-gap / held-out / duplicate-poker A/B / LBR). Small-sample
  bb/100 is noise; LLM suggestions are hypotheses until measured.
- The floor is NOT consistently wired: the live HU bot (bot.py) uses postflop.py (equity thresholds), the
  solver-calibrated texture c-bet lives in gto_baseline.py, the preflop GTO table is wired into 6-max but not
  HU, and the 62-rule exploit DB is not wired anywhere yet.

============ THE USER'S THREE FRAMING COMMENTS (answer these directly) ============
C1 (this consult): do Phase 1 together with you.
C2: "Exploitative play needs opponent history. If we build a loop where recursive exploitative play converges
    to GTO (self-play), couldn't that ALSO improve our pure GTO part -- the part that needs no history?"
C3: "The bot is a brainstorm DRAWING of an engine. The parts fit conceptually but it would not run smoothly
    in reality. The goal is NOT more complexity or more data -- it is to optimize everything so it runs
    PERFECTLY. But computations (net/CPU) DO make sense: they tell us how to make the parts fit exactly."

============ QUESTIONS — answer EACH concretely, each WITH a verification method ============
Q1. MESH THE 62 RULES INTO THE EXISTING CHANNEL: the cleanest design that SIMPLIFIES (does not add a parallel
    system). How to trigger a rule from the live opponent model (stat crosses condition), map `delta`->the
    bluff/value/foldcatch channels, and handle (a) the SIZING deltas the channel can't express and (b) rule
    stats not measured live. Should the 62 rules REPLACE the messy 11,520-directive playbook as the cold-start
    source? Give the exact data flow and the grounded gate that proves the wired exploiter is >= the current one.
Q2. MAKE THE ENGINE RUN (C3): list the bot's concrete INTEGRATION GAPS (parts that don't mesh / don't run
    smoothly), RANKED by EV, and for each the minimal fix to make it fit + the gate. No new features -- only
    fitting. Which single fix most makes the floor "run perfectly" with what we have?
Q3. SELF-PLAY -> FLOOR (C2): is the logic sound that a recursive exploit loop pointed at SELF (no opponent
    history) converges to GTO and thereby UPGRADES the history-free floor? Give the minimal correct algorithm
    (Deep-CFR / NFSP / fictitious play), how it FITS our floor (warm-start from solver caches; distill into the
    existing policy), what compute it needs (RunPod GPU, high-leverage only), and how to VERIFY convergence
    (LBR / exploitability on a small game like Leduc first).
Q4. For each of Q1-Q3, restate the single grounded gate that must pass before we keep the change.

Be specific and honest. If a part is low-value or should be DELETED to simplify, say so."""


def main() -> None:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        ids = {m.id for m in client.models.list().data}
    except Exception:  # noqa: BLE001
        ids = set()
    model = next((m for m in (([config.OPENAI_MODEL] if config.OPENAI_MODEL else []) +
                              config.OPENAI_MODEL_PREFERENCE) if m and (not ids or m in ids)), "gpt-4o")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": brief()}]
    print(f"=== querying OpenAI {model} (Phase 1 integration consult) ...", flush=True)
    try:
        r = client.chat.completions.create(model=model, messages=msgs, max_completion_tokens=9000)
    except Exception as e:  # noqa: BLE001
        print(f"(retry minimal: {type(e).__name__})", flush=True)
        r = client.chat.completions.create(model=model, messages=msgs)
    text = r.choices[0].message.content
    out = config.ROOT / "docs" / "phase1_openai.md"
    out.write_text(f"# Phase 1 integration consult — OpenAI {model}\n\n{text}\n", encoding="utf-8")
    print(f"saved {out} ({len(text)} chars, model={model})", flush=True)


if __name__ == "__main__":
    main()
