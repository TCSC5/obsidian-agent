@echo off
REM === Navigate to project root ===
cd /d %~dp0

REM === Activate virtual environment ===
call venv\Scripts\activate.bat

REM === Run summarizer agent ===
python summarizer_agent.py

pause
