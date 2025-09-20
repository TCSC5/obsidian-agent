@echo off
REM === run_env_check.bat ===
REM Quick diagnostic to confirm .env variables are loading correctly

cd /d D:\MyScripts\obsidian-agent

REM Activate virtual environment
call venv\Scripts\activate

REM Run the Python env_check tool
python env_check.py

echo.
echo === Done. If OPENAI_API_KEY shows 'yes' and VAULT_PATH is correct, environment is good. ===
pause
