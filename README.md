# Obsidian Agent

Automation stack for an Obsidian vault. Python agents (summarizer, linker, planner, insights, dashboards) with Windows `.bat` launchers.

## What’s here
- **Agents**: Python scripts for summarizing, linking, planning, evaluating, and dashboards.
- **Launchers**: `run_*.bat` entrypoints (verbose/debug launchers archived in `_archive/launchers_debug`).
- **Vault**: Optional Obsidian content under `vault/` (gitignored by default).
- **Cleanup**: `cleanup.ps1` makes a backup, reports, purges Python caches, and can archive debug launchers.

## Quickstart (Windows)
```powershell
# Create virtual environment
python -m venv venv
venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
git clone https://github.com/TCSC5/obsidian-agent.git
cd obsidian-agent 
```
### 2. Configure Vault Path

**Option A: Set environment variable (recommended)**
```cmd
# Windows - set permanently
setx VAULT_PATH "C:\Users\YourName\Sync"

# Restart your terminal for it to take effect
```

**Option B: Pass as CLI flag each time**
```bash
python resource_indexer.py --vault-path="C:\Your\Vault" --dry-run
```
## WSL Quickstart
```bash
# Install nvm and Node 20 (Linux)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
. "$HOME/.nvm/nvm.sh"
nvm install 20
nvm use 20
```
## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VAULT_PATH` | Optional* | Path to your Obsidian vault | `C:\Users\YourName\Sync` |
| `OPENAI_API_KEY` | Optional | OpenAI API key (for AI features) | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Optional | Anthropic API key (for AI features) | `sk-ant-...` |
| `MAX_RETRIES` | Optional | Retry attempts for API calls | `3` |
| `LOG_LEVEL` | Optional | Logging verbosity | `INFO` |

*Optional if you always pass `--vault-path` CLI flag

**Create `.env` file (optional):**
```bash
# In repo root: D:\MyScripts\obsidian-agent\.env
VAULT_PATH=C:\Users\top2e\Sync
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
MAX_RETRIES=3
LOG_LEVEL=INFO

# Codex CLI
npm install -g @openai/codex
codex --version
``` 
**⚠️ Never commit `.env` - it's already in `.gitignore`**
---

## Indexing Tools

### Resource Indexer (`resource_indexer.py`)

**Purpose:** Manages metadata for learning resources in `Resources/learning_inputs/`.

**Features:**
- Adds YAML frontmatter to notes without it
- Validates and backfills required fields (domain, tags, relevance)
- Creates `.bak` backups before modifying files
- Generates browsable index files
- **Supports `--dry-run` for safe preview**

**Usage:**
```bash
# Preview changes (safe, no modifications)
python resource_indexer.py --vault-path="C:\Your\Vault" --dry-run

# Apply changes with backups (recommended)
python resource_indexer.py --vault-path="C:\Your\Vault"

# Or use launcher (uses VAULT_PATH env var)
.\run_resource_indexer.bat

# Skip backups (faster, less safe)
python resource_indexer.py --vault-path="C:\Your\Vault" --no-backup

# Don't backfill existing YAML
python resource_indexer.py --vault-path="C:\Your\Vault" --no-backfill

# Show all options
python resource_indexer.py --help
```

**CLI Flags:**
- `--vault-path` - Path to Obsidian vault (overrides `VAULT_PATH` env var)
- `--dry-run` - Preview changes without modifying files
- `--resources-folder` - Folder to scan (default: `Resources/learning_inputs`)
- `--index-path` - Where to write Markdown index (default: `Resources/resource_index.md`)
- `--json-path` - Where to write JSON index (default: `Resources/resource_index.json`)
- `--no-backfill` - Don't add missing fields to existing YAML
- `--no-backup` - Don't create `.bak` files before modifying

**Outputs:**
- `Resources/resource_index.md` - Markdown table for browsing
- `Resources/resource_index.json` - JSON metadata for processing
- `*.bak` - Backup files (unless `--no-backup`)

**Example Output:**
```bash
$ python resource_indexer.py --vault-path="C:\Users\top2e\Sync" --dry-run

[DRY-RUN MODE] No files will be modified

[info] Scanning: C:\Users\top2e\Sync\Resources\learning_inputs
[DRY-RUN] Would add YAML frontmatter to: example_note.md
[DRY-RUN] New fields: domain=['ai'], tags=['tutorial']

[DRY-RUN] Would write Markdown index to: Resources\resource_index.md
[DRY-RUN] Would write JSON index to: Resources\resource_index.json
[DRY-RUN] Index would contain 12 entries

[summary] scanned=12 newly_yaml=2 updated_yaml=0

✓ Dry run complete. Run without --dry-run to apply changes.
```

