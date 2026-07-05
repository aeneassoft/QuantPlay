@echo off
title PokerB - 6-max (5 Bots)
cd /d "C:\Users\hampe\Desktop\PokerB"
echo ============================================================
echo   PokerB  -  6-max No-Limit Hold'em  gegen 5 Bots
echo   Der Browser oeffnet sich automatisch ( http://127.0.0.1:8000 ).
echo   Zum Beenden: dieses Fenster schliessen  (oder Strg+C).
echo ============================================================
echo.
"C:\Users\hampe\AppData\Local\Programs\Python\Python312\python.exe" -m pokerbot.web.six_server --open --port 8000
echo.
echo --- PokerB wurde beendet ---
pause
