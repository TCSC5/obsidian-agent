@echo off
cd /d D:\MyScripts\obsidian-agent
call venv\Scripts\activate.bat
python cleanup_review_log.py
pause