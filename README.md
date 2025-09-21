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
 
```

## WSL Quickstart
```bash
# Install nvm and Node 20 (Linux)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
. "$HOME/.nvm/nvm.sh"
nvm install 20
nvm use 20

# Codex CLI
npm install -g @openai/codex
codex --version
```
