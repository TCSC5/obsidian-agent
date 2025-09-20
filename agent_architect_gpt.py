
import os
import re
import csv
import json
import shutil
from datetime import datetime
from collections import Counter

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
VAULT_PATH = os.getenv("VAULT_PATH", "C:/Users/top2e/Sync")
VAULT_SYSTEM_DIR = os.path.join(VAULT_PATH, "System")

# ---------- Helpers ----------
def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def detect_any(text, keywords):
    tl = text.lower()
    return any(k in tl for k in keywords)

def count_hits(text, keywords):
    tl = text.lower()
    return sum(tl.count(k) for k in keywords)

def score_proposal(signal_strength, urgency, impact):
    # Simple composite (0-100)
    return round(100 * (0.4*signal_strength + 0.3*urgency + 0.3*impact), 1)

# ---------- Load inputs ----------
logs = {
    "run_log": read_text(os.path.join(DATA_DIR, "run_log.md")),
    "reflection_log": read_text(os.path.join(DATA_DIR, "reflection_log.md")),
    "feedback_log": read_text(os.path.join(DATA_DIR, "feedback_log.md")),
    "learning_loops": read_text(os.path.join(DATA_DIR, "learning_loops.md")),
    "agent_perf": read_text(os.path.join(DATA_DIR, "agent_performance_report.md")),
}
success_rows = read_csv_rows(os.path.join(DATA_DIR, "success_log.csv"))  # optional

all_text = "\n".join(logs.values())

# ---------- Suggest improvements to existing agents ----------
NEG_FLAGS = ["error", "issue", "miss", "missed", "missing", "skip", "skipped", "stalled", "slow", "low", "outdated", "bug", "fail"]
IMPROVEMENTS = []

agents_specs = [
    ("Linking Agent",      ["link", "backlink", "orphan", "graph", "see also"]),
    ("Summarizer Agent",   ["summary", "summarizer", "too long", "too short", "tags"]),
    ("Pitch Deck Generator", ["pitch", "deck", "call to action", "convert"]),
    ("Insights Agent",     ["insight", "novel", "research gap"]),
    ("Planner Agent",      ["plan", "weekly", "carryover", "overdue", "schedule"]),
    ("Dashboard Generator",["dashboard", "visual", "chart", "graph"]),
    ("Scoring Agent",      ["impact_score", "metrics", "weights", "synergy"]),
    ("Reflection Agent",   ["reflection", "retrospective", "trend"]),
    ("Memory + Feedback Agent", ["feedback", "memory", "pattern"]),
    ("Learning Loop Agent",["repeating", "pattern", "loop"]),
    ("Agent Performance GPT", ["performance", "agent", "report"]),
]

for agent_name, signals in agents_specs:
    hits_neg = count_hits(all_text, NEG_FLAGS)
    hits_agent = count_hits(all_text, signals)
    # Heuristic: if agent topics appear and negativity present, suggest improvement
    if hits_agent > 0 and hits_neg > 0:
        IMPROVEMENTS.append({
            "agent": agent_name,
            "why": f"Detected {hits_agent} mentions around '{agent_name}' topics with {hits_neg} negative flags across logs.",
            "suggestions": [
                "Tighten prompts and acceptance criteria.",
                "Add explicit success/failure checks in logs.",
                "Increase synergy/priority weighting if appropriate.",
                "Add unit-style tests for this agent's outputs."
            ]
        })

# De-duplicate by agent
seen = set()
IMPROVEMENTS = [i for i in IMPROVEMENTS if not (i['agent'] in seen or seen.add(i['agent']))]

# ---------- Propose new agents (gaps) ----------
PROPOSALS = []

# Gap Tracker Agent
loops_text = logs["learning_loops"]
feedback_text = logs["feedback_log"]
rep_re = re.findall(r"\((\d+)x\)", loops_text)
rep_total = sum(int(n) for n in rep_re) if rep_re else 0
if rep_total > 0 or "gap" in feedback_text.lower():
    signal = min(1.0, 0.2 + rep_total*0.05)
    PROPOSALS.append({
        "name": "Gap Tracker Agent",
        "why": "Repeated issues detected in learning loops and/or explicit 'gap' mentions in feedback.",
        "triggers": ["learning_loops.md", "feedback_log.md"],
        "score": score_proposal(signal, 0.6, 0.7)
    })

