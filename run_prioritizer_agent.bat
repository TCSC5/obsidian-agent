@echo off
cd /d D:\MyScripts\obsidian-agent

echo ════════════════════════════════
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

echo 🧠 Running Prioritizer Agent on Express folder...
python prioritizer_agent.py

echo ✅ Done.
pause
