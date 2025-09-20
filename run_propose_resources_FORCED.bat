@echo off
REM run_propose_resources_FORCED.bat
set VAULT_PATH=C:\Users\top2e\Sync
set REL=Resources\learning_inputs

echo [Propose] Forcing all notes into review and backing up originals on edit...
python "%~dp0propose_resources.py" --vault "%VAULT_PATH%" --rel "%REL%" --force-propose --backup-on-edit
if %errorlevel% neq 0 (
  echo [ERROR] Propose stage failed.
  pause
  exit /b 1
)
echo.
echo [OPEN] resource_index.md for review.
start "" "%VAULT_PATH%\Resources\resource_index.md"