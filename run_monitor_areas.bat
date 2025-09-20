@echo off
cd /d D:\MyScripts\obsidian-agent
call venv\Scripts\activate.bat
python monitor_areas_agent.py
pause
