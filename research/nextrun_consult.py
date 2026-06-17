"""NEXT-RUN preparation consult — design + validate the CFV-net data-gen CALCULATION before scaling (the user's
"bereite den nächsten Run / die nächsten Calculations vor; nutze erstmal die APIs"). Grounded in the MEASURED pilot
result. Routing: RIGOROUS CFV/backward-induction math + sample-complexity -> o3 ; POKER-practical coverage + ROI ->
gpt-5.5 ; Claude VETS in-session (clean boundary: LLM output is DESIGN/VALIDATION, never a training label).
Run: python -m extraction.nextrun_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_POKER = "gpt-5.5"
O3 = "o3"

BRIEF = """OUR LIVE, MEASURED SITUATION (ground every answer here; be brutally honest, quantify, flag overkill):
- HU NLHE 200bb cash. Bot is ~−72 bb/100 vs GTO Wizard AI (AIVAT, n>=2500). An EV X-ray localized −72 to PREFLOP
  (87%); a near-Nash preflop blueprint was built+wired and moved it toward −53 (partial n). The REMAINING gap is
  POSTFLOP near-Nash. The chosen path = DeepStack-style continual re-solving with a learned COUNTERFACTUAL-VALUE
  (CFV) net (NOT a policy net — the strategy is RE-SOLVED, so it escapes the imitation ceiling that made an fcpa
  policy net −212).
- The CFV net must serve a FLOP depth-limited re-solve (flop->turn tree) by returning, at the TURN-boundary LEAF,
  per-hand counterfactual values for BOTH players assuming Nash continuation. Input we plan: 4-card turn board +
  both players' 169-class weighted ranges + pot/eff. Output: per-class CFV for OOP and IP (338 values).
- DATA-GEN (current): `turn_boundary_cfv` SOLVES ALL 48 RIVER RUN-OUTS SEPARATELY (each a river-only TexasSolver
  solve with pot fixed at the turn pot, ranges = the turn-boundary ranges), extracts per-combo river CFVs (a
  B1-validated backward EV pass), and AVERAGES per combo over the ~46 valid run-outs. Cost = 48 solves/sample =
  ~12-16 min/sample on an oversubscribed cloud CPU -> a multi-pod run produced ZERO samples (no sample finished in
  the window). We added a `k_rivers` knob (sample K of 48) for a pilot.
- PILOT RESULT (just measured, K=12, 123 local samples, 99 train / 24 held-out, target-standardized 392->338 MLP,
  512x3 ReLU): train_mse(normalized) -> 0.0000 (the net FITS the train set perfectly) but held-out MAE = 96% of the
  CFV scale (≈ predicting noise on unseen boards). DIAGNOSIS: architecture+features are SOUND; the SOLE blocker is
  DATA VOLUME (99 samples is ~1000x too few). CFV scale ≈ ±2600 chips (pots 20-60, eff 40-80 in bb=100 chips)."""

O3_SYSTEM = ("You are a rigorous game theorist + ML theorist (zero-sum extensive-form games, CFR, counterfactual "
             "values, backward induction, regression sample-complexity). Distinguish provable from heuristic. Serve "
             "THIS bot + the measured numbers. Give EXACT formulas/algorithms; flag any error in our current method.")

O3_Q = BRIEF + """

REASON RIGOROUSLY — these are the load-bearing CALCULATIONS for the next run:

A. WHAT CFV DOES THE FLOP->TURN RESOLVER ACTUALLY NEED AT ITS TURN-BOUNDARY LEAF? Formalize the counterfactual value
   v_i(h) for player i, hand h, at the FIRST turn node (before any turn betting), under a Nash continuation of the
   TURN betting round + the river. Write it as the standard CFR counterfactual value (counterfactual reach of the
   OPPONENT times expected utility of the subtree). Be explicit that this INCLUDES the turn betting round.

B. IS OUR CURRENT TARGET CORRECT OR AN APPROXIMATION? Our method solves each river SEPARATELY with the pot FIXED at
   the turn pot (no turn betting) and averages over the river card. Show formally that this computes E_river[ value
   at the START OF THE RIVER ] = the value assuming the TURN IS CHECKED THROUGH (no turn bets/raises), NOT the true
   turn-node CFV from (A). Characterize the error: on which turn nodes/boards is "turn-checked-through" a large vs
   negligible approximation? Is averaging 48 INDEPENDENT river solves even self-consistent (each river re-solved as
   its own game, not sharing one turn strategy)?

