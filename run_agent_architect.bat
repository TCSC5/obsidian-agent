@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM === Run Agent Architect ===
python agent_architect.py

pause
