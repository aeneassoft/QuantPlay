# Our Bot vs Poker-Theory Itself — the in-engine duels (2026-07-06)

User ask: *"Let our bot play poker against poker theory itself."* Two $0, in-engine, variance-
cancelled embodiments of "theory," run against our engine (HEAD-default exploit bot; the mean ≈ the shipped
v2.2 anchor, which differs only in the tail). Drivers: `research/theory_duel.py` (analytic) +
`pokerbot/benchmark/gto_oracle_match.py` (solver). Both use the mirror/duplicate gate (each deck played
twice, seats swapped → card luck cancels).

## Results

| Opponent = "theory" | method | bb/100 | 95% CI | notes |
|---|---|---|---|---|
| **NULL** (theory vs itself) | mirror, n=6000 | **+0.00 ± 0.00** | — | validates the instrument |
| **Analytic** GTOBaseline (Chen/MDF/balanced), our GTO-floor | mirror, n=6000, 100bb | **−16.03 ± 10.30** | −36 .. +4 | |
| **Analytic** GTOBaseline, our full exploit engine | mirror, n=6000, 100bb | **−19.44 ± 10.51** | −40 .. +1 | |
| **Solver** TexasSolver oracle (541 live solves, 0 fallback), 40bb | paired, n=120 | **−33.3 ± 60.8** | −152 .. +86 | too noisy for sign |

(A 6-hand oracle smoke read +233 — pure tail noise; the n=120 run corrects it. *Small samples lie.*)

## What it means

1. **Our bot does NOT beat poker theory — in any instrument.** Every point estimate loses (−16, −19, −33),
   all overlapping the **−20** we already know from live AIVAT vs GTO Wizard. This is the EXPECTED truth:
   nobody beats the equilibrium (the GTOW leaderboard best is −3.14). Our engine is a solid-but-clearly-
   losing-to-theory bot at ~−20.

2. **The ~−20 is robust across THREE independent instruments** — live AIVAT vs GTOW (−20), Analyzer per-
   decision EV-loss (19.3, no AIVAT), and now the in-engine mirror vs analytic theory (−16..−19, no AIVAT,
   no GTOW). Different opponents, different methods, same number ⇒ the −20 is our **intrinsic deviation
   cost vs equilibrium play**, not a measurement artifact and nothing GTOW-specific. (This also settles the
   AIVAT-skew question: a third, AIVAT-free instrument lands on the same −20.)

3. **The exploit overlay contributes ~nothing vs theory** (EXPLOIT − FLOOR = −3.4, statistically zero). You
   can only exploit deviations; a fixed near-GTO opponent has none. The overlay's value is vs humans/leaky
   fields — exactly the doctrine "exploitation = a bounded overlay, never the goal."

4. **The mirror can't cancel all-in STRATEGY variance** (SE stays ±10 at n=6000, ±61 at n=120) — when two
   strategies diverge on a stack-off, the whole stack swings one way in hand A and not in hand B. This is
   why the trusted tight live gate is AIVAT, not raw mirror bb/100.

## Not worth chasing

Tightening the oracle number to ±20 would need n≈1100 (~7h of live solves) — not worth it: the trusted tight
number is already the AIVAT −20 vs GTOW. The duel's job was insight, and it delivered: **we lose to theory,
consistently, at ~−20; v2.2 stays the validated anchor.**
