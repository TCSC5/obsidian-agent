# apply_resources.py
# Stage 2 of 2: finalize metadata (with required-field gating) + learn
#
# - Reads Resources/resource_index.md for [x] Accept decisions
# - Finalizes a note if: Accept checked OR you edited it since proposal OR auto-accept by confidence
# - Blocks finalization if required fields (default: domain,tags) are missing/placeholder
# - Logs finalized metadata into Resources/system/learning_db.json (domains + tags + author)
#
# Usage (example):
#   python apply_resources.py --vault C:/Users/you/Sync --rel Resources/learning_inputs --reviewer "Michael" --strip-scaffold
#
# Tip: add --require-fields domain,tags,author,source if you want stricter gating

import argparse, json, re, sys
from pathlib import Path
from datetime import datetime

FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?', re.MULTILINE)

def parse_args():
    ap = argparse.ArgumentParser(description="Finalize resource metadata and update learning DB.")
    ap.add_argument("--vault", required=True)
    ap.add_argument("--rel", default=r"Resources\learning_inputs")
    ap.add_argument("--reviewer", default="Michael")
    ap.add_argument("--min-confidence", type=float, default=None, help="Auto-accept if all listed --fields meet this confidence")
    ap.add_argument("--fields", default="domain,tags", help="Fields to check for --min-confidence")
    ap.add_argument("--strip-scaffold", action="store_true", help="Remove auto_filled and confidence on finalize")
    ap.add_argument("--require-fields", default="domain,tags", help="Comma-separated list of fields required to finalize")
    return ap.parse_args()

def read_text(p: Path):
    try: return p.read_text(encoding="utf-8")
    except: return p.read_text(encoding="utf-8", errors="ignore")
def dump_text(p: Path, txt: str):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(txt, encoding="utf-8")

def parse_yaml_block(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m: return {}, text
    yml, body = m.group(1), text[m.end():]
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
    for k in d:
        if k not in order: order.append(k)
    def fmt(v):
        if isinstance(v, list): return "[" + ", ".join(f'"{x}"' for x in v) + "]"
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, dict): return "{" + ", ".join(f"{k}: {v[k]}" for k in v) + "}"
        return f'"{v}"' if v is not None else '""'
    return "---\n" + "\n".join(f"{k}: {fmt(d[k])}" for k in order if k in d) + "\n---\n"

# -------- learning DB helpers --------
def load_learning_db(vault: Path) -> dict:
    p = vault / "Resources" / "system" / "learning_db.json"
    if not p.exists():
        return {"token_stats": {}, "author_stats": {}, "tag_stats": {}, "domain_stats": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"token_stats": {}, "author_stats": {}, "tag_stats": {}, "domain_stats": {}}

def save_learning_db(vault: Path, db: dict):
    p = vault / "Resources" / "system" / "learning_db.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    dump_text(p, json.dumps(db, indent=2))

def tokenize_title(title: str):
    return [t for t in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(t) > 2]

def learn_from_note(db: dict, meta: dict):
    title = meta.get("title","")
    tokens = set(tokenize_title(title))

    domains = meta.get("domain") or []
    if isinstance(domains, str): domains = [domains] if domains else []
    tags = meta.get("tags") or []
    if isinstance(tags, str): tags = [tags] if tags else []
    author = (meta.get("author","") or "").strip()

    db.setdefault("token_stats", {})
    for tk in tokens:
        ts = db["token_stats"].setdefault(tk, {"domain": {}, "tags": {}})
        for d in domains:
            ts["domain"][d] = ts["domain"].get(d, 0) + 1
        for tg in tags:
            ts["tags"][tg] = ts["tags"].get(tg, 0) + 1

    if author:
        db.setdefault("author_stats", {})
        db["author_stats"][author] = db["author_stats"].get(author, 0) + 1
    for d in domains:
        db.setdefault("domain_stats", {})
        db["domain_stats"][d] = db["domain_stats"].get(d, 0) + 1
    for tg in tags:
        db.setdefault("tag_stats", {})
        db["tag_stats"][tg] = db["tag_stats"].get(tg, 0) + 1

