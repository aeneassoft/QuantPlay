"""Smoke-test the Claude coach against a real hand."""
from __future__ import annotations

from pokerbot.coach.coach import Coach
from pokerbot.engine.game import HeadsUpGame
from pokerbot.strategy.bot import PokerBot


def main() -> None:
    g = HeadsUpGame(names=("You", "Bot"), seed=5)
    g.start_hand()
    st = g.state()
    actor = st["to_act"]
    bot = PokerBot(actor, seed=1)
    dec = bot.decide(st)
    print(f"Hand: {' '.join(st['players'][actor]['hole'])} | Bot decision: "
          f"{dec['action']} {dec.get('amount') or ''}")

    coach = Coach(language="de")
    print("Coach available:", coach.available)
    print("\n=== EXPLAIN BOT MOVE ===")
    print(coach.explain_move(st, actor, dec))
    print("\n=== ASK A QUESTION ===")
    print(coach.ask("Wie spiele ich AKs Heads-Up gegen einen aggressiven Gegner?", st, actor))


if __name__ == "__main__":
    main()
