"""Probe what the local LoRA actually OUTPUTS for (a) the exploit-directive prompt vs (b) a poker decision
prompt — to confirm its real capability/role. Run: python -m extraction.llm_probe
"""
from __future__ import annotations

from pokerbot.coach.meta_coach import MetaCoach, _SYS_EXPLOIT

c = MetaCoach(provider="local")
ex = c._chat(_SYS_EXPLOIT,
             "OPPONENT (public stats only):\n{\"vpip\": 25, \"fold_to_cbet\": 0.73, \"af\": 0.3}\n"
             "CONTEXT:\n{\"street\": \"flop\", \"facing\": \"check\"}", max_tokens=280)
print("=== EXPLOIT-PROMPT RAW ===")
print(ex[:900])
dec = c._chat("You are a GTO poker solver. Answer with the optimal action.",
              "Hero has As Ks on Qh 7d 2c. Pot 10bb, effective 100bb, opponent checked. What is the action?",
              max_tokens=160)
print("\n=== DECISION-PROMPT RAW ===")
print(dec[:900])
