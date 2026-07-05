# ★★★ SESSION-HANDOFF (2026-07-05, ~23:00) — READ THIS FIRST, THEN docs/STATE.md ★★★

**You are continuing a live campaign. Read this file completely, then `docs/STATE.md` (top section), then act.
The user's standing mission: iterate autonomously toward GTO Wizard leaderboard #1 (beat −3.14 bb/100 AIVAT);
honest asymptote of the current architecture −8..−11; ~−10 is the realistic ladder target. Doctrine: ONLY bb
count (never GTO-score). Everything ships through the gate ladder: stress → replay → (canary) → paired
Analyzer grade (user uploads in Chrome) → live smoke. ONE lever family per Analyzer arm. German with the user.**

## ⚠️ PRIORITY 0 — A RUNPOD CPU POD MAY STILL BE RUNNING (BILLING!)
The previous session fired `python -m infra.export_pod 64 10` (pod `g5rke3x93p7eas`, 64 vCPU, $2.24/hr,
IP 213.173.111.79 ssh port 37471, started ~22:35 local). It generates FIVE Analyzer arms in parallel
(`/root/pokerb/hu_{v3fresh,v32,v33,v34,v35}_1500.txt` + `/root/arm_*.log`). The campaign process lived in the
OLD session — if it died with the session, its atexit-kill may NOT have fired and the pod runs on.
**FIRST ACTIONS:**
1. `python -m infra.runpod_run --status` — if no pod: fine, check `data/gtow_upload/pod/` for pulled results.
2. If the pod is RUNNING: adopt it — `ssh -i C:\Users\hampe\.ssh\pokerb_runpod -p 37471 root@213.173.111.79
   "ls /root/pokerb/hu_*_1500.txt"`. All 5 files there → scp them to `data/gtow_upload/pod/` + the logs, then
   **KILL: `python -m infra.runpod_run --kill`** and verify `--status` is empty. Not all done → poll every
   ~20min (each arm ~4-9h from 22:35); hard budget stop: kill by ~08:30 (10h wall) regardless, pull what exists.
3. Expected cost: $14-22 total; user budget ~$30. NEVER leave the pod alive unattended.

## THE CURRENT STAND (one paragraph)
Shipped bot = **PRINCE v3** (`POKERB_PRINCE=1`, commit 85d2919): paired-Analyzer **17.93** vs v2.2's 20.66;
live anchor −19.70 ± 4.37 (n=2,393, tag `v2` = restore point, pushed to GitHub). **v3.2 is REFUTED (26.14!)**
— the river-thin-value class is PARKED after 4 failed attempts; lesson: our tracked ranges are too wide on
check lines → e_call overestimated. Remaining Analyzer queue (flags built, gates green, default-OFF):
**v3.3** `POKERB_RAISE_NARROW=1` (raise-range narrowing, Laplace-shrunk mined mix), **v3.4** `POKERB_AUDIT_FIX=1`
(9-find audit bundle), **v3.5** `POKERB_ADVISOR_ROLE_POS=1` (advisor role convention — potentially the biggest).
The pod arms provide exactly these + a FRESH v3 anchor (`hu_v3fresh`) — **compare pod arms ONLY against the pod
anchor** (same platform + fixed exporter; the old 17.93 file is old-exporter and NOT comparable to pod arms).

## WHAT HAPPENS WHEN THE POD FILES ARRIVE
1. Copy `hu_v3fresh_1500.txt` + `hu_v33_1500.txt` (+ v34, v35; v32 = replication of a refuted lever, low
   priority) to the Desktop and ask the user to upload them to the GTOW Analyzer in Chrome (he does this).
2. Read verdicts from the Analyzer UPLOADS page (Chrome MCP, `get_page_text` on app.gtowizard.com →
   Uploads — the row shows "Avg. EV loss"). Baseline = the FRESH anchor's number, not 17.93.
3. Per verdict: better by ≥ ~1.5 → promote the flag into PRINCE_PROFILE (gto_mode.py) + fingerprint + commit
   + push; worse → document refutation in STATE + memory, park. Then 300-hand live tail-smoke for promoted
   levers (`tools/gtow_client`, key #2 = TEST environment only), pre-registered rules in docs/VERSION_PRINCE.md.

## TOOLING (new this session — USE IT)
- **GitHub MCP** (`.mcp.json`, npx @modelcontextprotocol/server-github, token via env var
  GITHUB_PERSONAL_ACCESS_TOKEN, already set User-scope): repo aeneassoft/PokerB, branch `serverless-worker`
  (pushed through e54e6ee + handoff commits). Use it for commits-review/issues/pushes; `gh` CLI is the fallback
  (authenticated). Push after every meaningful commit block now — GitHub is current.
- **Serena MCP** (codebase, LSP symbol navigation, 305 files indexed) — active from this session on.
- **Instruments** (all deterministic since the PYTHONHASHSEED root fix): `research/stress_suite.py --configs ...`
  (70 spots; arms incl. prince_v33/v34/v35), `research/replay_graded.py --config prince --env FLAG=1`,
  byte-identity = 2 identical runs + diff vs `data/cleanup_baseline/final_A.json`. decide() is 12.1× faster
  (memoization) — exports/canaries are cheap now.
- `docs/RESEARCH_SWEEP_2026-07-05.md` = verified papers + OpenAI math verdicts; NOTES.md = the RAM lever map
  (flop LIBRARY = queue #1 after the ladder, ISO cache built `POKERB_ISO_CACHE`, RAM-dial via Compact CFR).

## AFTER THE LADDER (pre-decided, don't relitigate)
1. **Flop solve LIBRARY** (precompute canonical flops — sidesteps the twice-confirmed live NO-GO; Johanson map
   in NOTES.md; uint8-compressed dumps fit the real 15.7GB RAM).
2. **v4 feasibility** (real-time depth-limited CFR + neural leaves): read TurboReBeL first
   (openreview.net/forum?id=yMo7Z670f6, unconfirmed link) — memory `parallel-cfr-v4-path` has the full map.
3. Error budget rest: 4bet discipline / turn passivity (selection-aware) / preflop BB-defend.

## STANDING RULES (from CLAUDE.md + memories — the ones sessions break most)
- No behavior change ships ungated; no post-gate retuning; exact gate-tested values only.
- Byte-identity harness before/after ANY refactor (clean-code discipline memory).
- Perplexity/LLM paper claims: NEVER cite without existence verification.
- Keys live in `C:\Users\hampe\Desktop\Secret keys\` — never hardcode, never commit.
- Update STATE.md top before ending any turn that moves a number. Keep the user's German.