C. THE EFFICIENT + CORRECT CALCULATION (dump_rounds=2). If instead we solve the TURN subgame ONCE (TexasSolver dumps
   the turn AND river action probabilities for the subgame) and BACKWARD-INDUCT to the turn node, do we get the EXACT
   turn-node CFV of (A) in ONE solve? Specify the full backward induction: (i) river leaves — showdown via card
   eval + fold nodes; (ii) river-card chance averaging with correct CARD REMOVAL (combo h valid iff disjoint from
   board+opp combo); (iii) reach-weighting by the OPPONENT's range (counterfactual reach) through turn+river action
   probs; (iv) the zero-sum / range-EV self-checks that must hold. Note that one turn solve has ~10-100x fewer total
   solves than 48 independent river solves — confirm the correctness is NOT sacrificed for the speed.

D. SAMPLE COMPLEXITY + GENERALIZATION. We need a 338-output CFV regressor that GENERALIZES across (board, ranges,
   pot). The pilot fits 99 samples to 0 but held-out 96%. Estimate the ORDER of samples needed and, crucially, the
   sample-efficiency levers: (1) BOARD ISOMORPHISM / suit symmetry — how large is the reduction, and should we
   canonicalize boards as a feature so the net never re-learns suit-permutations? (2) range PARAMETERIZATION so the
   net interpolates over ranges rather than memorizing exact 169-vectors; (3) per-bucket/per-class output heads vs a
   flat 338; (4) regularization (dropout, weight decay) + a smaller net; (5) does predicting NORMALIZED-by-pot CFVs
   (scale-free) improve transfer across pot sizes? Give a concrete recommended config + a held-out gate that proves
   generalization (not just fit)."""

POKER_SYSTEM = ("You are the world's strongest applied NLHE solver/GTO engineer (DeepStack/Libratus-level) AND a "
                "brutally honest ROI analyst. Ground every claim in THIS bot + the measured numbers. Quantify bb/100; "
                "flag overkill and anything uncertain.")

POKER_Q = BRIEF + """

ANSWER CONCRETELY (engineering + ROI for the NEXT RUN):

1. COVERAGE FOR A USEFUL HU 200bb FLOP RESOLVER: which (flop texture x turn card x range-pair x pot/SPR) points must
   the CFV net cover to be useful, and roughly HOW MANY distinct training points is that? Our ranges should come from
   REAL preflop+flop lines (SRP/3BP/4BP, c-bet/check, call/raise), not uniform-random — specify the sampling that
   matches what a live range-tracker emits, so the net is accurate where it is actually queried.

2. BET ABSTRACTION for the turn+river solve in data-gen: what size menu (e.g. 33/66/100/150% + all-in) is the MINIMUM
   that makes the CFV faithful, vs overkill that explodes solve time? Tie to faithful big-pot values (our −72 lesson:
   a confident WRONG equilibrium in big pots is worse than folding).

3. ROI HONESTY: given 87% of our −72 was PREFLOP (now largely addressed) and postflop-non-jam was the SMALLEST X-ray
   term (~−10), what bb/100 can a good flop CFV-net realistically recover vs GTO Wizard? Is building the CFV net
   (Phase B, needs thousands of solves) HIGHER or LOWER ROI than first doing the $0 "range-tracker keystone" (make
   the EXISTING turn/river TexasSolver resolver sharp by feeding it correct line-narrowed ranges)? Recommend the
   order.

4. DEPLOY-SAFETY GATES: beyond held-out MAE, what checks prove the net is safe to put INTO the live resolver without
   making things worse (zero-sum, nut/air monotonicity, range-EV vs a direct solve on held-out boards, L1 vs the
   solver's true CFVs)? Give the specific go/no-go thresholds you would require before it touches a real decision."""


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 45000) -> str:
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
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:140]})", flush=True)
    return ""


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {O3} (rigorous: correct turn-boundary CFV calc + sample complexity) ...", flush=True)
    reason = ask_openai(O3, O3_SYSTEM, O3_Q)
    (out / "nextrun_calc_o3.md").write_text(f"# Next-run CFV calculation — rigorous ({O3})\n\n{reason}\n", encoding="utf-8")
    print(f"  saved docs/nextrun_calc_o3.md ({len(reason)} chars)", flush=True)
    print(f"=== {GPT_POKER} (poker-practical: coverage, abstraction, ROI, deploy gates) ...", flush=True)
    poker = ask_openai(GPT_POKER, POKER_SYSTEM, POKER_Q)
    (out / "nextrun_design_gpt55.md").write_text(f"# Next-run design — poker-practical ({GPT_POKER})\n\n{poker}\n", encoding="utf-8")
    print(f"  saved docs/nextrun_design_gpt55.md ({len(poker)} chars)", flush=True)
    print("DONE — Claude VETS both (clean boundary) + folds into the next-run plan + the corrected calculation.", flush=True)


if __name__ == "__main__":
    main()
