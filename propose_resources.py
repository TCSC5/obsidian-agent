# propose_resources.py
# Stage 1 of 2: propose metadata + build the Review Queue (learning-aware)
#
# - Scans Resources/learning_inputs for *.md
# - Ensures front matter with placeholders and applies learned suggestions
# - Writes centralized backups the first time it changes a file
# - Builds:
#     Resources/resource_index.json  (machine-readable; includes _proposal_snapshot)
#     Resources/resource_index.md    (Review Queue with one [ ] Accept per item)
#
# Usage (example):
#   python propose_resources.py --vault C:/Users/you/Sync --rel Resources/learning_inputs --force-propose
#
# Notes:
# - Suggestions come from Resources/system/learning_db.json (if present)
# - You edit notes directly or check "Accept" later; apply_resources.py finalizes

import argparse, json, hashlib, re, sys, shutil
from pathlib import Path
from datetime import datetime, timedelta

FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?', re.MULTILINE)

DEFAULT_YAML = {
    "type": "resource",
    "domain": ["needs_domain"],
    "tags": [],
    "author": "",
    "date": "",
    "source": "",
    "relevance": "",
    "meta_status": "proposed",
    "needs_review": True,
    "auto_filled": [],
    "confidence": {},
}

FORCE_PROPOSE = False

def _normalize_confidence(val):
    if isinstance(val, dict): return val
    if isinstance(val, str):
        s = val.strip()
        if not s: return {}
        try: return json.loads(s)
        except Exception:
            try: return json.loads(s.replace("'", '"'))
            except Exception: return {}
    return {}

def parse_args():
    ap = argparse.ArgumentParser(description="Propose metadata and build review queue.")
    ap.add_argument("--vault", required=True, help="Obsidian vault root")
    ap.add_argument("--rel", default=r"Resources\learning_inputs", help="Relative path to learning inputs")
    ap.add_argument("--backup-days", type=int, default=21, help="Prune centralized backups older than N days")
    ap.add_argument("--force-propose", action="store_true", help="Force all notes into proposed state")
    ap.add_argument("--backup-on-edit", action="store_true", help="(Kept for compatibility; backups are centralized)")
    return ap.parse_args()

def _today_str(): return datetime.now().strftime("%Y-%m-%d")
def _central_backup_path(vault_root: Path, note_path: Path) -> Path:
    rel = note_path.relative_to(vault_root)
    return vault_root / "Resources" / "backups" / _today_str() / rel

def _prune_old_backups(base: Path, keep_days: int):
    if keep_days <= 0 or not base.exists(): return
    cutoff = datetime.now() - timedelta(days=keep_days)
    for d in base.iterdir():
        try:
            dt = datetime.strptime(d.name, "%Y-%m-%d")
        except Exception:
            continue
        if dt < cutoff:
            shutil.rmtree(d, ignore_errors=True)

def sha256(s: str): return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()
def read_text(p: Path):
    try: return p.read_text(encoding="utf-8")
    except: return p.read_text(encoding="utf-8", errors="ignore")
