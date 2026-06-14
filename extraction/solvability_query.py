"""Ask OpenAI (gpt-5.1) to reason — rigorously AND creatively (ML/CS) — about how close we can get to
mathematically SOLVING 6-max NLHE, and what a proof of solvability would require. Output is saved + later
hand-vetted (the underlying theory is well-established: CFR, PPAD-hardness, CCE, Pluribus).

Run:  python -m extraction.solvability_query
"""
from __future__ import annotations

from openai import OpenAI

from pokerbot import config

SYSTEM = (
    "You are simultaneously a game theorist, a theoretical computer scientist (complexity, equilibrium "
    "computation), and a machine-learning researcher (CFR, deep RL, self-play). Reason RIGOROUSLY with real "
    "theory, but also CREATIVELY across ML/CS. Be honest and precise; do NOT overclaim. Distinguish carefully "
    "between 'superhuman' and 'solved', and between heads-up (2p zero-sum) and 6-max (multiplayer general-sum)."
)

USER = (
    "Question: How close can we realistically get to mathematically SOLVING 6-max No-Limit Hold'em — i.e., "
    "computing or provably approximating an equilibrium with bounded exploitability — and what would a proof "
    "that it is 'solvable' actually require?\n\n"
    "Please cover, concretely and honestly:\n"
    "1. THE LANDSCAPE. Why 2-player zero-sum NLHE is solvable to epsilon (minimax/LP duality; CFR/MCCFR "
    "converges to a Nash eq; exploitability is a clean, measurable scalar), and why 6-player is fundamentally "
    "harder: general-sum + multiplayer => computing a Nash equilibrium is PPAD-hard, Nash is non-unique and "
    "non-interchangeable, and CFR has NO convergence-to-Nash guarantee beyond 2p zero-sum. Be precise about "
    "what breaks.\n"
    "2. WHAT 'SOLVED' SHOULD EVEN MEAN here. Is the right target an epsilon-Nash, a specific equilibrium, a "
    "coarse-correlated equilibrium (CCE), or a bounded-exploitability blueprint? Why CCE / no-regret targets "
    "are far more tractable than Nash in the multiplayer setting, and what guarantees no-regret dynamics DO "
    "give (Hannan/CCE convergence) vs. don't.\n"
    "3. CREATIVE ML/CS PATHS to get closer: abstraction + MCCFR (Pluribus = superhuman, NOT solved, via "
    "blueprint + depth-limited subgame re-solving); Deep-CFR and function approximation (and their lack of "
    "guarantees); last-iterate vs average-iterate convergence; population/team play; exploitability "
    "lower-bounds via LBR; magnetic/optimistic regret dynamics; any recent theory you know that tightens "
    "multiplayer guarantees. Rank them by promise.\n"
    "4. AN HONEST VERDICT. In what precise sense is 6-max NLHE 'solvable' or not, what is the strongest "
    "provable statement we could realistically aim for (e.g. 'a profile with measured exploitability <= X "
    "bb/100 against a best-response oracle'), and the single most promising direction to PROVE we can "
    "approximate it. Flag clearly anything that is open/unknown.\n\n"
    "Cite the real concepts (CFR/CFR+, MCCFR, PPAD/Nash hardness, CCE, no-regret, Pluribus, LBR). "
    "Prefer correctness over optimism."
)


def _client_and_model():
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    # resolve to the best available model from the preference list
    try:
        ids = {m.id for m in client.models.list().data}
    except Exception:  # noqa: BLE001
        ids = set()
    for m in (([config.OPENAI_MODEL] if config.OPENAI_MODEL else []) + config.OPENAI_MODEL_PREFERENCE):
        if m and (not ids or m in ids):
            return client, m
    return client, "gpt-4o"


def main() -> None:
    client, model = _client_and_model()
    print(f"querying {model} ...", flush=True)
    try:
        r = client.chat.completions.create(
            model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
            max_completion_tokens=6000)
        text = r.choices[0].message.content
    except Exception as e:  # noqa: BLE001 — some reasoning models reject params; retry minimal
        print(f"(retry minimal: {type(e).__name__})", flush=True)
        r = client.chat.completions.create(
            model=model, messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}])
        text = r.choices[0].message.content

    out = config.DATA_DIR / "sessions" / "solvability_6max.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# 6-max NLHE solvability — {model}\n\n{text}\n", encoding="utf-8")
    print(f"\n===== {model} =====\n{text}\n\nSaved -> {out}")


if __name__ == "__main__":
    main()
