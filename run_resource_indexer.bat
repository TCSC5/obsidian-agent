@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"

REM Activate venv (.venv preferred, fallback venv)
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
if not defined VIRTUAL_ENV if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"

python resource_indexer.py %*
set EXITCODE=%ERRORLEVEL%

popd
exit /b %EXITCODE%
