"""'Make Opus 4.8 work like Fable 5' — audit our poker bot through the fablize verified-discipline lens
(github.com/fivetaku/fablize): verification-grounding, multi-story gate, investigation protocol, no
promising-without-doing. Three focused Claude-API audits that SHARE one PROMPT-CACHED bot-context block (call 1
writes the cache, calls 2-3 read it at 0.1x) -> a brutally-honest outside look at what is VERIFIED vs merely
claimed/hoped. Run: python -m extraction.fable5_bot_audit
"""
from __future__ import annotations

from pokerbot import config

FABLE5_SYS = """You operate in FABLE-5 VERIFIED-DISCIPLINE mode (the fablize methodology — procedures distilled from
~1,500 tool-calls of controlled Fable-5-vs-Opus-4.8 testing). It transfers PROCEDURE, not capability: do not pretend
to raise the ceiling — MAKE THE ANALYSIS REACH ITS OWN CEILING: exhaustive, evidence-bound, brutally honest. Hard rules:
- VERIFICATION GROUNDING: every claim must cite the evidence that verifies it. Measured/executable artifacts must be
  run+observed before any 'done'. Flag EVERY claim that is asserted but not actually verified.
- MULTI-STORY GATE: decompose the work; refuse a groundless 'done'. For each objective state whether it is truly
  evidenced or merely declared.
- INVESTIGATION PROTOCOL: for any failure/loss, reproduce it, COMPETE the hypotheses, trace the COMPLETE causal chain
  — never stop at the first plausible cause.
- NO PROMISING-WITHOUT-DOING: catch 'I'll do X' / 'should help' / 'the plan is' — those are NOT results. Hard-separate
  DONE+measured from planned/hoped.
You are auditing a real poker-bot project (context below, prompt-cached). Hold it to this standard; be specific, cite
what evidence exists, and name the cheapest experiment that would close each gap."""

BOT_CONTEXT = """THE BOT (honest, as built; HEADS-UP NLHE focus, also 6-max):
THREE LAYERS + a new core:
- FLOOR (least-loss vs near-GTO): solver-IMITATION advisor MLPs (flop/turn/river) that predict the TexasSolver's
  bet/check FREQUENCY from board+hand features; + analytic pot-odds/MDF defense; + fold-equity sizing; + a CFR
  push/fold blueprint (verified Nash <=~10bb).
- REAL-TIME re-solving: resolver.py live-solves river/turn public states with TexasSolver + a range_tracker.
- EXPLOIT overlay: a Dirichlet per-node opponent model + an LCB-gated safe-exploit engine (fires only on a measured leak).
- NEW CORE (current pivot): a from-scratch neural Deep CFR self-play net (deep_cfr.py Leduc; deep_cfr_hunl.py HUNL;
  deepcfr_adapter.py net->bot) — pure self-play, no imitation.

THE CLAIMS WE HAVE MADE (audit each — verified vs asserted):
1. "The integrated bot is ~-72 bb/100 vs GTO Wizard AI" — from GTO Wizard AIVAT runs at n>=2500 (the #1 benchmark,
   ~10x variance cut). Multiple configs: floor -70.7, floor+flop-defense -66.4 AND -74.7 (same config, two runs),
   resolver+wide -72.06, resolver+narrowed -75.68, floor+river-defense -80.6.
2. "Run-to-run noise is +-8 bb/100" — INFERRED from -66.4 vs -74.7 (same config) being ~1 sigma apart. Two data points.
3. "The resolver HURTS / the range-tracker keystone did not recover it" — resolver -72/-76 < floor -66/-71 across runs.
4. "vs Slumbot +31 bb/100" — measured over 2000 hands, stderr +-46 (huge).
5. "vs weak bots +300..+700 bb/100" — internal benchmark.
6. "The floor matches solver FREQUENCIES but loses bb/100" — GTO-gap 31%(flop)/29%(river) with aggregate freqs
   aligned; AND a PAIRED head-to-head vs a TexasSolver-driven oracle = -160 +-75 (n=80 decks). The unpaired +184 was
   card variance (pairing flipped the sign).
7. "DCFR+ took the neural Leduc run 445->338 mbb, still falling" — one run; LinearCFR plateaued ~445-470; vanilla
   tabular CFR ~21 mbb. DCFR+ at iter 75 was 544 (WORSE) then dropped to 338 by iter 200 (I waited for the plateau).
8. "The first HUNL fcpa net beats call-station/always-fold/random" — head-to-head, but the eval BOUNCES wildly
   (call-station +1621 -> +519 -> +1333 across iters; high eval variance). vs always-fold ~+47 stable.
9. "Fine bet abstraction + richer features is the next-highest-leverage upgrade" — 4 sources (MoP theory, the AAAI-26
   DCFR+ paper, GPT-5.5, Supremus) "converge". NOT measured on our bot.
10. "Plateau priors: fcpa -50..-80, fine-abstraction -20..-45, value-net+resolving -15..-30" — GPT-5.5 ENGINEERING
    PRIORS, explicitly flagged not-measured.
11. "A B200 won't help (the Python MCCFR traverse is the bottleneck, not the GPU)" — reasoned + the local
    observation that GPU was slower for tiny Leduc nets (per-batch transfer overhead). Not profiled rigorously.
12. "The commit-cap anti-spew fix" — tested paired vs GTOBaseline: +8.5 +-12 (ns), fired only 3/600 decks (the
    opponent doesn't create the spot). Left OFF (unproven).

VALIDATION METHODS WE HAVE: Leduc EXACT exploitability (gold correctness gate); paired/duplicate vs GTOBaseline
(deterministic, card-luck-cancelled); GTO Wizard AIVAT (decision-grade n>=2500); head-to-head vs baseline bots;
the clairvoyance toy-game (planned, not yet built). The GTOW baseline of the first neural net is RUNNING now.

THE GOAL: beat / match GTO Wizard AI (currently a measured -72). vs the field we already crush. The thesis:
the edge is exploiting each opponent's gap to GTO, not out-GTO-ing near-GTO."""

