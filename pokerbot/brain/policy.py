"""The Qwen POLICY bridge — turns a loaded (model, tok) into `policy(table, seat) -> (action, amount_chips)`, the
protocol `training/rl_env.py` expects. ONE source of the prompt (`build_messages` / `SYSTEM_PROMPT`) so SFT == RL ==
inference == eval are byte-identical. Generation is grammar-CONSTRAINED to our DSL (`brain/dsl_grammar.py`) where
possible, then parsed + executed via `run_program(strict)` (the semantic gate) → an exact, legal action.

`build_messages` and `parse_completion` are MODEL-FREE (testable with $0). Only `QwenPolicy._generate` needs a GPU model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pokerbot.brain import api as _api
from pokerbot.brain import dsl_grammar
from pokerbot.brain import modes
from pokerbot.brain.executor import run_program
from pokerbot.brain.format_spot import ACTION_RE, format_spot, spot_from_table

SYSTEM_PROMPT = (
    "You are a 6-max No-Limit Hold'em GTO engine. You receive a spot and OUTPUT A PYTHON DECISION PROGRAM in our DSL "
    "— no prose outside # comments. Compute with the engine API (exact math), then commit exactly one action.\n"
    "Your remembered poker 'rules' are a HYPOTHESIS to VERIFY via the engine — never the answer. DERIVE every decision "
    "from api.* (the engine is the only truth); do not decide from gut feel.\n"
    "API: api.equity(hole, villain_range, board), api.required_equity(to_call, pot), api.pot_odds(to_call, pot), "
    "api.mdf(bet, pot), api.spr(eff, pot), api.outs_equity(outs, cards), api.board_texture(board), "
    "api.hand_rank(hole, board), api.hand_class_of(hole). Spot fields: spot.hero_hole, spot.board, spot.pot, "
    "spot.to_call, spot.hero_pos, spot.n_active.\n"
    "End with a decision DERIVED from the engine values via control flow — EITHER decide(action[, size_bb]) for a pure "
    "action, OR decide_mix({'action': freq, ...}[, size=bb]) for a MIXED strategy (GTO is mixed; a single pure line is "
    "exploitable). action is one of fold, check, call, bet, raise, allin; size is the TOTAL bet in big blinds. Write the "
    "RULE so the engine-computed equity picks the branch; the engine runs it with exact numbers. Example:\n"
    "eq = api.equity(spot.hero_hole, ['AA','KK','AQs'], spot.board)\n"
    "req = api.required_equity(spot.to_call, spot.pot)\n"
    "if eq >= req + 0.2:\n    decide_mix({'raise': 0.7, 'call': 0.3}, size=7.5)\n"
    "elif eq >= req:\n    decide_mix({'call': 0.8, 'raise': 0.2}, size=7.5)\nelse:\n    decide_mix({'fold': 0.85, 'call': 0.15})"
)


def build_messages(spot) -> list[dict]:
    """The canonical chat prompt — used by the trainer (dataset 'prompt') AND QwenPolicy (generation). Single source."""
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": format_spot(spot)}]


_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_TAG = re.compile(r"</?think>")


def extract_program(text: str) -> str:
    """Pull the DSL program out of raw model text. Strips Qwen3's `<think>...</think>` block (the chat template
    emits one — empty in non-thinking — before the answer; left in, it breaks the DSL grammar => frac_bad), incl. a
    DANGLING `<think>` with no close (keep the program after it), and any markdown fence / surrounding prose. Used by
    inference, eval AND the GRPO reward, so it must clean ALL of them."""
    t = (text or "").strip()
    t = _THINK.sub("", t)                  # drop the paired reasoning block
    t = _THINK_TAG.sub("", t).strip()      # drop any dangling/stray <think> or </think> tag (keep the program)
    m = _FENCE.search(t)
    if m:
        return m.group(1).strip()
    return t


def parse_completion(text: str, spot, timeout_s: float | None = None) -> dict:
    """Raw model text -> {action, amount, ok, error, intended, program}. `ok` follows run_program(strict) (grammar +
    legality). If the program is rejected but the text carries an `ACTION:`/decide line, fall back to a LEGAL action but
    keep ok=False (a hard-negative for RL). `timeout_s` caps the program's wall-clock (the mode's decision budget)."""
    prog = extract_program(text)
    res = run_program(prog, spot, timeout_s=timeout_s, strict=True)
    res["program"] = prog
    if not res["ok"]:
        m = ACTION_RE.search(text)
        if m:
            act, amt = _api.legalize(spot, m.group(1), float(m.group(2)) if m.group(2) else None)
            res["action"], res["amount"] = act, amt           # safe, legal — but ok stays False (still a hard-negative)
    return res


@dataclass
class QwenPolicy:
    """Wrap a loaded (model, tok) as a poker policy. `sampling=False` (greedy) for eval/continuation; the GRPO trainer
    does its OWN sampling, so in-loop this class is used only via `build_messages` + periodic eval."""
    model: object
    tok: object
    sampling: bool = False
    constrained: bool = True
    max_new_tokens: int | None = None          # None -> the ACTIVE mode's reasoning budget (brain/modes.py)
    temperature: float = 1.0
    top_p: float = 1.0

    def __post_init__(self):
        if self.max_new_tokens is None:
            self.max_new_tokens = modes.current().max_new_tokens
        self._lp = dsl_grammar.regex_logits_processor(self.tok) if self.constrained else None

    def _generate(self, messages: list[dict]) -> str:
        import torch
        enc = self.tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        enc = {k: v.to(self.model.device) for k, v in enc.items()}
        n_in = enc["input_ids"].shape[1]
        kw = dict(max_new_tokens=self.max_new_tokens,
                  pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
        kw.update(dict(do_sample=True, temperature=self.temperature, top_p=self.top_p) if self.sampling
                  else dict(do_sample=False))
        if self._lp is not None:
            kw["logits_processor"] = self._lp
        with torch.no_grad():
            out = self.model.generate(**enc, **kw)
        return self.tok.decode(out[0][n_in:], skip_special_tokens=True)

    def decide_verbose(self, table, seat) -> dict:
        """Full parse result (for eval/audit): {action, amount, ok, error, intended, program}."""
        spot = spot_from_table(table, seat)
        return parse_completion(self._generate(build_messages(spot)), spot,
                                timeout_s=modes.current().time_budget_s)

    def __call__(self, table, seat):
        """policy(table, seat) -> (action, amount_chips). Always a LEGAL action (executor legalizes)."""
        res = self.decide_verbose(table, seat)
        return res["action"], res["amount"]