# -------- acceptance / gating --------
def lists_equal_unordered(a, b): return sorted((a or [])) == sorted((b or []))

def is_field_filled(meta: dict, field: str) -> bool:
    v = meta.get(field)
    if field == "domain":
        if isinstance(v, list) and len(v) > 0 and v != ["needs_domain"]: return True
        if isinstance(v, str) and v and v != "needs_domain": return True
        return False
    if field == "tags":
        if isinstance(v, list) and len(v) > 0: return True
        if isinstance(v, str) and v: return True
        return False
    return bool(v)

def should_auto_accept(meta: dict, min_conf: float, fields: list) -> bool:
    if min_conf is None: return False
    conf = meta.get("confidence", {})
    if not isinstance(conf, dict):
        try: conf = json.loads(str(conf))
        except Exception: conf = {}
    for f in fields:
        if conf.get(f, 0.0) < min_conf: return False
    return True

def main():
    args = parse_args()
    vault = Path(args.vault)

    index_md = vault / "Resources" / "resource_index.md"
    index_json = vault / "Resources" / "resource_index.json"
    if not index_json.exists():
        print("[error] resource_index.json not found; run propose first.", file=sys.stderr)
        sys.exit(2)

    # Parse Accept checkboxes
    accept_map = {}
    if index_md.exists():
        for ln in read_text(index_md).splitlines():
            m = re.search(r'^- \[( |x|X)\] Accept \| .* \| .* \| \[open\]\((.*?)\)', ln.strip())
            if m: accept_map[m.group(2)] = (m.group(1).lower() == "x")

    items = json.loads(index_json.read_text(encoding="utf-8"))
    db = load_learning_db(vault)
    conf_fields     = [f.strip() for f in (args.fields or "").split(",") if f.strip()]
    require_fields  = [f.strip() for f in (args.require_fields or "").split(",") if f.strip()]

    finalized = 0
    blocked   = 0

    for it in items:
        fpath = Path(it["_path"])
        rel   = it["_rel_path"]
        raw = read_text(fpath)
        meta, body = parse_yaml_block(raw)

        if meta.get("meta_status","") != "proposed":
            continue

        was_checked = accept_map.get(rel, False)

        snap = it.get("_proposal_snapshot", {}) or {}
        edited_since = (
            (meta.get("title","") != snap.get("title","")) or
            (not lists_equal_unordered(meta.get("domain",[]), snap.get("domain",[]))) or
            (not lists_equal_unordered(meta.get("tags",[]),   snap.get("tags",[]))) or
            (meta.get("relevance","") != snap.get("relevance",""))
        )
        auto_accept = should_auto_accept(meta, args.min_confidence, conf_fields)
        proceed = (was_checked or edited_since or auto_accept)

        if not proceed:
            continue

        # Required-fields gating
        missing = [fld for fld in require_fields if not is_field_filled(meta, fld)]
        if missing:
            blocked += 1
            print(f"[BLOCKED] '{meta.get('title', fpath.name)}' missing required: {', '.join(missing)}")
            # Leave as proposed/needs_review:true
            continue

        # Finalize — manual edits win; never overwrite with snapshot
        meta["meta_status"] = "reference"
        meta["needs_review"] = False
        meta["reviewed_on"] = datetime.now().strftime("%Y-%m-%d")
        meta["reviewer"] = args.reviewer

        if args.strip_scaffold:
            meta.pop("auto_filled", None)
            meta.pop("confidence", None)

        dump_text(fpath, to_yaml(meta) + (body if body is not None else ""))
        finalized += 1

        # Learn
        learn_from_note(db, meta)

    save_learning_db(vault, db)
    print(f"[OK] Finalized {finalized} note(s).")
    if blocked:
        print(f"[WARN] Blocked {blocked} note(s) due to missing required fields.")
    print(f"[OK] Updated learning DB at Resources/system/learning_db.json")

if __name__ == "__main__":
    main()
