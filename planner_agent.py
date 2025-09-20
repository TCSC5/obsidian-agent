# -*- coding: utf-8 -*-
"""
planner_agent.py — Generate a weekly plan from carryover tasks + high-priority Express items
"""

import os, re
from datetime import datetime
from pathlib import Path

# --- Robust .env loader ---
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
except Exception:
    pass

# Diagnostic
_k = os.getenv("OPENAI_API_KEY")
print(f"[env] OPENAI_API_KEY loaded? {'yes' if _k else 'no'}")

# --- Optional OpenAI client ---
_use_gpt = False
client = None
try:
    from openai import OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        client = OpenAI()  # reads key from env
        _use_gpt = True
except Exception:
    _use_gpt = False
    client = None

# Paths
VAULT = Path(os.getenv("VAULT_PATH", r"C:\\Users\\top2e\\Sync"))
PLANS = VAULT / "Plans"
PLANS.mkdir(parents=True, exist_ok=True)

previous_plan = PLANS / "weekly_plan.md"
new_plan = PLANS / "weekly_plan.md"

# Step 1: Extract unfinished tasks from previous plan
carryover_tasks = []
if previous_plan.exists():
    lines = previous_plan.read_text(encoding="utf-8", errors="replace").splitlines()
    carryover_tasks = [line.strip() for line in lines if re.match(r"^- \[ \]", line)]

# Step 2: Collect high priority items from Express
express_dirs = [VAULT / "Express" / "pitch", VAULT / "Express" / "insights"]
priority_items = []

def extract_yaml_frontmatter(filepath: Path):
    content = filepath.read_text(encoding="utf-8", errors="replace")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            yaml = content[3:end].strip()
            return dict(re.findall(r"(\w+):\s*(.+)", yaml))
    return {}

def extract_title_and_body(filepath: Path):
    lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    title = filepath.stem
    for line in lines:
        if line.strip().lower().startswith("# "):
            title = line.strip("# ").strip()
            break
    content = "\n".join(lines)
    return title, content

for folder in express_dirs:
    if not folder.exists():
        continue
    for fpath in folder.glob("*.md"):
        meta = extract_yaml_frontmatter(fpath)
        if (meta.get("priority","").lower() == "high") or (meta.get("urgency","").lower() == "high"):
            title, body = extract_title_and_body(fpath)
            priority_items.append((title, body, fpath.name))

# Step 3: Convert priority items into GPT-driven action bullets (optional)
gpt_tasks = []
for title, body, fname in priority_items:
    if not _use_gpt or client is None:
        # Heuristic fallback: make a single generic task per item
        gpt_tasks.append(f"- [ ] Review '{title}' and define next action")
        continue

    prompt = f"""From the following markdown note, extract 1–3 high-value action items as a checklist for this week.
Title: {title}
---
{body[:1200]}
---
Respond ONLY with lines like:
- [ ] First task
- [ ] Second task
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        task_lines = [line for line in (res.choices[0].message.content or "").splitlines() if line.strip().startswith("- [ ]")]
        if task_lines:
            gpt_tasks.extend(task_lines)
        else:
            gpt_tasks.append(f"- [ ] Define next action for '{title}'")
    except Exception as e:
        gpt_tasks.append(f"- [ ] (GPT error) Define next action for '{title}'")

# Step 4: Write the new weekly plan
lines = []
lines.append("# 📆 Weekly Plan (Generated)")
lines.append("")

if carryover_tasks:
    lines.append("## 🧾 Carryover Tasks")
    lines.extend(carryover_tasks)
    lines.append("")

if gpt_tasks:
    lines.append("## 🔥 New Priority Projects")
    lines.extend(gpt_tasks)
    lines.append("")

lines.append(f"---\nGenerated on: {datetime.now().strftime('%Y-%m-%d')}\n")

new_plan.write_text("\n".join(lines), encoding="utf-8")
print(f"✅ Weekly plan written to {new_plan}")
