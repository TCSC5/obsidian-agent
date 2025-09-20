@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Generating pitch decks from summaries...
python generate_pitch_deck.py

echo Done.
pause
