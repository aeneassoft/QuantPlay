@echo off
setlocal
title QuantPlay - Heads-Up (1 bot + advisor)
cd /d "%~dp0.."
set PORT=8001
rem Free the port: a leftover python server (e.g. from an AI session) would block the start with WinError 10048.
rem Kills ONLY python processes listening on that port, nothing else.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'python') { Stop-Process -Id $p.Id -Force } }" >nul 2>&1
echo ============================================================
echo   QuantPlay  -  Heads-Up No-Limit Hold'em  (1 bot + engine advisor; Claude coach optional)
echo   The browser opens automatically at  http://127.0.0.1:%PORT%
echo   To stop: close this window (or Ctrl+C).
echo ============================================================
echo.
rem Configuration (server.py, 2026-09-09): PRINCE profile + exploit OFF + AUSLESE chain FINAL_STACK (r8_stack,
rem auslese-v5) + TexasSolver resolver ON = the measured GTOW arm 'v5-H'. Opponent AND advisor play the same policy.
set POKERB_TURN_DEFENSE=0.07
set POKERB_SLOWPLAY=0.25
python -m pokerbot.web.server --open --port %PORT%
echo.
echo --- QuantPlay heads-up stopped ---
pause