def dump_text(p: Path, txt: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")

def parse_yaml_block(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m: return {}, text
    yml = m.group(1); body = text[m.end():]
    data = {}
    for ln in yml.splitlines():
        if re.match(r'^\s*#', ln) or re.match(r'^\s*$', ln): continue
        m2 = re.match(r'^([A-Za-z0-9_]+):\s*(.*)$', ln)
        if not m2: continue
        k, v = m2.group(1), m2.group(2).strip()
        if v.startswith('[') and v.endswith(']'):
            inner = v[1:-1].strip()
            items = [i.strip().strip('"').strip("'") for i in inner.split(',')] if inner else []
            data[k] = [i for i in items if i]
        elif v.lower() in ("true","false"):
            data[k] = (v.lower() == "true")
        elif v.startswith("{") and v.endswith("}"):
            try: data[k] = json.loads(v.replace("'", '"'))
            except Exception: data[k] = {}
        else:
            data[k] = v.strip('"').strip("'")
    return data, body

def to_yaml(d: dict) -> str:
    order = ["title","type","domain","tags","author","date","source","relevance",
             "meta_status","needs_review","auto_filled","confidence","reviewed_on","reviewer"]
    # include any unknown keys at end
    for k in d:
        if k not in order: order.append(k)
    def fmt(v):
        if isinstance(v, list): return "[" + ", ".join(f'"{x}"' for x in v) + "]"
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, dict): return "{" + ", ".join(f"{k}: {v[k]}" for k in v) + "}"
        return f'"{v}"' if v is not None else '""'
    return "---\n" + "\n".join(f"{k}: {fmt(d[k])}" for k in order if k in d) + "\n---\n"

def ensure_defaults(meta: dict, filename: str):
    updated = False
    auto_filled = meta.get("auto_filled", [])
    if not isinstance(auto_filled, list): auto_filled = []
    conf = _normalize_confidence(meta.get("confidence", {}))

    if not meta.get("title"):
        stem = Path(filename).stem.replace("_"," ").replace("-"," ")
        meta["title"] = stem
        auto_filled.append("title"); conf["title"] = 0.90; updated = True

    for k, v in DEFAULT_YAML.items():
        if k not in meta or (isinstance(v, (str, list)) and not meta.get(k)):
            meta[k] = v
            if k not in ("meta_status","needs_review","auto_filled","confidence"):
                auto_filled.append(k); conf[k] = 0.50; updated = True

    if not meta.get("domain"):
        meta["domain"] = ["needs_domain"]

    meta["auto_filled"] = sorted(set(auto_filled))
    meta["confidence"]  = conf

    if meta.get("meta_status","") == "reference":
        meta["needs_review"] = False
    elif meta.get("meta_status","") == "proposed":
        meta["needs_review"] = True
    else:
        meta["meta_status"] = "proposed"; meta["needs_review"] = True

    return meta, updated

# ---------- learning helpers ----------
def _learning_db_path(vault: Path) -> Path: return vault / "Resources" / "system" / "learning_db.json"
def _load_learning_db(vault: Path) -> dict:
    p = _learning_db_path(vault)
    if not p.exists(): return {"token_stats": {}, "author_stats": {}, "tag_stats": {}, "domain_stats": {}}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {"token_stats": {}, "author_stats": {}, "tag_stats": {}, "domain_stats": {}}
def _tokenize_title(t: str): return [x for x in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(x) > 2]

def _suggest_from_learning(db: dict, meta: dict):
    """
    Suggest domain/tags/author from learning_db:
      - Token-based scores from token_stats
      - Fallback to global tag_stats if no token matches
      - Author suggested if one is globally dominant (>=60%)
    """
    title = meta.get("title","")
    tokens = set(_tokenize_title(title))
    token_stats = db.get("token_stats", {})
    domain_scores, tag_scores = {}, {}

    for tk in tokens:
        ts = token_stats.get(tk, {})
        for d, c in ts.get("domain", {}).items():
            domain_scores[d] = domain_scores.get(d, 0) + c
        for tg, c in ts.get("tags", {}).items():
            tag_scores[tg] = tag_scores.get(tg, 0) + c

    # Domain suggestion
    need_domain = (not meta.get("domain")) or meta.get("domain") == ["needs_domain"]
    if need_domain and domain_scores:
        d, score = sorted(domain_scores.items(), key=lambda x: (-x[1], x[0]))[0]
        if score >= 2:
            meta["domain"] = [d]
            meta.setdefault("auto_filled", []).append("domain")
            meta.setdefault("confidence", {})["domain"] = 0.75

    # Tag suggestion from tokens
    if not meta.get("tags") and tag_scores:
        tops = [k for k, v in sorted(tag_scores.items(), key=lambda x: -x[1])[:5] if v >= 2]
        if tops:
            meta["tags"] = tops
            meta.setdefault("auto_filled", []).append("tags")
            meta.setdefault("confidence", {})["tags"] = 0.70

    # Tag fallback from global tag_stats (if still empty)
    if not meta.get("tags"):
        global_tags = db.get("tag_stats", {})
        if global_tags:
            top_global = [k for k,_ in sorted(global_tags.items(), key=lambda x: -x[1])[:5]]
            if top_global:
                meta["tags"] = top_global
                meta.setdefault("auto_filled", []).append("tags")
                meta.setdefault("confidence", {})["tags"] = 0.60

    # Author suggestion (dominant overall)
    if not meta.get("author"):
        a = db.get("author_stats", {})
        if a:
            total = sum(a.values()) or 1
            best, cnt = sorted(a.items(), key=lambda x: -x[1])[0]
            if cnt / total >= 0.60:
                meta["author"] = best
                meta.setdefault("auto_filled", []).append("author")
                meta.setdefault("confidence", {})["author"] = 0.70

def build_index_entry(vault_root: Path, rel_dir: Path, file_path: Path, meta: dict, had_yaml: bool, updated: bool):
    rel_from_learning = file_path.relative_to(vault_root / rel_dir)
    return {
        "title": meta.get("title",""),
        "type": meta.get("type","resource"),
        "domain": meta.get("domain", ["needs_domain"]),
        "tags": meta.get("tags", []),
        "author": meta.get("author",""),
        "date": meta.get("date",""),
        "source": meta.get("source",""),
        "relevance": meta.get("relevance",""),
        "meta_status": meta.get("meta_status","proposed"),
        "_path": str(file_path),
        "_rel_path": str(rel_from_learning).replace("\\","/"),
        "_had_yaml": had_yaml,
        "_updated": updated,
        "_proposal_snapshot": {
            "title": meta.get("title",""),
            "domain": meta.get("domain", ["needs_domain"]),
            "tags": meta.get("tags", []),
            "relevance": meta.get("relevance",""),
        }
    }

def main():
    args = parse_args()
    global FORCE_PROPOSE
    FORCE_PROPOSE = bool(args.force_propose)

    vault = Path(args.vault)
    rel_dir = Path(args.rel)
    learning_dir = vault / rel_dir
    if not learning_dir.exists():
        print(f"[error] Directory not found: {learning_dir}", file=sys.stderr); sys.exit(2)

    md_files = sorted([p for p in learning_dir.rglob("*.md") if p.is_file()])
    index_json = vault / "Resources" / "resource_index.json"
    index_md   = vault / "Resources" / "resource_index.md"
    diffs_dir  = vault / "Resources" / "logs" / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)

    db = _load_learning_db(vault)
    index, review_rows = [], []

    for p in md_files:
        raw = read_text(p)
        had_yaml = bool(FRONTMATTER_RE.match(raw))
        meta, body = parse_yaml_block(raw)

        meta_status = str(meta.get("meta_status","")).lower()
        needs_rev   = bool(meta.get("needs_review", False))
        should_process = FORCE_PROPOSE or (meta_status != "reference") or needs_rev

        before = sha256(raw)
        meta, _ = ensure_defaults(dict(meta), p.name)
        if FORCE_PROPOSE:
            meta["meta_status"] = "proposed"; meta["needs_review"] = True

        # learning-based suggestions
        _suggest_from_learning(db, meta)

        new_text = raw
        if should_process:
            new_text = to_yaml(meta) + (body if body is not None else "")

        after = sha256(new_text)
        if should_process and after != before:
            bpath = _central_backup_path(vault, p)
            bpath.parent.mkdir(parents=True, exist_ok=True)
            if not bpath.exists():
                dump_text(bpath, raw)
            dump_text(p, new_text)
            dump_text(diffs_dir / (p.stem + ".diff.txt"), f"FILE: {p}\nBEFORE: {before}\nAFTER:  {after}\n")

        entry = build_index_entry(vault, rel_dir, p, meta, had_yaml, (after != before) and should_process)
        index.append(entry)

        if entry["meta_status"] != "reference" or meta.get("needs_review", True):
            review_rows.append(
                f'- [ ] Accept | {entry["title"]} | proposed: domain,tags,relevance | '
                f'[open]({entry["_rel_path"]})'
            )

    # Write artifacts
    dump_text(index_json, json.dumps(index, indent=2))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"# 📚 Resource Index\n_Last updated: {now}_\n\n"
    review_header = "## Review Queue (check **Accept** if proposal is correct; otherwise edit the note)\n\n"
    review_md = ("\n".join(review_rows) + "\n\n") if review_rows else "_No items to review._\n\n"

    table = [
        "| Title | Domain | Tags | Relevance | Date | Source | File |",
        "|---|---|---|---:|---|---|---|"
    ]
    for e in index:
        dom = ", ".join(e.get("domain",[]))
        tags = ", ".join(e.get("tags",[]))
        table.append(
            f'| {e["title"]} | {dom} | {tags} | {e.get("relevance","")} | {e.get("date","")} | {e.get("source","")} | [open]({e["_rel_path"]}) |'
        )
    dump_text(index_md, header + review_header + review_md + "\n".join(table) + "\n")

    _prune_old_backups(vault / "Resources" / "backups", args.backup_days)
    print(f"[OK] Proposed. Wrote:\n- {index_md}\n- {index_json}\n[NOTE] Run apply_resources.py after you Accept or edit.")

if __name__ == "__main__":
    main()
