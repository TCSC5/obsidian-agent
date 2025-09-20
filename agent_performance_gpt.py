# -*- coding: utf-8 -*-
"""
agent_performance_gpt.py — Evaluates agent pipeline health and generates performance insights.
"""

import os
import csv
from datetime import datetime

def load_logs(data_dir):
    logs = {}
    for name in [
        "run_log.md",
        "reflection_log.md",
        "feedback_log.md",
        "learning_loops.md"
    ]:
        path = os.path.join(data_dir, name)
        logs[name] = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                logs[name] = f.read()
    return logs

def evaluate_agent_health(logs):
    health = {}
    for name, content in logs.items():
        if content.strip():
            lines_count = len(content.strip().splitlines())
            health[name] = f"Found — {lines_count} lines"
        else:
            health[name] = "Missing or empty"
    return health

def propose_new_agents(logs):
    proposals = []
    fb = logs.get("feedback_log.md", "").lower()
    if "gaps" in fb:
        proposals.append({
            "name": "Gap Tracker Agent",
            "why": "Logs and monitors repeated feedback gaps.",
            "score": 0.75
        })
    ll = logs.get("learning_loops.md", "").lower()
    if "insight" in ll and "pattern" in ll:
        proposals.append({
            "name": "Insight Evolution Agent",
            "why": "Tracks how insights evolve into strategies.",
            "score": 0.80
        })
    rl = logs.get("run_log.md", "").lower()
    if "synergy" in rl:
        proposals.append({
            "name": "Synergy Refinement Agent",
            "why": "Adjusts tagging/link weighting based on synergy patterns.",
            "score": 0.70
        })
    if not proposals:
        proposals.append({
            "name": "—",
            "why": "No immediate improvements identified.",
            "score": 0.00
        })
    return proposals

def write_report(report_path, health_report, proposals):
    base_dir = os.path.dirname(os.path.dirname(report_path))
    synergy_csv = os.path.join(base_dir, "System", "synergy_scores.csv")
    synergy_lines = ["## Synergy Health"]

    if os.path.exists(synergy_csv):
        try:
            with open(synergy_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            coverage = len(rows)
            comps = [float(r.get("composite_score", 0) or 0) for r in rows]
            hot_count = sum(
                1 for r in rows
                if float(r.get("disagreement_abs", 0) or 0) > 0.35
            )

            mean_c = sum(comps) / coverage if coverage else 0.0
            p90 = sorted(comps)[int(0.9 * (len(comps) - 1))] if comps else 0.0

            synergy_lines += [
                f"- Notes scored: {coverage}",
                f"- Composite Avg / P90: {mean_c:.2f} / {p90:.2f}",
                f"- High disagreement (>0.35): {hot_count}",
                ""
            ]
        except Exception:
            synergy_lines += ["- Warning: Unable to parse synergy data.", ""]
    else:
        synergy_lines += ["- Info: No synergy snapshot found.", ""]

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Agent Performance Report — {now}",
        "",
        "## Health Check"
    ]
    for name, status in health_report.items():
        lines.append(f"- `{name}`: {status}")
    lines += ["", *synergy_lines, "## Proposed New Agents"]
    for p in proposals:
        lines.append(f"- **{p['name']}** — {p['why']} (score: {p['score']:.2f})")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Agent performance report saved to: {report_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")
    report_path = os.path.join(data_dir, "agent_performance_report.md")
    logs = load_logs(data_dir)
    health = evaluate_agent_health(logs)
    proposals = propose_new_agents(logs)
    write_report(report_path, health, proposals)
