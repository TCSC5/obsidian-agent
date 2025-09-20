@echo off
REM run_backfill_learning.bat
REM Runs the backfill script to update learning_db.json from all finalized notes

set VAULT_PATH=C:/Users/top2e/Sync
set REL=Resources/learning_inputs

python "%~dp0backfill_learning.py" --vault "%VAULT_PATH%" --rel "%REL%"
if %errorlevel% neq 0 (
  echo [ERROR] Backfill failed.
  pause
  exit /b 1
)

echo.
echo [DONE] Backfill complete. You can now run propose to see improved suggestions.
pause
