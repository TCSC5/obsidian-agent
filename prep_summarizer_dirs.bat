@echo off
set "VAULT_PATH=C:\Users\top2e\Sync"

REM Create expected output folders if missing
if not exist "%VAULT_PATH%\Summaries" mkdir "%VAULT_PATH%\Summaries"
if not exist "%VAULT_PATH%\data" mkdir "%VAULT_PATH%\data"

REM Write a test file to confirm permissions
echo test > "%VAULT_PATH%\Summaries\_write_test.txt"
echo test > "%VAULT_PATH%\data\_write_test.txt"

REM Show the folder contents
echo === DIR Summaries ===
dir /b "%VAULT_PATH%\Summaries"
echo === DIR data ===
dir /b "%VAULT_PATH%\data"
pause