# Insight Evolution Agent
if detect_any(all_text, ["insight", "pattern"]) and detect_any(all_text, ["action", "plan", "convert"]):
    PROPOSALS.append({
        "name": "Insight Evolution Agent",
        "why": "Multiple mentions of insights/patterns evolving into actions; track maturation path.",
        "triggers": ["feedback_log.md", "learning_loops.md", "reflection_log.md"],
        "score": score_proposal(0.6, 0.5, 0.8)
    })

# Synergy Refinement Agent
if detect_any(all_text, ["synergy", "links", "graph"]):
    PROPOSALS.append({
        "name": "Synergy Refinement Agent",
        "why": "Emphasis on link density/synergy suggests fine-tuning thresholds and weights.",
        "triggers": ["run_log.md", "links_log.csv", "vault_index.json"],
        "score": score_proposal(0.6, 0.4, 0.75)
    })

# Schedule Optimizer Agent
if detect_any(all_text, ["overdue", "carryover", "schedule", "time block"]):
    PROPOSALS.append({
        "name": "Schedule Optimizer Agent",
        "why": "Planning friction detected; optimize cadence, block sizes, or priority mapping.",
        "triggers": ["Plans/weekly_plan.md", "run_log.md"],
        "score": score_proposal(0.55, 0.55, 0.65)
    })

# If we have success scores, use them to propose Prompt Tuning Agent
if success_rows:
    try:
        scores = [float(r.get("score", 0)) for r in success_rows if r.get("score")]
        avg = sum(scores)/len(scores) if scores else None
    except Exception:
        avg = None
    if avg is not None and avg < 70:
        PROPOSALS.append({
            "name": "Prompt Tuning Agent",
            "why": f"Average success score {avg:.1f} < 70; revisit prompts, context windows, and templates.",
            "triggers": ["success_log.csv", "Express/"],
            "score": score_proposal(0.7, 0.6, 0.8)
        })

# Sort proposals by score desc

# --- Synergy disagreement trigger ---
try:
    synergy_csv = os.path.join(BASE_DIR, "System", "synergy_scores.csv")
    high_disagree = 0
    if os.path.exists(synergy_csv):
        with open(synergy_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    if float(row.get("disagreement_abs", 0) or 0) > 0.35:
                        high_disagree += 1
                except Exception:
                    pass
    if high_disagree >= 5:
        PROPOSALS.append({
            "name": "Tag Harmonizer + Link Seeder",
            "why": f"{high_disagree} notes show large Refined vs Legacy disagreement; likely inconsistent tags/links.",
            "triggers": ["System/synergy_scores.csv", "data/vault_index.json", "data/links_log.csv"],
            "score": 0.78
        })
except Exception:
    pass

PROPOSALS.sort(key=lambda x: x["score"], reverse=True)

# ---------- Build report ----------
ts = datetime.now().strftime("%Y-%m-%d %H:%M")
out_path = os.path.join(DATA_DIR, "agent_architect_report.md")
lines = [f"# 🧩 Agent Architect — System Review ({ts})", ""]

lines.append("## 🔧 Suggested Improvements to Existing Agents")
if not IMPROVEMENTS:
    lines.append("✅ None needed this run.")
else:
    for it in IMPROVEMENTS:
        lines.append(f"### {it['agent']}")
        lines.append(f"- **Why:** {it['why']}")
        lines.append("- **Recommendations:**")
        for s in it["suggestions"]:
            lines.append(f"  - {s}")
        lines.append("")

lines.append("## 🆕 Proposed New Agents")
if not PROPOSALS:
    lines.append("✅ None needed this run.")
else:
    lines.append("| Priority | Proposed Agent | Score | Rationale | Triggers |")
    lines.append("|---:|---|---:|---|---|")
    for i, p in enumerate(PROPOSALS, 1):
        lines.append(f"| {i} | {p['name']} | {p['score']:.1f} | {p['why']} | {', '.join(p['triggers'])} |")

with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# Sync to vault/System
try:
    os.makedirs(VAULT_SYSTEM_DIR, exist_ok=True)
    shutil.copy2(out_path, os.path.join(VAULT_SYSTEM_DIR, "agent_architect_report.md"))
    print(f"✅ Architect report: {out_path}")
    print(f"✅ Synced to vault: {os.path.join(VAULT_SYSTEM_DIR, 'agent_architect_report.md')}")
except Exception as e:
    print(f"⚠️ Sync failed: {e}")
