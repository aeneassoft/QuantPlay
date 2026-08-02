"""Claude-backed coaching + the trainer's decision capture/grading modules (TRAINER_PLAN.md P0).

The Coach import is guarded: coach.py hard-imports `anthropic` at module level, but the trainer
modules (decision_log/registry/grader) must import inside the six_server play path even without
the anthropic package installed.
"""
try:
    from pokerbot.coach.coach import Coach
    __all__ = ["Coach"]
except Exception:  # noqa: BLE001 — anthropic optional; trainer modules stay importable
    __all__ = []
