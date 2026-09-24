# Postflop edge & Open Poker Arena — status

## 1) Slumbot: the edge (honestly)
Postflop rebuilt (board texture, range-vs-range equity, **fold-equity-optimal bet sizing**,
MDF defense). Then **measured Slumbot's fold curve** (378 probe bets) — clear deviations from GTO:
- **Flop 0.5×pot: folds 47 %** (breakeven 33 %) → overfold → bluff here
- **River 0.66×pot: folds 55 %** (breakeven 40 %) → overfold → bluff here
- **Turn small (0.33–0.66×): folds 7–25 %** → underfold → do NOT bluff small

In exploit mode the bot picks the +EV size based on data.

**Results vs Slumbot (200bb, 50/100):**
| Variant | Hands | bb/100 |
|---|---|---|
| old bot | 500 | −170 |
| improved, **without** exploit | 500 | −196 |
| improved, **with** exploit (run 1) | 500 | **+150.9** |
| improved, **with** exploit (run 2) | 700 | **−16.0** |
| **exploit combined** | **1,200** | **+53.5 (±~70)** |

**Honestly:** The exploit *clearly* helps (a huge positive swing vs "without exploit", and only
exploitation of a *static* bot explains that). But the true win rate is **not yet tightly
proven** — the variance is enormous. A robust proof needs several thousand hands.

```powershell
python -m pokerbot.benchmark.probe --hands 350          # learn Slumbot's fold curve (fresh)
python -m pokerbot.benchmark.slumbot --hands 500 --exploit   # with edge
python -m pokerbot.benchmark.slumbot --hands 500             # without edge (comparison)
```

## 2) Open Poker Arena (6-max) — client ready
- **6-max brain** (`pokerbot/arena/sixmax.py`): position-aware open/3bet/call ranges +
  multiway-adjusted postflop. Validated locally (EP AA→raise, BTN A5s→raise, KK→3bet, air→fold …).
- **WebSocket client** (`pokerbot/arena/openpoker.py`): auth (`Bearer`/`?token=`), `join_lobby`,
  `your_turn` → decision → `action`, rebuy/reconnect. **Endpoint reachability + auth handshake
  confirmed** (server answers exactly per the docs).

**You only need an API key (1 step):**
```powershell
curl -X POST https://api.openpoker.ai/api/register -H "Content-Type: application/json" `
  -d '{\"name\":\"machiavel_bot\",\"email\":\"YOUR_EMAIL\",\"terms_accepted\":true}'
# -> store the api_key safely (shown only once), then:
$env:OPENPOKER_API_KEY = "your_key"
python -m pokerbot.arena.openpoker
```

**Notes:**
- Some live message fields (e.g. the dealer position per hand) are only partly specified in
  the docs. The client logs unknowns and keeps playing defensively — on the first real run
  I will adjust based on the real messages (a 10-minute job).
- **Biggest arena lever:** learn each opponent bot's fold curve *live* (our probe/exploit method)
  — against exploitable bots that is where we gain the most. That is the next expansion step.
