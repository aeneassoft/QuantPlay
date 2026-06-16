"""Distill the CFR / architecture papers (books/papers/CFR + the WEVA AGT paper) into knowledge_base artifacts via
the Claude API, then consult GPT-5.5 for the NEXT-RUN architecture of our from-scratch HUNL Deep CFR net.

Grounded in the live build: deep_cfr_hunl.py = fcpa abstraction + 20-dim strength features + dual-net Deep CFR, just
upgraded LinearCFR -> DCFR+ (Leduc neural exploitability 445 -> 338, still falling). Goal: beat the -72 imitation
floor vs GTO Wizard. Resources: local RTX 3080 Ti + optional RunPod. Vet ALL output for hallucination (in-session).

Run: python -m extraction.cfr_papers_consult
"""
from __future__ import annotations

import json
import re

from pokerbot import config

PAPERS = [
    ("deep_pdcfr_paper", "paper_aaai26.txt",
     "Deep (Predictive) Discounted CFR (AAAI-26): model-free neural DCFR+/PDCFR+ via cumulative-ADVANTAGE "
     "bootstrapping + DREAM-style variance-reduction baseline net. (We already applied DCFR+ 1+2; var-reduction is open.)"),
    ("seq_equilibrium_cfr_paper", "paper_cfr.txt",
     "CFR for Sequential Equilibrium (ICLR-26): decreasing LOCAL perturbation -> converges to a refinement (SE/EFPE) "
     "that plays well in OFF-equilibrium infosets (where weak/human opponents drift)."),
    ("harvard_general_cfr_paper", "paper_harvard.txt",
     "Harvard 2022 thesis (Meyer, adv. Parkes/Zhang): toward GENERAL CFR; two novel variants incl. value-of-information."),
    ("weva_abstraction_paper", "paper_agt.txt",
     "WEVA (arXiv 2605.10900, Tsinghua 2026): warm-up EV-based INFO ABSTRACTION via k-means on early-CFR per-hand EVs; "
     "up to -80% exploitability vs equity/rank buckets, no domain knowledge, no pretraining."),
    ("nn_architecture_paper", "paper_nnarch.txt",
     "Optimized NN architecture for classification (Nadeem 2026): generic hidden-layer/dropout/normalization design. "
     "Likely LOW relevance to our advantage/policy REGRESSION net — vet honestly, do not force-fit."),
]

OUR_BUILD = """OUR TARGET (ground every answer here; honest, not hyped):
We are building our OWN from-scratch neural Deep CFR self-play GTO core for HEADS-UP NLHE (pokerbot/strategy/
deep_cfr_hunl.py), to replace a solver-IMITATION floor stuck at -72 bb/100 vs GTO Wizard AI (the loss is BROAD
postflop quality, not a single fixable leak; run-to-run noise is +/-8 bb/100 at n=2500).
The net, concretely:
- GAME: self-contained, cloneable HUNL state machine; fcpa betting abstraction (fold / call|check / POT-size / all-in),
  capped raises, treys showdown; chip frame SB50/BB100/20000 (=200bb).
- FEATURES (20-dim, strength-bucketed): treys-normalized made strength (preflop heuristic), street one-hot, button,
  pot/owe/remaining ratios, raise count, hole high/low/pair/suited/gap, board suit-count/paired/flush-draw.
- ALGORITHM: external-sampling MCCFR + DUAL nets (advantage net per player; policy net = time-averaged strategy).
  Just upgraded LinearCFR -> DCFR+ (discount alpha=2 + clip + bootstrap of cumulative ADVANTAGES; gamma=2 averaging);
  Leduc neural exploitability went 445 (LinearCFR plateau) -> 338 and still falling. NO variance-reduction baseline yet.
- INFERENCE: the bot samples the policy net directly (NO real-time resolving). Verified feature reconstruction
  (0 mismatches) so the net plugs straight into the bot + the GTO Wizard adapter.
- VALIDATION: exact exploitability on Leduc (correctness proof); head-to-head vs check-call/always-fold/random on
  HUNL; then GTO Wizard AIVAT (#1 benchmark, decision-grade n>=2500).
- RESOURCES: local RTX 3080 Ti (12 GB) + optional RunPod GPU; ~1.9 s/iter @ 80 trav on CPU (the Python traverse is
  the bottleneck, not the net).
- KNOWN GAPS vs SOTA (Supremus = DeepStack lineage: continual safe re-solving + CFV value nets + DCFR+ + FINE bet
  abstraction F/C/0.33/0.5/0.75/1/1.25/2/allin): our betting is crude (fcpa), features are hand-crafted strength
  buckets, no CFV/value net, no variance reduction, no real-time resolving."""

DISTILL_SYS = (
    "You are a rigorous ML / game-theory engineer distilling a research paper for ONE specific build (described by "
    "the user). Extract ONLY what concretely helps THAT build. Be brutally honest about relevance — if a paper is "
    "generic or inapplicable to a from-scratch HUNL Deep CFR net, SAY SO and mark it low. Output STRICTLY a JSON "
    "array of objects, each {\"component\": str, \"description\": str, \"application_to_our_net\": str, "
    "\"relevance\": \"high\"|\"med\"|\"low\"}. No prose outside the JSON array."
)

