@echo off
setlocal enableextensions enabledelayedexpansion

REM ----- Vault path (confirmed) -----
set "VAULT_PATH=C:\Users\top2e\Sync"

cd /d D:\MyScripts\obsidian-agent
if not exist logs mkdir logs
call venv\Scripts\activate

REM ----- Timestamped log name (YYYY-MM-DD_HHMMSS) -----
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do (set d=%%d-%%b-%%c)
for /f "tokens=1-3 delims=:." %%a in ("%time%") do (set t=%%a%%b%%c)
set "LOG=logs\decision_debug_!d!_!t!.log"

echo [INFO] Using VAULT_PATH=%VAULT_PATH% > "!LOG!" 2>&1

REM ----- Record the exact summarizer args we’ll pass -----
echo [INFO] Summarizer args: --no-archive --debug >> "!LOG!" 2>&1

REM ----- Orchestrator (verbose) + pass-through summarizer debug -----
python orchestrator_agent_profiled.py ^
  --profile decision ^
  --verbose ^
  --continue-on-error ^
  --retries 1 ^
  --summarizer-args --no-archive --debug >> "!LOG!" 2>&1

echo [OK] Decision profile complete. See "!LOG!".
echo [OK] Also check logs\summarizer_report.md (if created).
pause
