"""Meta-coach for the continuous improvement of our training / pod run.

It does NOT play hands — it STEERS the improvement loop between checkpoints: given a JSON checkpoint of
metrics (GTO-oracle gaps, Slumbot bb/100, current params), it returns concrete, PRIORITIZED directives
(which leak to fix, param changes, what to try next) as structured JSON — cheap enough to call every
checkpoint of a pod run.

Engine-agnostic so we pick the cheapest thing that's good enough:
  * provider="anthropic" (default): Claude Haiku 4.5 via API — strong reasoning, few calls, trivial cost.
  * provider="openai": any OpenAI-compatible endpoint — e.g. a SMALL open model (7-14B, one GPU) self-
    hosted on the pod via vLLM, or Venice. (NOT MiMo-V2-Flash/Kimi — those are 309B/1T MoEs needing
    ~8-GPU nodes; the in-loop hypothesis role only needs a small, fast reasoner.)

Demo on our real current numbers: python -m pokerbot.coach.meta_coach
"""
from __future__ import annotations

import json

from pokerbot import config

_SYS = (
    "You are the META-COACH of a No-Limit Hold'em bot's training loop. You do NOT play hands — you steer "
    "the improvement between checkpoints. Given a JSON checkpoint of metrics, reply with STRICT JSON only:\n"
    '{"summary": "<=2 sentences", "directives": [{"priority": 1, "change": "...", "why": "...", '
    '"how": "..."}], "continue": true}\n'
    "Rules: max 5 directives, ordered by impact; tie each directive to a metric in the checkpoint; 'how' "
    "must be concrete and actionable for an engineer; output nothing outside the JSON."
)

_SYS_EXPLOIT = (
    "You are an in-the-loop exploit-HYPOTHESIS generator for a No-Limit Hold'em trainer. From the "
    "opponent's PUBLIC stats, reason briefly about their likely strategic LEVEL (level-0 = plays cards "
    "at face value; level-1 = attacks perceived weakness; level-2 = traps the level-1 player) and emit "
    "ONE bounded, machine-checkable directive as STRICT JSON:\n"
    '{"reasoning": "<=2 sentences recursive ToM", "level": 0, '
    '"target": {"street": "flop|turn|river", "facing": "bet|check|3bet"}, '
    '"adjust": {"action": "value_bet_thinner|bluff_more|fold_more|call_wider|raise_more", '
    '"freq_delta": 0.1}, "confidence": 0.5}\n'
    "You are a PROPOSER: a solver/benchmark verifies the directive against an exploitability budget "
    "before anything is applied. Keep freq_delta in [-0.3, 0.3]; deviate only where the stat is clearly "
    "off GTO; output nothing outside the JSON."
)

_SYS_DIRECT = (
    "You are the ACTIVE DIRECTOR (Claude) of a time-boxed (~30 min) GPU distillation run for a No-Limit "
    "Hold'em policy net that imitates a GTO solver. Each round you see the current GTO-gap (overall + per "
    "spot-class: role OOP/IP and board texture) plus the time/epoch budget. Decide the curriculum that "
    "MINIMISES the gap in the remaining time. Reply STRICT JSON only:\n"
    '{"focus": ["worst spot-classes to oversample / solve more"], "epochs_next": 300, "lr": 0.001, '
    '"note": "<=2 sentences reasoning", "continue": true}\n'
    "Be decisive: pour remaining compute where the gap is largest; lower lr as the gap flattens; set "
    "continue=false only if the gap is already tiny or time is up."
)


