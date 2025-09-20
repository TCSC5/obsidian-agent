@echo off
REM env_check.bat - run the Python environment checker
SETLOCAL
echo Activating venv if present...
IF EXIST "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) ELSE (
  echo [warn] venv\Scripts\activate.bat not found — continuing without activation.
)
python env_check.py
echo.
echo Done. Press any key to exit.
pause > nul
ENDLOCAL
