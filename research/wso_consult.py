"""Have GPT-5.5 + o3 translate the War Strategy Optimization (WSO) algorithm to poker (user request, 2026-06-16).
WSO is a war-themed metaheuristic GLOBAL OPTIMIZER (attack/defense soldier movement, King+Commander guidance,
weight-update + rank, weak-soldier relocation). HONEST framing baked into the prompt: it is a numerical optimizer,
NOT a game/Nash solver — so we ask for (a) what it actually is, (b) RIGOROUS uses as a black-box optimizer in our
exploit-primary bot, (c) the war-metaphor mapping, (d) what does NOT transfer. Clean boundary: the output = design
ideas to VET, never gospel/training-label. Saves docs/wso_poker_gpt55.md + docs/wso_poker_o3.md.
Run: python -m extraction.wso_consult
"""
from research.nash_consult import ask_openai

WSO = open("data/wso_text.txt", encoding="utf-8").read()[:60000]

SYS = ("You are an expert in BOTH metaheuristic optimization AND imperfect-information game AI (poker: CFR, "
       "depth-limited solving, opponent modeling, safe exploitation). Be rigorous and HONEST. Cleanly SEPARATE "
       "(1) defensible/rigorous claims from (2) metaphorical/speculative inspiration. Do NOT fabricate or over-claim "
       "— if WSO does not transfer to something, say so plainly. The reader runs an exploit-primary HU/6-max "
       "No-Limit Hold'em bot: a near-Nash GTO FLOOR (CFR + a TexasSolver/CFV-net resolver) + an ADAPTIVE "
       "opponent-exploitation layer (a per-node Dirichlet opponent model, LCB-gated safe exploitation). Thesis: "
       "GTO = insurance/floor, the EDGE = exploiting each opponent's gap to GTO; poker as a theory-of-mind / "
       "military-strategy game, not a chess-style forward search.")

Q = ("Below is the War Strategy Optimization (WSO) paper text. TASK: translate its ALGORITHMS to poker, for THIS bot.\n\n"
     "1. WHAT WSO ACTUALLY IS (4-6 sentences): the attack vs defense position-update equations, the King (best) + "
     "Commander (2nd best) guidance, the weight-update + rank, the weak-soldier relocation; and its TYPE — is it a "
     "single-objective CONTINUOUS global optimizer (like PSO/GA), NOT a game/Nash/equilibrium solver? State it plainly.\n\n"
     "2. RIGOROUS / defensible uses as a BLACK-BOX OPTIMIZER in our bot. Be concrete about the OBJECTIVE and the "
     "DECISION VECTOR. Candidates: tuning the exploit-layer hyperparameters; bet-size grids; opponent-model priors / "
     "the LCB-gate threshold; a parametric strategy vector; optimizing realized bb/100 vs a fixed opponent model OR "
     "measured exploitability (LBR). Give a concrete recipe (decision vector, objective, eval) + the CATCH (the "
     "objective is STOCHASTIC/noisy — bb/100 has huge variance — how WSO must be adapted: re-sampling, common random "
     "numbers, surrogate, etc.).\n\n"
     "3. The WAR-METAPHOR mapping (attack vs defense; King=best response; Commander=2nd; weak-soldier relocation; "
     "weight by rank) onto poker STRATEGY concepts (aggression/defense lines, anchoring on the best line found, "
     "abandoning losing lines, reallocating frequency) — clearly LABELED as inspiration, not math.\n\n"
     "4. HONEST LIMITS: what does NOT transfer (imperfect information, opponent ADAPTATION/non-stationarity, "
     "Nash/equilibrium, the fact that a poker strategy lives on a SIMPLEX of mixed strategies / a huge game tree, not "
     "a low-dim continuous vector)? Where would naively applying WSO MISLEAD us or be strictly worse than CFR / our "
     "existing methods? Be blunt.\n\n"
     "Keep it under ~800 words, dense and concrete. Prefer 'here is the exact recipe' over generalities.\n\n"
     "=== WSO PAPER TEXT (first 14 pages, fitz-extracted; math symbols may be imperfect) ===\n" + WSO)

for model, fn in (("gpt-5.5", "wso_poker_gpt55.md"), ("o3", "wso_poker_o3.md")):
    print(f"=== {model} (WSO -> poker) ...", flush=True)
    txt = ask_openai(model, SYS, Q, effort="high", cap=22000)
    open(f"docs/{fn}", "w", encoding="utf-8").write(f"# WSO (War Strategy Optimization) -> poker ({model}, 2026-06-16)\n\n{txt}\n")
    print(f"  saved docs/{fn} ({len(txt)} chars)", flush=True)
print("WSO CONSULT DONE", flush=True)
