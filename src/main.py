# -*- coding: utf-8 -*-
"""
main.py — Obsidian vault linker using Chat Completions API.

Env:
  VAULT_PATH, OPENAI_API_KEY
Index:
  ./data/vault_index.json
"""

import os, sys, json, csv, re
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

# --- UTF‑8-safe console on Windows ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def safe_print(*args):
    try:
        print(*args)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((" ".join(str(a) for a in args) + "\n").encode(enc, errors="replace"))

# --- Env & paths ---
load_dotenv(find_dotenv())
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE, "data"); os.makedirs(DATA_DIR, exist_ok=True)

VAULT_PATH = os.getenv("VAULT_PATH")
if not VAULT_PATH or not os.path.isdir(VAULT_PATH):
    safe_print(f"ERROR: VAULT_PATH invalid -> {VAULT_PATH!r}"); sys.exit(2)

INDEX_PATH = os.path.join(DATA_DIR, "vault_index.json")
if not os.path.exists(INDEX_PATH):
    safe_print(f"ERROR: Index not found -> {INDEX_PATH}"); sys.exit(3)

LOG_CSV = os.path.join(DATA_DIR, "links_log.csv")
LOG_JSON = os.path.join(DATA_DIR, "links_log.json")
inbox = os.path.join(VAULT_PATH, "00_Inbox"); os.makedirs(inbox, exist_ok=True)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    safe_print("ERROR: OPENAI_API_KEY not set"); sys.exit(4)

client = OpenAI(api_key=api_key)

# --- Helpers ---
def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_tags_and_context(path, content):
    tags, folder = [], os.path.relpath(os.path.dirname(path), VAULT_PATH)
    if content.startswith("---"):
        try:
            lines = content.split("\n")
            if lines and lines[0].strip() == "---":
                idx = lines[1:].index("---") + 1 if "---" in lines[1:] else len(lines)
                yaml = "\n".join(lines[1:idx])
                m = re.search(r"^tags:\s*\[(.*?)\]", yaml, re.MULTILINE)
                if m:
                    tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
        except:
            pass
    return tags, folder

def gpt_summarize_with_links(content, index, tags, folder):
    summary = "\n".join(f"- {it.get('title','(untitled)')}: {it.get('preview','')}" for it in index[:20])
    prompt = (
      f"You are a knowledge assistant.\nFolder: {folder}\n"
      f"Tags: {', '.join(tags) if tags else '(none)'}\n\n"
      f"{content}\n\nOther notes:\n{summary}\n\n"
      "Which titles are most related? List one per line."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return [ln.strip("-* ").strip() for ln in (resp.choices[0].message.content or "").splitlines() if ln.strip()]

def log_relationships(src, related):
    ts = datetime.now().isoformat(timespec="seconds")
    recs = [{"source": src, "target": r, "timestamp": ts} for r in related]
    new = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source","target","timestamp"])
        if new: w.writeheader()
        w.writerows(recs)
    data = []
    if os.path.exists(LOG_JSON):
        try:
            with open(LOG_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = []
    data.extend(recs)
    with open(LOG_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_backlinks(src, related):
    for r in related:
        path = os.path.join(VAULT_PATH, f"{r}.md")
        if not os.path.exists(path): continue
        lines = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except:
            with open(path, "r", errors="replace") as f:
                lines = f.read().splitlines()
        ref = f"[[{src}]]"
        if any(ref in ln for ln in lines): continue
        if lines and lines[0].strip() == "---" and "---" in lines[1:]:
            idx = lines[1:].index("---") + 1
            lines.insert(idx+1, "related:"); lines.insert(idx+2, f"  - {ref}")
        else:
            lines = ["---", f"title: {r}", "tags: []", "related:", f"  - {ref}", "---"] + lines
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        safe_print(f"Backlinked {src} → {r}")

def update_note(path, related, tags):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except:
        with open(path, "r", errors="replace") as f:
            lines = f.read().splitlines()
    title = os.path.splitext(os.path.basename(path))[0]
    links = [f"[[{t}]]" for t in related]
    if lines and lines[0].strip() == "---" and "---" in lines[1:]:
        idx = lines[1:].index("---") + 1
        lines.insert(idx+1, "related:")
        for link in links:
            lines.insert(idx+2, f"  - {link}")
    else:
        lines = ["---", f"title: {title}", f"tags: [{', '.join(tags)}]" if tags else "tags: []", "related:", *links, "---"] + lines
    if links:
        lines.append(""); lines.append("## See also")
        for link in links:
            lines.append(f"- {link}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def process_note(p):
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    tags, folder = extract_tags_and_context(p, content)
    index = load_index()
    rel = gpt_summarize_with_links(content, index, tags, folder)
    update_note(p, rel, tags)
    src = os.path.splitext(os.path.basename(p))[0]
    log_relationships(src, rel)
    ensure_backlinks(src, rel)
    safe_print(f"Processed {os.path.basename(p)}")

if __name__ == "__main__":
    safe_print("✅ VAULT_PATH:", VAULT_PATH)
    safe_print("📂 Inbox:", inbox)
    files = [f for f in os.listdir(inbox) if f.endswith(".md")]
    if not files:
        safe_print("No files — exiting."); sys.exit(0)
    for fname in files:
        try:
            process_note(os.path.join(inbox, fname))
        except Exception as e:
            safe_print(f"ERROR {fname}: {e}")
