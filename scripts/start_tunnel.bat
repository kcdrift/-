@echo off
REM =========================================================
REM Cloudflare fixed-domain tunnel launcher for ZUCAI site
REM Prerequisite: buy a domain, add it to Cloudflare, create a
REM   Cloudflare Tunnel in Dashboard, then paste the token below.
REM =========================================================
set TOKEN=REPLACE_WITH_YOUR_TUNNEL_TOKEN
set CF=C:\Users\1\.workbuddy\binaries\node\versions\22.22.2\cloudflared
set PY=C:\Users\1\.workbuddy\binaries\python\versions\3.13.12\python.exe

REM Switch to project root (this script lives in <root>/scripts)
cd /d "%~dp0\.."

REM Start local prediction service only if 8080 is free
netstat -ano | findstr ":8080" | findstr "LISTEN" >nul
if errorlevel 1 (
  echo [INFO] Starting local prediction service on 8080...
  start "" "%PY%" "web\app.py"
  timeout /t 3 >nul
) else (
  echo [INFO] 8080 already listening, skip Flask start
)

echo [  INFO] Starting Cloudflare tunnel (fixed domain)...
"%CF%" tunnel --token %TOKEN% --url http://localhost:8080
