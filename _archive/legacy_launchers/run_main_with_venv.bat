@echo off
REM === Set Vault Path (optional override) ===
set VAULT_PATH=%~dp0vault

REM === Navigate to script directory ===
cd /d %~dp0

REM === Activate virtual environment ===
call venv\Scripts\activate.bat

REM === Run Python script from /src folder ===
python src\main.py

pause