---

### Vault Scanner (`generate_vault_index.py`)

**Purpose:** Read-only scanner for entire vault.

**Features:**
- **Never modifies files** (read-only)
- Scans all `.md` files (except Archives, .obsidian)
- Extracts minimal metadata (path, folder, title, tags, mtime, size)
- Useful for general vault navigation, search, or dashboards

**Usage:**
```bash
# Use default vault path (from VAULT_PATH env var)
python generate_vault_index.py

# Specify custom vault
python generate_vault_index.py --vault-path="D:\MyVault"

# Custom output location
python generate_vault_index.py --output="reports\vault_scan.json"

# Show all options
python generate_vault_index.py --help
```

**CLI Flags:**
- `--vault-path` - Path to Obsidian vault (overrides `VAULT_PATH` env var)
- `--output` - Output JSON file path (default: `data/vault_index.json`)

**Output:**
- `data/vault_index.json` - Full vault index with metadata

**Example Output:**
```bash
$ python generate_vault_index.py

[info] Scanning vault: C:\Users\top2e\Sync
[ok] Indexed 247 notes to D:\MyScripts\obsidian-agent\data\vault_index.json
```

---

### When to Use Which?

| Goal | Use |
|------|-----|
| Add/validate learning resource metadata | `resource_indexer.py` |
| Generate training manifest | `resource_indexer.py` |
| Preview metadata changes safely | `resource_indexer.py --dry-run` |
| Find all notes in vault | `generate_vault_index.py` |
| Build custom dashboards | `generate_vault_index.py` |
| Audit vault structure | `generate_vault_index.py` |

**Key Difference:**
- **`resource_indexer.py`** - Active metadata manager (modifies files, validates schema)
- **`generate_vault_index.py`** - Passive scanner (read-only, simple metadata)

---

## Project Structure
```
obsidian-agent/
├── resource_indexer.py           # Learning resource metadata manager
├── generate_vault_index.py       # Read-only vault scanner
├── orchestrator_agent.py         # Main pipeline coordinator
├── orchestrator_agent_profiled.py
├── promote_notes.py
├── training_pipeline.py
├── generate_dashboard_v2.py
├── run_*.bat                     # Windows launchers
├── taxonomy.yaml                 # Classification rules
├── System/                       # Generated logs (gitignored)
├── data/                         # Generated artifacts
│   └── training_manifest.json    # Training registry (tracked)
├── .venv/                        # Virtual environment (gitignored)
└── .github/
    ├── COPILOT.md                # AI assistant context
    └── pull_request_template.md  # PR template
```

**Note:** The Obsidian vault itself lives outside this repo and is never committed.

---

## Development Workflow

### Before Making Changes
```bash
# Create feature branch
git checkout -b feat/your-feature-name

# Make changes
# ...

# Test with dry-run first
python resource_indexer.py --vault-path="C:\Your\Vault" --dry-run
```

### Opening a PR

1. Fill out the PR template (auto-loaded when you open a PR)
2. Include smoke test output in the "Evidence" section
3. Ensure checklist items pass:
   - `--dry-run` supported for file-writes
   - No secrets committed
   - CLI flags documented
   - README updated if behavior changed

### Code Standards

- **Python:** PEP 8, formatted with Black (line length 88)
- **Imports:** Alphabetical - stdlib → third-party → local
- **Dry-run:** All file-writing operations must support `--dry-run`
- **Logging:** UTC timestamps, machine-parseable format

---

## Troubleshooting

### Scripts can't find vault

**Error:** `[error] No --vault-path provided and VAULT_PATH env var not set.`

**Fix:**
```bash
# Option 1: Set environment variable
setx VAULT_PATH "C:\Users\top2e\Sync"

# Option 2: Pass flag explicitly
python resource_indexer.py --vault-path="C:\Your\Vault" --dry-run
```

### `.bat` launchers don't work

**Error:** Launcher fails or shows "venv not found"

**Fix:**
```bash
# Recreate virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### YAML frontmatter not being added

**Cause:** Running in dry-run mode

**Fix:**
```bash
# Remove --dry-run flag to actually apply changes
python resource_indexer.py --vault-path="C:\Your\Vault"
```

---

## Contributing

See `.github/pull_request_template.md` for PR guidelines and checklist.

**Key requirements:**
- All file-writing operations support `--dry-run`
- No secrets in code (use environment variables)
- CLI flags documented in script docstrings
- Test locally before pushing

---

## License

Private repository - all rights reserved.
