# CLAUDE.md — PokerB

**Goal: a world-class 6-max No-Limit Hold'em AI that PLAYS GTO — i.e. approaches TRUE GTO.** The AI is three
assets ("the gold"): a **self-growing, EV-grounded dataset**, a **fine-tuned Qwen "brain"**, and **our engine as the
scaffold** the brain drives. Built across many sessions — see the user memory + `docs/STATE.md` for history.

> **★★★★★ POKER IN A NUTSHELL — DIE FUNDAMENTALE LINIE (User-Zeichnung, 2026-07-06; docs/POKER_NUTSHELL.md).**
> Poker = die UNVORHERSEHBARE WELLE (Over/Underbet) um die Handstärke, gerahmt von zwei berechenbaren Ankern
> (Preflop = pure Statistik; River = „The Bill", wo alles beglichen wird). Die Welle (Flop/Turn = Spieltheorie)
> dient zwei Zwecken: FOLD EQUITY (mehr betten → Folds) + EXTRACTION/Milking (weniger betten → Gegner melken).
> Das Ganze MUSS ein SEESAW sein (always switching up → unpredictable + noise) — hörst du auf zu schaukeln,
> wirst du lesbar. **DIESES MODELL IST PRÄDIKTIV:** es erklärt den v8-Live-Bruch (Purify flachte das Seesaw ab →
> Check-Range transparent → −20 auf −58), die Value/Bluff-Polarisierung (Gewicht je Ast am Bill), die Straßen-
> Doktrin (Preflop/River rechnen, Flop/Turn = Welle, Fold-Equity-Job) und die River-Primacy. **BINDEND: der Bot
> ist ein Seesaw, kein Fixpunkt — das Mixing/die Deception NIE abflachen. Balance = nicht-verhandelbar; das
> Schaukeln SELBST ist der Edge; gegen adaptive Gegner wird das Umschalten über Zeit (Red Queen) zum Exploit.
> Bankroll/Varianz (mehr Bluffen = mehr Varianz) = eine noch un-formalisierte Achse.** OBFUSCATION-Erweiterung
> (User): kryptografische Unvorhersehbarkeit der REALISIERUNG (CSPRNG statt Mersenne-Twister) für maximale
> Uneinsichtbarkeit — relevant vs ADAPTIVE Gegner (Menschen), irrelevant vs statischen GTOW (der die RANGE
> exploitet, nicht die RNG-Sequenz); zweit-Ordnung ÜBER der Balance (obfuscation ≠ balance). Determinismus-
> Tension: geseedete RNG fürs MESSEN, CSPRNG fürs LIVE-Spiel vs Menschen (Kontext-Split, wie Purify).
>
> **★★★★★ OPERATIVE DOKTRIN (User, 2026-07-06) — PROFIT-EMPIRISMUS. ZIEL: GTOW-LEADERBOARD TOP 5.**
> Wir sind zuerst eine **statistische Mustererkennungs-Maschine über Millionen Händen**: es zählt
> ausschließlich, was bb druckt ("nur bb zählen", jetzt radikalisiert). **Formeln sind SUPPENFLEISCH** —
> MDF/Pot-Odds/e_call/Blocker schwimmen als Features/Prioren IN den empirisch abgeschmeckten Deciders
> (die Advisor-MLPs sind das Muster), nie als Dogma darüber. Mathematisch elegant + druckt nicht = Tonne
> (gemessen: frequency-matching 3× refuted). Mathematisch "falsch" + druckt = shipped (gemessen: SB-fold-clamp).
> **Axiome als Knöpfe:** MODELL-Annahmen/Gleichgewichts-Begriffe/Präzisions-Budgets/Spiel-Perturbationen sind
> frei drehbar mit explizitem Bedingungs-Test (`docs/CONDITIONAL_POKER_LEMMAS.md`: L1 Purify, L2 Mr-Orange,
> L3 v3.2b, L4 Iso). NICHT drehbar (nicht aus Dogma — es ist das Scoreboard selbst): Chip-Erhaltung,
> Σp=1, EV-Linearität (`tests/test_math_suite.py` bewacht; 17/17 deep). Lead-Generator: `research/money_mine.py`
> (AIVAT-gewichtete P&L-Attribution; Buckets = Leads, nicht Beweise — konditionierte Teilmengen sind nicht
> unverzerrt). Der einzige Geschmackstest bleibt die Gate-Leiter — ein Degenerierter ohne ehrliches
> Scoreboard weiß nicht, was druckt.
> **AIVAT-ADAPTED (Paper arXiv:1612.06915 gelesen, Ledger):** der Mittelwert ist per Theorem NICHT gambar
> ("cannot appear to do better by changing play") → Metrik-Gaming-Ideen sind Artefakte per Konstruktion.
> Legitime Anpassung: (1) pures EV, (2) niedrigvarianter Stil = engere SE = billigere Wahrheit (per-Hand-SD
> 1000→214 gemessen), (3) On-Tree-Sizings = besserer Baseline-Fit = weniger Mess-Rauschen.
> **MESS-ÖKONOMIE (User-Beobachtung 2026-07-06, hart):** der **Chrome/Analyzer-Kanal ist um Größenordnungen
> schneller als die API** — Export 1500 Hände ≈ 4 min lokal (post-Memoisierung), Analyzer graded sie in
> Minuten; die Live-API braucht ~8-9h für 2500. → **Analyzer-first**: μ-Vergleiche/Arm-Verdikte laufen über
> gepaarte seed-Exports + Chrome-Upload (skalierbar: mehrere 1500er-Blöcke pro Arm = SE/√k); die API ist der
> knappe Kanal NUR für Live-Anker, Tail-Smokes und Leaderboard-Einträge. Upload-Regeln: CRLF pflicht,
> Hand-IDs verbrennen beim ERSTEN Kontakt (auch bei gescheiterten Uploads — nie idbase/dayoffset wiederholen;
> Ledger in STATE).

> **★ NORTH STAR (2026-06-17) — PLAY GTO / ACHIEVE TRUE GTO, in 6-max NLHE.**
> Rigorous target = the **robust correlated equilibrium**. (Einy–Haimanko–Lagziel, *Economic Theory* 2022,
> `books/papers/Springer - Nash + Incomplete Information.pdf`: a Nash eq is *strongly robust to incomplete
> information* **iff** it is the UNIQUE correlated equilibrium; a 2-player zero-sum game with a unique NE has a unique
> CE.) → that is WHY heads-up is the solver/SOTA domain (unique NE → unique CE → strongly robust) and WHY **6-max is
> fundamentally harder** (multiplayer general-sum → no unique-CE guarantee → **strong robustness is NOT free**). So
> "true GTO" here = **lowest achievable exploitability + solver-match + cross-opponent-distribution robustness**,
> enforced EMPIRICALLY. **Exploitation = a BOUNDED, GTO-EVALUATED overlay** (a deviation justified by EV gain vs its
> exploitability cost) — never the goal in itself.
>
> **The approach:** an **LLM brain** — a fine-tuned **Qwen3** (8B first, size-agnostic pipeline → 32B later) — that
> DRIVES our engine via **program-of-thought**: it emits Python calling our engine-API (`pokerbot/brain/api.py`),
> which EXECUTES → an exact, verifiable action. The LLM does NOT *be* a solver; it *orchestrates* one (math by code =
> no LLM-arithmetic errors; legality by the engine; judgment by NL). SOTA value-nets (DeepStack/Supremus) are HU-only;
> a from-scratch 6-max net is DEPRIORITIZED (no clean GTO benchmark + extreme complexity). Plan:
> `.claude/plans/gut-dann-sind-wir-toasty-forest.md` · `docs/QWEN_6MAX_PLAN.md` · `docs/DATASET_SPEC.md`.
>
> **★★★ CURRENT TRUTH + VEHICLE (2026-07-04) — THE "−47 ENGINE" IS DEAD; the ENGINE-ALONE is the vehicle toward GTOW,
> and it is FAR better than every number in this repo claimed.** Two things flipped this session:
> **(1) The engine is NOT −47.** A fresh HEAD-default GTOW run (all flags OFF = the shipped `pokerbot/strategy/bot.py`)
> measured **AIVAT −20.09 ± 7.18 bb/100 (n=974)**, BODY **−8 to −11** (5–10% trim), **0 catastrophes**. The −47.18 was
> a STALE ACCOUNT AGGREGATE over dead code eras (the −106 jam-spew era etc.). The body is near the GTOW leaderboard
> (best −3.14, frontier LLMs −9). CROSS-CHECKED: the GTOW-Analyzer per-decision HU EV-loss (**19.3 bb/100**) ≈ the live
> AIVAT (−20) → two independent metrics agree → the loss is REAL deviation cost, not tail luck. The −20 lives entirely
> POSTFLOP (river −8.6 + flop −8.3; preflop −1.6 = near-solved blueprint), in NORMAL pots (not jams).
> **(2) Both disciplines are now ABSOLUTELY GTO-GRADED** (GTOW Analyzer, the repeatable Chrome loop; `research/
> pokerstars_export.py` HU + `research/sixmax_export.py` 6-max): **HU 53.4% GTO-score / Freq-Diff 54.6%** (the shipped
> EXPLOIT-PRIMARY engine deviates from GTO by design → −EV vs near-GTO GTOW) vs **6-max 85.9% / EV-loss 7.61** (the
> `tag` core, far more GTO-aligned). The user chose the **ENGINE-ALONE path** (fast, $0/hand, fully ours); **the goal
> (explicit, 2026-07-04): TIE GTOW (0 bb/100)** — staged via −10; the full ledger + path = `docs/TIE_GTOW.md`
> (the 19.33 bb/100 gap decomposes into a spread exploit-frequency deviation ≈10.7 + named concentrated leaks ≈8.6:
> BB-flop-over-fold 2.9, river-aggression 1.6, cbet-fold 1.3, river-value 1.0 …). **The active lever = `POKERB_GTO_MODE` (built this session, `pokerbot/strategy/gto_mode.py`, default
> OFF): flip exploit OFF + play GTOW's MEASURED tree** (the 12.5k-hand census `data/census/gtow_tree.json` →
> `research/gtow_tree_census.py`; sub-fixes S1–S5 in the plan: exploit-off, range-tracker fix, off-tree snap, river
> guards, resolver-on-census-tree). Hypothesis (the next $0 deterministic test): exploit-OFF lifts the HU GTO-score
> from 53% toward the 6-max 85% and shrinks the Freq-Diff. NOTE (measurement): engine GTOW runs are **effectively FREE**
> (in-process from the PC, `--agent-type pokerbot`, no pod); the "$10 budget" is a statistical-honesty constraint, not
> money. **Every "−47" reference below/elsewhere is STALE — read it as −20 raw / −8…−11 body.** Live detail + the S6
> GTOW-mode A/B (must be gated vs −20.09, not −47): `docs/STATE.md`. Also built: `pokerbot/vision/screen_reader.py`
> (universal VLM poker-table reader, any site).
> **The BRAIN track (Claude/GLM below) is a PROVEN, still-valid asset — but SECONDARY now**: it BYPASSES the engine's
> `bot.py` wins (drives `api.legalize` directly, [[brain-engine-two-products]]), and the engine-alone is the cheaper,
> faster, fully-ours bet the user picked. Keep the brain for research + the teacher-gold loop; the engine is the product.
>
> **★ CURRENT BRAIN (2026-06-19, SECONDARY now — see the 2026-07-04 block above) — CLAUDE OPUS 4.8 is the brain; Claude-ONLY first, Qwen is Step 2 (decide later).**
> Measured truth (GTOW leaderboard, read-only API): frontier LLMs with high reasoning play HUNL at ~−9 bb/100 AIVAT
> (GPT-5.2 −8.26, GPT-5.5 −9.23) — ~5× better than the STALE −47 engine aggregate (the CURRENT engine is −20 raw /
> −8…−11 body, see the 2026-07-04 block — the gap to the frontier is now small). So the brain is now a **frontier LLM prompted via program-of-thought**, NOT the (warm-start)
> Qwen-8B: `pokerbot/brain/claude_brain.py` `ClaudeBrain` → emits a DSL program calling `api.*` (exact math / equity /
> the live solver) → `executor.run_program` → an exact LEGAL action (gtow `--agent-type claude`; `research/llm.ask_claude`,
> thinking=adaptive = the leaderboard's "extra-high reasoning"). **Judgment by Claude, math + legality by the engine; we
> steer it in natural language → fast iteration.** ORDER: **Claude-only first DID prove the recipe** (−28.55 AIVAT —
> the teacher + proof); **Step 2 — our own RL-able AI — is NOW IN EXECUTION = GLM-Z1-9B (THUDM, MIT; not Qwen) SFT→RL**
> on a RunPod H100 SXM. Live status: `docs/STATE.md` (the SFT warm-start WORKS at 97.5% token-acc; the RL-lift is the
> open question). Honestly capped LOWER (9B ≪ Opus). Imitation-cap (still true): TRAINING a small model on our data ≤ our −47; PROMPTING a
> frontier model is NOT so capped (its own reasoning ~−9). Frontier API = PC-hub ONLY (never the pod). Honest ceiling:
> nobody beats GTOW (best −3.14) — a too-good number (e.g. a "+" vs GTOW) is an ARTIFACT to debug, never a win.
> **★ MEASURED (2026-06-21) — the GLM-Z1-9B brain (engine+brain) vs GTOW ≈ −17 bb/100 in the BODY (5%-trimmed, NEAR the leaderboard −3…−17) but a FAT TAIL of -EV postflop BETTING + coolers drags the RAW to −40/−68 (high variance; the anti-spew gate was REFUTED by a $0 counterfactual — STATE.md #3), via
> INFERENCE-WIRING fixes, NOT weights.** The arc: pure engine −47 → GLM-GRPO −43.30 → two SERVE-TIME wiring fixes (the
> `gtow_to_state` preflop `to_call` bug [inflated required_equity → over-fold] + the `format_spot` made-hand read [the GLM
> mis-read its own hand], both OOD, NO retraining) → a **body ~−17** (5%-trimmed, near the leaderboard; the RAW is −40/−68 = a fat tail of -EV betting/coolers; the once-cited −28.36 was a LUCKY low-tail session — raw swings −28↔−90 at n≤1500, all tail).** ★ **THE RL-LIFT QUESTION IS NOW
> ANSWERED (negatively, for this setup):** a re-SFT on made-hand-NATIVE gold + a fresh GRPO REGRESSED to −90.18 (postflop/
> river spew; the self-play sixmax league ≠ GTOW → RL learned league-beating aggression that loses to GTOW). The
> `gtow_glm_pod` A/B + the protected baseline = the "never ship a regression" gate. **THE LESSON: the wins are the WIRING
> (what the engine feeds the LLM at serve time), not the weights; baking a serve-hint into TRAINING backfires.** A
> separate cross-check found our solver/blueprint ORACLE is ~90% aligned with GTOW (NOT grossly broken) → the speculative
> postflop-solver overhaul (the old "PLAN #2") is NOT justified by the data. The baseline (`models/grpo_slim.tgz`, ≈ −40 robust,
> served `POKERB_MADE_HAND=1`+`POKERB_TOCALL_FIX=1`) is the PRODUCT. **NEXT (gated):** modest serve-time hints (the advisor
> bet-frequency, A/B'd OFF/ON default-OFF) for the one remaining real leak (postflop turn UNDER-betting); the deeper RL
> lever needs a BETTER REWARD (GTOW-anchored / stronger league), not more steps. Live detail: `docs/STATE.md`; harness
> `infra/gtow_glm_pod.py`. (The SIGALRM-in-worker-thread bug that first hid the GLM as frac_bad=1.0 is fixed in
> `executor._alarm_available`.)
>
> **Two-node system:** (1) **the PC (hub)** = the self-growing EV-gated dataset + a frontier-distillation loop
> (OpenAI/Claude → a HARD-CODED deterministic EV-TRUTH filter → dataset) + CPU mass-solving + the training monitor +
> scp-orchestration; (2) **RunPod** = Qwen SFT→GRPO (reward = 6-max self-play EV via `table.py` + the `sixmax`
> opponent league; GTO-anchored eval = PokerBench-acc + bb/100 + LBR-exploitability + robustness-spread). Frontier
> APIs feed ONLY the PC, never the pod; **the engine is TRUTH, the frontier a GATED PRIOR.**
>
> **CLEAN BOUNDARY (hard rule):** SFT/distillation = WARM-START only; the imitation ceiling is real (a HU policy net
> hit −212, a solver-imitation floor plateaued ~−72). **Only RL/self-play with realized-EV reward lifts above the
> teacher.** External assets (the 6 books, CFR/Pluribus/Supremus papers, PokerBench, Pluribus hands, frontier LLMs)
> seed / validate / distill-UNDER-GATE — never an ungated training label.

> **★★★★★ MILESTONE `v2` (git tag, 2026-07-05) — PRINCE v2.2 (SUPERSEDED by v3, block below) — PRECISION-MEASURED at
> AIVAT −19.70 ± 4.37 bb/100 vs GTO Wizard (n=2,393, pre-registered; ZERO catastrophes ≤−50bb, per-hand SD 214 =
> leaderboard-grade, body −6..−9).** This is the first bot the team versioned as a restore point (`git checkout v2`;
> commits `6bbf1c3`+`a49e244`). Config = `POKERB_PRINCE=1` (20-flag profile, `pokerbot/strategy/gto_mode.py`). The
> honest read: the DISTRIBUTION was transformed vs the old HEAD (tail eliminated, ± small) but the MEAN did not move
> (HEAD was −20.09 ± 7.18; the −11.61 was a lucky n=100 draw) — discipline bought SAFETY, not μ. The remaining loss
> is postflop (river −8.5 + flop −6.4, x-ray); mission = leaderboard #1 (beat −3.14), gap ≈ 16.5 bb/100 almost all
> river+flop. Instruments built this generation (all reusable, all $0): `research/stress_suite.py` (constructed-
> catastrophe gate), `research/replay_graded.py` (graded-hand regression gate), `research/freq_mine.py` (GTOW's
> revealed per-node frequencies from 13.5k hands = free teacher). NEXT = μ-levers on the river (Q6 anchors:
> `data/freq_targets/gtow_frequencies.json`), each gated stress→replay→canary→live. **The −20 in every block BELOW
> is the SAME engine measured; v2 is that engine with the deception+eCall+line-U+size-inject layer, tail-fixed.**
>
> **⟵ SUPERSEDED (2026-07-06): the shipped profile was REVERTED to PRINCE v2.2 — the validated −19.70/rank-#11
> anchor. v3 (PAIR/RIVER_DEFENSE) and every later lever (RAISE_NARROW/OVERBET_MENU/PURIFY/TURN_DEF_ADVISOR) are
> Analyzer-only and/or the v8 live-breakers (−58); by the user's 90%-confidence rule they are EXCLUDED from the
> final bot and demoted to default-OFF re-test arms. See STATE.md's top block. The v3 record below is history.**
> **★★★★★ PRINCE v3 SHIPPED + THE LEVER PIPELINE + THE INFRASTRUCTURE LEAP (2026-07-05 evening).** The shipped
> bot is now **PRINCE v3** (commit 85d2919): the v2.2 profile + PAIR_DEFENSE 0.10 + RIVER_DEFENSE 0.06 — gated by
> the agreed v3-test-protocol (**paired Analyzer 17.93 vs v2.2's 20.66 on identical seed-55 deals** = the decisive
> $0 gate; tail-smoke 0 catastrophes, worst −19.3bb). v3.1 (flat thin-floor) was Analyzer-REFUTED (19.76) = the
> THIRD measured proof that **frequency-matching without the teacher's SELECTION loses**. IN THE PIPELINE (built,
> all gates green, default-OFF, ONE Analyzer arm each): **v3.2** RIVER_THIN_SEL (selection-aware thin value via
> eCall), **v3.3** RAISE_NARROW (raise-facing-bet range narrowing toward the MINED GTOW raise mix —
> `research/raise_mine.py`, 488 raises: jams ~62% nutted, flop raises 53% air), **v3.4** AUDIT_FIX (9 finds of the
> 90-agent audit: PAIR_DEFENSE fired on check-raises, TURN_DEFENSE cancelled BARREL_DISCIPLINE, vacuous river
> bluffcatcher gate, covered-stack pot odds, threshold floor, phantom sizer arms, raise=aggro), **v3.5**
> ADVISOR_ROLE_POS (advisors were queried by INITIATIVE but trained by POSITION → inverted in 3bet pots).
> **MEASUREMENT-SEAM FIXES (live now):** the live blinds order [BB,SB] was unpacked as [SB,BB] → EVERY live AIVAT
> run carried a baked-in preflop over-fold (+7pp required equity BB-vs-open; exports unaffected); the config
> fingerprint missed 13 flags; export all-in run-outs lacked HH board sections (**future pairings need FRESH
> anchors**). **INFRASTRUCTURE: decide() is 12.1× faster** (999→83ms, proven-pure memoization, commit 114e107) and
> the instruments are now TRULY process-deterministic (set-iteration/PYTHONHASHSEED root fix in
> `ranges.combos_for_classes` — every prior "deterministic" run carried boundary-spot jitter). Clean-code
> discipline = standing rule (memory `clean-code-discipline`; the byte-identity harness is THE refactor gate).
> **THE v4 PATH (post-lever-ladder, decided):** real-time depth-limited CFR + neural leaves per Li&Huang
> (`books/papers/CFR/2605.19928v1.pdf`) + EVPA (ICLR25, read: ensemble pruning needs the nets; the geometric
> transfer measured NO-OP vs TexasSolver — it prunes internally) + TurboReBeL (leaf training) — ladder ≈ −10
> asymptote, v4 = the way below −8. Research ledger: `docs/RESEARCH_SWEEP_2026-07-05.md` (27/36 papers
> existence-verified; Perplexity scrambles metadata — NEVER cite unverified). Codebase MCP: Serena (`.mcp.json`,
> LSP symbol navigation, active from the next session). Analyzer sequencing: v3.2 → v3.3 → v3.4 → v3.5, one arm
> per user upload, fresh anchors from the fixed exporter.
>
> **★ FUTURE BUILD CANDIDATE (user-flagged 2026-07-07, deferred) — the VALUE-OF-COMPUTATION ARBITER**
> ([`docs/SURFING_CONSULT.md`](docs/SURFING_CONSULT.md), memory [[value-of-computation-arbiter]]). From extracting
> Andy Clark's *Surfing Uncertainty* (predictive processing) + a GPT-5.5 math/CS translation: PP is mostly an
> elegant re-description of RL/solver methods (NO new poker objective — poker stays chip-EV, not prediction-error
> min), BUT 3 concepts converge on ONE buildable high-leverage lever = **precision-weighted value-of-computation
> control**: spend resolver/CFR budget ONLY where the fast cached policy is likely wrong or the top-2 EV gap is
> small AND the pot is large. Build: a calibrated **ΔEV = EV(resolved) − EV(fast)** quantile regressor over cheap
> features (advisor policy+entropy, range-confidence, pot/SPR, top-2 margin, cache age, board texture, opponent
> line-surprise) → invoke the resolver iff `E[ΔEV] − λ·solve_ms > threshold` (+ river-all-in triggers). This is the
> IMPLEMENTABLE core of the v4 path (it decides WHERE the real-time CFR runs) and attacks the −20 postflop leak
> directly; aligns with `docs/PRECISION_DOCTRINE.md`. The transferable book-insight: the brain rivals machines at
> poker via metareasoning EFFICIENCY (optimal scarce-compute allocation), not raw compute or a better objective.
>
> **★★★★★ 2026-08-04 — DREI NEUE STANDBEINE (Detail: STATE.md): SNOWIE-BRÜCKE, TURNIER-MODUS, MULTIWAY.**
> **(1) PokerSnowie-Brücke produktionsreif** (`pokerbot/vision/snowie_*`): spielt PokerSnowie 4 vollautomatisch
> (13,3 Hände/min, ~4% Aussetzer, beide Themes). Härtungs-Doktrin daraus: NIE mit falschen Zahlen rechnen
> (Gatter → Eskalation nur bei sauberen Kernfeldern → ehrlicher Ausschluss), Chip-Erhaltung als Gatter,
> Zweitquellen-Pflicht für den Pot, Klick-/Aktions-Verifikation, 5-Fälle-Regressionsnetz (`research/
> snowie_regress.py`) + Marathon-Wächter. **Messung (3 Läufe, 3.651 Hände): Konto −$2.915, aber der BEREINIGTE
> Pool (3.114 saubere Hände) = +3,2 bb/100 [−37,+44] — der Bot war ≈ break-even vs Snowie, die Automatisierungs-
> Steuer fraß das Konto** (jede Klasse einzeln obduziert + abgedichtet). Prince-HU in der Brücke NUR postflop
> (User-Einwand korrekt: MP-Open ≈ 15–20% Range, die HU-Projektion läse ~50%); 6-max-POSITIONS-PRIOR für die
> Gegner-Range + Bayes-Korrektur über beobachtete Aktionen (`make_seeded_tracker`/`ActionLog`).
> **(2) TURNIER-MODUS GEBAUT + VALIDIERT** (Sklansky + Endgame/ICM systematisch extrahiert →
> `knowledge_base/tournament/DOKTRIN.md`): exaktes Malmuth-Harville (`strategy/icm.py`, gegen unabhängige
> Enumeration getestet), Doktrin-Schicht (`strategy/tournament.py`: BF-Skalierung NUR der Call-Seite =
> Gap-Doktrin; **anteiliges Risiko-Premium** BF_eff = 1+(BF−1)·(to_call/Stack) — der volle BF wurde vom
> gepaarten Experiment REFUTIERT (−8pp, Bubble-Ausbluten), das anteilige VALIDIERT: **μ-3 n=1500 gepaart:
> +10,0 ± 5,0 pp ROI, 95%-Band [+0,2, +19,9], MEHR Siege UND bessere Ladder**), Direktor (Level/Antes/
> Eliminierung/Schrumpfung), Arena mit gepaarten Seeds (`arena/tourney.py`). HU = BF 1 → Prince v2.2 spielt
> Turnier-Endspiele UNANGETASTET. Druck-Hebel (Doktrin 9, `icm_pressure_mult`): der Coverstack erntet die
> Zwangs-Tightness ICM-spielender Gegner — die PS-$1050-Vermessung belegt dieses Tightening empirisch
> (FoldVsRaise 54→62%, Jam 1,1→13,1%; `research/ps_tourney_field.py` + `ps_tourney_duel.py`).
> **(3) MULTIWAY 7–10**: Engine-Labels bis 10-max, sixmax-Buckets NUR für neue Labels (6-max byte-identisch =
> Anker-Schutz), Trainer `?players=9`. **Ökologie-Erkenntnisse:** GG-$10/$20 (härtester Pool, 85% TAG):
> GTO +106/Exploit +126 (modell-optimistisch), P_D-Klon −216 vs **P_D-A-GAME (Reset-Klon) +16,6 ± 5,3
> [+6,3,+27] = signifikanter Gewinner — der TILT kostet ~233 bb/100** (die teuerste gemessene Verhaltensvariable
> des Projekts). AIVAT vs Snowie: voll nicht möglich (kein Showdown-Logging); Leiter definiert
> (Showdown-Logger → All-in-Glücksbereinigung → MIVAT-light).
>
> **★★★★ NEW SESSION? READ [`_PRINCE_START_HERE.md`](_PRINCE_START_HERE.md) FIRST (the ROOT MARKER, 2026-07-04)** —
> the current mission in one page: **VERSION "PRINCE"** ([`docs/VERSION_PRINCE.md`](docs/VERSION_PRINCE.md) = the
> ACTIVE BUILD CARD with the merged lever queue + measurement ladder). The measured stand: GTO-mode **−11.61** (n=100
> smoke) / HEAD **−20.09** (n=974) = #11 leaderboard; the deception layer SHIPPED (turn-defense + slowplay, canary +
> mechanics ✓, live in the HU app). Doctrine (measured): **the GTO-score is DEAD as a target — ONLY bb count**
> (frequency-matching GTOW cost EV). Opponent intel: [`docs/GTOW_DOSSIER.md`](docs/GTOW_DOSSIER.md) — GTOW = the Ruse
> REAL-TIME re-solver; bet-size/translation attacks REFUTED ($0, 13.5k hands). PRE-STAGED top-3 levers (flop-resolver
> go/no-go · river-eCall · line-U + instruments first) await the user's build command.
>
> **New Claude session? Start with [`docs/STATE.md`](docs/STATE.md)** — the LIVE source of truth. Live repo tree =
> [`INDEX.md`](INDEX.md). This file = stable conventions + the north star; `STATE.md` = what's happening now.
>
> **⟳ KEEP STATE.md CURRENT — standing rule.** After any turn that moves a headline number (a measurement), lands a
> build, or shifts priorities, UPDATE STATE.md's top CURRENT section *before ending the turn* — lead with the current
> frontier, demote superseded numbers to a one-line "history" pointer. A fresh context must start from the truth.
>
> **Deferred-precision / open questions:** [`NOTES.md`](NOTES.md) — approximations we ship now + should compute
> exactly later. Add an entry when you ship a heuristic.
>
> **★ FORWARD PLAN — how to improve the bot + the personal coaching path:** [`docs/ROADMAP.md`](docs/ROADMAP.md). Two
> tracks. **(A) Make the bot UNDERSTAND poker as well as possible** — the live lever is the consolidated
> **understanding layer** (`pokerbot/brain/understanding.py::strategic_read` = SPR/position/pot-odds/MDF + board
> texture + the made-hand read + the MEASURED GTO heuristics fused into ONE engine-computed frame, gated
> `POKERB_UNDERSTANDING`, default OFF), so the brain reasons from first principles even on the ~60–85% of spots the
> solver never covers; next = measure it (deterministic GTOW per-decision first), the river over-size fix, render the
> solver's preferred SIZE. **(B) A Claude-API COACHING path for the user PERSONALLY** — review the user's own
> CoinPoker/PokerStars hands, engine-grounded (`api.*` + the understanding layer) + GTO-anchored, personalized to their
> tracked leaks; most machinery exists (`pokerbot/coach/coach.py` + `research/study_grade.py`). Honest: the
> understanding layer is BUILT but EV-UNMEASURED; the coaching path is PROPOSED. Details + the reuse map in ROADMAP.md.

## Working discipline — Fable-5 verified mode (embedded from `github.com/fivetaku/fablize`)
How to work on THIS project. Transfers PROCEDURE, not capability — *make the work reach its own ceiling, don't fake it.*
- **Verification grounding:** run + observe the artifact — a measured run, a paired/duplicate A/B, exact
  exploitability, a `test_*`, a UI via TestClient — BEFORE any "done". A claim without its cited evidence is not done.
- **Multi-story gate:** decompose; refuse a groundless "done". Per objective, state truly-evidenced vs merely-declared.
- **Investigation protocol:** for any loss/failure, reproduce it, COMPETE the hypotheses, trace the COMPLETE causal
  chain — never stop at the first plausible cause.
- **No promising-without-doing:** "I'll do X" / "should help" are NOT results. Hard-separate DONE+measured from planned/hoped.
- **Grounded gate (hard-won):** only a GROUNDED signal (solver-gap / AIVAT / exact exploitability / a deterministic
  check) gates a change. Single-rule raw-bb/100 A/B is too noisy (plausible fixes were REVERTED after measurement);
  small samples lie (n≤150 AIVAT lied as −13 vs the real −72). Paired/duplicate eval cancels card luck.

## Style & communication standard (DEFAULT — `books/papers` / `aiStyle.pdf`, Stanford *Art of Elegant Coding*)
How I write code AND talk about it — the standing default, every turn.
- **Elegant code — 4 pillars.** (1) **Names** meaningful + accurate; a name must NEVER mislead about the type/content
  it holds (`weight_str` holding a float is a leak). Descriptive, not over-verbose. (2) **Constants, not magic numbers**
  — name them (UPPERCASE module-level) so intent + tunability are explicit (matches our `# a prior; RL tunes` idiom).
  (3) **Comments** explain the WHY + the non-obvious (why `0.378`), never restate the code; one honest line beats three
  hollow ones. (4) **Decomposition** — small single-purpose functions; split a function >~15 lines; extract a repeated
  >~4-line block into a helper.
- **Communication — be TIMELY, SPECIFIC, HONEST, CONSISTENT.** TIMELY: surface issues inline as I work, not deferred.
  SPECIFIC: exact `file:line` + a concrete alternative + a one-line WHY. **HONEST: NO hollow praise / hallucinated
  approval** — never call code good when it isn't, never claim a comment/test/result that isn't there (the paper's #1
  LLM failure mode; this IS the Verification-grounding gate restated). CONSISTENT: uniform format; write code that reads
  like the surrounding code (match its naming, comment density, idiom).

> **★★★★★ AKTIVER PLAN (2026-08-16) — AUTOGYM: die selbstpruefende Trainings-Schleife. ZIEL = an die
> GTOW-BASELINE herankommen** (Referenz −19,70 ± 4,37; Treppe −15 → −10 → Leaderboard-Band, jede Stufe vs GTOW
> gemessen, $0 in-process). Gebaut: `pokerbot/autogym/` — `oracle.py` (die VEREINHEITLICHTE Mathematik-Benchmark:
> die 78 Formelfunktionen aus `knowledge_base/math/` werden stufenweise zu Urteilen ueber echte
> Self-Play-Entscheidungen verdrahtet; Stufen HART/P/L/F), `gym_hu.py` + `gym_six.py` (getrennte Self-Play-Gyms
> mit Buchfuehrung; HU auf gepaarten Decks mit Button-Tausch → Paar-Drift als Symmetrie-Check, Button-Netto als
> kartenbereinigter Positionswert), `improver.py` (minen → patchen → gepaartes A/B-Gate → Journal),
> `selftest.py` (der lokale Beweis E1–E4). **Sicherheits-Kontrakt (bindend): Formeln unveraenderlich +
> Fraction-Referenz-Pflicht; Orakel-Knoepfe = Mess-Konfig, fuer den Improver GESPERRT (Goodhart); Bot-Knoepfe
> tunable mit Schranken, Anwendung NUR durchs Gate; P-Patches als Wrapper, nie Quelltext; alles ins Journal.**
> Doktrin: ueberall VORREGISTRIERTE Erwartungen; die Schleife muss LOKAL bewiesen sein (Erwartungs-Leiter
> E1–E6, `docs/AUTOGYM_PLAN.md`), erst dann der Pod (CPU-Kerne, keine GPU — CFR/Self-Play-Rechnung).
> Erster Pilot: 500 Haende + 3.577 gegradete Entscheidungen in 52 s lokal; HART 0, P 0, L 35, F 3.
> **★ ERGEBNIS NACH 2 TAGEN (2026-08-17): DIE SCHLEIFE FUNKTIONIERT. Versionskette basis → AUSLESE v1
> (+6,1±1,5, 2x99k repliziert) → AUSLESE v3 (~+9 kumulativ; 15pp-Marge; 3 Direktlaeufe gepoolt +3,9±0,95
> vs v1 + 183k-Anker +8,68±1,28 vs Basis).** Kern-Doktrin GEMESSEN (3x + Brown 2026 Theorie): SELEKTION
> schlaegt Frequenz/Anpassung — welche Haende, nie wie oft. Abgelehnt (Replikations-Pflicht!): v2/sel_all,
> einmal_guard, mdf/podds/lizenz_guard. Mess-Lektionen (bindend): kein Name ohne 3 Laeufe (2x verfruehte
> Taufe verhindert); per-Deck-Edges sind FETTRANDIG → 2SE-Intervalle zu optimistisch (robuste SE = offenes
> Paket); leiser Kanal (Kandidat vs Kandidat) >> lauter (vs Basis); Kanal VOR dem Bau vermessen (AP8);
> ungeseedete MC bricht Paarungen; eine Worker-Flotte zur Zeit (RAM). Werkzeuge: pargate (--incumbent,
> Thread-Pin, ETA), exploit_jagd (20 persistente Jaeger; Haertungs-Landkarte VPIP 0,76/FtB 0,30/Agg 0,32),
> snowie_export (Gate-Paritaet!), verify_refs (66/66), Advisor-Batch (2,2x), runde4-Kampagnen-Muster,
> data/runs/+STAND.md. 6-max-Katalog v0 (30k Haende): Flop-Overfold ist HU-SPEZIFISCH (6max foldet 0,216
> bei erlaubt 0,30). Papers verankert: Brown (27 Bluffs strukturell, Band 0,36-0,50) + SPIRAL-RAE
> (Reward-Design fuer kuenftiges RL). Detail: docs/AUTOGYM_PLAN.md + EXPLOIT_KATALOG.md + Journal.
> **VERSIONIERUNGS-REGEL (User, 2026-08-16, bindend): VOR jeder Bot-Veraenderung wird der Stand
> eingefroren (git-Tag; aktuelle Basis = Tag `autogym-basis`); ein veraenderter Bot bekommt am ENDE einen
> NAMEN und wird als Tag versioniert. MESS-DOKTRIN: NICHT vs GTOW messen — die drei Instrumente sind
> (1) die Mathematik-Benchmark (Orakel), (2) Self-Play-Gates (gepaarte Decks), (3) der gepaarte
> A/B-Anker NEUER BOT vs ALTE BASIS (`duplicate_ab` auf identischen Decks). GTOW nur zur Not.**

## Grenze — was NICHT in dieses Repo gehoert (stehende Regel, 2026-08-16)
Der Kern ist **Pokerbot, Poker-Trainer, Poker-Verstaendnis** — sonst nichts. Alles andere (persoenliche
Akten, Beziehungs-/Chat-Analysen, Geopolitik, Zahlentheorie, Berichte ueber reale Personen) liegt im
Root unter **`_privat/`**: gitignored, durch einen lokalen `pre-commit`-Hook blockiert, nie gepusht.
Beschreibung dort in `_privat/LIESMICH.md`. **Nichts daraus wird versioniert, auch nicht mit `git add -f`.**
Wenn aus einer solchen Arbeit ein echter Poker-Befund faellt, wandert er ENTPERSONALISIERT in den Kern
(so geschehen: das 66-bb/100-Abflachen in `docs/POKER_NUTSHELL.md`, der Entropie-Bias in `NOTES.md`) —
die Rohdaten und die Person bleiben draussen.

## Run / play
- **6-max vs 5 bots (the app):** `python -m pokerbot.web.six_server --open` → http://127.0.0.1:8000 (launcher
  `PokerB 6max spielen.bat`). Logs each hand to `data/sessions/`; "Analyse" = end-of-session breakdown.
  Multiway: `http://127.0.0.1:8000?players=9` (2–10 Sitze). Turnier-Arena (Sim): `python -m pokerbot.arena.tourney`.
