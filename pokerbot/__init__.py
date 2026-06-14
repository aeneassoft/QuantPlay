"""PokerB — a Heads-Up No-Limit Hold'em bot grounded in GTO + exploitative play.

Sub-packages:
  engine    — cards, hand evaluation, equity, the HU NLHE game state machine
  strategy  — the decision engine (preflop ranges, postflop math, exploit layer)
  knowledge — loaders for the extracted book knowledge (ranges, concepts, math)
  coach     — LLM-backed explanations / coaching via the Claude API
  web       — FastAPI app to play against the bot in the browser
"""

__version__ = "0.1.0"
