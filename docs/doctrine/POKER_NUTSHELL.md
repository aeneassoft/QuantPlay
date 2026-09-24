# POKER IN A NUTSHELL — the fundamental line (user drawing, 2026-07-06)

> The essence from which the whole bot architecture follows. Not a metaphor — a diagnostic tool that
> predicts several MEASURED findings. Image: the user's hand sketch.

## The picture
Y axis = HAND STRENGTH. The naive line: bet proportionally to the hand ("honest" poker). The edge lies
in the WAVE around it — the deliberate deviation: OVERBET (above the line) / UNDERBET (below the line).

Two ANCHORS (computable, the circles):
- **Preflop** = "pure statistics + opponent matching" — pure computation (blueprint).
- **River = "The Bill"** — where the bill is settled; terminal, simple bet/check/bluff mechanics.
  Bankroll truth: more bluffing → higher variance → bankroll swings.

In between the WAVE = flop/turn = game theory (deviation from hand strength).

Two PURPOSES of the deviation (the V):
- **Fold equity** — bet more than the hand justifies → generate folds.
- **Induced confidence / extraction / milking** — bet less / trap → keep the opponent confident, milk him.

The DEEPEST point: **Seesaw (game theory) → always switching up over time → unpredictable + noise.**
Never stay in one mode; oscillate forever, otherwise you become readable.

## Why this IS the fundamental line — it explains our measurements
1. **Seesaw ⇒ the v8 live break.** PURIFY flattened the mixing (modal) → SLOWPLAY never fired → check range
   transparent → −20 to −58 live. "Stop rocking = become predictable" — exactly measured.
2. **The V ⇒ the value/bluff separation + polarization** (B/(P+B) = the weight per branch on the river).
3. **The anchors ⇒ the street doctrine** (preflop/river compute, flop/turn = wave, fold-equity job).
4. **"The Bill" ⇒ river primacy** (there the whole hand is settled).

## Consequence for the bot line (binding)
- The bot is a SEESAW, not a fixed point.
- Preflop/river: compute (hold the anchors).
- Flop/turn: GENERATE the wave — over/underbet for fold equity OR extraction, balanced AND temporally
  unpredictable (LINE_U seed, mixing, deception — NEVER flatten; that is the Purify live lesson as law).
- Balance is non-negotiable (seesaw), but the rocking ITSELF is the edge; against adaptive opponents
  the switching over time (Red Queen) becomes the exploit.
- Bankroll/variance = a deliberate axis (more bluffing = more variance). NOT yet formalized as an explicit
  dial — candidate: a variance/bankroll dial over the bluff frequency.

## OBFUSCATION / cryptographic unpredictability (User, 2026-07-06)
Papers: Suppes, "On an Example of Unpredictability in Human Behavior" (Philosophy of Science 31(2), 1964,
VERIFIED — genuine unpredictability of human behavior is achievable/valuable) + biorxiv
2025.11.16.688665 (403-blocked, UNCHECKED).
- **Core:** the seesaw needs TWO things — (a) balanced FREQUENCIES (game theory, non-negotiable) AND
  (b) unpredictable REALIZATION. Our mixing uses `random.Random` (Mersenne Twister, NOT
  cryptographic); an opponent who sees enough of our action stream could in principle predict future
  "random" choices. A CSPRNG (secrets/os.urandom) makes the realization unpredictable EVEN for an
  opponent who knows our strategy.
- **HONEST limit:** obfuscation ≠ balance. You cannot obfuscate away an UN-balanced range — GTOW &
  re-solvers exploit the RANGE, not the RNG sequence. So: second order ABOVE balance, relevant vs
  ADAPTIVE pattern recognizers (humans/adaptive bots), IRRELEVANT vs static GTOW (benchmark).
- **Determinism tension:** we seed the RNG DELIBERATELY for reproducibility (byte identity, deterministic
  measurement). A CSPRNG breaks that. Resolution = context split (like Purify): seeded for MEASURING/analyzing, CSPRNG
  for LIVE play vs humans. Low priority vs the river/range work; noted as a deception-layer upgrade.

## WAVE SUPERPOSITION (user drawing #2, 2026-07-06) — the measurable formalism
Thesis: bluffing + bet sizings = superimposed waves; superposition produces a total variance "bigger than
the sum". Mathematically exact: Var(X+Y) = Var(X)+Var(Y)+2·Cov(X,Y) → positive correlation = bigger than the sum.
**TWO AXES, opposite recipes (the actual unification):**
- **Within the hand (the line across streets): CONSTRUCTIVE interference wanted.** A coherent barrel
  plan (flop→turn→river as ONE wave) generates more fold equity than 3 independent bets = "bigger than the
  sum" as POWER. = our LINE_U / line coherence. Street waves in phase.
- **Across hands (the observed action stream): WHITE spectrum wanted.** The stream should look like noise
  → no adversary finds a frequency. = Obfuscation, now MEASURABLE via power spectral density /
  spectral flatness (Wiener entropy) / autocorrelation. Peaks = exploitable pattern; flat = unreadable.
