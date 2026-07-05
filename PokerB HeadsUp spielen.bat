@echo off
setlocal
title PokerB - Heads-Up (1 Bot + Coach)
cd /d "C:\Users\hampe\Desktop\PokerB"
echo ============================================================
echo   PokerB  -  Heads-Up No-Limit Hold'em  (1 Bot + Claude-Coach)
echo   Der Browser oeffnet sich automatisch ( http://127.0.0.1:8001 ).
echo   Zum Beenden: dieses Fenster schliessen  (oder Strg+C).
echo ============================================================
echo.
rem VERSION PRINCE deception layer (2026-07-04, measured: mechanics probe + paired canary PASSED).
rem Exploit stays ON vs humans (the opponent model is the product's strength); these two kill the
rem user-found leaks: the readable check range + the turn over-fold vs stabs.
set POKERB_TURN_DEFENSE=0.07
set POKERB_SLOWPLAY=0.25
"C:\Users\hampe\AppData\Local\Programs\Python\Python312\python.exe" -m pokerbot.web.server --open --port 8001
echo.
echo --- PokerB wurde beendet ---
pause
