# -*- coding: utf-8 -*-
"""
decision_support_agent.py — GPT-powered Decision Support

Purpose:
- Fuse multiple signals (Synergy, Prioritizer YAML, Insight Evolution) + file content
- Produce a ranked "Top 5 to Act On This Week" with reasoning + next action

Inputs:
- System/synergy_scores.csv
- Express/pitch/*.md and Express/insights/*.md (YAML: priority, urgency, actionability, relevance)
- System/insight_evolution.md (optional, to include lifecycle status)
- (Optional) Plans/weekly_plan.md to avoid duplicating already planned items

Outputs:
- data/decision_support.md  (primary)
- System/decision_support.md (synced copy for vault visibility)

Env:
- VAULT_PATH (defaults to C:\\Users\\top2e\\Sync)
- OPENAI_API_KEY (optional; if absent, uses deterministic heuristics)
"""

import os, re, csv, json
from pathlib import Path
from datetime import datetime

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

# OpenAI (optional) — safe, optional client
_use_gpt = False
client = None
try:
    # The new OpenAI SDK reads OPENAI_API_KEY from env automatically
    from openai import OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        client = OpenAI()
        _use_gpt = True
except Exception:
    _use_gpt = False
    client = None

VAULT  = Path(os.environ.get("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
BASE   = Path(__file__).parent.resolve()
DATA   = BASE / "data"
SYSTEM = VAULT / "System"
DATA.mkdir(parents=True, exist_ok=True)
SYSTEM.mkdir(parents=True, exist_ok=True)

EXPRESS_PITCH    = VAULT / "Express" / "pitch"
EXPRESS_INSIGHTS = VAULT / "Express" / "insights"
SYNERGY_CSV      = SYSTEM / "synergy_scores.csv"
EVOLUTION_MD     = SYSTEM / "insight_evolution.md"
PLANNER_MD       = VAULT / "Plans" / "weekly_plan.md"

OUT_MD       = DATA / "decision_support.md"
OUT_MD_VAULT = SYSTEM / "decision_support.md"

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def frontmatter(md: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", md, re.DOTALL)
    if not m:
        return {}, md
    head = m.group(1)
    body = md[m.end():]
    d = {}
    try:
        import yaml
        d = yaml.safe_load(head) or {}
        if not isinstance(d, dict):
            d = {}
    except Exception:
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip()
    return d, body

def clamp01(x):
    try:
        x = float(x)
        if x < 0: return 0.0
        if x > 1: return 1.0
        return x
    except Exception:
        return 0.0

def prio_to_num(s: str):
    s = (s or "").strip().lower()
    if s.startswith("h"): return 1.0
    if s.startswith("m"): return 0.5
    if s.startswith("l"): return 0.0
    return 0.0

def load_synergy():
    scores = {}
    if not SYNERGY_CSV.exists():
        return scores
    with SYNERGY_CSV.open(encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for row in rd:
            path = (row.get("note_path") or "").replace("\\", "/")
            try:
                s = float(row.get("composite_score") or 0)
            except Exception:
                s = 0.0
            scores[path] = s
    return scores

def parse_evolution():
    status_map = {}
    if not EVOLUTION_MD.exists():
        return status_map
    md = read_text(EVOLUTION_MD)
    # rows look like: | [[Express/insights/insight_foo.md|Insight: Foo]] | **planned** | 2025-08-20 | ...
    for line in md.splitlines():
        if line.startswith("| [[") and "]] |" in line:
            try:
                parts = [p.strip() for p in line.strip("|").split("|")]
                link = parts[0]  # [[path|Title]]
                status = re.sub(r"\*", "", parts[1]).strip().lower()
                m = re.search(r"\[\[(.+?)\|", link)
                rel_path = m.group(1) if m else ""
                status_map[rel_path] = status
            except Exception:
                pass
    return status_map

def list_candidates():
    files = []
    for root in [EXPRESS_PITCH, EXPRESS_INSIGHTS]:
        if not root.exists():
            continue
        for p in root.glob("*.md"):
            files.append(p)
    return files

def already_planned_titles():
    titles = set()
    if not PLANNER_MD.exists():
        return titles
    md = read_text(PLANNER_MD)
    for m in re.finditer(r"^- \[ \]\s*(.+)$", md, flags=re.MULTILINE):
        titles.add(m.group(1).strip()[:80])
    return titles

def build_features():
    synergy   = load_synergy()
    evolution = parse_evolution()
    planned   = already_planned_titles()

    candidates = []
    for p in list_candidates():
        rel_path = str(p.relative_to(VAULT)).replace("\\", "/")
        md = read_text(p)
        fm, body = frontmatter(md)
        tmatch = re.search(r"^\s*#\s+(.+)$", md, flags=re.MULTILINE)
        title = (tmatch.group(1).strip() if tmatch else p.stem).strip()

        # numeric signals
        pr = prio_to_num(fm.get("priority"))
        ur = prio_to_num(fm.get("urgency"))
        ac = prio_to_num(fm.get("actionability"))
        try:
            rel = float(fm.get("relevance", 0))
        except Exception:
            rel = 0.0
        rel_n = max(0.0, min(1.0, rel/10.0))

        syn = 0.0
        if rel_path in synergy:
            syn = synergy[rel_path]
        else:
            base = os.path.basename(rel_path)
            for k, v in synergy.items():
                if os.path.basename(k) == base:
                    syn = v
                    break

        status = evolution.get(rel_path, "unknown")

        # basic penalty if already completed/planned
        status_penalty = 0.0
        if status == "completed": status_penalty = 0.25
        if status == "planned":   status_penalty = 0.10

        composite = (
            0.52*syn +
            0.18*((pr+ur)/2.0) +
            0.16*ac +
            0.14*rel_n
        ) * (1.0 - status_penalty)

        snippet = re.sub(r"\s+", " ", md).strip()[:900]

        candidates.append({
            "title": title,
            "rel_path": rel_path,
            "synergy": round(syn, 3),
            "priority": fm.get("priority",""),
            "urgency": fm.get("urgency",""),
            "actionability": fm.get("actionability",""),
            "relevance": rel,
            "status": status,
            "composite": round(composite, 4),
            "snippet": snippet
        })

    candidates.sort(key=lambda x: x["composite"], reverse=True)
    return candidates

def gpt_reason(item):
    if not _use_gpt or client is None:
        # heuristic fallback
        reasons = []
        if item["synergy"] >= 0.6: reasons.append("high network synergy")
        if (item["priority"] or "").lower().startswith("h"): reasons.append("high priority")
        if (item["urgency"] or "").lower().startswith("h"): reasons.append("high urgency")
        if item["status"] in ("idea","candidate"): reasons.append(f"stuck at {item['status']} stage")
        if not reasons: reasons.append("good overall signal")
        action = "Schedule a first concrete task this week with an owner and date."
        if "pitch" in item["rel_path"]:
            action = "Add acceptance criteria to the pitch and schedule a kickoff task."
        if "insights" in item["rel_path"]:
            action = "Promote this insight to a pitch or schedule a small test in Plans."
        return " • ".join(reasons).capitalize() + ".", action

    prompt = f"""
You are a decision-support assistant prioritizing knowledge work.
Given these signals for one note, explain *briefly* why it deserves attention and propose one concrete next action.

Return two lines exactly:
Reason: <one sentence>
Action: <one sentence starting with a verb>

Signals (JSON):
{json.dumps({k:v for k,v in item.items() if k!='snippet'}, indent=2)}
Content sample:
\"\"\"
{item['snippet']}
\"\"\"
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content": prompt}],
            temperature=0.2
        )
        text = res.choices[0].message.content or ""
        m1 = re.search(r"Reason:\s*(.+)", text, re.IGNORECASE)
        m2 = re.search(r"Action:\s*(.+)", text, re.IGNORECASE)
        reason = (m1.group(1).strip() if m1 else text.strip().splitlines()[0][:200])
        action = (m2.group(1).strip() if m2 else "Define a concrete next step and schedule it in Plans.")
        return reason, action
    except Exception:
        return "Good overall signal based on synergy and priority.", "Define a concrete next step and schedule it in Plans."

def build_report(items, top_n=5):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 🧭 Decision Support — Top {top_n} to Act On ({now})", ""]
    if not items:
        lines.append("_No candidates found in Express folders._")
    else:
        head = "| Rank | Note | Status | Synergy | Prio | Urg | Act | Rel | Why | Next Action |"
        sep  = "|---:|---|---|---:|:--:|:--:|:--:|---:|---|---|"
        lines += [head, sep]
        for i, it in enumerate(items[:top_n], 1):
            reason, action = gpt_reason(it)
            link = f"[[{it['rel_path']}|{it['title']}]]"
            lines.append(
                f"| {i} | {link} | {it['status']} | {it['synergy']:.2f} | "
                f"{it['priority'] or '—'} | {it['urgency'] or '—'} | {it['actionability'] or '—'} | "
                f"{it['relevance'] or 0:.1f} | {reason} | {action} |"
            )

    lines += [
        "",
        "### Scoring Notes",
        "- Composite = 0.52·Synergy + 0.18·Avg(Priority,Urgency) + 0.16·Actionability + 0.14·Relevance (0–10 → 0–1).",
        "- Penalties: -10% if planned, -25% if completed in Insight Evolution.",
        ""
    ]
    md = "\n".join(lines)
    OUT_MD.write_text(md, encoding="utf-8")
    try:
        OUT_MD_VAULT.write_text(md, encoding="utf-8")
    except Exception:
        pass
    print(f"✅ Decision support written to:\n- {OUT_MD}\n- {OUT_MD_VAULT}")

def main():
    items = build_features()
    build_report(items, top_n=5)

if __name__ == "__main__":
    main()
