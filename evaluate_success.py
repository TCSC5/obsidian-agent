
# -*- coding: utf-8 -*-
"""
evaluate_success.py — report using success_metrics.json (preferred) or success_log.csv (fallback)
Writes a short markdown report to data/evaluate_success.md
"""

import os, json, csv
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"; DATA.mkdir(exist_ok=True, parents=True)
SYSTEM = BASE / "System"
OUT = DATA / "evaluate_success.md"

def load_success_metrics():
    path = SYSTEM / "success_metrics.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def load_success_csv():
    path = DATA / "success_log.csv"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        rows.extend(r)
    return rows

def render_from_metrics(metrics):
    # metrics may contain a list of runs; pick last
    last = metrics[-1] if isinstance(metrics, list) and metrics else metrics
    ts = last.get("timestamp") or datetime.now().isoformat(timespec="seconds")
    summary = last.get("summary", {})
    synergy = last.get("synergy", {})
    lines = []
    lines.append(f"# Success Evaluation ({ts})")
    if summary:
        lines.append("## Pipeline Summary")
        for k, v in summary.items():
            lines.append(f"- **{k}**: {v}")
    if synergy:
        lines.append("## Synergy")
        for k, v in synergy.items():
            lines.append(f"- **{k}**: {v}")
    return "\n".join(lines).strip()

def render_from_csv(rows):
    lines = ["# Success Evaluation (CSV)"]
    if not rows:
        lines.append("_No rows in success_log.csv_")
        return "\n".join(lines)
    head = rows[-1]
    ts = head.get("timestamp") or head.get("date") or ""
    lines.append(f"**Last run:** {ts}")
    for k, v in head.items():
        if k.lower() in {"timestamp","date"}: 
            continue
        lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)

def main():
    metrics = load_success_metrics()
    if metrics:
        OUT.write_text(render_from_metrics(metrics), encoding="utf-8")
        print("[OK] Wrote", OUT)
        return
    rows = load_success_csv()
    OUT.write_text(render_from_csv(rows), encoding="utf-8")
    print("[OK] Wrote", OUT)

if __name__ == "__main__":
    main()