- **PokerSnowie automatisch spielen:** PokerSnowie 4 öffnen (Cash-Tisch) → `python -m pokerbot.vision.snowie_bridge
  --hands 20 --loose`; Langläufe über `python -m research.snowie_marathon --hands 2000` (ESC beendet ALLES).
- HU app (background/validation only now): `python -m pokerbot.web.server --open`.
- Always run from the project root as `python -m <module>`. Windows / PowerShell, Python 3.12. `pip install -r requirements.txt`.

## Architecture (logical; the live tree is [`INDEX.md`](INDEX.md))
- `pokerbot/engine/` — cards, treys evaluator, MC equity (`equity.py`), the **N-player `table.py` = the 6-max RL
  ENVIRONMENT** (start_hand / legal_actions / act / obs_for / result, side pots), HU `game.py`.
- `pokerbot/strategy/` — the engine PRIMITIVES the brain calls: `preflop_blueprint.py`, `range_tracker.py`,
  `advisor.py` (solver-frequency MLPs), `opp_model.py` (Dirichlet exploit), `postflop.py` (sizing/texture), `bot.py`.
- `pokerbot/brain/` — **the LLM-brain interface (NEW):** `api.py` (typed engine-API = the DSL vocabulary),
  `format_spot.py` (canonical 6-max spot, PokerBench-aligned), `executor.py` (program-of-thought sandbox),
  `understanding.py` (**the consolidated strategic read** — SPR/position/pot-odds/MDF + texture + made-hand +
  measured GTO heuristics in one engine-computed frame, gated `POKERB_UNDERSTANDING`; lets the brain reason on
  UNSOLVED spots), `claude_brain.py` (Claude-as-brain), `policy.py` (the shared SYSTEM_PROMPT + DSL).