class MetaCoach:
    def __init__(self, provider: str = "anthropic", model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None, adapter: str | None = None) -> None:
        self.provider = provider
        self._lm = self._tok = None
        if provider == "anthropic":
            from anthropic import Anthropic
            self.model = model or config.CLAUDE_HAIKU_MODEL
            key = api_key or config.ANTHROPIC_API_KEY
            self.client = Anthropic(api_key=key) if key else None
            self.available = self.client is not None
        elif provider == "local":   # our fine-tuned Qwen LoRA via transformers (no vLLM); lazy-loaded
            self.model = model or "Qwen/Qwen3-8B"
            self._adapter = adapter or str(config.ROOT / "models" / "qwen_poker_ckpt500")
            self.client = None
            self.available = True
        else:  # openai-compatible: a SMALL vLLM-served model on the pod (7-14B) / Venice / etc.
            from openai import OpenAI
            self.model = model or "Qwen/Qwen2.5-7B-Instruct"
            self.client = OpenAI(api_key=api_key or "EMPTY", base_url=base_url) if base_url else None
            self.available = self.client is not None

    def _ensure_local(self) -> None:
        if self._lm is not None:
            return
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        self._tok = AutoTokenizer.from_pretrained(self.model)
        qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                  bnb_4bit_quant_type="nf4")
        base = AutoModelForCausalLM.from_pretrained(self.model, quantization_config=qcfg, device_map="cuda")
        self._lm = PeftModel.from_pretrained(base, self._adapter).eval()

    def _chat(self, system: str, user: str, max_tokens: int = 1500) -> str:
        if self.provider == "local":
            import torch
            self._ensure_local()
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            enc = self._tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                                return_dict=True, enable_thinking=False)
            enc = {k: v.to(self._lm.device) for k, v in enc.items()}
            n_in = enc["input_ids"].shape[1]
            with torch.no_grad():
                out = self._lm.generate(**enc, max_new_tokens=min(max_tokens, 320), do_sample=False,
                                        pad_token_id=self._tok.pad_token_id or self._tok.eos_token_id)
            return self._tok.decode(out[0][n_in:], skip_special_tokens=True)
        if self.provider == "anthropic":
            m = self.client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                            messages=[{"role": "user", "content": user}])
            return "".join(b.text for b in m.content if getattr(b, "type", None) == "text")
        m = self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return m.choices[0].message.content or ""

    def review(self, checkpoint: dict) -> dict:
        """Between-runs meta-coach: metrics -> prioritized directives."""
        if not self.available:
            return {"error": f"no client for provider={self.provider}"}
        user = "CHECKPOINT:\n" + json.dumps(checkpoint, indent=2, ensure_ascii=False)
        return _parse_json(self._chat(_SYS, user).strip())

    def propose_exploit(self, opp_stats: dict, context: dict | None = None) -> dict:
        """In-loop HYPOTHESIS generator: reason recursive-ToM about the opponent's likely level from
        PUBLIC stats and emit ONE bounded, machine-checkable exploit directive. A PROPOSER only — the
        solver/benchmark verifies it (+ exploitability budget) before it is ever applied."""
        if not self.available:
            return {"error": f"no client for provider={self.provider}"}
        user = ("OPPONENT (public stats only):\n" + json.dumps(opp_stats, indent=2, ensure_ascii=False)
                + "\nCONTEXT:\n" + json.dumps(context or {}, ensure_ascii=False))
        return _parse_json(self._chat(_SYS_EXPLOIT, user, max_tokens=900).strip())

    def direct_run(self, run_state: dict) -> dict:
        """ACTIVE in-run director (use Opus): given the round's gap-by-spot-class + time budget, return a
        curriculum directive (focus classes, lr, epochs, continue) to minimise the gap in the time left."""
        if not self.available:
            return {"error": f"no client for provider={self.provider}"}
        return _parse_json(self._chat(_SYS_DIRECT, "RUN STATE:\n"
                                      + json.dumps(run_state, indent=2, ensure_ascii=False),
                                      max_tokens=700).strip())


def _parse_json(txt: str) -> dict:
    if "</think>" in txt:                              # Qwen3 thinking block -> keep only the answer after it
        txt = txt.rsplit("</think>", 1)[1].strip()
    if "```" in txt:                                   # strip code fences if present
        seg = txt.split("```")[1]
        txt = seg[4:].strip() if seg.lower().startswith("json") else seg.strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return {"raw": txt}


def main() -> None:
    mc = MetaCoach()
    if not mc.available:
        print("no Anthropic key found"); return
    checkpoint = {
        "stage": "phase1_analytic_baseline",
        "vs_slumbot": {"bb_per_100": -99.6, "stderr": 113.5, "hands": 350},
        "gto_oracle_check": {
            "overall_agreement": 0.51, "gto_bet_freq": 0.14, "baseline_bet_freq": 0.50,
            "spots": {"K72r_dry": {"gto": 0.0, "base": 0.43}, "882r_paired": {"gto": 0.0, "base": 0.54},
                      "QJ9ss_wet": {"gto": 0.15, "base": 0.55}, "652ss_low": {"gto": 0.41, "base": 0.49}},
        },
        "known_leak": "baseline over-donks OOP as the preflop caller; not aggressor/range-advantage aware",
        "assets": ["local TexasSolver GTO oracle (verify + distillation targets)",
                   "adaptive exploit layer (online opponent model)", "verified Nash push/fold"],
        "capabilities": "can edit strategy code, run the solver for any spot, re-benchmark vs Slumbot",
        "goal": "beat near-GTO Slumbot to break-even+ AND keep crushing the exploitable field",
    }
    print(f"MetaCoach via {mc.provider}:{mc.model}\n")
    print(json.dumps(mc.review(checkpoint), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
