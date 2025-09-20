@echo off
cd /d D:\MyScripts\obsidian-agent

echo Running Memory + Feedback Agent...
call venv\Scripts\activate.bat
python memory_feedback_agent.py

pause