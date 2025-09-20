
import os
import re
from datetime import datetime
from collections import defaultdict

from dotenv import load_dotenv, find_dotenv  # optional if available

# --- Setup ---
try:
    load_dotenv(find_dotenv())
except Exception:
    pass

VAULT_PATH = os.getenv("VAULT_PATH", "C:/Users/top2e/Sync")
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_MD = os.path.join(DATA_DIR, "insight_evolution.md")
OUT_CSV = os.path.join(DATA_DIR, "insight_evolution.csv")

# Heuristic target folders in vault
INSIGHTS_DIR = os.path.join(VAULT_PATH, "Express", "insights")
PITCH_DIR     = os.path.join(VAULT_PATH, "Express", "pitch")
PLANS_DIR     = os.path.join(VAULT_PATH, "Plans")
SUMMARIES_DIR = os.path.join(VAULT_PATH, "Summaries")

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def list_md(folder):
    if not os.path.exists(folder):
        return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".md")]

def first_heading_or_name(path, content=None):
    if content is None:
        content = read_text(path)
    m = re.search(r'^\s*#\s+(.*)', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # fallback to filename
    return os.path.splitext(os.path.basename(path))[0]

def extract_created_date(path):
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""

def count_mentions(text, key):
    key_q = re.escape(key)
    return len(re.findall(key_q, text, flags=re.IGNORECASE))

def gather_insights():
    insights = {}
    for p in list_md(INSIGHTS_DIR):
        content = read_text(p)
        title = first_heading_or_name(p, content)
        insights[title] = {
            "title": title,
            "path": os.path.relpath(p, VAULT_PATH).replace("\\", "/"),
            "first_seen": extract_created_date(p),
            "pitch_refs": 0,
            "plan_refs": 0,
            "completed_checks": 0,
            "summary_refs": 0,
        }
    return insights

def scan_refs(insights):
    # Build regex keys once
    titles = list(insights.keys())
    if not titles:
        return
    pitch_files = list_md(PITCH_DIR)
    plan_files  = list_md(PLANS_DIR)
    summary_files = list_md(SUMMARIES_DIR)

    # Scan pitch decks
    for fp in pitch_files:
        text = read_text(fp)
        for t in titles:
            insights[t]["pitch_refs"] += count_mentions(text, t)

    # Scan plans (look for checkboxes and mentions)
    for fp in plan_files:
        text = read_text(fp)
        for t in titles:
            cnt = count_mentions(text, t)
            if cnt:
                insights[t]["plan_refs"] += cnt
            # completed checkboxes: - [x] ... title
            insights[t]["completed_checks"] += len(re.findall(r"- \[x\].{0,40}" + re.escape(t), text, flags=re.IGNORECASE))

    # Scan summaries (could indicate progress)
    for fp in summary_files:
        text = read_text(fp)
        for t in titles:
            insights[t]["summary_refs"] += count_mentions(text, t)

def infer_status(row):
    # Simple state machine
    if row["completed_checks"] > 0:
        return "completed"
    if row["plan_refs"] > 0:
        return "planned"
    if row["pitch_refs"] > 0:
        return "pitched"
    if row["summary_refs"] > 0:
        return "candidate"
    return "idea"

def next_step(status):
    return {
        "idea": "Draft a 5-bullet pitch or add to Weekly Plan if actionable.",
        "candidate": "Decide: promote to pitch or schedule a test task.",
        "pitched": "Add acceptance criteria & schedule first task in Plans.",
        "planned": "Execute; mark checkboxes [x] when complete.",
        "completed": "Archive learning; consider writing a short case note.",
    }.get(status, "Review manually.")

def write_outputs(insights):
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = []
    for title, r in sorted(insights.items(), key=lambda kv: (infer_status(kv[1]), kv[0])):
        status = infer_status(r)
        ns = next_step(status)
        rows.append({
            "Insight": title,
            "First Seen": r["first_seen"],
            "PitchRefs": r["pitch_refs"],
            "PlanRefs": r["plan_refs"],
            "CompletedChecks": r["completed_checks"],
            "SummaryRefs": r["summary_refs"],
            "Status": status,
            "NextStep": ns,
            "Path": r["path"],
        })

    # Markdown
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# 🔄 Insight Evolution Tracker — {now}", "",
          "| Insight | Status | First Seen | Pitch | Plan | Done | Summary | Next Step |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        md.append(f"| [[{r['Path']}|{r['Insight']}]] | **{r['Status']}** | {r['First Seen']} | {r['PitchRefs']} | {r['PlanRefs']} | {r['CompletedChecks']} | {r['SummaryRefs']} | {r['NextStep']} |")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # CSV
    import csv
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["Insight","First Seen","PitchRefs","PlanRefs","CompletedChecks","SummaryRefs","Status","NextStep","Path"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Optional vault sync
    try:
        system_dir = os.path.join(VAULT_PATH, "System")
        os.makedirs(system_dir, exist_ok=True)
        import shutil
        shutil.copy2(OUT_MD, os.path.join(system_dir, "insight_evolution.md"))
        print(f"✅ Insight evolution written to: {OUT_MD}")
        print(f"✅ Synced to vault: {os.path.join(system_dir, 'insight_evolution.md')}")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")

def main():
    insights = gather_insights()
    if not insights:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write("# 🔄 Insight Evolution Tracker\n\n_No insights found in vault. Expected folder:_ `Express/insights/`.")
        print("⚠️ No insights found — created placeholder file.")
        return
    scan_refs(insights)
    write_outputs(insights)

if __name__ == "__main__":
    main()
