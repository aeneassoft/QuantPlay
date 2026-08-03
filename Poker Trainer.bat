@echo off
title PokerB - Trainer (6-max Coaching)
cd /d "C:\Users\hampe\Desktop\PokerB"
rem PRINCE v2.2-Profil (validierter Anker, AIVAT -19.70): gilt fuer den Live-HU-Takeover UND den Grading-Oracle.
set POKERB_PRINCE=1
rem Port 8000 freiraeumen: ein liegengebliebener python-Server (z.B. aus einer Claude-Sitzung) blockiert sonst
rem den Start mit WinError 10048. Beendet NUR python-Prozesse, die auf 8000 lauschen - nichts anderes.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'python') { Stop-Process -Id $p.Id -Force } }" >nul 2>&1
echo ============================================================
echo   PokerB TRAINER  -  6-max No-Limit Hold'em Coaching
echo   Der Browser oeffnet sich automatisch:
echo       http://127.0.0.1:8000/training
echo   Modi auf dem Startbildschirm:
echo       GTO     - Grundlinie; heads-up uebernimmt Prince v2
echo       Exploit - die Bots lernen dich und nutzen deine Leaks
echo       Arena   - wilde Online-Landschaft als Stresstest
echo   Zum Beenden: dieses Fenster schliessen  (oder Strg+C).
echo ============================================================
echo.
"C:\Users\hampe\AppData\Local\Programs\Python\Python312\python.exe" -m pokerbot.web.six_server --trainer --port 8000
echo.
echo --- PokerB Trainer wurde beendet ---
pause
