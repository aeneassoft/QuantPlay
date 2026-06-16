"""4-API focused consult on the P0 range-tracker — the linchpin blocking the GTO resolver path.
NOT 'how to GTO' (decided: resolver). The genuinely-open sub-problem the MVP2 plan glosses:
how to build a defensible Bayesian range update when the blueprint only outputs P(bet)."""
import sys, time, requests
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"C:\Users\hampe\Desktop\PokerB\docs")
KEYS = Path(r"C:\Users\hampe\Desktop\Secret keys\AI")
VENICE = (KEYS / "Venice.ai - API key.txt").read_text(encoding="utf-8").strip()
OPENAI = (KEYS / "OpenAI - API key - Goldbach.txt").read_text(encoding="utf-8").strip()
PPLX = (KEYS / "Perplexity API key.txt").read_text(encoding="utf-8").strip()
ANTHROPIC = (KEYS / "Claude API key.txt").read_text(encoding="utf-8").strip()

CONTEXT = """POKER BOT — HU NLHE. The GTO direction is ALREADY DECIDED (gpt-5.5 + o3 consults, vetted):
the -160 bb/100 vs TexasSolver is ABSTRACTION error; the fix is a HYBRID = supervised blueprint +
targeted real-time subgame RESOLVING (TexasSolver, river/turn to terminal, no value net) driven by a
RANGE TRACKER. River-first. This is NOT in question.

THE BLOCKER (P0, the linchpin): the range tracker. It must reconstruct BOTH players' ranges at the
actual public node so the resolver solves the real public STATE. The plan: range_next(h) ∝
range_prev(h) · policy(action | state, h). Current code is a STUB (preflop class-sets only, no
postflop narrowing). The plan itself warns: 'a bad range reconstruction makes the resolver WORSE
than the floor.'

THE EXISTING MATERIAL I must build on:
- Preflop ranges: class-sets (sb_open / bb_defend / top-X% by raise count). Reasonable prior.
- Blueprint = a trained MLP advisor that outputs ONLY P(bet) (bet-vs-check) per hand, per street
  (flop/turn/river), per role (IP/OOP). It does NOT output: a full action distribution, anything
  for facing-bet defense (call/fold/raise), or anything for bet-SIZE selection.
- TexasSolver v0.2.0 (range strings support per-class and per-combo weights like 'AsKh:0.62').
- equity (MC/exact), board-class, blocker features all exist.
- The resolver reads OUR hand's strategy at the solved node and samples; floor-fallback on timeout."""

Q = """THE FIVE HARD QUESTIONS (the plan glosses these — they decide if P0 is sound or garbage):

(1) INCOMPLETE-BLUEPRINT UPDATE. The blueprint only gives P(bet). For a bet/check node the Bayes
update is clean: bet -> weight *= P(bet|h); check -> weight *= (1-P(bet|h)). But for the actions the
blueprint is SILENT on — facing-bet defense (call/fold/raise) and bet-SIZE — what policy do I use for
the range update so the resolver's input ranges aren't garbage? Concretely: when villain CALLS my bet,
how do I narrow their range without a call-policy? When villain BETS a specific SIZE, how do I update?
Give a defensible, implementable rule for each silent action type.

(2) PER-COMBO WEIGHTED RANGES into TexasSolver. Is feeding 1326 per-combo weighted combos
('AsKh:0.62,...') sound, or should I aggregate to class-level average weights? Any
fidelity/format/solve-stability concerns? Which is the right call for v1?

(3) OWN-RANGE vs VILLAIN-RANGE fidelity. The resolver reads OUR hand's strategy at the node. The
solve needs BOTH ranges. How much does OUR-OWN range reconstruction fidelity actually matter for the
quality of the action it returns FOR US, vs the villain-range fidelity? Where should I spend the
fidelity budget?

(4) VALIDATION WITHOUT GROUND TRUTH. There is no labeled 'true range at this node.' Beyond
(sum->1, shrinks down a betting line, excludes dead/board cards), what are real self-consistency or
cross-checks? Is there a solver-based or equity-based test that catches a BAD tracker before it
silently makes the resolver worse? How would YOU prove the tracker is trustworthy?

(5) THE SAFE MINIMUM-VIABLE TRACKER. The plan warns a bad tracker is worse than the floor. What is
the SIMPLEST range tracker that is SAFE (provably/robustly not worse than the floor) even if crude —
and should the resolver be GATED on a range-confidence measure (fall back to floor when the
reconstruction is too uncertain)? What measure?"""

PROMPT_PPLX = CONTEXT + "\n\n" + Q + """

YOU = literature/practice. How do the ACTUAL strong HU-NLHE systems (Pluribus, DeepStack, Slumbot,
Supremus, modern GTO solvers / GTO Wizard AI) reconstruct ranges for real-time resolving? Cite the
concrete mechanism each uses (gadget game, range-gadget, Bayesian update via blueprint, CFV nets).
Map their mechanism onto my P(bet)-only-blueprint constraint. Concrete, cited. 900-1400 words."""

