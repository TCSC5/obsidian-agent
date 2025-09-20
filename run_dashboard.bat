@echo off
cd /d %~dp0
call venv\Scripts\activate.bat
python generate_dashboard_v2.py
pause
