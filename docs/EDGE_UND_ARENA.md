# Postflop-Edge & Open-Poker-Arena — Stand

## 1) Slumbot: der Edge (ehrlich)
Postflop neu gebaut (Board-Textur, Range-vs-Range-Equity, **Fold-Equity-optimales Bet-Sizing**,
MDF-Defense). Dann **Slumbots Fold-Kurve gemessen** (378 Probe-Bets) — klare Abweichungen von GTO:
- **Flop 0.5×Pot: foldet 47 %** (Breakeven 33 %) → Overfold → hier bluffen
- **River 0.66×Pot: foldet 55 %** (Breakeven 40 %) → Overfold → hier bluffen
- **Turn klein (0.33–0.66×): foldet 7–25 %** → Underfold → NICHT klein bluffen

Der Bot wählt im Exploit-Modus datenbasiert die +EV-Größe.

**Ergebnisse vs Slumbot (200bb, 50/100):**
| Variante | Hände | bb/100 |
|---|---|---|
| alter Bot | 500 | −170 |
| verbessert, **ohne** Exploit | 500 | −196 |
| verbessert, **mit** Exploit (Lauf 1) | 500 | **+150,9** |
| verbessert, **mit** Exploit (Lauf 2) | 700 | **−16,0** |
| **Exploit kombiniert** | **1.200** | **+53,5 (±~70)** |

**Ehrlich:** Der Exploit hilft *klar* (riesiger positiver Schwung ggü. „ohne Exploit", und nur
Exploitation eines *statischen* Bots erklärt das). Die wahre Win-Rate ist aber **noch nicht eng
bewiesen** — Varianz ist gewaltig. Belastbarer Beweis braucht mehrere Tausend Hände.

```powershell
python -m pokerbot.benchmark.probe --hands 350          # Slumbots Fold-Kurve (neu) lernen
python -m pokerbot.benchmark.slumbot --hands 500 --exploit   # mit Edge
python -m pokerbot.benchmark.slumbot --hands 500             # ohne Edge (Vergleich)
```

## 2) Open Poker Arena (6-max) — Client steht
- **6-max-Gehirn** (`pokerbot/arena/sixmax.py`): positionsbewusste Open/3bet/Call-Ranges +
  Multiway-angepasstes Postflop. Lokal validiert (EP AA→raise, BTN A5s→raise, KK→3bet, Air→fold …).
- **WebSocket-Client** (`pokerbot/arena/openpoker.py`): Auth (`Bearer`/`?token=`), `join_lobby`,
  `your_turn` → Entscheidung → `action`, Rebuy/Reconnect. **Endpunkt-Erreichbarkeit + Auth-Handshake
  bestätigt** (Server antwortet exakt laut Doku).

**Du brauchst nur einen API-Key (1 Schritt):**
```powershell
curl -X POST https://api.openpoker.ai/api/register -H "Content-Type: application/json" `
  -d '{\"name\":\"machiavel_bot\",\"email\":\"DEINE_EMAIL\",\"terms_accepted\":true}'
# -> api_key sicher speichern (wird nur einmal gezeigt), dann:
$env:OPENPOKER_API_KEY = "dein_key"
python -m pokerbot.arena.openpoker
```

**Hinweise:**
- Einige Live-Nachrichtenfelder (z. B. die Dealer-Position pro Hand) sind in den Docs nur teils
  spezifiziert. Der Client loggt Unbekanntes und spielt defensiv weiter — beim ersten echten Lauf
  justiere ich anhand der realen Nachrichten nach (10-Minuten-Sache).
- **Größter Arena-Hebel:** pro Gegner-Bot die Fold-Kurve *live* lernen (unsere Probe/Exploit-Methode)
  — gegen ausbeutbare Bots holen wir so am meisten. Das ist der nächste Ausbauschritt.
