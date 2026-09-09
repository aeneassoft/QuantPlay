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
rem Konfiguration (Stand 2026-09-09, server.py D1-Fix): PRINCE-Profil + Exploit AUS + AUSLESE-Kette
rem FINAL_STACK (r8_stack, auslese-v5) + TexasSolver-Resolver AN = der gemessene GTOW-Arm 'v5-H'.
rem Gegner UND Berater spielen dieselbe Politik (Fingerprint beider im /api/view). Die beiden Flags
rem unten sind Teil der AUSLESE_ENV (server.py setzt sie ohnehin per setdefault; hier explizit).
set POKERB_TURN_DEFENSE=0.07
set POKERB_SLOWPLAY=0.25
"C:\Users\hampe\AppData\Local\Programs\Python\Python312\python.exe" -m pokerbot.web.server --open --port 8001
echo.
echo --- PokerB wurde beendet ---
pause
