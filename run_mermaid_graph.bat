@echo off
REM === Navigate to project root ===
cd /d %~dp0

REM === Activate virtual environment ===
call venv\Scripts\activate.bat

REM === Run Mermaid graph generator ===
python generate_mermaid_graph.py

pause