- `pokerbot/arena/` — `sixmax.py` (the opponent LEAGUE: TAG/LAG/nit/station/maniac profiles).
- `pokerbot/{web,benchmark,coach,analysis}/` — apps; benchmarks (`slumbot.py`, `gtowizard.py`, `lbr.py`,
  `duplicate.py`); coaching; session analysis. Trainer-Multiway: `six_server` + `six.html` bis 10-max (`?players=9`).
- `pokerbot/vision/` — **die PokerSnowie-Brücke (NEU 2026-08-04):** `snowie_local.py` (Karten/Glyphen,
  Template-Matching mit Margin-Regel), `snowie_state.py` (kompletter Tisch-Zustand, Zweitquellen-Pot,
  Gatter-Kette), `snowie_bridge.py` (Spielschleife, Prince-HU postflop, ActionLog, Wächter). Regressionsnetz
  `research/snowie_regress.py` (konservierte Tatorte), Marathon `research/snowie_marathon.py`.
- **Turnier (NEU 2026-08-04):** `pokerbot/strategy/icm.py` (exaktes Malmuth-Harville + bubble_factor +
  icm_call_threshold), `pokerbot/strategy/tournament.py` (Structure/Director/anteiliges Risiko-Premium/
  Druck-Hebel), `pokerbot/arena/tourney.py` (gepaarte SNG-Arena). Doktrin: `knowledge_base/tournament/DOKTRIN.md`.