PROMPT_O3 = CONTEXT + "\n\n" + Q + """

YOU = theory (you gave the CFR decomposition that diagnosed this). Answer the 5 questions with CFR/
game-theory rigor. Especially: for (1), is a crude/uniform policy for the silent actions provably
acceptable (bounded extra exploitability) or does it poison the resolve? For (3), formalize how
own-range error vs villain-range error propagates to the action EV the resolver returns. For (5),
give a concrete gate. Be honest where a crude tracker is NOT safe. 1200-1800 words."""

PROMPT_CLAUDE = CONTEXT + "\n\n" + Q + """

YOU = implementation. Give the CONCRETE algorithm for a v2 range tracker I can code today on top of
the existing P(bet) advisor: data structure (per-combo weight dict), the street-by-street walk, the
exact update rule per action type (bet/check via advisor; call/fold/raise and sizes via your
recommended fallback), dead-card handling, normalization, and the emitted TexasSolver weighted-range
string. Then: the unit tests that gate P0, and the resolver-side confidence gate. Flag every place a
shortcut introduces a real risk. Pseudocode/Python welcome. 1400-2000 words."""

PROMPT_VENICE = CONTEXT + "\n\n" + Q + """

YOU = RED TEAM. Be brutal. Where is this whole P0-range-tracker plan self-deception? Three sharp risks:
(a) is a Bayesian tracker driven by a P(bet)-only blueprint going to be SO crude that the resolver it
feeds is just an expensive way to reproduce the floor's errors? (b) is the team about to spend days on
a tracker when the honest move is something else? (c) what is the ONE thing that, if it's true, makes
this entire P0 effort a waste — and how would they detect it cheaply BEFORE building? No hedging.
600-1000 words."""

def venice(p):
    t=time.time(); r=requests.post("https://api.venice.ai/api/v1/chat/completions",
        headers={"Authorization":f"Bearer {VENICE}","Content-Type":"application/json"},
        json={"model":"venice-uncensored","messages":[{"role":"user","content":p}],
              "temperature":0.8,"max_tokens":4000},timeout=360); r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time()-t

def pplx(p):
    t=time.time(); r=requests.post("https://api.perplexity.ai/chat/completions",
        headers={"Authorization":f"Bearer {PPLX}","Content-Type":"application/json"},
        json={"model":"sonar-pro","messages":[{"role":"user","content":p}],"max_tokens":3500},
        timeout=300); r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], time.time()-t

def o3(p):
    t=time.time(); from openai import OpenAI
    c=OpenAI(api_key=OPENAI)
    r=c.chat.completions.create(model="o3",messages=[{"role":"user","content":p}],
        max_completion_tokens=14000,reasoning_effort="high")
    return r.choices[0].message.content, time.time()-t

def claude(p):
    t=time.time(); import anthropic
    c=anthropic.Anthropic(api_key=ANTHROPIC)
    r=c.messages.create(model="claude-sonnet-4-5",max_tokens=8000,
        messages=[{"role":"user","content":p}])
    return r.content[0].text, time.time()-t

JOBS=[("1","perplexity",pplx,PROMPT_PPLX),("2","o3",o3,PROMPT_O3),
      ("3","claude",claude,PROMPT_CLAUDE),("4","venice",venice,PROMPT_VENICE)]

def run(idx,tag,fn,p,ts):
    try:
        txt,el=fn(p)
        (OUT/f"range_tracker_consult_{tag}.md").write_text(
            f"# {idx}_{tag} — range-tracker P0 consult\n\nElapsed: {el:.1f}s\n\n---\n\n{txt}\n",encoding="utf-8")
        return idx,tag,el,len(txt),txt,None
    except Exception as e:
        return idx,tag,0,0,"",repr(e)

def main():
    ts=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    print(f"Firing {len(JOBS)} APIs on the P0 range-tracker sub-problem at {ts}...\n",flush=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs=[ex.submit(run,*j,ts) for j in JOBS]; res=[]
        for f in as_completed(futs):
            r=f.result(); res.append(r)
            print(f"  [{r[0]}_{r[1]}] {r[2]:.1f}s ({r[3]} chars) {'ERR: '+r[5] if r[5] else 'OK'}",flush=True)
    res.sort(key=lambda x:x[0])
    print("\n"+"="*70+"\nALL RESPONSES\n"+"="*70)
    for idx,tag,el,ln,txt,err in res:
        print(f"\n\n{'#'*70}\n# {idx}_{tag} ({el:.1f}s)\n{'#'*70}\n"); print(err if err else txt)

if __name__=="__main__":
    main()
