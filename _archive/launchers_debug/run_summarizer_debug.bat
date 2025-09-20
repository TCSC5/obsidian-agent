@echo off
setlocal
set "VAULT_PATH=C:\Users\top2e\Sync"
cd /d D:\MyScripts\obsidian-agent
if not exist logs mkdir logs
call venv\Scripts\activate

for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (set d=%%d-%%b-%%c)
for /f "tokens=1-3 delims=:." %%a in ("%time%") do (set t=%%a%%b%%c)
set "LOG=logs\summarizer_probe_!d!_!t!.log"

echo [INFO] Using VAULT_PATH=%VAULT_PATH% > "!LOG!" 2>&1

REM --- Snapshot inputs/outputs before ---
echo.>>"!LOG!" & echo === BEFORE: DIR 00_Inbox ===>>"!LOG!"
dir /b "%VAULT_PATH%\00_Inbox" >>"!LOG!" 2>&1
echo.>>"!LOG!" & echo === BEFORE: DIR Summaries ===>>"!LOG!"
dir /b "%VAULT_PATH%\Summaries" >>"!LOG!" 2>&1

REM --- Phase 1: intake-only ---
echo.>>"!LOG!" & echo === PHASE 1: intake-only (start) ===>>"!LOG!"
python -u -X dev summarizer_agent_v5.py --intake-only --debug --no-archive >>"!LOG!" 2>&1
echo [PHASE 1 EXITCODE] %ERRORLEVEL% >>"!LOG!" 2>&1
echo === PHASE 1: intake-only (end) ===>>"!LOG!"

REM --- Phase 2: normalize-only ---
echo.>>"!LOG!" & echo === PHASE 2: normalize-only (start) ===>>"!LOG!"
python -u -X dev summarizer_agent_v5.py --normalize-only --debug --no-archive >>"!LOG!" 2>&1
echo [PHASE 2 EXITCODE] %ERRORLEVEL% >>"!LOG!" 2>&1
echo === PHASE 2: normalize-only (end) ===>>"!LOG!"

REM --- Phase 3: generate ---
echo.>>"!LOG!" & echo === PHASE 3: generate (start) ===>>"!LOG!"
python -u -X dev summarizer_agent_v5.py --mode generate --debug --no-archive >>"!LOG!" 2>&1
echo [PHASE 3 EXITCODE] %ERRORLEVEL% >>"!LOG!" 2>&1
echo === PHASE 3: generate (end) ===>>"!LOG!"

REM --- Snapshot outputs after ---
echo.>>"!LOG!" & echo === AFTER: DIR Summaries ===>>"!LOG!"
dir /b "%VAULT_PATH%\Summaries" >>"!LOG!" 2>&1
echo.>>"!LOG!" & ech
