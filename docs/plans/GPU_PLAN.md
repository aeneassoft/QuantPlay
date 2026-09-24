# GPU_PLAN.md — the 3080 Ti in the autogym (decided by measurement, 2026-08-16)

**Measurements of this evening:** CUDA runs (3080 Ti, 12.9 GB). The batched advisor pass
(1300x20) is NOT faster on GPU than on CPU (3.20 vs 3.52 ms — launch+transfer eat the
gain at small batches). Profile before: the live loop was batch-1 overhead, solved by
CPU batching (2.2x). **Conclusion: live inference stays CPU; the GPU gets the
mass jobs.** That is not a guess but the micro-benchmark.

## Job 1 — THE EXACT 169x169 EQUITY MATRIX (the poker-specific GPU kernel)
Brown's reference blueprint (brown_vnm_169.md): per pairing enumerate all C(48,5)=1,712,304 boards exactly.
Total volume ~5x10^10 hand evaluations: **CPU ~2 days (24 cores), GPU with a
tensorized 7-card evaluator ~minutes.** That is exactly 'tuning the graphics card for the poker
game': a batch evaluator as an integer tensor kernel (rank histograms + flush masks as
torch ops), poker-specific, reusable for every future enumeration.
YIELD: the Fraction-capable E1 reference for check V1 value_ordnung (win/split as exact
INTEGER counters -> real fractions), replacement for the not-reference-grade preflop_eqmatrix.json
(MC 600), and the Brown taxonomy (88/27/54) reproducible locally.
VALIDATION (pre-registered): 200 random (pairing, board) samples must hit treys
BIT-EXACTLY; row-sum symmetry W(i,j)+W(j,i)=1; AA-vs-random as a known anchor.

## Job 2 — Offline hindsight grading (oracle accelerator)
Re-grade decisions.jsonl.gz in batch (equity MC for L checks): one process, large batches,
no worker contention — the objection against live GPU does not apply here.

## Job 3 — v4 value-net training (the natural use)
Gate-0/CFV nets (DeepStack spec 7x500) and every Deep-CFR training: 12.9 GB go a long way.
The 3080 Ti is the TRAINING device of the v4 path; the pod stays CPU self-play.

## Do not do (measured/decided)
- Advisor live inference on GPU (benchmark above). 22 workers x 1 GPU = contention.
- GPU 'tuning' in the sense of clock/driver fiddling: none of it beats the right kernel.

**Order:** Job 1 as the next build (own session, the evaluator is a one-day build
with a validation gate), Job 2 afterwards as a by-product of the same evaluator, Job 3 with the
v4 entry.
