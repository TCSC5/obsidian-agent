#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Enricher / Metadata Agent (v4, with checklist & gating)
- Ensures core frontmatter exists (title, type, tags, created, status, source_note when derivative)
- Appends a Metadata Checklist to each note
- Frontmatter 'meta_status': metadata_pending → enriched when all required fields present
- Logs to logs/metadata_log.csv and appends to logs/gating_report.md
"""

import os, re, csv, argparse
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from gating_utils import read_text, write_text, parse_frontmatter, compose_frontmatter, update_status_in_md

META_CHECKLIST = """## 🧾 Metadata Checklist

- [ ] **Title** present
- [ ] **Type** present (e.g., summary, insight, pitch, note)
- [ ] **Tags** (≥ 1)
- [ ] **Created** date present
- [ ] **Status** present
- [ ] **Source** present if derivative (`source_note:`)
- [ ] **Sensitivity** reviewed (mask or ⚠️ tag if needed)
"""

REQ_LABELS = [
    "Title",
    "Type",
    "Tags",
    "Created",
    "Status",
]

def load_settings_env():
    if load_dotenv:
        for f in [".env", "settings.env"]:
            if Path(f).exists():
                try:
                    load_dotenv(f, override=False)
                except Exception:
                    pass

def env_or_default(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v if v not in (None, "") else default

def in_excluded(path: Path, exclude_folders):
    parts = [p.lower() for p in path.parts]
    return any(x.lower() in parts for x in exclude_folders)

def has_nonempty(val):
    if val is None: return False
    if isinstance(val, str): return val.strip() != ""
    if isinstance(val, list): return len(val) > 0
    return True

def main():
    load_settings_env()

    vault = Path(env_or_default("VAULT_PATH", r"C:\Users\top2e\Sync"))
    logs_rel = env_or_default("LOGS_DIR", "logs")
    # default scan: Summaries + Express (insights/pitch)
    scan_dirs = [d.strip() for d in env_or_default("META_SCAN_DIRS", "Summaries,Express").split(",") if d.strip()]
    exclude_dirs = [d.strip() for d in env_or_default("META_EXCLUDE_DIRS", "Archives,.obsidian").split(",") if d.strip()]

    parser = argparse.ArgumentParser(description="Auto-Enricher / Metadata Agent v4")
    parser.add_argument("--vault", default=str(vault))
    parser.add_argument("--logs", default=logs_rel)
    parser.add_argument("--scan", default=",".join(scan_dirs))
    parser.add_argument("--exclude", default=",".join(exclude_dirs))
    args = parser.parse_args()

    vault = Path(args.vault)
    logs = vault / args.logs
    logs.mkdir(parents=True, exist_ok=True)

    chosen_dirs = [vault / d for d in args.scan.split(",") if d.strip()]
    files = []
    for d in chosen_dirs:
        if d.exists():
            files += [p for p in d.rglob("*.md") if p.is_file() and not in_excluded(p, args.exclude.split(","))]

    log_path = logs / "metadata_log.csv"
    write_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp","file","action","note"])

        for p in files:
            md = read_text(p)
            fm, body, s, e = parse_frontmatter(md)

            changed = False
            # Ensure frontmatter keys
            defaults = {
                "title": fm.get("title") or p.stem.replace("-", " ").title(),
                "type": fm.get("type") or "",
                "tags": fm.get("tags") or [],
                "created": fm.get("created") or "",
                "status": fm.get("status") or "",
            }
            for k, v in defaults.items():
                if fm.get(k) != v:
                    fm[k] = v
                    changed = True

            # source_note required for derivative types
            if (fm.get("type") in ["summary","insight","pitch"]) and not has_nonempty(fm.get("source_note")):
                fm["source_note"] = ""
                changed = True

            # meta_status default
            if "meta_status" not in fm:
                fm["meta_status"] = "metadata_pending"
                changed = True

            if changed:
                head = compose_frontmatter(fm)
                md = f"---\n{head}\n---\n{body}"
                write_text(p, md)
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(p), "frontmatter-updated", "defaults ensured"])

            # Ensure checklist present
            if "Metadata Checklist" not in md:
                md = md.rstrip()+"\n\n"+META_CHECKLIST+"\n"
                write_text(p, md)
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(p), "checklist-appended", "metadata checklist"])

        # Gating: flip to enriched when all requirements present/non-empty
        for p in files:
            md = read_text(p)
            fm, body, s, e = parse_frontmatter(md)
            ok = has_nonempty(fm.get("title")) and has_nonempty(fm.get("type")) and has_nonempty(fm.get("tags")) and has_nonempty(fm.get("created")) and has_nonempty(fm.get("status"))
            if fm.get("type") in ["summary","insight","pitch"]:
                ok = ok and has_nonempty(fm.get("source_note"))
            if fm.get("meta_status","") != "enriched" and ok:
                fm["meta_status"] = "enriched"
                head = compose_frontmatter(fm)
                new_md = f"---\n{head}\n---\n{body}"
                write_text(p, new_md)
                w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(p), "status→enriched", "metadata complete"])

    # Append to gating report
    rep = logs / "gating_report.md"
    lines = []
    if rep.exists():
        lines.append(read_text(rep).rstrip())
    lines.append("\n## Metadata Readiness\n")
    lines.append("| File | meta_status | Ready? |")
    lines.append("|---|---|:---:|")
    for p in files:
        md = read_text(p)
        fm, body, *_ = parse_frontmatter(md)
        ok = bool(fm.get("title")) and bool(fm.get("type")) and bool(fm.get("tags")) and bool(fm.get("created")) and bool(fm.get("status"))
        if fm.get("type") in ["summary","insight","pitch"]:
            ok = ok and bool(fm.get("source_note"))
        lines.append(f"| {p.name} | {fm.get('meta_status','')} | {'✅' if ok else '❌'} |")
    write_text(rep, "\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
