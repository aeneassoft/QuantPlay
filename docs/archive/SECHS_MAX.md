# PokerB 6-max — Spielen & Analyse

## 🎮 Sofort spielen
**Doppelklick auf `PokerB 6max spielen.bat`** (liegt auf dem Desktop) → Browser öffnet sich, du
spielst gegen **5 Bots**. Schnell, **ohne Tipps**. Buttons: Fold / Check / Call /
Bet-Raise (Slider + ½ / ¾ / Pot) / All-in. Nach jeder Hand „Nächste Hand ▸".

## 📝 Deine Hände werden geloggt
Jede Hand (Positionen, **deine Aktionen + Einsatzgrößen**, Board, Ergebnis, Netto pro Spieler) wird
in `data/sessions/session_<zeitstempel>.jsonl` gespeichert.

## 📊 Analyse am Ende
Klick **„Meine Hände analysieren"** → Statistik (VPIP, PFR, 3-bet, Postflop-Aggression, Showdown-%,
**bb/100**) + eine ehrliche Spielstil-Einordnung und deine größten Leaks (von Claude formuliert).
(Validiert: nach 15 Test-Händen als „Calling Station" wurde genau das erkannt.)

## 🤖 Profi-Daten katalogisiert (zum Lernen)
**10.000 Pluribus-Hände** (der superhumane 6-max-Bot) sind in `knowledge_base/hand_histories/`
normalisiert (`pluribus_hands.jsonl`) + Positions-Stats (`pluribus_stats.json`). Quelle: PHH-Dataset
(Uni Toronto). So spielt Pluribus 6-max (Open-Frequenzen eng EP → weit LP) — nutzbar, um unseren Bot
Richtung dieses Profils zu tunen.

## 📐 Mathe-Buch
„The Mathematics of Poker" wird via **gpt-5.1** in `knowledge_base/math/mathematics_of_poker.json`
(+ `.md`) extrahiert (Toy-Games, Indifferenz, optimale Bluff-/Bet-Sizing-Frequenzen).

## ⚙️ Unter der Haube
Echte **N-Spieler-Engine mit Side-Pots** (`pokerbot/engine/table.py`) — stress-getestet über 500
Hände (374 Side-Pot-Hände), Chip-Erhaltung hielt jede Hand. Bots: `pokerbot/arena/sixmax.py`
(positionsbewusste Ranges + Equity + Fold-Equity-Sizing), instant (kein LLM im Spiel).

Start auch manuell: `python -m pokerbot.web.six_server --open`
