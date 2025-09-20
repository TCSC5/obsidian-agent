@echo off
REM === Set your vault path here ===
set VAULT_PATH=C:\Users\top2e\Sync

REM === Move to the folder where the script lives ===
cd /d D:\MyScripts\obsidian-agent

REM === Run the indexer and echo its output for troubleshooting ===
call venv\Scripts\activate
echo [Running resource indexer...]
python resource_indexer.py --vault-path "%VAULT_PATH%"
echo [Indexer finished. Check summary above.]

REM === Open the index in your default Markdown app (Obsidian if associated) ===
start "" "%VAULT_PATH%\Resources\resource_index.md"

REM === Keep the window open for troubleshooting ===
pause
