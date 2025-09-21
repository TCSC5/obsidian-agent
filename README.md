# Obsidian Agent

Automation stack for an Obsidian vault. Python agents (summarizer, linker, planner, insights, dashboards) with Windows `.bat` launchers.

## What’s here
- **Agents**: Python scripts for summarizing, linking, planning, evaluating, and dashboards.
- **Launchers**: `run_*.bat` entrypoints (verbose/debug launchers archived in `_archive/launchers_debug`).
- **Vault**: Optional Obsidian content under `vault/` (gitignored by default).
- **Cleanup**: `cleanup.ps1` makes a backup, reports, purges Python caches, and can archive debug launchers.

## Quickstart (Windows)
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
 
