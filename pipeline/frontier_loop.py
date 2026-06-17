"""The gated active-distillation loop — the PC-hub's self-growing engine (Phase 3).

It targets Qwen's WEAK CLUSTERS (from pipeline/monitor.py), asks the FRONTIER (Claude/OpenAI via research/llm.py) for
a GTO-anchored decision + reasoning on each weak spot, then forces EVERY proposal through the deterministic EV-TRUTH
filter (pipeline/filter.py) before it can enter the dataset. Frontier = a PRIOR; the ENGINE = TRUTH — this is what
keeps distillation from re-importing the −10/−30 imitation/hallucination ceiling.

HARD RULE (CLAUDE.md): frontier APIs feed ONLY this PC hub — NEVER the RunPod trainer. The proposer is injectable so
the loop+gate plumbing is testable offline (no API spend).
"""
from __future__ import annotations

import json

from dataset.schema import make_example
from pokerbot.brain.format_spot import format_spot
from pipeline.filter import EVFilter
from research.llm import claude_json, openai_json

SYS = (
    "You are a GTO specialist for 6-max No-Limit Hold'em. Given a decision spot, output the GTO-optimal action with a "
    "brief, math-grounded reason (pot-odds / equity / MDF / SPR / board texture). ANCHOR on GTO; deviate ONLY for a "
    "bounded, EV-justified read. Bet/raise size_bb = the TOTAL bet in BIG BLINDS (null for fold/check/call). "
    "Be exact and concise — the engine will fact-check your math, so do not bluff numbers."
)

DISTILL_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["fold", "check", "call", "bet", "raise", "all-in"]},
        "size_bb": {"type": ["number", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["action", "size_bb", "reasoning"],
    "additionalProperties": False,
}


def frontier_proposer(provider: str = "claude"):
    """Return proposer(spot_text) -> (proposal_dict, (in_tok, out_tok)) backed by the real frontier API."""
    def _p(spot_text: str):
        if provider == "openai":
            return openai_json(SYS, spot_text, DISTILL_SCHEMA, "gto_decision")
        data, (it, ot, _cr) = claude_json(SYS, spot_text, DISTILL_SCHEMA)
        return data, (it, ot)
    return _p


def to_example(spot_text: str, proposal: dict) -> dict:
    """Frontier proposal -> a program-of-thought decision record (reasoning comment + decide(...))."""
    a = (proposal.get("action") or "").lower().replace("all-in", "allin")
    size = proposal.get("size_bb")
    reason = (proposal.get("reasoning") or "").strip().replace("\n", " ")[:500]
    call = f"decide({a!r}, {size})" if size is not None else f"decide({a!r})"
    return make_example("distill", spot_text, f"# {reason}\n{call}",
                        action={"action": a, "size_bb": size}, type_="decision", meta={"distilled": True})


def run(weak_spots, ev_filter: EVFilter | None = None, out_path=None,
        proposer=None, provider: str = "claude", limit: int | None = None) -> dict:
    """weak_spots = iterable of structured `Spot`s. Gate each frontier proposal; APPEND accepted to out_path (jsonl).
    Returns stats incl. token spend + reject reasons. `proposer` is injectable for offline tests."""
    ev_filter = ev_filter or EVFilter()
    proposer = proposer or frontier_proposer(provider)
    tok_in = tok_out = 0
    accepted, rejected = [], []
    for i, spot in enumerate(weak_spots):
        if limit and i >= limit:
            break
        spot_text = format_spot(spot)
        try:
            proposal, (it, ot) = proposer(spot_text)
        except Exception as e:  # noqa: BLE001
            rejected.append(("api-error", str(e)[:80]))
            continue
        tok_in += it
        tok_out += ot
        ex = to_example(spot_text, proposal)
        v = ev_filter.gate(ex, spot)
        if v.ok:
            accepted.append(ex)
        else:
            rejected.append((v.gate, v.reason))
    if out_path and accepted:
        with open(out_path, "a", encoding="utf-8") as f:
            for ex in accepted:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    return {"accepted": len(accepted), "rejected": len(rejected), "filter": dict(ev_filter.stats),
            "tokens": {"in": tok_in, "out": tok_out}, "reject_reasons": rejected[:20]}