AUDITS = [
    ("verification_audit",
     "VERIFICATION AUDIT. Go claim-by-claim through THE CLAIMS WE HAVE MADE (1-12). For each: is it VERIFIED (cite the "
     "measurement), WEAKLY-evidenced, or merely ASSERTED/HOPED? Call out every number trusted on thin evidence (e.g. a "
     "2-point noise inference, a +-46 stderr, an unproven plateau prior) and every place we declared a 'done' or a "
     "'next lever' without measuring it on OUR bot. Rank the claims from most- to least-trustworthy."),
    ("causal_chain_audit",
     "CAUSAL-CHAIN AUDIT of the -72 vs GTO Wizard. Is the cause traced, or does 'broad postflop quality' paper over an "
     "UNtraced gap? We competed some hypotheses (abstraction vs features vs convergence vs ranges vs sizing) — did we "
     "actually FALSIFY any, or just assert convergence? Is the neural-net pivot grounded in a traced cause, or is it a "
     "hope that a different method escapes a cause we never localized? Name the single cheapest experiment that would "
     "trace WHERE the -72 comes from (which streets/lines/sizes), and whether we already have the data (the per-hand "
     "gtow logger) to do it without new compute."),
    ("next_build_rigor",
     "NEXT-BUILD RIGOR. The next run (fine bet abstraction + richer features) rests on 4 sources 'converging'. "
     "Convergent opinion is NOT verification. What would Fable-5 discipline DEMAND we verify cheaply BEFORE committing "
     "hours of compute? Give the smallest falsifiable test, the exact pass/fail threshold given our +-8 (or worse) "
     "noise, and what result would KILL the fine-abstraction direction (so we don't rationalize a null). Also: are we "
     "at risk of the same 'frequency-match but lose EV' trap the floor fell into, now with a self-play net?"),
]


def ask_cached(system_blocks, user, max_tokens=4000):
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    m = client.messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system_blocks,
                               messages=[{"role": "user", "content": user}])
    u = m.usage
    return ("".join(b.text for b in m.content if getattr(b, "type", None) == "text"),
            getattr(u, "cache_creation_input_tokens", 0), getattr(u, "cache_read_input_tokens", 0))


def main() -> None:
    docs = config.ROOT / "docs"
    docs.mkdir(exist_ok=True)
    system_blocks = [
        {"type": "text", "text": FABLE5_SYS},
        {"type": "text", "text": "PROJECT CONTEXT (the audit target):\n" + BOT_CONTEXT,
         "cache_control": {"type": "ephemeral"}},   # cache the big static context -> shared across the 3 audits
    ]
    out = ["# Fable-5-discipline audit of the bot (Claude API, prompt-cached context)\n",
           "_System = the fablize verified-discipline procedures; the bot context is prompt-cached across 3 audits._\n"]
    for key, q in AUDITS:
        print(f"=== {key} ...", flush=True)
        txt, cw, cr = ask_cached(system_blocks, q)
        print(f"  cache: wrote {cw} tok, read {cr} tok", flush=True)
        out.append(f"\n## {key}  (cache write {cw} / read {cr} tok)\n\n{txt}\n")
    (docs / "fable5_bot_audit.md").write_text("\n".join(out), encoding="utf-8")
    print("saved docs/fable5_bot_audit.md", flush=True)


if __name__ == "__main__":
    main()
