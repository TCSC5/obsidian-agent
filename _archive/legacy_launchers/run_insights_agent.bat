@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Generating GPT-originated insights from summaries...
python generate_insights_agent.py

echo Done.
pause
