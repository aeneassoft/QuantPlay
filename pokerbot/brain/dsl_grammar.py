"""DSL constrained-decoding grammar — the GENERATIVE half of "the brain runs on our own language" (2026-06-17 directive).

`grammar.py` is the SEMANTIC gate (AST whitelist, run AFTER generation in the executor). THIS file is the GENERATIVE
constraint: a regex over the canonical decision-program FORM, so the model can ONLY emit valid DSL while decoding —
invalid tokens are unsamplable, not merely rejected after the fact. Two consumers:
  * TRL GRPO generation  -> `vllm_regex()`  feeds `GRPOConfig(vllm_structured_outputs_regex=...)`.
  * local transformers generate (policy/eval) -> `regex_logits_processor(tok)` (outlines, best-effort).

The canonical FORM (a straight-line "compute then commit", optionally a single engine-resolved conditional):
    # free-text reasoning as comments
    <var> = <expr over api.* / spot.* / literals>      # zero or more compute lines
    decide("<action>"[, <size_bb>])                    # OR an if/elif/else whose branches each decide(...)

The model writes the RULE; the executor runs it with EXACT engine numbers (it never sees api results mid-generation),
so the engine-resolved `if equity > pot_odds: decide('call') else: decide('fold')` is the load-bearing pattern.
The regex is a SUBSET of what `grammar.py` accepts (constrained output is always AST-valid); `grammar.py` +
`run_program(strict)` remain the hard backstop for anything the regex lets through.
"""
from __future__ import annotations

import re

# ---- atoms ----------------------------------------------------------------
_WS = r"[ \t]*"
_NUM = r"-?\d+(?:\.\d+)?"
_STR = r"""(?:'[^'\n]*'|"[^"\n]*")"""                    # single- OR double-quoted (converters use repr -> single)
_LIST = r"\[[^\]\n]*\]"                                  # a flat list literal (e.g. ['AA','KK'])
_ACTION = r"""(?:'(?:fold|check|call|bet|raise|allin|all-in)'|"(?:fold|check|call|bet|raise|allin|all-in)")"""
# an api call with simple (non-nested-call) args, or a spot attribute, or a literal/name
_APICALL = r"api\.\w+\([^()\n]*\)"
_PAREN = r"\([^()\n]*\)"                                 # a flat parenthesized group, e.g. (spot.pot + spot.to_call)
_ATOM = rf"(?:{_APICALL}|spot\.\w+|{_LIST}|{_STR}|{_NUM}|{_PAREN}|\w+)"
_OP = r"(?:\*\*|//|[-+*/%]|==|!=|<=|>=|<|>|is not|is|and|or|not)"  # `is not`/`is` -> the api.solver_freq None-guard (`if f is not None`)
# a flat expression: atoms joined by binops/comparisons (paren-groups are atoms; contents are AST-gated by grammar.py)
_EXPR = rf"{_ATOM}(?:{_WS}{_OP}{_WS}{_ATOM})*"

# ---- statements -----------------------------------------------------------
_COMMENT = rf"{_WS}#[^\n]*"
_ASSIGN = rf"{_WS}\w+{_WS}={_WS}{_EXPR}"
_DECIDE = rf"{_WS}decide\({_ACTION}(?:{_WS},{_WS}{_NUM})?\)"
# decide_mix({'fold': .2, 'call': .5, 'raise': .3}, size=7.5) — a MIXED strategy (a DICT of action->frequency +
# optional size). Pure strategies are exploitable by construction; GTO is mixed -> the policy class MUST emit a
# distribution. (Dict, not kwargs: 'raise' is a Python keyword and cannot be a kwarg name.)
_DICTITEM = rf"{_ACTION}{_WS}:{_WS}{_NUM}"
_DECIDE_MIX = (rf"{_WS}decide_mix\({_WS}\{{{_WS}{_DICTITEM}(?:{_WS},{_WS}{_DICTITEM})*{_WS}\}}"
               rf"(?:{_WS},{_WS}size{_WS}={_WS}{_NUM})?{_WS}\)")
_COMMIT = rf"(?:{_DECIDE}|{_DECIDE_MIX})"                # a commit = a pure decide OR a mixed strategy
# a single engine-resolved conditional: if/elif*/else? where every branch body is exactly one commit
_IF = (rf"{_WS}if{_WS}{_EXPR}{_WS}:\n{_COMMIT}\n"
       rf"(?:{_WS}elif{_WS}{_EXPR}{_WS}:\n{_COMMIT}\n)*"
       rf"(?:{_WS}else{_WS}:\n{_COMMIT}\n?)?")

_PREAMBLE = rf"(?:(?:{_COMMENT}|{_ASSIGN})\n)*"          # zero+ comment / compute lines
_PROGRAM = rf"{_PREAMBLE}(?:{_COMMIT}|{_IF})\n?"

DSL_REGEX = re.compile(rf"^{_PROGRAM}$")


def matches(program: str) -> bool:
    """True iff `program` is in the canonical constrained-decoding DSL form (trailing-newline-normalized)."""
    return bool(DSL_REGEX.fullmatch((program or "").rstrip() + "\n"))


def vllm_regex(think_cap_chars: int | None = None) -> str:
    """The raw regex string for TRL `GRPOConfig(vllm_structured_outputs_regex=...)` (vLLM structured outputs).
    None (default) = the pure-DSL form (Qwen non-thinking). With `think_cap_chars` set (GLM-Z1 / any reasoning model whose
    PROMPT opens `<think>`), the completion is `<reasoning ≤N chars></think> <program>`: the `{0,N}` HARD-bounds the think
    so `</think>` + the program ALWAYS fit inside `max_completion_length` — the structural defense vs the frac_bad=0.93
    thinking-ramble (stronger than a soft prompt). `[\\s\\S]` (not `(?s).`) so it spans newlines without an inline flag
    (vLLM's structured-output backend may not honor `(?s)`)."""
    if think_cap_chars is None:
        return _PROGRAM
    return rf"[\s\S]{{0,{int(think_cap_chars)}}}</think>\s*{_PROGRAM}"


def regex_logits_processor(tokenizer):
    """Best-effort LOCAL constrained decoding (transformers .generate) via `outlines`. Returns a LogitsProcessorList
    or None if outlines is unavailable — callers then fall back to unconstrained generation + the AST/run_program gate."""
    try:
        from outlines.processors import RegexLogitsProcessor          # type: ignore
        from transformers import LogitsProcessorList
        return LogitsProcessorList([RegexLogitsProcessor(_PROGRAM, tokenizer)])
    except Exception:  # noqa: BLE001 — outlines absent / version skew -> caller falls back to the AST backstop
        return None
