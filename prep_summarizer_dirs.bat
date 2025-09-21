@echo off
setlocal enabledelayedexpansion

REM Enhanced permissions checking for Obsidian Agent
REM Uses environment variable or defaults to common path
if defined VAULT_PATH (
    set "VAULT_ROOT=%VAULT_PATH%"
) else (
    set "VAULT_ROOT=C:\Users\top2e\Sync"
)

echo ===============================================
echo Obsidian Agent - Permissions and Setup Check
echo ===============================================
echo Vault path: %VAULT_ROOT%
echo.

REM Critical directories that need to be writable
set "DIRS_TO_CHECK=Summaries data logs Express\pitch Express\insights Resources Areas"

REM Check if vault root exists and is accessible
if not exist "%VAULT_ROOT%" (
    echo [ERROR] Vault root directory does not exist: %VAULT_ROOT%
    echo Please check VAULT_PATH environment variable or update this script.
    pause
    exit /b 1
)

REM Test vault root write permissions
echo test > "%VAULT_ROOT%\_vault_write_test.tmp" 2>nul
if errorlevel 1 (
    echo [ERROR] Cannot write to vault root: %VAULT_ROOT%
    echo Check permissions and ensure the path is accessible.
    pause
    exit /b 1
) else (
    echo [OK] Vault root is writable
    del "%VAULT_ROOT%\_vault_write_test.tmp" >nul 2>&1
)

REM Check each critical directory
set ERROR_COUNT=0
echo.
echo Checking critical directories:

for %%D in (%DIRS_TO_CHECK%) do (
    set "CURRENT_DIR=%VAULT_ROOT%\%%D"
    echo Checking: !CURRENT_DIR!
    
    REM Create directory if it doesn't exist
    if not exist "!CURRENT_DIR!" (
        mkdir "!CURRENT_DIR!" 2>nul
        if errorlevel 1 (
            echo   [ERROR] Cannot create directory: %%D
            set /a ERROR_COUNT+=1
        ) else (
            echo   [OK] Created directory: %%D
        )
    ) else (
        echo   [OK] Directory exists: %%D
    )
    
    REM Test write permissions
    if exist "!CURRENT_DIR!" (
        echo test > "!CURRENT_DIR!\_perm_test.tmp" 2>nul
        if errorlevel 1 (
            echo   [ERROR] No write permission in: %%D
            set /a ERROR_COUNT+=1
        ) else (
            echo   [OK] Write permission confirmed: %%D
            del "!CURRENT_DIR!\_perm_test.tmp" >nul 2>&1
        )
    )
)

echo.
if %ERROR_COUNT% equ 0 (
    echo ===============================================
    echo [SUCCESS] All permissions checks passed!
    echo The vault is ready for Obsidian Agent operations.
    echo ===============================================
) else (
    echo ===============================================
    echo [FAILURE] %ERROR_COUNT% permission issues found!
    echo Please resolve the errors above before running agents.
    echo ===============================================
)

echo.
echo Directory overview:
for %%D in (%DIRS_TO_CHECK%) do (
    set "CURRENT_DIR=%VAULT_ROOT%\%%D"
    if exist "!CURRENT_DIR!" (
        echo   %%D: exists
    ) else (
        echo   %%D: missing
    )
)

echo.
echo For detailed permissions analysis, run:
echo   python permissions_checker.py --vault-path "%VAULT_ROOT%"
echo.

pause
