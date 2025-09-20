# Obsidian Agent

This is a context-aware GPT-powered automation tool for processing and linking notes in an Obsidian vault.

## Features
- Adds `related:` YAML links based on semantic similarity
- Inserts `See also:` sections in note body
- Logs relationships (CSV & JSON)
- Adds bidirectional links
- Supports masked GPT summaries (optional)

## Structure
- `src/` — Python scripts (e.g. `main.py`)
- `scripts/` — Automation helpers (`.bat`, `.sh`)
- `vault/` — Your Obsidian vault or test notes
- `data/` — Logs and index files
- `logs/` — Execution and error logs

## Usage
1. Set up `.env` with your OpenAI key and vault path.
2. Activate the virtual environment: `venv\Scripts\activate`
3. Run: `python src/main.py`
