
import os
import re
import csv
import json
from collections import Counter
from datetime import datetime
import shutil

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
VAULT_PATH = os.getenv("VAULT_PATH", "C:/Users/top2e/Sync")
VAULT_SYSTEM_DIR = os.path.join(VAULT_PATH, "System")

# Inputs
FILES_MD = {
    "run_log": os.path.join(DATA_DIR, "run_log.md"),
    "reflection": os.path.join(DATA_DIR, "reflection_log.md"),
    "feedback": os.path.join(DATA_DIR, "feedback_log.md"),
    "loops": os.path.join(DATA_DIR, "learning_loops.md"),
}
FILES_CSV = {
    "success": os.path.join(DATA_DIR, "success_log.csv"),  # optional
}

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def read_csv_rows(path):
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    return rows

def score_proposal(signal_strength: float, urgency: float, impact: float) -> float:
    # Weighted composite score (0-100)
    return round(100 * (0.4 * signal_strength + 0.3 * urgency + 0.3 * impact), 1)

def detect_patterns(text: str, keywords):
    text_l = text.lower()
    return sum(k in text_l for k in keywords)

def build_proposals(md, rows):
    proposals = []

    # Signals from logs
    feedback = md["feedback"]
    loops = md["loops"]
    reflection = md["reflection"]
    runlog = md["run_log"]

    # 1) Repeated suggestions / issues -> "Gap Tracker Agent"
    rep_count = len(re.findall(r"\(.*x\)", loops))
    if rep_count > 0 or "gap" in feedback.lower():
        signal = min(1.0, 0.2 + 0.1 * rep_count)
        urgency = 0.7 if "gap" in feedback.lower() else 0.4
        impact = 0.7
        proposals.append({
            "name": "Gap Tracker Agent",
            "why": "Repeated issues detected in learning loops and/or feedback mentions gaps.",
            "triggers": ["learning_loops.md", "feedback_log.md"],
            "score": score_proposal(signal, urgency, impact)
        })

    # 2) Insight-to-Action Evolution -> "Insight Evolution Agent"
    # heuristic: presence of "insight", "action", "pattern" across logs
    evo_hits = detect_patterns(loops + feedback + reflection, ["insight", "action", "pattern"])
    if evo_hits >= 2:
        signal = min(1.0, 0.2 * evo_hits)
        urgency = 0.5
        impact = 0.8
        proposals.append({
            "name": "Insight Evolution Agent",
            "why": "Multiple mentions of insights/patterns suggest tracking maturation into actions.",
            "triggers": ["feedback_log.md", "learning_loops.md", "reflection_log.md"],
            "score": score_proposal(signal, urgency, impact)
        })

    # 3) Synergy / link density tuning -> "Synergy Refinement Agent"
    if "synergy" in runlog.lower() or "links" in runlog.lower():
        signal = 0.6
        urgency = 0.4
        impact = 0.7
        proposals.append({
            "name": "Synergy Refinement Agent",
            "why": "Run snapshot indicates emphasis on link counts/synergy – tune weights and tagging.",
            "triggers": ["run_log.md", "vault_index.json", "links_log.csv"],
            "score": score_proposal(signal, urgency, impact)
        })

    # 4) Underperforming outputs -> "Prompt Tuning Agent"
    # heuristic: if success_log.csv exists and average score < threshold
    avg_score = None
    if rows:
        try:
            scores = [float(r.get("score", 0)) for r in rows if r.get("score")]
            if scores:
                avg_score = sum(scores) / len(scores)
        except Exception:
            avg_score = None
    if avg_score is not None and avg_score < 70:
        signal = 0.7
        urgency = 0.6
        impact = 0.8
        proposals.append({
            "name": "Prompt Tuning Agent",
            "why": f"Average success score {avg_score:.1f} < 70; prompts and templates may need refinement.",
            "triggers": ["success_log.csv", "Summaries/", "Express/"],
            "score": score_proposal(signal, urgency, impact)
        })

    # 5) Planner friction -> "Schedule Optimizer Agent"
    if detect_patterns(reflection + feedback, ["time", "schedule", "overdue", "carryover"]) >= 2:
        signal = 0.6
        urgency = 0.5
        impact = 0.6
        proposals.append({
            "name": "Schedule Optimizer Agent",
            "why": "Multiple mentions of time/scheduling/overdue indicate cadence misalignment.",
            "triggers": ["Plans/weekly_plan.md", "run_log.md"],
            "score": score_proposal(signal, urgency, impact)
        })

    # Sort by score desc
    proposals.sort(key=lambda x: x["score"], reverse=True)
    return proposals

def main():
    md = {k: read_text(v) for k, v in FILES_MD.items()}
    rows = read_csv_rows(FILES_CSV["success"]) if os.path.exists(FILES_CSV["success"]) else []
    proposals = build_proposals(md, rows)

    out_path = os.path.join(DATA_DIR, "agent_proposals.md")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 🧩 Agent Architect — Proposals ({ts})", ""]
    if not proposals:
        lines.append("✅ No proposals at this time — system looks stable.")
    else:
        lines.append("| Priority | Proposed Agent | Score | Rationale | Triggers |")
        lines.append("|---:|---|---:|---|---|")
        for i, p in enumerate(proposals, 1):
            lines.append(f"| {i} | {p['name']} | {p['score']:.1f} | {p['why']} | {', '.join(p['triggers'])} |")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Sync to vault/System
    try:
        os.makedirs(VAULT_SYSTEM_DIR, exist_ok=True)
        shutil.copy2(out_path, os.path.join(VAULT_SYSTEM_DIR, "agent_proposals.md"))
        print(f"✅ Proposals saved: {out_path}")
        print(f"✅ Synced to vault: {os.path.join(VAULT_SYSTEM_DIR, 'agent_proposals.md')}")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")

if __name__ == "__main__":
    main()
