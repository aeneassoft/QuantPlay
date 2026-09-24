# PokerB 6-max — play & analysis

## 🎮 Play right away
**Double-click `PokerB 6max spielen.bat`** (on the desktop) → the browser opens, you
play against **5 bots**. Fast, **without hints**. Buttons: Fold / Check / Call /
Bet-Raise (slider + ½ / ¾ / pot) / All-in. After every hand "Next hand ▸".

## 📝 Your hands are logged
Every hand (positions, **your actions + bet sizes**, board, result, net per player) is
stored in `data/sessions/session_<timestamp>.jsonl`.

## 📊 Analysis at the end
Click **"Analyze my hands"** → statistics (VPIP, PFR, 3-bet, postflop aggression, showdown %,
**bb/100**) + an honest playing-style classification and your biggest leaks (phrased by Claude).
(Validated: after 15 test hands played as a "calling station", exactly that was detected.)

## 🤖 Pro data catalogued (for learning)
**10,000 Pluribus hands** (the superhuman 6-max bot) are normalized in `knowledge_base/hand_histories/`
(`pluribus_hands.jsonl`) + position stats (`pluribus_stats.json`). Source: PHH dataset
(University of Toronto). This is how Pluribus plays 6-max (open frequencies tight EP → wide LP) — usable to tune our bot
toward this profile.

## 📐 Math book
"The Mathematics of Poker" is extracted via **gpt-5.1** into `knowledge_base/math/mathematics_of_poker.json`
(+ `.md`) (toy games, indifference, optimal bluff/bet-sizing frequencies).

## ⚙️ Under the hood
Real **N-player engine with side pots** (`pokerbot/engine/table.py`) — stress-tested over 500
hands (374 side-pot hands), chip conservation held every hand. Bots: `pokerbot/arena/sixmax.py`
(position-aware ranges + equity + fold-equity sizing), instant (no LLM in the game).

Start manually as well: `python -m pokerbot.web.six_server --open`
