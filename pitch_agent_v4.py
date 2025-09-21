#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pitch Agent (v4, with gating)
- Converts summaries with YAML status: pitch → Express/pitch/pitch_<slug>.md
- Requires summary checklist boxes checked before conversion:
  * Check Summary Accuracy
  * Curate Related Links
  * Decide Next Step
- After conversion, audits existing pitches and **updates frontmatter status**
  from 'draft' → 'ready' when required sections are filled.
- Writes logs/gating_report.md (appends to existing report).
"""

import os, re, csv, json, argparse
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

def load_settings_env():
    if load_dotenv:
        for env_candidate in [".env", "settings.env"]:
            if Path(env_candidate).exists():
                try:
                    load_dotenv(env_candidate, override=False)
                except Exception:
                    pass

def env_or_default(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v if v not in (None, "") else default

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def write_text(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def slugify(s: str) -> str:
    import re
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s or "untitled"

def parse_frontmatter(md: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*", md, re.DOTALL)
    if not m:
        return {}, md, None, None
    head = m.group(1)
    body = md[m.end():]
    d = {}
    try:
        import yaml
        d = yaml.safe_load(head) or {}
        if not isinstance(d, dict): d = {}
    except Exception:
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip()
    return d, body, m.start(), m.end()

REQ_BOXES = [
    "Check Summary Accuracy",
    "Curate Related Links",
    "Decide Next Step",
]

def checklist_passed(md_body: str):
    for label in REQ_BOXES:
        if not re.search(rf"- \[[xX]\].*{re.escape(label)}", md_body):
            return False
    return True

PITCH_CHECKLIST = """## 🎯 Pitch Review Checklist

- [ ] **One-paragraph Summary** (what/why now)
- [ ] **Problem** articulated
- [ ] **Audience / Who benefits** defined
- [ ] **Proposed Solution** clear and feasible
- [ ] **Value Proposition** (why us / differentiation)
- [ ] **Evidence / Proof** linked
- [ ] **Risks & Mitigations** captured
- [ ] **Plan & Timeline** with milestones
- [ ] **Success Metrics** (SMART) listed
- [ ] **Call to Action** (decision or next step)
"""

def build_yaml(title: str, source_link: str, created_iso: str, tags, related):
    y = [
        "---",
        f"title: {title}",
        f"source_note: {source_link}",
        f"created: {created_iso}",
        f"tags: {tags if tags else '[pitch_deck, express]'}",
        "type: pitch",
        "status: draft",
        "audience: ",
        "owner: ",
        "timeline_start: ",
        "timeline_end: ",
        f"related: {related if related else '[]'}",
        "---",
        ""
    ]
    return "\n".join(y)

def make_body(title: str, source_summary_path: str):
    return f"""# {title}

> Source: [[{source_summary_path}]]

## Summary (1 paragraph)
_Brief, compelling overview._

## Problem
_What pain are we solving? For whom?_

## Audience / Who Benefits
_Target users/buyers/stakeholders._

## Proposed Solution
_Key features or approach._

## Value Proposition
_Why now? Why us? What changes if we succeed?_

## Evidence / Proof
_Traction, research, benchmarks, references._

## Risks & Mitigations
_Biggest risks and how we’ll handle them._

## Plan & Timeline
_Milestones by week/month; rough budget/resources._

## Success Metrics
_Define SMART metrics to judge outcomes._

## Call to Action
_What decision or next step do we need?_

