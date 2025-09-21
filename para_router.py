
# -*- coding: utf-8 -*-
r"""
para_router.py — Gated PARA routing (no Inbox auto-moves)

Design:
- Inbox is sacred intake: notes without a `type` are ignored (no move).
- Summarizer adds `type: summary` — router leaves summaries in place.
- After review/gating, you convert to either:
    * type: area_note + area: [...]
    * type: resource_note + resources: [...]
  Router then files to Areas/… or Resources/… (or _Other when undefined).
- `type: pitch` and `type: insight` are just placed (or kept) in Express folders.
- Taxonomy is loaded from System/taxonomy.yaml and self-heals if malformed,
  even when PyYAML isn't installed.

CLI:
  python para_router.py --scan
  python para_router.py --file "C:/path/to/note.md"
  python para_router.py --dry-run
"""

import os, sys, argparse, shutil, re
from pathlib import Path

try:
    import yaml  # optional
except Exception:
    yaml = None

BASE = Path(os.getenv("BASE_PATH") or Path(__file__).parent)
VAULT = Path(os.getenv("VAULT_PATH") or "C:/Users/youruser/Sync")
SYSTEM = BASE / "System"
TAXONOMY = SYSTEM / "taxonomy.yaml"

FOLDERS = {
    "insight":       "Express/insights",
    "pitch":         "Express/pitch",
    "summary":       "Summaries",
    "area_note":     "Areas",
    "resource_note": "Resources",
}

REQUIRES = {
    "insight":       {"area": False, "resources": False},
    "pitch":         {"area": False, "resources": False},
    "summary":       {"area": False, "resources": False},
    "area_note":     {"area": True,  "resources": False},
    "resource_note": {"area": False, "resources": True},
}

DEFAULT_TAXONOMY = {
    "other_label": "Other – undefined",
    "areas": ["Career","Health","Learning & Growth","Personal Finance"],
    "resources": ["Books & Articles","Prompts","Research","Templates"],
    "holding_folders": {
        "areas": "Areas/_Other",
        "resources": "Resources/_Other",
    },
}

# ---------- lightweight YAML helpers ----------

def _minimal_yaml(text: str):
    data = {}
    stack = [(-1, data)]
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1] if stack else data

        if line.startswith("- "):
            val = line[2:].strip().strip('"').strip("'")
            if isinstance(parent, list):
                parent.append(val)
            else:
                # ignore malformed
                pass
            continue

        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip(); v = v.strip()
            if not isinstance(parent, dict):
                continue
            if v == "":
                parent[k] = {}
                stack.append((indent, parent[k]))
            else:
                if v.startswith("[") and v.endswith("]"):
                    items = [i.strip().strip("'").strip('"') for i in v[1:-1].split(",") if i.strip()]
                    parent[k] = items
                else:
                    parent[k] = v.strip().strip('"').strip("'")
    return data

def load_yaml_file(path: Path):
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if yaml:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            pass
    return _minimal_yaml(text)

