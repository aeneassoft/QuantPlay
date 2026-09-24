@echo off
title QuantPlay - Trainer (6-max coaching)
cd /d "%~dp0.."
set PORT=8000
rem PRINCE v2.2 profile (the validated heads-up anchor) applies to the grading oracle.
set POKERB_PRINCE=1
rem Free the port: a leftover python server (e.g. from an AI session) would block the start with WinError 10048.
rem Kills ONLY python processes listening on that port, nothing else.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'python') { Stop-Process -Id $p.Id -Force } }" >nul 2>&1
echo ============================================================
echo   QuantPlay TRAINER  -  6-max No-Limit Hold'em coaching
echo   The browser opens automatically at  http://127.0.0.1:%PORT%/training
echo   Modes on the start screen: GTO / Exploit / Arena / Tournament / Match
echo   Online version (no install): https://quantplay.io
echo   To stop: close this window (or Ctrl+C).
echo ============================================================
echo.
python -m pokerbot.web.six_server --trainer --port %PORT%
echo.
echo --- QuantPlay trainer stopped ---
pause
