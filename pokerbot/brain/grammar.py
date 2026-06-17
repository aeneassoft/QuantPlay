"""The DSL GRAMMAR gate — the structural enforcement that the brain runs on OUR language, not arbitrary Python.

The vision (2026-06-17): Qwen is the HOST we repurpose; it stops being a free-form language model and becomes a
computational poker AI whose EXECUTABLE SURFACE IS our engine-DSL. This validator makes that literal: a program is
ACCEPTED only if every AST node is in a curated whitelist and every call/attribute targets `api.*`, `spot.*`,
`decide(...)`, or a safe builtin. Anything foreign — import, open, lambda, def/class, while, dunder access, attribute
escapes off call results — is STRUCTURALLY REJECTED before execution. Not sandbox-caught: grammar-rejected.

This is how we drive hallucination-as-malformed-output toward ZERO: the model cannot emit a construct outside our
language and have it run; a violation becomes a hard-negative (RL signal), never an action. Constrained DECODING at
inference/GRPO (making invalid tokens UNSAMPLABLE in the first place) is the GPU-side complement; this AST gate is the
$0, always-on backstop. The ENGINE still computes every number (api), so numeric hallucination is impossible by
construction — the model emits the CALL, never the value.
"""
from __future__ import annotations

import ast

# Whitelist of AST node types. Default-DENY: anything not here is rejected. (No FunctionDef/ClassDef/Lambda/Import/
# While/With/Try/Global/Delete/Yield/Await — none have a benign place in a decision program.)
_ALLOWED_NODES = {
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign,
    ast.If, ast.IfExp, ast.For, ast.Pass, ast.Break, ast.Continue,
    ast.comprehension, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.Call, ast.keyword, ast.Starred,
    ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Subscript, ast.Slice,
    ast.Attribute,
    ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
}

# Attributes / method-calls are allowed ONLY on these names (the engine vocabulary + the spot).
_OWNERS = {"api", "spot"}
# Bare function names the DSL may call (the decision sink + the safe builtins the executor exposes).
_SAFE_CALLS = {"decide", "min", "max", "abs", "round", "sum", "len", "sorted", "range", "float", "int", "bool",
               "str", "list", "dict", "tuple", "enumerate", "zip", "any", "all", "map", "filter", "divmod",
               "pow", "repr", "isinstance"}


def validate_program(program: str) -> tuple[bool, str]:
    """(ok, reason). ok iff the program is pure DSL: whitelisted nodes only, calls/attrs on api/spot/safe-builtins
    only, no dunder escapes, and it commits exactly via decide()."""
    try:
        tree = ast.parse(program or "", mode="exec")
    except SyntaxError as e:
        return False, f"syntax error: {e.msg}"
    has_decide = False
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            return False, f"disallowed construct: {type(node).__name__}"
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return False, f"dunder name: {node.id}"
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return False, f"dunder attribute: .{node.attr}"
            if not (isinstance(node.value, ast.Name) and node.value.id in _OWNERS):
                return False, "attribute access only on api/spot"
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                if not (isinstance(f.value, ast.Name) and f.value.id in _OWNERS):
                    return False, "method call only on api.*/spot.*"
            elif isinstance(f, ast.Name):
                if f.id in ("decide", "decide_mix"):     # decide_mix = a MIXED strategy (frequencies over actions)
                    has_decide = True
                elif f.id not in _SAFE_CALLS:
                    return False, f"call to non-DSL name: {f.id}()"
            else:
                return False, "complex call target (only api.*/spot.*/safe-builtin)"
    if not has_decide:
        return False, "no decide() — a decision program must commit an action"
    return True, "valid DSL"
