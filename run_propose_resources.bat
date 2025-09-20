
@echo off
REM run_propose_resources.bat
REM Edit VAULT_PATH below to your local vault root
set VAULT_PATH=C:\Users\top2e\Sync
set REL=Resources\learning_inputs

echo [Propose] Scanning and staging YAML proposals...
python "%~dp0propose_resources.py" --vault "%VAULT_PATH%" --rel "%REL%"
if %errorlevel% neq 0 (
  echo [ERROR] Propose stage failed.
  exit /b 1
)
echo.
echo [OPEN] resource_index.md for review.
start "" "%VAULT_PATH%\Resources\resource_index.md"
