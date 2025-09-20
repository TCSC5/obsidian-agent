# -*- coding: utf-8 -*-
"""
generate_dashboard_v2.py — updated to append:
  1) the Mermaid system-flow diagram
  2) curated Dataview sections from `dashboard_sections.md`

Enhancements in this build:
- Excludes noisy folders from "Recent Notes"
- Adds a prerequisites callout at the top
- Self-heals by copying assets into the vault if missing (first run)
- Safer wiki-links rendering in the "Recent Notes" list

Search order (for both files):
- repo folder (same as this script)
- Vault root
- Vault/Resources
- Vault/System
"""

import os
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

BASE = Path(__file__).resolve().parent
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"C:\Users\top2e\Sync"))
DATA_DIR = BASE / "data"
DASHBOARD_PATH = VAULT_PATH / "dashboard.md"

# --- New: exclude noisy dirs from recent scan
EXCLUDED_RECENT_DIRS = {"System", ".obsidian", ".git", "node_modules", ".trash"}


def count_md_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*.md"))


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def safe_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_append(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)


def recent_files(root: Path, limit: int = 10):
    if not root.exists():
        return []
    files = []
    for p in root.rglob("*.md"):
        # Skip excluded directories anywhere in the path
        if any(part in EXCLUDED_RECENT_DIRS for part in p.parts):
            continue
        files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def build_dashboard_header() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"# Obsidian Dashboard\n\n_Last updated: {now}_\n\n"


# --- New: prerequisites note
def build_prereqs_note() -> str:
    return (
        "> [!info] Dashboard prerequisites\n"
        "> Enable **Dataview**, **Buttons**, and **Mermaid** (core) for full rendering.\n\n"
    )


def build_quick_stats() -> str:
    sections = [
        ("Inbox", VAULT_PATH / "00_Inbox"),
        ("Summaries", VAULT_PATH / "Summaries"),
        ("Insights", VAULT_PATH / "Express" / "insights"),
        ("Pitch", VAULT_PATH / "Express" / "pitch"),
        ("Projects", VAULT_PATH / "Projects"),
        ("Areas", VAULT_PATH / "Areas"),
        ("Resources", VAULT_PATH / "Resources"),
        ("Archives", VAULT_PATH / "Archives"),
        ("System", VAULT_PATH / "System"),
    ]
    lines = ["## Quick Stats\n"]
    for name, folder in sections:
        lines.append(f"- **{name}**: {count_md_files(folder)} files")
    lines.append("")
    return "\n".join(lines)


def build_recent_section() -> str:
    lines = ["## Recent Notes\n"]
    recs = recent_files(VAULT_PATH, limit=12)
    if not recs:
        lines.append("_No recent files found._\n")
        return "\n".join(lines)
    for p in recs:
        rel = p.relative_to(VAULT_PATH).as_posix()
        # Escape pipes to avoid wiki-link alias parsing issues
        rel = rel.replace("|", "\\|")
        lines.append(f"- [[{rel}]]")
    lines.append("")
    return "\n".join(lines)


def build_logs_snapshot() -> str:
    lines = ["## Run Snapshot\n"]
    run_log = DATA_DIR / "run_log.md"
    if run_log.exists():
        # Show last 40 lines to keep it compact
        content = safe_read(run_log).strip().splitlines()[-40:]
        lines.append("```\n" + "\n".join(content) + "\n```\n")
    else:
        lines.append("_No run_log.md found in data/._\n")
    return "\n".join(lines)


def find_mermaid_diagram() -> str:
    """
    Returns the Mermaid code block string to append, or '' if not found.
    Looks in:
      1) Working dir:   BASE / obsidian_agent_flow_after_insights_pitch.md
      2) Vault root:    VAULT_PATH / obsidian_agent_flow_after_insights_pitch.md
      3) Resources:     VAULT_PATH / 'Resources' / 'obsidian_agent_flow_after_insights_pitch.md'
      4) System:        VAULT_PATH / 'System' / 'obsidian_agent_flow_after_insights_pitch.md'
    """
    candidates = [
        BASE / "obsidian_agent_flow_after_insights_pitch.md",
        VAULT_PATH / "obsidian_agent_flow_after_insights_pitch.md",
        VAULT_PATH / "Resources" / "obsidian_agent_flow_after_insights_pitch.md",
        VAULT_PATH / "System" / "obsidian_agent_flow_after_insights_pitch.md",
    ]
    for c in candidates:
        if c.exists():
            text = safe_read(c).strip()
            if text.startswith("```mermaid"):
                return text
            # If the file only contains the mermaid body, wrap it
            if "flowchart" in text and "mermaid" not in text.splitlines()[0]:
                return f"```mermaid\n{text}\n```"
    return ""


def find_dashboard_sections() -> str:
    """
    Returns the Markdown block containing Dataview sections, or '' if not found.
    Looks in the same places as the mermaid finder.
    """
    candidates = [
        BASE / "dashboard_sections.md",
        VAULT_PATH / "dashboard_sections.md",
        VAULT_PATH / "Resources" / "dashboard_sections.md",
        VAULT_PATH / "System" / "dashboard_sections.md",
    ]
    for c in candidates:
        if c.exists():
            return safe_read(c).strip() + "\n"
    return ""


# --- New: self-heal assets in vault if missing
def ensure_asset_in_vault(filename: str) -> None:
    """
    If `filename` exists next to this script but not in the vault (in root/Resources/System),
    copy it into the vault root. Safe to call repeatedly.
    """
    src = BASE / filename
    if not src.exists():
        return

    # If it's found anywhere in the typical vault search paths, do nothing.
    search_targets = [
        VAULT_PATH / filename,
        VAULT_PATH / "Resources" / filename,
        VAULT_PATH / "System" / filename,
    ]
    if any(t.exists() for t in search_targets):
        return

    try:
        (VAULT_PATH / filename).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        # Best-effort; ignore copy errors
        pass


def main():
    # 0) Best-effort placement of assets into the vault (first-run friendly)
    ensure_asset_in_vault("obsidian_agent_flow_after_insights_pitch.md")
    ensure_asset_in_vault("dashboard_sections.md")

    # 1) Build base dashboard content
    parts = [
        build_dashboard_header(),
        build_prereqs_note(),  # New callout
        build_quick_stats(),
        build_recent_section(),
        build_logs_snapshot(),
    ]
    safe_write(DASHBOARD_PATH, "\n".join(parts))

    # 2) Append Mermaid diagram if available
    mermaid_block = find_mermaid_diagram()
    safe_append(DASHBOARD_PATH, "\n## System Flow\n\n")
    if mermaid_block:
        safe_append(DASHBOARD_PATH, mermaid_block + "\n")
    else:
        safe_append(DASHBOARD_PATH, "_Mermaid diagram file not found._\n")

    # 3) Append Dataview sections if available
    sections_md = find_dashboard_sections()
    safe_append(DASHBOARD_PATH, "\n## PARA Views & Reports\n\n")
    if sections_md:
        safe_append(DASHBOARD_PATH, sections_md)
    else:
        safe_append(DASHBOARD_PATH, "_dashboard_sections.md not found._\n")

    print(f"[OK] Dashboard written to: {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
