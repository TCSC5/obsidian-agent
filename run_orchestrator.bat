@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM --- Jump to project root ---
cd /d D:\MyScripts\obsidian-agent

REM --- Activate venv ---
echo [orchestrator] Activating virtual environment...
call venv\Scripts\activate.bat || goto :err

REM --- Ensure folders exist ---
if not exist logs mkdir logs
if not exist data mkdir data
if not exist System mkdir System

REM --- Optional: set VAULT_PATH here if not using .env ---
REM set VAULT_PATH=C:\Users\top2e\Sync

REM --- If there is an incoming suggestions JSON, clean it into links_log.csv ---
if exist data\incoming_links.json (
  echo [orchestrator] Cleaning incoming links (data\incoming_links.json)...
  python clean_links_json_to_csv.py --in data\incoming_links.json --index data\vault_index.json --out data\links_log.csv --append || goto :err
)

REM --- Timestamp for logs ---
for /f %%I in ('powershell -NoProfile -Command "$ts = Get-Date -Format yyyy-MM-dd_HH-mm-ss; Write-Output $ts"') do set TS=%%I

REM --- Run the orchestrator; pass through any args you supply to this .bat ---
echo [orchestrator] Running orchestrator_agent.py %*
python orchestrator_agent.py %* 1> "logs\orchestrator_!TS!.out.log" 2> "logs\orchestrator_!TS!.err.log" || goto :err

echo [orchestrator] Done. Logs: logs\orchestrator_!TS!.out.log / .err.log
exit /b 0

:err
echo [orchestrator] ERROR %ERRORLEVEL%. Check logs\orchestrator_!TS!.err.log
exit /b %ERRORLEVEL%
