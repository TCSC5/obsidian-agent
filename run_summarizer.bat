@echo off
REM === Navigate to project root ===
cd /d %~dp0

REM === Activate virtual environment if it exists ===
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM === Run summarizer agent (canonical version) ===
python agents\summarizer_agent.py %*