def save_yaml_file(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml:
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for s in v:
                lines.append(f"  - {s}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        else:
            lines.append(f"{k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def normalize_taxonomy(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.setdefault("other_label", DEFAULT_TAXONOMY["other_label"])
    for key in ("areas","resources"):
        v = cfg.get(key)
        if isinstance(v, str):
            v = [s.strip() for s in v.split(",") if s.strip()]
        if not isinstance(v, list):
            v = DEFAULT_TAXONOMY[key].copy()
        cfg[key] = v
    hf = cfg.get("holding_folders")
    if not isinstance(hf, dict):
        hf = {}
    areas_h = hf.get("areas") if isinstance(hf.get("areas"), str) else DEFAULT_TAXONOMY["holding_folders"]["areas"]
    res_h   = hf.get("resources") if isinstance(hf.get("resources"), str) else DEFAULT_TAXONOMY["holding_folders"]["resources"]
    cfg["holding_folders"] = {"areas": areas_h, "resources": res_h}
    return cfg

def load_taxonomy() -> dict:
    if not TAXONOMY.exists():
        save_yaml_file(TAXONOMY, DEFAULT_TAXONOMY)
        return DEFAULT_TAXONOMY.copy()
    cfg = load_yaml_file(TAXONOMY)
    cfg = normalize_taxonomy(cfg)
    save_yaml_file(TAXONOMY, cfg)  # write back normalized
    return cfg

# ---------- frontmatter ----------

def read_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end]
    body = text[end+4:]
    if yaml:
        try:
            meta = yaml.safe_load(fm_text) or {}
        except Exception:
            meta = _minimal_yaml(fm_text)
    else:
        meta = _minimal_yaml(fm_text)
    return meta, body

def write_frontmatter(path: Path, meta: dict, body: str):
    if yaml:
        fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    else:
        lines = []
        for k, v in meta.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for s in v:
                    lines.append(f"  - {s}")
            elif isinstance(v, dict):
                lines.append(f"{k}:")
                for kk, vv in v.items():
                    lines.append(f"  {kk}: {vv}")
            else:
                lines.append(f"{k}: {v}")
        fm = "\n".join(lines).strip()
    path.write_text(f"---\n{fm}\n---\n{body.lstrip()}", encoding="utf-8")

def normalize_single(v):
    if isinstance(v, list):
        return (v[0] if v else "").strip()
    return (v or "").strip()

# ---------- rules ----------

def enforce_mutual_exclusion(meta: dict):
    t = str(meta.get("type","")).strip()
    if t == "area_note":
        meta.pop("resources", None)
    if t == "resource_note":
        meta.pop("area", None)

def validate_fields(meta: dict, taxonomy: dict):
    t = str(meta.get("type","")).strip()
    needs = REQUIRES.get(t, {"area": False, "resources": False})
    other = taxonomy.get("other_label", "Other – undefined")
    allowed_areas = set(a.strip() for a in taxonomy.get("areas", []))
    allowed_resources = set(r.strip() for r in taxonomy.get("resources", []))

    notes = []
    needs_review = False

    def pick(key, allowed):
        nonlocal needs_review
        if not needs[key]:
            meta.pop(key, None)
            return
        v = normalize_single(meta.get(key))
        if not v:
            meta[key] = [other]
            needs_review = True
            notes.append(f"{key} missing → set to {other}")
            return
        if v not in allowed:
            base_folder = "Areas" if key == "area" else "Resources"
            if (Path(VAULT) / base_folder / v).exists():
                meta[key] = [v]
                notes.append(f"{key} '{v}' accepted (matching folder exists).")
                return
            meta[key] = [other]
            needs_review = True
            notes.append(f"{key} '{v}' not in taxonomy → {other}")
            return
        meta[key] = [v]

    pick("area", allowed_areas)
    pick("resources", allowed_resources)
    if needs_review:
        meta["meta_status"] = "needs_review"
    return notes, needs_review

def ensure_holding(cfg):
    Path(VAULT, cfg["holding_folders"]["areas"]).mkdir(parents=True, exist_ok=True)
    Path(VAULT, cfg["holding_folders"]["resources"]).mkdir(parents=True, exist_ok=True)

def destination_for(meta: dict, taxonomy: dict) -> Path:
    t = str(meta.get("type","")).strip()
    other = taxonomy.get("other_label", "Other – undefined")
    ensure_holding(taxonomy)

    if t == "insight":
        return Path(VAULT, FOLDERS["insight"])
    if t == "pitch":
        return Path(VAULT, FOLDERS["pitch"])
    if t == "summary":
        return Path(VAULT, FOLDERS["summary"])
    if t == "area_note":
        a = normalize_single(meta.get("area"))
        if not a or a == other:
            return Path(VAULT, taxonomy["holding_folders"]["areas"])
        return Path(VAULT, "Areas", a)
    if t == "resource_note":
        r = normalize_single(meta.get("resources"))
        if not r or r == other:
            return Path(VAULT, taxonomy["holding_folders"]["resources"])
        return Path(VAULT, "Resources", r)
    # Unknown or missing type: do not move
    return None

def move_note(src: Path, dest_dir: Path, dry_run=False):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / src.name
    if dry_run:
        print(f"[dry-run] MOVE  {src}  ->  {dst}")
        return dst
    if str(src.resolve()) == str(dst.resolve()):
        print(f"[skip] Already in place: {src}")
        return dst
    if dst.exists():
        stem, suf = src.stem, src.suffix
        i = 1
        while True:
            candidate = dest_dir / f"{stem} ({i}){suf}"
            if not candidate.exists():
                dst = candidate
                break
            i += 1
    shutil.move(str(src), str(dst))
    print(f"[moved] {src}  ->  {dst}")
    return dst

def process_note(path: Path, taxonomy: dict, dry_run=False, verbose=True):
    meta, body = read_frontmatter(path)
    if verbose:
        print(f"\n== Processing: {path} ==")

    t = str(meta.get("type","")).strip()
    if not t:
        print("  - skip: no `type` (raw inbox intake)")
        return path  # leave in place

    enforce_mutual_exclusion(meta)
    notes, needs_review = validate_fields(meta, taxonomy)

    if not dry_run:
        write_frontmatter(path, meta, body)

    dest_dir = destination_for(meta, taxonomy)
    if dest_dir is None:
        print("  - skip: unknown type → no move")
        return path

    new_path = move_note(path, dest_dir, dry_run=dry_run)
    for n in notes:
        print("  -", n)
    return new_path

def scan_sources():
    # DO NOT scan Inbox; respect intake → summarizer → gating flow
    candidates = [
        "Summaries",
        "Express/pitch",
        "Express/insights",
        "Areas/_Other",
        "Resources/_Other",
    ]
    for rel in candidates:
        p = Path(VAULT) / rel
        if p.exists():
            for md in p.rglob("*.md"):
                yield md

def main():
    ap = argparse.ArgumentParser(description="Gated PARA router (ignores Inbox; routes only gated types)")
    ap.add_argument("--file", help="Process a single note (.md)")
    ap.add_argument("--scan", action="store_true", help="Scan Summaries/Express/_Other (not Inbox)")
    ap.add_argument("--dry-run", action="store_true", help="Don't write/move, just show actions")
    args = ap.parse_args()

    # Enhanced permissions checking for PARA routing
    try:
        from permissions_utils import preflight_check
        required_dirs = ["Areas", "Resources", "Projects", "Archives", "Summaries", "Express"]
        if not preflight_check(VAULT, required_dirs):
            print("❌ Permission check failed for PARA Router")
            print("   Please ensure vault directories are accessible.")
            return
    except ImportError:
        print("⚠️  Permissions utilities not available, proceeding without validation...")

    taxonomy = load_taxonomy()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print("File not found:", path)
            sys.exit(1)
        process_note(path, taxonomy, dry_run=args.dry_run)
        return

    if args.scan:
        found = False
        for md in scan_sources():
            found = True
            process_note(md, taxonomy, dry_run=args.dry_run)
        if not found:
            print("No notes found in Summaries/Express/_Other. Nothing to route.")
        return

    ap.print_help()

if __name__ == "__main__":
    main()