- `dataset/` — **the GOLD (NEW):** `build/` (KB→DSL JSONL converters) + the self-growing dataset shards + **`registry.py`**
  = the single source of truth for ALL data (every asset's role/schema/provenance; the training pipeline reads gold by
  ROLE via `registry.sft_gold()`) → **[`CATALOG.md`](CATALOG.md)** the generated data map (`python -m dataset.build_manifest`).
- `training/` — **Qwen (NEW):** `qwen_sft.py` (SFT, Qwen3-8B QLoRA on the DSL data), `qwen_grpo.py` (RL self-play),
  `qwen_eval.py` (PokerBench-acc + bb/100 + LBR).
- `pipeline/` — **the PC-hub program (NEW):** `frontier_loop.py` (gated active distillation), `filter.py` (the
  deterministic EV-truth/relevance filter), `monitor.py`, `orchestrate.py` (scp to/from the pod).
- `research/` — the one-off mining/consult/solve scripts (the historical `extraction/`; reusable: `llm.py` = the
  OpenAI/Claude call helpers, `mass_solve.py`, `preflop_*`, `cfv_*`).
- `infra/` — `runpod_run.py` (pod lifecycle) + the pod campaign/setup.
- `knowledge_base/` — extracted theory = the dataset's SOURCE: `math/` (Mathematics of Poker → `formulas.py`),
  `concepts/`, `theory/` (CFR/Pluribus/Supremus/AGT), `exploit/` (11.5k directives), `ranges/`, `postflop/`,
  `hand_histories/` (10k Pluribus). **Hard-referenced by `config.py` + strategy — do not move without updating both.**
