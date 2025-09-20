#!/usr/bin/env python3
# backfill_learning.py — note-level domain/author/tag stats + per-token enrichment + CSV report
#
# Builds learning_db.json and learning_report.csv
# - JSON at: <vault>/Resources/system/learning_db.json
# - CSV  at: <vault>/Resources/system/learning_report.csv
#
# Usage:
#   python backfill_learning.py --vault "C:/Users/You/Sync" [--rel "Resources/learning_inputs"] [--out "<path to json>"] [--dry-run]

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict, Counter

FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?')

STOPWORDS = {
    "the","a","an","and","or","of","for","with","to","from","in","on","at","by",
    "is","are","be","as","it","that","this","these","those"
}

@dataclass
class NoteMeta:
    path: Path
    title: str
    domain: str
    author: str
    tags: list[str]

def parse_args():
    ap = argparse.ArgumentParser(description="Build learning_db.json from note frontmatters.")
    ap.add_argument("--vault", required=True, help="Root of your Obsidian vault")
    ap.add_argument("--rel", default=r"Resources/learning_inputs", help="Relative path to learning inputs (within vault)")
    ap.add_argument("--out", default=None, help="Output JSON path. Default: <vault>/Resources/system/learning_db.json")
    ap.add_argument("--dry-run", action="store_true", help="Compute and print stats but do not write JSON/CSV")
    return ap.parse_args()

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def parse_yaml_frontmatter(txt: str) -> dict:
    m = FRONTMATTER_RE.match(txt)
    if not m:
        return {}
    raw = m.group(1)
    meta = {}
    current_key = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_\-]+:\s*", line):
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val == "":
                meta[key] = []
                current_key = key
            else:
                meta[key] = val
                current_key = key
        elif line.lstrip().startswith("- "):
            if current_key is None:
                continue
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(line.strip()[2:].strip())
        else:
            if current_key and isinstance(meta.get(current_key), str):
                meta[current_key] = (meta[current_key] + "\n" + line.rstrip())
    if "tags" in meta and isinstance(meta["tags"], str):
        parts = re.split(r"[,\s]+", meta["tags"])
        meta["tags"] = [t for t in (p.strip() for p in parts) if t]
    return meta

def tokenize_title(title: str) -> list[str]:
    if not title:
        return []
    toks = re.split(r"[^A-Za-z0-9]+", title.lower())
    return [t for t in toks if t and t not in STOPWORDS and len(t) >= 2]

def ensure_dict(d: dict, *keys: str) -> dict:
    cur = d
    for k in keys:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    return cur

def bump(d: dict, key: str, inc: int = 1):
    d[key] = int(d.get(key, 0)) + inc

def collect_notes(vault: Path, rel: str) -> list[NoteMeta]:
    root = (vault / Path(rel)).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Input folder not found: {root}")
    notes: list[NoteMeta] = []
    for p in root.rglob("*.md"):
        txt = read_text(p)
        fm = parse_yaml_frontmatter(txt)
        title = fm.get("title") or p.stem
        domain = (fm.get("domain") or "").strip() or "unknown"
        author = (fm.get("author") or "").strip() or "unknown"
        tags = fm.get("tags") or []
        tags = [str(t).strip() for t in tags if str(t).strip()]
        notes.append(NoteMeta(path=p, title=title, domain=domain, author=author, tags=tags))
    return notes

def build_db(notes: list[NoteMeta]) -> dict:
    token_stats: dict = {}
    domain_stats = defaultdict(int)
    author_stats = defaultdict(int)
    tag_stats = defaultdict(int)

    for note in notes:
        domain_stats[note.domain] += 1
        author_stats[note.author] += 1
        unique_tags = sorted(set(note.tags))
        for t in unique_tags:
            tag_stats[t] += 1

        tokens = tokenize_title(note.title)
        for tok in tokens:
            tok_bucket = ensure_dict(token_stats, tok)
            dom_bucket = ensure_dict(tok_bucket, "domain")
            bump(dom_bucket, note.domain, 1)
            tag_bucket = ensure_dict(tok_bucket, "tags")
            for t in unique_tags:
                bump(tag_bucket, t, 1)

    db = {
        "token_stats": token_stats,
        "domain_stats": dict(sorted(domain_stats.items())),
        "author_stats": dict(sorted(author_stats.items())),
        "tag_stats": dict(sorted(tag_stats.items())),
    }
    return db

def summarize(notes: list[NoteMeta], db: dict) -> str:
    counts = Counter(n.domain for n in notes)
    tag_total = sum(db["tag_stats"].values())
    lines = []
    lines.append("=== Backfill Summary ===")
    lines.append(f"Notes processed: {len(notes)}")
    lines.append("Domains (from notes): " + ", ".join(f"{k}={v}" for k,v in counts.items()))
    lines.append(f"Unique tags: {len(db['tag_stats'])} (total note-level tag hits: {tag_total})")
    lines.append("Guardrails:")
    lines.append(f"  sum(domain_stats) == #notes ? {'OK' if sum(db['domain_stats'].values()) == len(notes) else 'MISMATCH'}")
    lines.append(f"  sum(author_stats) == #notes ? {'OK' if sum(db['author_stats'].values()) == len(notes) else 'MISMATCH'}")
    return "\n".join(lines)

def write_csv_report(csv_path: Path, db: dict):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        # Domain stats
        w.writerow(["section","key","count"])
        for key, val in db["domain_stats"].items():
            w.writerow(["domain_stats", key, val])
        # Spacer
        w.writerow([])
        # Author stats
        for key, val in db["author_stats"].items():
            w.writerow(["author_stats", key, val])
        # Spacer
        w.writerow([])
        # Tag stats
        for key, val in db["tag_stats"].items():
            w.writerow(["tag_stats", key, val])

def main():
    args = parse_args()
    vault = Path(args.vault).expanduser().resolve()
    if not vault.exists():
        print(f"[error] Vault path not found: {vault}", file=sys.stderr)
        sys.exit(2)

    rel = args.rel.replace("\\", "/")
    try:
        notes = collect_notes(vault, rel)
    except Exception as e:
        print(f"[error] Failed to collect notes: {e}", file=sys.stderr)
        sys.exit(3)

    if len(notes) == 0:
        print(f"[warn] No notes found in {vault / rel}", file=sys.stderr)

    db = build_db(notes)
    print(summarize(notes, db))

    if args.dry_run:
        print("[info] Dry run: not writing JSON/CSV.")
        return

    out_json = Path(args.out) if args.out else (vault / "Resources" / "system" / "learning_db.json")
    out_csv  = out_json.parent / "learning_report.csv"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    try:
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"[ok] Wrote {out_json}")
        # CSV
        write_csv_report(out_csv, db)
        print(f"[ok] Wrote {out_csv}")
        # guardrails
        if sum(db["domain_stats"].values()) != len(notes):
            print("[warn] domain_stats sum != number of notes (expected 1 per note).", file=sys.stderr)
        if sum(db["author_stats"].values()) != len(notes):
            print("[warn] author_stats sum != number of notes (expected 1 per note).", file=sys.stderr)
    except Exception as e:
        print(f"[error] Failed to write outputs: {e}", file=sys.stderr)
        sys.exit(4)

if __name__ == "__main__":
    main()
