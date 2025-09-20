@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM === Run Enhanced Agent Architect ===
python agent_architect_gpt.py

pause
