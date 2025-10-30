@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM --- Jump to project root (relative to this bat file) ---
cd /d %~dp0

REM --- Activate venv if it exists ---
if exist venv\Scripts\activate.bat (
    echo [orchestrator] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [orchestrator] No venv found, using system Python
)

REM --- Ensure folders exist ---
if not exist logs mkdir logs
if not exist data mkdir data
if not exist System mkdir System

REM --- If there is an incoming suggestions JSON, clean it into links_log.csv ---
if exist data\incoming_links.json (
    echo [orchestrator] Cleaning incoming links...
    python clean_links_json_to_csv.py --in data\incoming_links.json --index data\vault_index.json --out data\links_log.csv --append 2>nul
)

REM --- Timestamp for logs ---
set TS=%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TS=%TS: =0%

REM --- Run the orchestrator ---
echo [orchestrator] Running orchestrator_agent.py
python orchestrator_agent.py %* > logs\orchestrator_!TS!.out.log 2> logs\orchestrator_!TS!.err.log

REM --- Check result ---
if %ERRORLEVEL% EQU 0 (
    echo [orchestrator] Done. Logs: logs\orchestrator_!TS!.out.log
    exit /b 0
)

echo [orchestrator] ERROR %ERRORLEVEL%. Check logs\orchestrator_!TS!.err.log
exit /b %ERRORLEVEL%
