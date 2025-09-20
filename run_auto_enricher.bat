@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Running auto-enricher for pitch decks...
python enriched_auto_enricher.py

pause