- `books/` — the 6 poker books (`poker/`: Mathematics of Poker, Beyond GTO, Exploitative Poker, Modern Poker Theory,
  NLHE Theory & Practice, Theory of Poker) + `papers/` (CFR, Pluribus, Supremus, the PokerBench-LLM + Nash-robustness PDFs).
- `docs/` (`STATE.md` entry point + `ROADMAP.md` forward plan + plans/consults) · `tests/` · `data/` (gitignored) · `models/` (`qwen_poker_ckpt500`) · `tools/` (TexasSolver + GTOW client).

## The common language (DSL) — see [`docs/DATASET_SPEC.md`](docs/DATASET_SPEC.md)
Math (`knowledge_base/math/formulas.py`) ↔ Code (the `brain/api.py` engine-API) ↔ Language (concepts/prompt). A
training example = a canonical spot → a **decision-program** (Python calling the API + brief NL) → the executed action.
Same `format_spot()` byte-identical across SFT / RL / inference / eval. Qwen-native (code), exact (math by code),
verifiable (run it → exact RL reward).

## Config / keys
- `pokerbot/config.py`: paths, models, API keys read from `C:\Users\hampe\Desktop\Secret keys\` (Claude+OpenAI under
  `AI\`, RunPod) with env-var override — **never hardcode keys**. The OpenAI/Claude call helpers live in
  `research/llm.py` (`ask_openai`/`ask_claude`/`claude_json`/`openai_json`).
- Models: Claude `claude-opus-4-8`; OpenAI auto-resolves (`OPENAI_MODEL_PREFERENCE`, gpt-5.1/gpt-5.5/o3). Base LLM = **Qwen3-8B**.

## Conventions / gotchas
- Cards are 2-char strings (`'As'`, `'Td'`) — treys-compatible. `bb = 100` chips; UIs show bb.
- `six_server.index()` reads `six.html` fresh per request; other servers cache HTML at import → restart for UI edits.
- A backgrounded server killed via TaskStop can hold its port: `Get-NetTCPConnection -LocalPort <p>` → `Stop-Process -Id <pid> -Force`.
- Verify UIs via `fastapi.testclient.TestClient`, not the (hanging) screenshot tool.

## Heavy compute / pod (RunPod)
- `infra/runpod_run.py` provisions/kills a GPU pod. **ALWAYS `--kill` when done** (`DELETE /pods/{id}` = full
  terminate; a "stop" still bills storage). Verify `--status` = no tracked pods.
- **Prefer H100/H200 for Qwen.** B200 = Blackwell sm_100: training kernels are immature (torch SDPA math-fallback,
  ~10× slower observed) → only with `pip install -U torch --index-url …/cu128` AND verified `+cu128` throughput.
- **CPU and GPU heavy jobs do NOT coexist on one box** (mass-solve starves the GPU trainer + saturates sshd). The
  GPU job runs on the pod, the CPU mass-solve LOCALLY (the 2-node split). SSH key `C:\Users\hampe\.ssh\pokerb_runpod`.
- Data moves PC↔pod via a single **scp tarball** (`pokerbot/`+`research/`+`dataset/`) + scp results back; the campaign
  pattern is self-killing (`atexit`+`finally`).

## History (superseded — context only; the live state is STATE.md)
The project was a HU exploit-primary engine measured **−72 bb/100 vs GTO Wizard** (87% preflop; AIVAT n=2498); the
solver-imitation floor + the fcpa policy net (−212) showed the imitation ceiling; a near-Nash preflop blueprint +
range-tracker keystone + a solver-grafted-preflop pass were built (grounded but flat in bb/100 vs near-GTO). Those
are now **background/validation** — the goal pivoted to the 6-max GTO-achieving Qwen brain above.

## Tests
`python -m tests.test_game` · `python -m tests.test_table` · `python -m tests.test_bot` · `python -m tests.test_range_tracker`
· `python -m tests.test_icm` · `python -m tests.test_tournament` · Snowie-Vision: `python -m research.snowie_regress --run`
