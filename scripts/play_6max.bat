@echo off
title QuantPlay - 6-max (5 bots, plain table)
cd /d "%~dp0.."
set PORT=8000
rem Free the port: a leftover python server (e.g. from an AI session) would block the start with WinError 10048.
rem Kills ONLY python processes listening on that port, nothing else.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($p -and $p.ProcessName -match 'python') { Stop-Process -Id $p.Id -Force } }" >nul 2>&1
echo ============================================================
echo   QuantPlay  -  6-max No-Limit Hold'em against 5 bots (plain table, no coaching)
echo   The browser opens automatically at  http://127.0.0.1:%PORT%
echo   Multiway: http://127.0.0.1:%PORT%?players=9   (2-10 seats)
echo   To stop: close this window (or Ctrl+C).
echo ============================================================
echo.
python -m pokerbot.web.six_server --open --port %PORT%
echo.
echo --- QuantPlay stopped ---
pause
