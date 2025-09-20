@echo off
REM run_apply_resources.bat
set VAULT_PATH=C:\Users\top2e\Sync
set REL=Resources\learning_inputs
set REVIEWER=Michael

echo [Apply] Finalizing accepted/edited notes and updating the learning DB...
python "%~dp0apply_resources.py" --vault "%VAULT_PATH%" --rel "%REL%" --reviewer "%REVIEWER%" --strip-scaffold
if %errorlevel% neq 0 (
  echo [ERROR] Apply stage failed.
  pause
  exit /b 1
)
echo.
echo [DONE] Review complete. Pending items remain in proposed state.