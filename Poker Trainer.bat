@echo off
title PokerB - Trainer (6-max Coaching)
cd /d "C:\Users\hampe\Desktop\PokerB"
echo ============================================================
echo   PokerB TRAINER  -  6-max No-Limit Hold'em Coaching
echo   Der Browser oeffnet sich automatisch:
echo       http://127.0.0.1:8000/training
echo   GTO-Modus / Exploit-Modus waehlbar auf dem Startbildschirm.
echo   Zum Beenden: dieses Fenster schliessen  (oder Strg+C).
echo ============================================================
echo.
"C:\Users\hampe\AppData\Local\Programs\Python\Python312\python.exe" -m pokerbot.web.six_server --trainer --port 8000
echo.
echo --- PokerB Trainer wurde beendet ---
pause
