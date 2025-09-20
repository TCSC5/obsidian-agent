
# -*- coding: utf-8 -*-
"""
generate_snapshot_log.py — richer snapshot
- Pulls quick stats from logs/gating_report.md, System/synergy_scores.csv,
  and data/agent_performance_report.md (if present).
- Writes data/snapshot_log.md and syncs to Vault/System/snapshot_log.md when VAULT_PATH is set.
"""

import os, csv, json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
DATA = BASE / "data"; DATA.mkdir(parents=True, exist_ok=True)
SYSTEM = BASE / "System"
LOGS = BASE / "logs"; LOGS.mkdir(parents=True, exist_ok=True)

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync")
OUT = DATA / "snapshot_log.md"
OUT_VAULT = VAULT / "System" / "snapshot_log.md"

def parse_gating():
    rpt = LOGS / "gating_report.md"
    counts = {}
    if not rpt.exists():
        return counts
    for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line and line.strip().startswith("- "):
            k, v = line[2:].split(":", 1)
            counts[k.strip()] = v.strip()
    return counts

def parse_synergy():
    path = SYSTEM / "synergy_scores.csv"
    if not path.exists():
        return {}
    # very light stats: count rows
    n = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        for i, _ in enumerate(f, start=1):
            n = i
    return {"scored_notes": max(0, n-1)}  # minus header

def extract_health():
    rep = DATA / "agent_performance_report.md"
    if not rep.exists():
        return ""
    text = rep.read_text(encoding="utf-8", errors="replace")
    # include only the top section
    head = text.splitlines()[:40]
    return "\n".join(head).strip()

def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gating = parse_gating()
    synergy = parse_synergy()
    health = extract_health()

    lines = [f"# Snapshot {ts}", ""]
    if gating:
        lines.append("## Gating")
        for k, v in gating.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    if synergy:
        lines.append("## Synergy")
        for k, v in synergy.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
    if health:
        lines.append("## Agent Health (excerpt)")
        lines.append(health)
        lines.append("")

    OUT.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print("Snapshot saved to", OUT)

    # sync to vault
    try:
        OUT_VAULT.parent.mkdir(parents=True, exist_ok=True)
        OUT_VAULT.write_text(OUT.read_text(encoding="utf-8"), encoding="utf-8")
        print("Synced to vault:", OUT_VAULT)
    except Exception as e:
        print("[warn] Could not sync to vault:", e)

if __name__ == "__main__":
    main()
