
# -*- coding: utf-8 -*-
"""
generate_dashboard_v3.py — Updated
Now shows:
- Snapshot (run_log)
- 🔄 Insight Evolution (preview)
- 🧭 Decision Support (preview)
- 🪞 Reflection Highlights (raw preview)
- 🪞 Reflection Summary (GPT)
- 🔗📈 Synergy Snapshot
- 📆 Weekly Plan (preview)
- 🧩 Agent Architect Report (preview)

Writes dashboard to both ./dashboard.md and <VAULT>/dashboard.md
"""

import os, re
from datetime import datetime
from pathlib import Path

VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync")
BASE  = Path(__file__).parent.resolve()
DATA  = BASE / "data"
SYSTEM = VAULT / "System"
OUT_LOCAL = BASE / "dashboard.md"
OUT_VAULT = VAULT / "dashboard.md"

def read_text(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def first_lines(s, n=40):
    lines = s.strip().splitlines()
    return "\n".join(lines[:n])

def find_first(*candidates):
    for p in candidates:
        if p and Path(p).exists():
            return Path(p)
    return None

def section(title):
    return f"\n## {title}\n"

def build():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"# 📊 Obsidian Agent Dashboard — {now}\n"]

    # 1) Snapshot stats from run_log.md if present
    run_log = find_first(DATA/"run_log.md", SYSTEM/"run_log.md", VAULT/"System"/"run_log.md")
    if run_log:
        txt = read_text(run_log)
        notes = re.search(r"\*\*Notes Indexed:\*\*\s*(\d+)", txt)
        links = re.search(r"\*\*Links Created:\*\*\s*(\d+)", txt)
        parts.append(section("Snapshot"))
        parts.append(f"- **Notes Indexed:** {notes.group(1) if notes else '—'}")
        parts.append(f"- **Links Created:** {links.group(1) if links else '—'}\n")

    # 2) Insight Evolution table (System/insight_evolution.md)
    evo = find_first(DATA/"insight_evolution.md", SYSTEM/"insight_evolution.md")
    parts.append(section("🔄 Insight Evolution"))
    if evo:
        parts.append(first_lines(read_text(evo), n=24) + "\n\n_See full: [[System/insight_evolution.md]]_")
    else:
        parts.append("_No insight_evolution.md found. Run insight_evolution_agent.py._")

    # 3) Decision Support
    dec = find_first(DATA/"decision_support.md", SYSTEM/"decision_support.md")
    parts.append(section("🧭 Decision Support — Top to Act On"))
    if dec:
        parts.append(first_lines(read_text(dec), n=24) + "\n\n_See full: [[System/decision_support.md]]_")
    else:
        parts.append("_No decision_support.md found. Run decision_support_agent.py._")

    # 4) Reflection Highlights (raw log preview)
    refl = find_first(DATA/"reflection_log.md", SYSTEM/"reflection_log.md")
    parts.append(section("🪞 Reflection Highlights"))
    if refl:
        parts.append(first_lines(read_text(refl), n=24) + "\n\n_See full: [[data/reflection_log.md]] or [[System/reflection_log.md]]_")
    else:
        parts.append("_No reflection log found. Run reflection_agent.py._")

    # 5) Reflection Summary (GPT)
    rs = find_first(DATA/"reflection_summary.md", SYSTEM/"reflection_summary.md")
    parts.append(section("🪞 Reflection Summary (GPT)"))
    if rs:
        parts.append(first_lines(read_text(rs), n=24) + "\n\n_See full: [[System/reflection_summary.md]]_")
    else:
        parts.append("_No reflection summary found. Run reflection_summarizer_agent.py._")

    # 6) Synergy Snapshot
    synergy = find_first(VAULT/"System"/"synergy_scores.csv", SYSTEM/"synergy_scores.csv", DATA/"synergy_scores.csv")
    parts.append(section("🔗📈 Synergy Snapshot"))
    if synergy and synergy.exists():
        parts.append("- See **System/synergy_scores.csv** (top pairs and EMA shown in Reflection).")
    else:
        parts.append("_No synergy scores yet. Run synergy_refinement.py._")

    # 7) Planner status
    plan = find_first(VAULT/"Plans"/"weekly_plan.md")
    parts.append(section("📆 Weekly Plan"))
    if plan:
        parts.append(first_lines(read_text(plan), n=24) + "\n\n_See full: [[Plans/weekly_plan.md]]_")
    else:
        parts.append("_No weekly plan found. Run planner_agent.py._")

    # 8) Agent Architect Report
    arch = find_first(SYSTEM/"agent_architect_report.md")
    parts.append(section("🧩 Agent Architect — System Review"))
    if arch:
        parts.append(first_lines(read_text(arch), n=24) + "\n\n_See full: [[System/agent_architect_report.md]]_")
    else:
        parts.append("_No architect report found. Run agent_architect_agent.py._")

    md = "\n".join(parts).strip() + "\n"
    OUT_LOCAL.write_text(md, encoding="utf-8")
    try:
        OUT_VAULT.write_text(md, encoding="utf-8")
    except Exception:
        pass
    print(f"[OK] Dashboard written to:\n- Local: {OUT_LOCAL}\n- Vault: {OUT_VAULT}")

if __name__ == "__main__":
    build()
