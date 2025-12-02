@echo off
cd /d D:\MyScripts\obsidian-agent

echo Running Long-Term Learning Loop Agent...
call venv\Scripts\activate.bat
python learning_loop_agent.py

pause