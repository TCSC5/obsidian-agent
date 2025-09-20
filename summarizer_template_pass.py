# -*- coding: utf-8 -*-
"""
summarizer_agent.py — patched to ALWAYS ensure a full YAML template exists.

What it does
------------
1) Scans the Inbox for .md files.
2) Ensures each file has a complete YAML front matter with the standardized fields.
   - Preserves existing values; only adds missing fields.
   - Writes list-typed fields as YAML lists where appropriate.
3) Updates lightweight workflow values:
   - status: [summarized] (only if status is missing)
   - link_status: [pending] (only if missing)
   - meta_status: [metadata_pending] (only if missing)
   - created: ISO date (only if missing)
   - last_run: ISO timestamp (always updated)
   - source: 'Inbox' (only if missing)
4) Saves the file back in place (Inbox). (If you want to move it to Summaries, set MOVE_TO_SUMMARIES=True)

Environment
-----------
- Optional .env with VAULT_PATH. Otherwise defaults to C:\\Users\\<user>\\Sync.
- Edit INBOX and SUMMARIES below if your structure differs.

Usage
-----
  python summarizer_agent.py
"""

import os, re
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# -------- Config --------
VAULT_PATH = os.getenv("VAULT_PATH") or os.path.join(Path.home(), "Sync")
INBOX = os.getenv("INBOX_PATH") or os.path.join(VAULT_PATH, "00_Inbox")
SUMMARIES = os.getenv("SUMMARIES_PATH") or os.path.join(VAULT_PATH, "Summaries")
LOGS_DIR = os.getenv("LOGS_DIR") or os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Set to True if you want the agent to move files into Summaries after templating
MOVE_TO_SUMMARIES = False

# -------- YAML helpers (no external deps) --------
YAML_START = re.compile(r'^---\\s*$', re.M)
YAML_KEY_RE = re.compile(r'^(?P<k>[A-Za-z0-9_]+):\\s*(?P<v>.*)$')

# Standard template with defaults. NOTE: list-typed fields are emitted as YAML lists.
def build_yaml_template(now_date: str, now_ts: str):
    return {
        "status": ["summarized"],
        "link_status": ["pending"],
        "meta_status": ["metadata_pending"],
        "area": "",
        "resources": [],
        "type": "",
        "tags": [],
        "related": [],
        "see_also": [],
        "acceptance_criteria": [],
        "priority": "medium",
        "urgency": "normal",
        "review_needed": True,
        "created": now_date,       # only if missing
        "last_run": now_ts,        # always updated
        "synergy_score": None,
        "success_score": None,
        "source": "Inbox",
    }

def extract_yaml_block(text: str):
    """Return (yaml_str, body, had_yaml) where yaml_str excludes --- lines."""
    lines = text.splitlines()
    if not lines or not lines[0].strip().startswith('---'):
        return ("", text, False)
    try:
        end_idx = next(i for i in range(1, len(lines)) if lines[i].strip().startswith('---'))
    except StopIteration:
        # Unclosed YAML; treat as no YAML
        return ("", text, False)
    yaml_str = "\\n".join(lines[1:end_idx])
    body = "\\n".join(lines[end_idx+1:])
    return (yaml_str, body, True)

def parse_yaml_shallow(yaml_str: str):
    """
    Very shallow parser for simple 'k: v' and list forms like:
      k: []
      k:
        - item
    Returns dict[str, object], where lists are Python lists when detected.
    """
    result = {}
    lines = yaml_str.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = YAML_KEY_RE.match(line)
        if not m:
            i += 1
            continue
        k = m.group('k')
        v = m.group('v').strip()

        # Multiline list block?
        if v == "" and i + 1 < len(lines) and lines[i+1].lstrip().startswith("-"):
            items = []
            i += 1
            while i < len(lines) and lines[i].lstrip().startswith("-"):
                item = lines[i].lstrip()[1:].strip()
                # drop any trailing comments
                if " #" in item:
                    item = item.split(" #", 1)[0].strip()
                items.append(item)
                i += 1
            result[k] = items
            continue

        # Inline empty list
        if v == "[]":
            result[k] = []
        # Inline list like [a, b]
        elif v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            result[k] = [x.strip() for x in inner.split(",")] if inner else []
        else:
            # Booleans/None
            if v.lower() in ("true", "false"):
                result[k] = (v.lower() == "true")
            elif v.lower() in ("null", "none"):
                result[k] = None
            else:
                result[k] = v
        i += 1
    return result

def dump_yaml(d: dict):
    """Dump dict to YAML string (front matter body only)."""
    def emit_key(k, v):
        if isinstance(v, list):
            if not v:
                return f"{k}: []"
            return f"{k}:\n" + "\\n".join([f"  - {item}" for item in v])
        elif isinstance(v, bool):
            return f"{k}: {'true' if v else 'false'}"
        elif v is None:
            return f"{k}: null"
        else:
            return f"{k}: {v}"
    keys = [
        "status","link_status","meta_status","area","resources","type","tags",
        "related","see_also","acceptance_criteria","priority","urgency",
        "review_needed","created","last_run","synergy_score","success_score","source"
    ]
    lines = []
    for k in keys:
        if k in d:
            lines.append(emit_key(k, d[k]))
    # include any extra keys discovered
    for k in d:
        if k not in keys:
            lines.append(emit_key(k, d[k]))
    return "\\n".join(lines)

def merge_yaml(existing: dict, template: dict, now_ts: str):
    """Preserve existing keys, fill in missing from template, update last_run."""
    out = dict(template)  # start with template
    for k, v in existing.items():
        out[k] = v  # override with existing values
    # Always refresh last_run
    out["last_run"] = now_ts
    return out

def ensure_yaml_template(md_text: str):
    now_date = datetime.now().date().isoformat()
    now_ts = datetime.now().replace(microsecond=0).isoformat()
    template = build_yaml_template(now_date, now_ts)
    yaml_str, body, had_yaml = extract_yaml_block(md_text)
    if had_yaml:
        existing = parse_yaml_shallow(yaml_str)
        merged = merge_yaml(existing, template, now_ts)
    else:
        merged = template
    fm = f"---\\n{dump_yaml(merged)}\\n---"
    return fm + "\\n" + body.lstrip()

def process_markdown_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    new_text = ensure_yaml_template(text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False

def main():
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(SUMMARIES, exist_ok=True)

    processed = []
    for fname in os.listdir(INBOX):
        if not fname.lower().endswith(".md"):
            continue
        fpath = Path(INBOX) / fname
        if process_markdown_file(fpath):
            processed.append(str(fpath))

    # simple log
    log_path = Path(LOGS_DIR) / f"summarizer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    log_lines = [f"Processed {len(processed)} files", *processed]
    log_path.write_text("\\n".join(log_lines), encoding="utf-8")

    if MOVE_TO_SUMMARIES:
        for p in processed:
            src = Path(p)
            dst = Path(SUMMARIES) / src.name
            try:
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                src.unlink()
            except Exception as e:
                # leave in place on error
                pass

if __name__ == "__main__":
    main()
