
# -*- coding: utf-8 -*-
"""
monitor_areas_agent.py — lightweight folder health check for PARA + Express

Scans these folders (if present) under VAULT_PATH:
  - Summaries/
  - Express/pitch/
  - Express/insights/
  - Areas/
  - Resources/
and prints simple counts + "hot spots" (most recently modified files).
"""

import os, time
from pathlib import Path

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync")

TARGETS = [
    ("Summaries", VAULT / "Summaries"),
    ("Pitches",   VAULT / "Express" / "pitch"),
    ("Insights",  VAULT / "Express" / "insights"),
    ("Areas",     VAULT / "Areas"),
    ("Resources", VAULT / "Resources"),
]

def list_md(p: Path):
    return [f for f in p.rglob("*.md")] if p.exists() else []

def main():
    for label, path in TARGETS:
        files = list_md(path)
        print(f"[{label}] {len(files)} notes in {path}")
        # show 5 most recent
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[:5]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
            print("  -", f.name, ts)
    print("[OK] Areas monitor complete.")

if __name__ == "__main__":
    main()
