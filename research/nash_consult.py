"""Nash-equilibrium-in-poker consult, grounded in our LIVE situation: the X-ray localized the −72 vs GTO Wizard to
PREFLOP (−50 of −75; MIT 15.S50 says preflop is near-Nash-solvable + where most value is); we are building a
from-scratch self-play Deep CFR net; the Fable-5 audit warned that minimizing self-play regret (own exploitability)
is NOT the same as beating a specific opponent (GTO Wizard). Routing (user): POKER -> gpt-5.5 ; REASONING/theory ->
o3 ; Claude vets in-session. Run: python -m extraction.nash_consult
"""
from __future__ import annotations

from pokerbot import config

GPT_POKER = "gpt-5.5"
O3 = "o3"

BRIEF = """OUR LIVE SITUATION (ground every answer here; honest, measured):
- HU NLHE 200bb. Decision-grade: our bot is ~−72 bb/100 vs GTO Wizard AI (AIVAT, n>=2500). An EV-attribution X-ray of
  the per-hand log shows the −72 is DOMINATED by PREFLOP: preflop contributes −50 of −75 (76% of hands, ≈always-fold
  level); postflop non-jam is the SMALLEST term (~−10); a deep-stack preflop all-in spew is −15 (mean −385/−527 per
  hand on our preflop all-ins at 200bb).
- Our HU preflop is a crude strength-model (open top-84% at a fixed 2.5bb + crude BB-defense/3bet ranges), NOT a real
  Nash preflop. MIT 15.S50 L4: preflop is where most value is, it is near-Nash-solvable (few variables), players play
  it badly; HU push/fold Nash is stable at M<=2 but "unstable" (rock-paper-scissors cycling) at M>=3.
- We are building our OWN from-scratch neural Deep CFR SELF-PLAY net to learn GTO. The Fable-5 audit's sharp point:
  minimizing self-play regret (own exploitability) is NOT the same as MAXIMIZING bb/100 vs a SPECIFIC opponent
  (GTO Wizard AI). The floor already showed frequency-match != EV-match (paired oracle −160)."""

POKER_SYSTEM = ("You are the world's strongest No-Limit Hold'em GTO/Nash theorist AND a brutally honest analyst. "
                "Ground every claim in THIS situation. Quantify; flag overkill and anything you are not certain of.")

POKER_Q = BRIEF + """

ANSWER CONCRETELY (poker-practical):
1. Is HU 200bb PREFLOP cleanly solvable to Nash (open/3bet/4bet/5bet/call ranges + SIZES), or only approximately? How
   close is GTO Wizard's preflop to true Nash, and where do real Nash preflop strategies MIX / differ from a simple
   "open top-84% at 2.5bb" heuristic (limps, multiple open sizes, 3bet/4bet mixing, position)?
2. DEEP-STACK ALL-IN DISCIPLINE at 200bb: vs a near-GTO opponent, which hands/lines make getting ALL-IN PREFLOP +EV
   (the Nash 4bet/5bet/call-jam range), and how badly does a too-loose deep-stack stack-off bleed? (We measure
   −385/−527 AIVAT per hand on our preflop all-ins — is that consistent with "getting it in as a dog at 200bb"?)
3. For our SELF-PLAY net to learn preflop Nash, what BET-SIZE abstraction does preflop REQUIRE (opens ~2-3bb, 3bets
   ~3x, 4bets, jams)? Is fcpa (fold/call/POT/allin) hopeless for preflop, and what minimal size menu fixes it?
4. How much of HU 200bb EV is PREFLOP vs postflop at GTO, and would nailing preflop Nash get us MOST of the way to
   GTO-Wizard parity (i.e. is our −50-preflop the highest-ROI fix)?"""

O3_SYSTEM = ("You are a rigorous game theorist (zero-sum games, online learning, CFR, exploitability). Cite the ACTUAL "
             "theory; distinguish what is provable from heuristic. Serve THIS bot + the measured −72; flag fabrications.")

O3_Q = BRIEF + """

REASON RIGOROUSLY:
1. HU NLHE is 2-player zero-sum -> a Nash equilibrium EXISTS and equals the minimax game value; CFR/self-play average
   strategy converges to an epsilon-Nash. Formalize what "our self-play net reached low exploitability" GUARANTEES
   about its bb/100 vs a SPECIFIC opponent (GTO Wizard AI). The crux: a Nash strategy guarantees >= the game value vs
   ANY opponent but does NOT maximize vs a specific exploitable one. If GTOW is itself near-Nash, what is the true
   ceiling vs it, and what does "beating" a near-Nash opponent even mean (sign of the game value for HU over both
   positions)?
2. The MIT result: HU push/fold Nash is STABLE at M<=2, "unstable" (best-response cycling) at M>=3. Reconcile with
   "a Nash always exists in finite 2p0s games": is the instability about (a) no PURE-strategy Nash (so a MIXED Nash
   exists), or (b) fictitious-play / best-response iteration not converging while CFR still would? What does this
   imply for actually solving preflop?
3. EXPLOITABILITY vs EV-vs-opponent: rigorously, why does minimizing own exploitability (self-play regret) NOT
   maximize EV vs a fixed sub-optimal opponent? If the GOAL is to beat GTOW specifically, is the right objective a
   BEST-RESPONSE / exploitative one (not Nash)? Tie this to our −72 and the audit's frequency-match != EV-match
   finding. What is the correct training/eval objective given the goal?"""


def ask_openai(model: str, system: str, user: str, effort: str = "high", cap: int = 40000) -> str:
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
            print(f"  ({model} err {list(kw)}: {type(e).__name__}: {str(e)[:120]})", flush=True)
    return ""


def main() -> None:
    out = config.ROOT / "docs"
    out.mkdir(exist_ok=True)
    print(f"=== {GPT_POKER} (Nash in poker — practical) ...", flush=True)
    poker = ask_openai(GPT_POKER, POKER_SYSTEM, POKER_Q)
    (out / "nash_poker_gpt55.md").write_text(f"# Nash in poker — practical ({GPT_POKER})\n\n{poker}\n", encoding="utf-8")
    print(f"  saved docs/nash_poker_gpt55.md ({len(poker)} chars)", flush=True)
    print(f"=== {O3} (Nash theory / self-play vs beating an opponent) ...", flush=True)
    reason = ask_openai(O3, O3_SYSTEM, O3_Q)
    (out / "nash_reason_o3.md").write_text(f"# Nash theory ({O3})\n\n{reason}\n", encoding="utf-8")
    print(f"  saved docs/nash_reason_o3.md ({len(reason)} chars)", flush=True)
    print("DONE — Claude vets + folds into the preflop/Nash plan.", flush=True)


if __name__ == "__main__":
    main()
