@echo off
REM Force set the vault path (optional override if not in .env)
REM set VAULT_PATH=C:\Users\top2e\Sync

REM Navigate to project root
cd /d %~dp0

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run the fixed main.py directly
python src\main.py

pause
