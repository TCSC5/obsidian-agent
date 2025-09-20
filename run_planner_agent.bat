@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Generating Weekly Plan...
python planner_agent.py

echo Weekly Plan Updated.
pause