One formalism that unites line coherence + obfuscation + polarization (the two amplitudes of the V) + seesaw.

**PROOF OF CONCEPT (2026-07-06, $0):** spectral analysis of our action stream (14,941 decisions):
lag-1 autocorr −0.34, spectral flatness 0.48 (far from white 1.0), largest peak 13.8× mean = REAL
structure → the instrument fires, the axis is real. CAVEAT: the raw stream is confounded by betting-round
mechanics; the PROPER instrument (research/strategy_spectrum.py, planned) isolates per spot type only the
real MIXING decisions. LIMIT: measures REALIZED predictability (vs ADAPTIVE observers) = the
deception/obfuscation track (vs humans), NOT the GTOW bb track (static, does not pattern-match our
stream). But it IS the rigorous form of "be a clean seesaw".

## FREQUENCY-BAND ARCHITECTURE — the real structural insight of the wave view (2026-07-06)
The strategy decomposes into three bands, each with its own mechanism/lever/measurement:
- **LOW (DC):** baseline, hand-strength-proportional. Blueprint + census tree. Nearly solved; TexasSolver's
  bet-menu ABSTRACTION lives here (bounded leak, partly closed via GTOW_TREE).
- **MID:** strategic wave (over/underbet for fold equity + extraction). Resolver deviations.
  RANGE-dependent = THE bb lever. Polarization (B/(P+B)) also lives here.
- **HIGH:** mixing/randomization (seesaw noise). Should be WHITE → CSPRNG vs adaptive opponents.

**★ THE CARRIER-WAVE INSIGHT (the mechanism behind "range quality multiplies everything"):** the range
is the CARRIER WAVE; the strategic mid-band wave is a FUNCTION of the range. Wrong range =
correct frequencies modulated onto the wrong carrier signal → the error corrupts the WHOLE wave, not
one decision. That is the spectral explanation of why range errors multiply every organ (OpenAI
confirmed 4×, here justified MECHANISTICALLY). → Range calibration cleans the carrier wave = at once the
largest bb lever AND the TexasSolver divergence fix (the same place).

## TEXASSOLVER DIVERGENCE vs GTOW — honest state (2026-07-06)
NOT cleanly measured (the 91.63 were a river-only confound; 2.2%/decision = good; version A mixes
abstraction + range error + raw GTO basis). Real divergence by construction, in order:
RANGE error (our leak, dominant → calibration) ≫ convergence (measurable via _exploitability_pct →
iterations up) > bet-menu abstraction (bounded → census menu, danger of over-enriching). Clean
measurement = the running river_coherence diagnostic score + the off-tree cross experiment. Honest ceiling: we
inherit TexasSolver's abstraction-limited exploitability, but ranges dominate.

## RANGE DETERMINATION: two axes + the EV refinement (User, 2026-07-06)
- **VPIP-based = VILLAIN'S range (EXPLOIT axis).** Population/stats prior = the DC fundamental of the
  opponent's range before the line updates it (our opp_model/Dirichlet). Useful vs HUMANS,
  ~0 vs GTOW (static). COMBINE, do not replace: prior → update per observed line (= the tracker).
- **Preflop portfolio + diverse postflop = OUR range (GTO axis, Brokos).** One "buys into" a
  hand portfolio that can run diverse lines postflop (value/bluff/protection/trap).
- **★ EV REFINEMENT (user formulation sharpened):** diversity DOES NOT RAISE the game-theoretic value
  (against GTO the game value is fixed). It buys: (1) EV PROTECTION (balance = unexploitable, no attack point),
  (2) EV REALIZATION (cash in equity better), (3) EV CAPTURE only vs WEAK opponents (the right line per
  opponent = exploit). Precisely: less exploitable + better realization, NOT higher game value.
- **★ WAVE CONNECTION:** the preflop range sets the BANDWIDTH of the postflop wave. Rich portfolio =
  wide bandwidth = the full over/under-bet wave (fold equity + extraction, the whole V) playable. Narrow
  portfolio = narrow bandwidth = predictable = exploitable. VPIP refines the OPPONENT'S carrier wave
  (exploit prior); the portfolio sets our OWN bandwidth (GTO construction).

- **★ MEASURED — FLATTENING COSTS 66 bb/100, AND IT COSTS IT AT EXTRACTION.** In a paired
  self-play experiment (80,000 hands, 100 bb deep, identical deals) a profile was played once
  rocking and once with flattened mixing: **−83.6 vs −149.6 bb/100**. The
  decisive additional finding is the decomposition: the opponent's continuation rate practically
  did NOT move (79.4% → 78.9%). The loss is therefore **not lost fold equity,
  but lost EXTRACTION** — a readable player is not folded to more often, he is
  paid off worse. That is the quantitative version of the seesaw doctrine above.
