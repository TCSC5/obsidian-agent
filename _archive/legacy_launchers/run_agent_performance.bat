@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM === Run Agent Performance GPT ===
python agent_performance_gpt.py

pause
