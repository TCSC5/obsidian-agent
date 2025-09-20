
@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM === Run Insight Evolution Agent ===
python insight_evolution_agent.py

pause
