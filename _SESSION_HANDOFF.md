# ★★★ SESSION-HANDOFF (2026-07-05, ~23:00) — READ THIS FIRST, THEN docs/STATE.md ★★★

**You are continuing a live campaign. Read this file completely, then `docs/STATE.md` (top section), then act.
The user's standing mission: iterate autonomously toward GTO Wizard leaderboard #1 (beat −3.14 bb/100 AIVAT);
honest asymptote of the current architecture −8..−11; ~−10 is the realistic ladder target. Doctrine: ONLY bb
count (never GTO-score). Everything ships through the gate ladder: stress → replay → (canary) → paired
Analyzer grade (user uploads in Chrome) → live smoke. ONE lever family per Analyzer arm. German with the user.**

## ✅ PRIORITY 0 — RESOLVED: the pod is DEAD (API-confirmed 0 pods, $0 billing). NO pod action needed.
The 2026-07-05 export-pod campaign FAILED to produce arm files and self-terminated. ROOT CAUSE (baked into
`infra/export_pod.py` now): the exports ran with the TURN resolver ON -> each 1500-hand export needs ~1500
live turn TexasSolver solves at ~150s each, ~1 solve/min on a 5-way-shared box = 10-20h/arm, never finishing
in budget. `--resolver off` only disables the RIVER resolver; the fix is `POKERB_TURN_RESOLVER=0` (now in
export_pod BASE_ENV). Cost of the failed run: ~$3-4. **The 5 Analyzer arms (fresh v3 anchor + v3.3/v3.4/v3.5,
v32=refuted) were NEVER generated — this is the open task.** Options for the next session (user picks):
(a) local overnight generation with POKERB_TURN_RESOLVER=0 (free, ~minutes/arm now that decide() is 12x
faster + turn solves off; all arms mutually paired vs a fresh turn-off local anchor); (b) one fresh pod via
the FIXED export_pod (`python -m infra.export_pod 64 8`, now turn-off, ~1-2h, ~$3). Recommend (a) — free,
and the pod added no value last run. Whichever: pair each arm ONLY against the fresh same-config anchor.

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
