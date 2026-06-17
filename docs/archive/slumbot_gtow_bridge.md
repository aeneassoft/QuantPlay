# GTOW-vs-Slumbot bridge consult (gpt-5.1, 2026-06-16)

Below I’ll separate what is actually *known/published* from *informed estimates*.

---

## 1. Published GTO Wizard / modern near‑Nash vs Slumbot results

**FACTS**

- As of my knowledge cutoff (Oct 2024), I am **not aware of any published head‑to‑head results in bb/100** of:
  - GTO Wizard AI vs Slumbot, or  
  - Supremus, ReBeL, Student-of-Games, Pluribus-HU, Libratus, DeepStack, etc. vs Slumbot.
- The main academic sources (DeepStack, Libratus, Pluribus, ReBeL, Student-of-Games) report:
  - Performance vs humans and/or ACPC fields.
  - No cross‑evaluation vs Slumbot is included in those papers or ACPC result summaries that I know of.

So I **do not have a published number + source** for any of those matchups.

---

## 2. Published exploitability / LBR for Slumbot

**FACTS**

- Exact exploitability for full‑scale HUNL strategies is not computable with current methods; only **approximate best response (LBR)** evaluations are used.
- ACPC organizers have published LBR-style exploitability numbers for some **competition bots**, but:
  - I do **not** know of a peer‑reviewed paper or official ACPC technical report that gives a clear LBR exploitability figure for **Slumbot specifically** (in either mbb/game or bb/100).
  - Slumbot’s author has publicly discussed implementation details and ACPC participation, but I have not seen a rigorous exploitability/LBR number attached to “Slumbot 2018” or the public web bot.

So: **no reliable published exploitability figure for Slumbot that I can cite.**

---

## 3. ESTIMATE – near‑Nash agent’s winrate vs Slumbot

What follows is *not* from data on Slumbot; it’s an informed range based on:

- Era and architecture (2012–2018 CFR-style bot with abstraction vs 2020s near‑Nash solvers).
- What we see in smaller games when going from “ACPC‑level abstraction bot” to “very low‑exploitability blueprint.”
- General knowledge that action + card abstraction in HUNL can leave **tens of bb/100** of exploitability on the table.

### Step 1: plausible full best‑response (BR) edge vs Slumbot

**ESTIMATE**

- A *true* unconstrained best response (perfect model of Slumbot, unabstracted response) could plausibly gain on the order of:

  **~30–150 bb/100** vs Slumbot at 200bb cap.

- Reasoning:
  - Abstracted HUNL strategies from that era are known to have significant systematic leaks (coarse bet‑trees, bucketed postflop, etc.).
  - Cross‑play between similar ACPC bots often shows only small edges, but that does *not* cap exploitability; in toy games, fairly “reasonable” CFR strategies can be 3–10× more exploitable than their edge vs peers would suggest.
  - 30 bb/100 is a conservative lower bound for a seriously exploitable but competition‑strong HUNL agent; 150 bb/100 is an aggressive but not absurd upper tail if abstractions are badly aligned at 200bb.

### Step 2: near‑Nash (GTO‑style) agent’s edge vs Slumbot

A near‑Nash “GTO Wizard–class” blueprint is *not* a tuned BR; it just plays an approximate equilibrium strategy.

**ESTIMATE**

- A strong near‑Nash agent (Libratus/ReBeL/Supremus/GTO‑Wizard‑like) **playing its default equilibrium strategy** vs Slumbot might realize roughly:

  **~10–40 bb/100**, with a central guess around **15–30 bb/100**.

- Intuition:
  - It cannot systematically contort its play to hit every Slumbot leak the way a dedicated BR would.
  - But its baseline equilibrium strategy tends to:
    - Defend correctly vs over‑/under‑aggression.
    - Choose better sizings and ranges than an older abstracted bot.
  - Empirically in other imperfect‑information domains, going from “ACPC‑quality” to “near‑Nash” often realizes on the order of **20–70% of full exploitability** when not actively exploiting. 10–40 bb/100 is consistent with that if true BR exploitability is somewhere in the 30–150 bb/100 band.

These are necessarily broad ranges; there is no direct measurement.

---

## 4. Is triangulation via Slumbot valid?

You’re asking: if

- Your **floor** (non‑exploitative bot) wins **X bb/100** vs Slumbot,  
- A near‑Nash bot (e.g., GTO Wizard AI) wins **Y bb/100** vs Slumbot (in principle),

can you infer your floor is about **(X − Y) bb/100** worse than GTO Wizard?

### Theoretical issues

**FACTS**

- HU NLHE is **non‑transitive** at the level of approximate strategies: A can beat B, B beat C, C beat A, even if all are “strong”.
- Exploitability only constrains edges vs **best response**; it doesn’t fix pairwise cross‑edges between two non‑Nash strategies.

### Practical assessment

**ESTIMATE**

- If:
  - both your bot and GTO‑Wizard‑class bots are *reasonably close to Nash*, and
  - Slumbot is significantly weaker (clearly exploitable),
- then **triangulation is directionally useful but noisy**.

Rule-of-thumb:

- Treat **(X − Y)** as a **rough estimate** of your gap vs GTO Wizard, but with **error bars easily on the order of ±10–20 bb/100**, and possibly more if:
  - Your bot and Slumbot share structural biases (same bet sizes, similar abstraction).
  - Your bot’s leaks sit in parts of the game that Slumbot doesn’t punish but GTO Wizard would (or vice versa).

So:

- You *can* say things like “I’m probably within ~Z bb/100 of a GTO‑Wizard‑class blueprint, with very wide uncertainty,”
- but you *cannot* safely claim fine-grained distances (e.g., “I’m 5 bb/100 from GTO Wizard”) from Slumbot-only tests.
