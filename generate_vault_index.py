
# -*- coding: utf-8 -*-
"""
generate_vault_index.py — index markdown notes with a `folder` field

Scans VAULT_PATH for *.md (skips Archives/.obsidian by default) and writes:
  data/vault_index.json : list of {"path","folder","title","tags","mtime","size"}
"""

import os, json, time, re
from pathlib import Path

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync")
BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(parents=True, exist_ok=True)
OUT = DATA / "vault_index.json"

SKIP_DIRS = {".obsidian", ".trash", "Archives"}

def read_yaml_frontmatter(text: str):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = text[3:end]
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta

def extract_title(path: Path, text: str):
    # prefer first markdown heading
    for line in text.splitlines():
        if line.strip().startswith("# "):
            return line.strip().lstrip("# ").strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()

def main():
    rows = []
    for p in VAULT.rglob("*.md"):
        rel = p.relative_to(VAULT).as_posix()
        parts = rel.split("/")
        if parts and parts[0] in SKIP_DIRS:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        meta = read_yaml_frontmatter(text)
        title = meta.get("title") or extract_title(p, text)
        tags = meta.get("tags", "")
        folder = "/".join(parts[:-1])
        st = p.stat()
        rows.append({
            "path": rel,
            "folder": folder,
            "title": title,
            "tags": tags,
            "mtime": int(st.st_mtime),
            "size": st.st_size,
        })
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Indexed {len(rows)} notes to {OUT}")

if __name__ == "__main__":
    main()
