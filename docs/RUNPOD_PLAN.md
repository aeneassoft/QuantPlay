# RunPod plan — stack-depth self-play hardening (READY, awaiting your "go")

**Goal:** make the bot measurably better by tuning it across *stack depths*, not just one 100bb config.
Your point is correct: effective stack depth (SPR) changes optimal postflop play even at fixed blinds,
and tournaments add rising blinds + ICM — so a single fixed configuration is leaving value on the table.

## What it does
`pokerbot/benchmark/runpod_train.py` sweeps a grid of **effective stack depths** (20 / 40 / 75 / 125 /
200 bb). For each depth it searches the adaptive+gate engine's key parameters (`value_eq`, `bluff_eq`,
`probe_budget`) to maximise a **robust** objective: mean bb/100 vs a large random opponent population,
heavily penalising losing to *any* opponent. Output: `knowledge_base/exploit/stack_depth_params.json`
— the best parameters per depth, which the engine can load to play **depth-aware**.

It is embarrassingly parallel (multiprocessing over depth × param-combo) and CPU-bound (pure-Python
Monte-Carlo equity — no GPU needed); it scales with vCPU cores.

## Cost & size
- Full run: 5 depths × 18 combos × 300 opponents × 300 hands ≈ 8M simulated hands.
- On a 32-vCPU CPU pod: ~30–90 min, **~$0.5–3** (account balance confirmed ~$55.6 — ample).

## How to launch (only on your word)
```
python -m extraction.runpod_launch          # DRY-RUN: checks balance, prints plan, provisions nothing
python -m extraction.runpod_launch --go      # provisions a cost-capped CPU pod
# then:  runpodctl send .   ->   bash /workspace/PokerB/pod_bootstrap.sh   ->   runpodctl receive <code>
```
`--go` aborts if the balance is below a safety reserve. If the headless pod-create mutation doesn't
match your account/template, create a 32-vCPU `python:3.12` pod in the RunPod UI and run the same
3 steps — the training job + `pod_bootstrap.sh` are ready either way.

## Tournament / ICM extension
Add `--icm` to wrap chip EV in a concave (sqrt) utility — a placeholder for a real ICM model. The next
iteration would add rising-blind levels + pay-jump payoffs so the same engine becomes tournament-aware
(this is also how the WSOP finalist data should be read: deep-stack, rising blinds, ICM — NOT cash).

## Status
**Prepared and dry-run-verified. Nothing has been provisioned. Waiting for your go.**