{PITCH_CHECKLIST}
"""

def pitch_fields_filled(md: str, fm: dict) -> bool:
    required = {
        "Summary (1 paragraph)": False,
        "Problem": False,
        "Audience": False,
        "Proposed Solution": False,
        "Value Proposition": False,
        "Evidence / Proof": False,
        "Risks & Mitigations": False,
        "Plan & Timeline": False,
        "Success Metrics": False,
        "Call to Action": False,
    }
    cur = None
    for line in md.splitlines():
        h = re.match(r"^##\s+(.*)", line.strip())
        if h:
            cur = h.group(1).strip()
            continue
        if cur:
            if re.search(r"[A-Za-z]{3,}|\[\[.*\]\]", line) and not line.strip().startswith("_"):
                for key in list(required.keys()):
                    if key in cur:
                        required[key] = True
    return all(required.values())

def update_frontmatter_status(md: str, new_status: str):
    fm, body, s, e = parse_frontmatter(md)
    if not fm: return md
    fm["status"] = new_status
    try:
        import yaml
        head = yaml.safe_dump(fm, sort_keys=False).strip()
    except Exception:
        head = "\n".join(f"{k}: {v}" for k,v in fm.items())
    return f"---\n{head}\n---\n{body}"

def main():
    load_settings_env()

    vault = Path(env_or_default("VAULT_PATH", r"C:\Users\top2e\Sync"))
    sums_rel  = env_or_default("SUMMARIES_DIR", "Summaries")
    out_rel   = env_or_default("PITCH_DIR", "Express/pitch")
    data_rel  = env_or_default("DATA_DIR", "data")
    logs_rel  = env_or_default("LOGS_DIR", "logs")

    summaries = vault / sums_rel
    out_dir   = vault / out_rel
    data_dir  = vault / data_rel
    logs_dir  = vault / logs_rel

    # Enhanced permissions checking before proceeding
    try:
        from permissions_utils import preflight_check
        required_dirs = [sums_rel, out_rel, data_rel, logs_rel]
        if not preflight_check(vault, required_dirs):
            print("❌ Permission check failed. Please run prep_summarizer_dirs.bat or check vault permissions.")
            print(f"   Vault path: {vault}")
            print("   Required directories:", ", ".join(required_dirs))
            return
    except ImportError:
        print("⚠️  Permissions utilities not available, proceeding without validation...")

    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    def load_idx(p: Path):
        try:
            return json.loads((p/"vault_index.json").read_text(encoding="utf-8"))
        except Exception:
            return []
    idx = load_idx(data_dir)
    def pick_related(base_text: str, k=5):
        def toks(s): return set(re.findall(r"[A-Za-z0-9]{3,}", s.lower()))
        base = toks(base_text)
        scored = []
        for entry in idx:
            title = entry.get("title") or Path(entry.get("path","")).stem
            blob = (str(title) + " " + " ".join(entry.get("tags") or [])).lower()
            ov = len(base & toks(blob))
            if ov>0: scored.append((ov, title.strip()))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, t in scored:
            w = f"[[{t}]]"
            if w not in out: out.append(w)
            if len(out)>=k: break
        return out

    log_path = logs_dir / "pitch_log.csv"
    write_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(["timestamp","source_summary","output_pitch","note"])

        for p in sorted(summaries.glob("*.md")):
            md = read_text(p)
            fm, body, *_ = parse_frontmatter(md)
            if (fm.get("status","").strip().lower() != "pitch"):
                continue
            if not checklist_passed(body):
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(p), "", "blocked: checklist incomplete"])
                continue
            title_guess = fm.get("title") or p.stem.replace("-", " ").title()
            created_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            source_link = f"[[{p.stem}]]"
            related = pick_related(md, 5)
            yaml = build_yaml(f"Pitch: {title_guess}", source_link, created_iso, fm.get("tags") or [], related)
            body_md = make_body(f"Pitch: {title_guess}", p.stem)
            out = out_dir / f"pitch_{slugify(p.stem)}.md"
            write_text(out, yaml + body_md)
            w.writerow([created_iso, str(p), str(out), "created"])
            print(f"[OK] Pitch generated → {out}")

    updated = 0
    for p in sorted(out_dir.glob("*.md")):
        md = read_text(p)
        fm, body, *_ = parse_frontmatter(md)
        if fm.get("status","") == "ready":
            continue
        if pitch_fields_filled(md, fm):
            new_md = update_frontmatter_status(md, "ready")
            write_text(p, new_md)
            updated += 1
    if updated:
        print(f"[OK] Updated {updated} pitch(es) to status: ready")

    rep = logs_dir / "gating_report.md"
    lines = []
    if rep.exists():
        lines.append(read_text(rep).rstrip())
    lines.append("\n## Pitches Readiness\n")
    lines.append("| File | Status | Ready? |")
    lines.append("|---|---|:---:|")
    for p in sorted(out_dir.glob("*.md")):
        md = read_text(p)
        fm, *_ = parse_frontmatter(md)
        ready = (fm.get("status","") == "ready")
        lines.append(f"| {p.name} | {fm.get('status','')} | {'✅' if ready else '❌'} |")
    write_text(rep, "\n".join(lines) + "\n")

if __name__ == "__main__":
    from pathlib import Path
    main()
