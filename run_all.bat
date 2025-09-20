@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM === Navigate to this script's folder ===
pushd "%~dp0"

REM === Activate virtualenv if present ===
if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [WARN] No venv found. Proceeding with system Python.
)

REM === Ensure logs folder exists ===
if not exist "logs" mkdir "logs"

REM === Timestamp for log file ===
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set RUNID=%%i
set "LOGFILE=logs\run_%RUNID%.log"

echo === Running Obsidian Agent Orchestrator ===
echo Log: %LOGFILE%

REM === Run the final orchestrator with resilient flags ===
python orchestrator_agent.py --continue-on-error --retries 1 >> "%LOGFILE%" 2>&1
set "RC=%ERRORLEVEL%"

if NOT "%RC%"=="0" (
  echo [ERROR] Orchestrator exited with code %RC%. See %LOGFILE% for details.
) else (
  echo [OK] Orchestrator completed successfully.
)

echo.
echo Done. Press any key to close...
pause >nul

popd
endlocal
