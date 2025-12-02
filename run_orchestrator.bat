@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM --- Jump to project root (relative to this bat file) ---
cd /d %~dp0

REM --- Activate venv if it exists ---
if exist venv\Scripts\activate.bat (
    echo [orchestrator] Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate.bat (
    echo [orchestrator] Activating .venv...
    call .venv\Scripts\activate.bat
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
    python clean_links_json_to_csv.py --in data\incoming_links.json --index data\vault_index.json --out data\links_log.csv --append
    if errorlevel 1 (
        echo [orchestrator] WARNING: Link cleaning failed. Check output above for details.
    )
)

REM --- Timestamp for logs (locale-independent PowerShell approach) ---
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set TS=%%I

REM --- Run the orchestrator (profiled version with --profile and --dry-run support) ---
echo [orchestrator] Running orchestrator_agent_profiled.py
python orchestrator_agent_profiled.py %* 1> logs\orchestrator_!TS!.out.log 2> logs\orchestrator_!TS!.err.log

REM --- Check result ---
if %ERRORLEVEL% EQU 0 (
    echo [orchestrator] Done. Logs: logs\orchestrator_!TS!.out.log
    exit /b 0
)

echo [orchestrator] ERROR %ERRORLEVEL%. Check logs\orchestrator_!TS!.err.log
exit /b %ERRORLEVEL%