CONSULT_SYS = (
    "You are the world's strongest No-Limit Hold'em GTO architect AND a brutally honest ML engineer. Ground EVERY "
    "claim in THIS build and the distilled papers. Rank by EV-gained / effort. No hype; explicitly flag overkill and "
    "self-deception. Quantify where you can."
)


def ask_claude(system: str, user: str, max_tokens: int = 6000) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    m = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system,
                               messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in m.content if getattr(b, "type", None) == "text")


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 32000) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for kw in ({"reasoning_effort": effort, "max_completion_tokens": cap},
               {"reasoning_effort": "medium", "max_completion_tokens": cap}, {"max_completion_tokens": cap}, {}):
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
            txt = r.choices[0].message.content or ""
            if txt.strip():
                return txt
            print(f"  ({model} empty, finish={r.choices[0].finish_reason})", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def _strip_fence(s: str) -> str:
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    return m.group(1).strip() if m else s


def main() -> None:
    theory = config.KNOWLEDGE_DIR / "theory"
    theory.mkdir(parents=True, exist_ok=True)
    docs = config.ROOT / "docs"
    docs.mkdir(exist_ok=True)
    summaries = []
    for slug, txtfile, note in PAPERS:
        p = config.DATA_DIR / txtfile
        if not p.exists():
            print(f"SKIP {slug}: {txtfile} missing", flush=True)
            continue
        text = p.read_text(encoding="utf-8")[:80000]      # cap big papers (Harvard ~115k)
        print(f"=== Claude distilling {slug} ({len(text)} chars) ...", flush=True)
        out = ask_claude(DISTILL_SYS, OUR_BUILD + f"\n\nPAPER — {note}\n\n{text}")
        raw = _strip_fence(out)
        try:
            data = json.loads(raw)
            (theory / f"{slug}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
            hi = [d for d in data if isinstance(d, dict) and d.get("relevance") == "high"]
            print(f"  -> {slug}.json ({len(data)} items, {len(hi)} high-relevance)", flush=True)
            summaries.append(f"### {slug} ({note.split(':')[0]})\n" + "\n".join(
                f"- [{d.get('relevance','?')}] {d.get('component','?')}: {d.get('application_to_our_net','')}"
                for d in data if isinstance(d, dict)))
        except Exception as e:  # noqa: BLE001
            (theory / f"{slug}.txt").write_text(out, encoding="utf-8")
            print(f"  -> {slug}.txt (raw; JSON parse failed: {e})", flush=True)
            summaries.append(f"### {slug}\n{out[:1500]}")

    digest = "\n\n".join(summaries)
    (docs / "cfr_papers_digest.md").write_text(f"# CFR papers — Claude distillation digest\n\n{digest}\n", encoding="utf-8")
    print(f"saved docs/cfr_papers_digest.md ({len(digest)} chars)\n=== GPT-5.5 next-run architecture consult ...", flush=True)

    consult_q = OUR_BUILD + f"\n\nDISTILLED PAPER INSIGHTS:\n{digest}\n\n" + """ANSWER CONCRETELY, ranked by EV/effort:
1. The SINGLE highest-leverage upgrade to our HUNL Deep CFR for the NEXT run. DCFR+ is done (445->338 on Leduc).
   Rank the top 3 of: (a) variance-reduction baseline net (DREAM/the AAAI-26 paper's component 3), (b) FINER bet
   abstraction (Supremus F/C/0.33/0.5/0.75/1/1.25/2/allin) vs our fcpa, (c) WEVA / richer learned features vs our
   hand-crafted strength buckets, (d) a CFV value net + depth-limited resolving (Supremus-style), (e) just scale
   iters/traversals. Which actually moves bb/100 vs GTO Wizard, and which is intellectually-appealing-but-low-ROI?
2. The EXACT next-run config for a strong net on an RTX 3080 Ti in a few hours: iters, traversals/iter, the bet
   menu, feature set, net width/depth, variance-reduction yes/no, CPU-traverse vs GPU. Be specific.
3. Is sampling straight from the policy net ENOUGH to beat GTO Wizard, or do we NEED real-time resolving (Supremus)?
   Where exactly does each plateau (give a bb/100 ballpark vs GTO Wizard for: fcpa policy-net, fine-abstraction
   policy-net, value-net+resolving)?
4. The CHEAPEST experiment that proves or kills the next direction before any big compute. Flag anything fabricated."""
    consult = ask_openai("gpt-5.5", CONSULT_SYS, consult_q)
    (docs / "cfr_architecture_gpt55.md").write_text(f"# Next-run architecture — GPT-5.5\n\n{consult}\n", encoding="utf-8")
    print(f"saved docs/cfr_architecture_gpt55.md ({len(consult)} chars)\nDONE — Claude (in-session) vets + builds the to-do.", flush=True)


if __name__ == "__main__":
    main()
