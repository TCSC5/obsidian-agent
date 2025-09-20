
# -*- coding: utf-8 -*-
"""
linking_agent_v4.py — suggest or refresh links

Fix: argparse attr is include_express (underscore), not include-express.
Adds --include-express flag to optionally scan Express/ folders.
"""

import os, argparse
from pathlib import Path

def list_md(p: Path):
    return [f for f in p.rglob("*.md")] if p.exists() else []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-express", dest="include_express", action="store_true",
                    help="Also scan Express/pitch and Express/insights")
    args = ap.parse_args()

    VAULT = Path(os.getenv("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")

    scan_targets = [
        ("Summaries", VAULT / "Summaries"),
        ("Areas",     VAULT / "Areas"),
        ("Resources", VAULT / "Resources"),
        ("Projects",  VAULT / "Projects"),
    ]
    if args.include_express:
        scan_targets += [
            ("Pitches",   VAULT / "Express" / "pitch"),
            ("Insights",  VAULT / "Express" / "insights"),
        ]

    total = 0
    for label, path in scan_targets:
        files = list_md(path)
        total += len(files)
        print(f"[scan] {label}: {len(files)} files")

    print(f"[OK] Linking scan completed: {total} files. (include_express={args.include_express})")

if __name__ == "__main__":
    main()
