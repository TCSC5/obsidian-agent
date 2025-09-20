@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Evaluating Success Metrics...
python evaluate_success.py

echo ✅ Evaluation complete.
pause
