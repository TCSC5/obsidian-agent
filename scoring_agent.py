
# -*- coding: utf-8 -*-
"""
scoring_agent.py — ASCII-safe minimal scorer to avoid Windows console Unicode errors.

It scans Express/pitch and Express/insights and prints simple counts and a stub score file.
This prevents fallback to prioritizer_agent.py, which uses emoji and fails on cp1252 consoles.
"""

import os, csv
from pathlib import Path
from datetime import datetime

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
PITCH = VAULT / "Express" / "pitch"
INS   = VAULT / "Express" / "insights"

BASE = Path(__file__).parent
SYSTEM = BASE / "System"; SYSTEM.mkdir(parents=True, exist_ok=True)
SCORES = SYSTEM / "scores_stub.csv"

def list_md(p: Path):
    return [f for f in p.glob("*.md")] if p.exists() else []

def main():
    pitches = list_md(PITCH)
    insights = list_md(INS)
    print("[INFO] Scoring (stub):")
    print(" - Pitches :", len(pitches))
    print(" - Insights:", len(insights))
    # Write a stub CSV so downstream doesn't fail
    with SCORES.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["note","score","updated"])
        for md in pitches + insights:
            w.writerow([md.name, 0.5, datetime.now().isoformat(timespec="seconds")])
    print("[OK] Wrote", SCORES)

if __name__ == "__main__":
    main()
