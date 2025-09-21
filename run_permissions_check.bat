@echo off
REM Run permissions check for Obsidian Agent
REM This script provides a convenient way to check vault permissions

echo ===============================================
echo Obsidian Agent - Permissions Checker
echo ===============================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not available or not in PATH
    echo Please ensure Python is installed and accessible.
    pause
    exit /b 1
)

REM Get vault path from environment or use default
if defined VAULT_PATH (
    set "VAULT_ROOT=%VAULT_PATH%"
) else (
    set "VAULT_ROOT=C:\Users\top2e\Sync"
)

echo Using vault path: %VAULT_ROOT%
echo.

REM Run the permissions checker
echo Running comprehensive permissions analysis...
python permissions_checker.py --vault-path "%VAULT_ROOT%"

REM Check exit code
if errorlevel 1 (
    echo.
    echo [ERROR] Permissions check failed or encountered errors.
    echo Please review the output above and fix any issues.
) else (
    echo.
    echo [SUCCESS] Permissions check completed.
)

echo.
echo For JSON output, run:
echo   python permissions_checker.py --vault-path "%VAULT_ROOT%" --json
echo.
echo To check a specific path, run:
echo   python permissions_checker.py --check-path "path\to\check"
echo.

pause