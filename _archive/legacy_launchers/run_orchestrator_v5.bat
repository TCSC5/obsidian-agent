@echo off
REM === Run Orchestrator Agent V5 ===
cd /d %~dp0

REM Activate your virtual environment (adjust if needed)
call venv\Scripts\activate

REM Run the orchestrator
python orchestrator_agent_v5.py

REM Pause so you can see results before window closes
pause
