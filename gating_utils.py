# gating_utils.py
# Reusable helpers for Obsidian Agent gating & checklists.

import re
from pathlib import Path
from typing import Dict, Tuple

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def write_text(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def parse_frontmatter(md: str) -> Tuple[Dict, str, int, int]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*", md, re.DOTALL)
    if not m:
        return {}, md, -1, -1
    head = m.group(1)
    body = md[m.end():]
    data = {}
    try:
        import yaml
        data = yaml.safe_load(head) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    return data, body, m.start(), m.end()

def compose_frontmatter(data: Dict) -> str:
    try:
        import yaml
        return yaml.safe_dump(data, sort_keys=False).strip()
    except Exception:
        return "\n".join(f"{k}: {v}" for k, v in data.items())

def update_status_in_md(md: str, new_status: str) -> str:
    fm, body, s, e = parse_frontmatter(md)
    if s == -1:
        return md
    fm["status"] = new_status
    head = compose_frontmatter(fm)
    return f"---\n{head}\n---\n{body}"

def checklist_passed(md_body: str, labels) -> bool:
    for label in labels:
        if not re.search(rf"- \[[xX]\].*{re.escape(label)}", md_body):
            return False
    return True

def sections_filled(md_body: str, section_names) -> bool:
    # A section is filled if any non-placeholder content exists beneath its heading.
    required = {name: False for name in section_names}
    cur = None
    for line in md_body.splitlines():
        h = re.match(r"^##\s+(.*)", line.strip())
        if h:
            cur = h.group(1).strip()
            continue
        if cur and any(name in cur for name in required.keys()):
            if re.search(r"[A-Za-z]{3,}|\[\[.*\]\]", line) and not line.strip().startswith("_"):
                for name in list(required.keys()):
                    if name in cur:
                        required[name] = True
    return all(required.values())
