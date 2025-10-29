@echo off
REM === Navigate to project root ===
cd /d %~dp0

REM === Activate virtual environment if it exists ===
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM === Run summarizer agent v5 with all arguments ===
python summarizer_agent_v5.py %*
