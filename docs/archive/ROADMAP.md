# PokerB Roadmap — Tournament-grade hybrid (GTO + Exploit + Adaptive)

**North star:** a bot whose **GTO is solid** (holds up vs world-class / near-GTO play, doesn't get
exploited) AND that **exploits the field** when it safely can — with a **robust adaptive regime
switch** deciding which mode to use — validated up to **winning real (tournament) play**.

Status legend:  ⬜ todo · 🔧 in progress · ✅ done

---

## Phase 1 — Position-aware GTO baseline  (fixes the loose VPIP-0.75 baseline)
Our −207 vs Slumbot came from a loose, self-exploitable baseline. Replace it with a real near-GTO one.
- ⬜ 1.1 Postflop GTO core from **Bill Chen / Mathematics of Poker**: bluff freq `α=s/(1+s)`,
  defense `MDF=P/(P+B)`, [0,1]-toy-game equity thresholds (value / bluff / bluff-catch) → balanced
  by construction, no solver needed.
- ⬜ 1.2 **Position-aware preflop**: per-position GTO ranges (BTN/CO/HJ/MP/UTG/SB/BB) grounded in
  *Modern Poker Theory* (Acevedo) + our verified CFR push/fold for short stacks.
- ⬜ 1.3 Wire it in as the engine's new **baseline** (`strategy/gto_baseline.py`), replacing the loose play.
- **Success:** VPIP/PFR fall into GTO-sane ranges; re-test vs Slumbot moves from −207 toward break-even.
  → ✅ **DONE:** `strategy/gto_baseline.py` (Chen α/MDF + anti-spew + position-aware preflop) **halved
  the loss: −207 → −99.6 bb/100 (±113 stderr, 350 hands) vs Slumbot.** Less self-exploitable, but
  analytic ceiling — not true GTO yet → motivates Phase 5 (neural Deep CFR). (Tighter number needs
  AIVAT / more hands.)

## Phase 2 — Adaptive regime detector  (the GTO↔Exploit switch must "sit")
- ⬜ 2.1 `σ_final = (1−λ)·σ_GTO + λ·σ_exploit` with a **hard exploitability-budget cap** on λ.
- ⬜ 2.2 λ per leak via **z-score significance** (Chen variance — only deviate when `|z|>2`, ~95%) +
  the **safe-exploit rule** `Δv_LB > 2·ε̃` (exploit only if the confidence-bounded gain beats 2× the
  extra exploitability).
- ⬜ 2.3 **Anti-strong-opponent self-check**: force λ=0 vs balanced play / when our exploits lose EV.
- **Success:** vs Slumbot λ→0 (GTO, break-even); vs the field λ→high (crushes); 200/200 unknowns held.

## Phase 3 — Re-validate & benchmark  (prove BOTH modes)
- ⬜ 3.1 **Slumbot live** (free, card-aware) with the new baseline.
- ✅ 3.2 **GTO oracle via TexasSolver** (local OSS SOTA solver — no API key needed). `strategy/gto_oracle.py`
  drives the bundled `console_solver.exe`, parses GTO frequencies per hand; `benchmark/gto_check.py` scores
  our baseline against it. Replaces the unavailable GTO Wizard key (CPU-bound, ms per solve).
  **First finding:** `gto_baseline` **over-donks OOP** — bets ~50% of flops as the preflop caller where GTO
  bets ~14% (51% agreement; K72r/882r GTO=0% donk). It's not preflop-aggressor/range-advantage aware →
  a concrete, fixable, self-exploitable leak (likely a big chunk of the −100 bb/100 vs Slumbot).
- ⬜ 3.3 **Weaponize, now POSITION-AWARE** vs opponents calibrated to real data (Pluribus/pros/online).
- **Success:** ≥ break-even vs near-GTO (Slumbot / GTO Wizard); still big +bb/100 vs the field.

## Phase 4 — Tournament module + placement  (the "win a real tournament" goal)
- ⬜ 4.1 Add **ICM + escalating blind levels + variable stacks + elimination** to the N-player engine
  (we have the side-pot table + an ICM hook).
- ⬜ 4.2 **Simulate a tournament**: our bot vs a field **calibrated to real data** → placement
  distribution, ITM%, ROI. (Honest: we have the WSOP-2023 *final-table* 83 hands for opponent
  calibration, not a full WSOP field — so we simulate a calibrated field.)
- **Success:** our bot finishes top-X / positive ROI across many simulated tournaments.

## Phase 5 — Final GTO engine: NLHE Deep CFR on a fast pod
- ⬜ 5.1 OpenSpiel Deep CFR on **abstracted NLHE** (universal_poker, fcpa sizes), warm-started from book
  ranges, on a **faster GPU pod** (cost-capped + auto-kill). Pipeline already proven on Leduc.
- ⬜ 5.2 Replace the Phase-1 analytic baseline with the **learned near-GTO net** where it's stronger.
- **Success:** lower measured exploitability; Slumbot / GTO Wizard results improve further.

---

**Dependencies:** ~~GTO Wizard API key~~ (dropped — no key; verify GTO via OpenSpiel exploitability +
TexasSolver oracle + Slumbot + Pluribus-alignment + internal frequency-check). Fast GPU pod (Phase 5).
**Order:** 1 → 2 → 3 → 4 → 5 (each validated before the next). Position-awareness threads through 1 & 3.

### Insights folded in (GTO Wizard benchmark paper arXiv 2603.23660 + their roadmap)
- **Yardstick:** GTO Wizard beats Slumbot by ~19.4 bb/100 → if we reach break-even vs Slumbot we're
  ~19 bb/100 from SOTA. Beating Slumbot is the concrete near-term target.
- **Adopt AIVAT** (variance reduction, ~10× fewer hands for significance) in our Slumbot benchmark
  (Phase 3) — our ±151 stderr/400 hands shrinks dramatically.
- **Pre-empt their roadmap:** GTO Wizard is HU-only; multiway, PLO and *skill-adaptive* solutions are
  "coming". Our edge is exactly there → prioritise **multiway/6-max + tournaments (Phase 4) + adaptive
  exploitation**. Their move toward skill-adaptive solving concedes that pure GTO isn't enough — it
  validates our GTO+exploit hybrid.
- LLMs (GPT-5.4/Opus 4.6/Gemini 3.1/Grok 4) all lose to GTO Wizard → confirms a specialised net (Deep
  CFR), not an LLM, is the right core.
