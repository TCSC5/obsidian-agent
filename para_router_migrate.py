# -*- coding: utf-8 -*-
"""
para_router.py — PARA router with Areas/Resources + bulletproof front‑matter repair

Key additions in this build
---------------------------
- Removes a stray YAML-looking block *even when it's literally escaped* (`---\n ... \n---`)
  and even if it appears a few lines down (we search within the first 4k chars).
- Keeps `--fix-frontmatter` (or `--fix`) mode to repair notes without moving them.

Routing priority (unchanged)
----------------------------
para override > status(archived/completed) > area > type (pitch/insight/summary) > resource_bucket > Resources.
"""

import os, re, sys, shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple, List

BASE = Path(__file__).resolve().parent
VAULT_PATH = Path(os.getenv("VAULT_PATH", r"C:\\Users\\top2e\\Sync"))
DATA_DIR = BASE / "data"
LOG = DATA_DIR / "para_router_log.md"


# ---------- IO ----------

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def write_text(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


# ---------- Frontmatter parse/dump ----------

def parse_frontmatter(md: str):
    m = re.match(r"^---\s*\n(.*?)\n---\s*", md, re.DOTALL)
    if not m:
        return {}, md, -1, -1
    head = m.group(1)
    body = md[m.end():]
    data: Dict = {}
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(head) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    return data, body, m.start(), m.end()

def dump_frontmatter(fm: Dict) -> str:
    try:
        import yaml  # type: ignore
        return yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    except Exception:
        return "\n".join(f"{k}: {v}" for k, v in fm.items())


# ---------- helpers ----------

def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\- ]+", "", s)
    s = re.sub(r"\s+", "-", s)
    return s[:120] if s else "untitled"

def _as_list(v) -> List[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if v is None:
        return []
    return [str(v).strip()]

def _ensure_list_in_fm(fm: Dict, key: str, values: List[str]) -> bool:
    cur = fm.get(key, None)
    if isinstance(cur, list):
        cur_norm = [str(x).strip() for x in cur if str(x).strip()]
    elif cur is None:
        cur_norm = None
    else:
        cur_norm = [str(cur).strip()]
    if cur_norm == values:
        return False
    fm[key] = values
    return True

def truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1","true","yes","y"}


# ---------- vocab & aliases ----------

ALLOWED_TYPES = {"summary","insight","pitch","checklist","log","idea","framework","reference"}
TYPE_ALIASES = {"summaries":"summary","insights":"insight","note":"reference","notes":"reference"}

ALLOWED_STATUS = {"draft","ready","review-needed","in-progress","completed","archived","gated","link-pending","enriched"}
STATUS_ALIASES = {"in progress":"in-progress","review":"review-needed","complete":"completed","done":"completed","archive":"archived"}

ALLOWED_LINK_STATUS = {"link_pending","linked"}
LINK_STATUS_ALIASES = {"link-pending":"link_pending","pending":"link_pending"}

ALLOWED_META_STATUS = {"metadata_pending","enriched","needs_review","completed"}
META_STATUS_ALIASES = {"metadata-pending":"metadata_pending","needs-review":"needs_review"}

RESOURCE_BUCKETS = {
    "Books-Articles": "Books & Articles",
    "Prompts": "Prompts",
    "Research": "Research",
    "Templates": "Templates",
    "Data": "Data",
    "Code": "Code",
    "Reports": "Reports",
    "Checklists": "Checklists",
    "Dashboards": "Dashboards",
}
RESOURCE_ALIASES = {
    "books & articles":"Books-Articles",
    "books-articles":"Books-Articles",
    "books_articles":"Books-Articles",
    "books":"Books-Articles",
    "articles":"Books-Articles",
    "prompt":"Prompts",
    "template":"Templates",
    "report":"Reports",
    "checklist":"Checklists",
    "dashboard":"Dashboards",
    "research":"Research",
    "data":"Data",
    "code":"Code",
}


# ---------- normalization ----------

def normalize_type(v) -> str:
    vals = [TYPE_ALIASES.get(x.lower(), x.lower()) for x in _as_list(v)]
    for x in vals:
        if x in ALLOWED_TYPES:
            return x
    return "reference"

def normalize_status(v) -> str:
    vals = [STATUS_ALIASES.get(x.lower(), x.lower()) for x in _as_list(v)]
    pref = ["archived","completed","in-progress","ready","draft","review-needed","gated","link-pending","enriched"]
    for p in pref:
        if p in vals:
            return p
    return "draft"

def normalize_link_status(v) -> List[str]:
    vals = []
    for x in _as_list(v):
        y = LINK_STATUS_ALIASES.get(x.lower(), x.lower())
        if y in ALLOWED_LINK_STATUS and y not in vals:
            vals.append(y)
    return vals[:1]

def normalize_meta_status(v) -> List[str]:
    vals = []
    for x in _as_list(v):
        y = META_STATUS_ALIASES.get(x.lower(), x.lower())
        if y in ALLOWED_META_STATUS and y not in vals:
            vals.append(y)
    return vals[:1]

def normalize_area_list(v) -> List[str]:
    return _as_list(v)[:1]

def normalize_resource_bucket(v) -> List[str]:
    out = []
    for x in _as_list(v):
        key = RESOURCE_ALIASES.get(x.lower(), x)
        if key in RESOURCE_BUCKETS and key not in out:
            out.append(key)
    return out[:1]


# ---------- bulletproof body cleanup ----------

LEGACY_KEYS = {"title","source_note","created","tags","type","status","link_status","meta_status","para","area","owner","due"}

def remove_yaml_like_block(s: str) -> Tuple[str, bool]:
    """
    Remove a '--- ... ---' block either with real newlines OR with *literal* \\n sequences,
    and not only at position 0 (we scan first 4000 chars). Only removes if the block
    looks like metadata (contains known keys).
    """
    changed = False
    limit = min(4000, len(s))

    # (A) Real newlines variant
    pat_real = re.compile(r"---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
    m = pat_real.search(s, 0, limit)
    if m:
        cand = m.group(1)
        if re.search(r"(?im)^(title|type|status|link_status|meta_status|area|para)\s*:", cand):
            s = s[:m.start()] + s[m.end():]
            changed = True
            return s, changed  # remove just one block per pass

    # (B) Escaped newlines variant (literal '\n')
    pat_esc = re.compile(r"---\\s*\\n(.*?)\\n---\\s*(?:\\n|$)", re.DOTALL)
    m = pat_esc.search(s, 0, limit)
    if m:
        cand = m.group(1)
        if re.search(r"(title|type|status|link_status|meta_status|area|para)\s*:", cand):
            s = s[:m.start()] + s[m.end():]
            changed = True

    return s, changed

def strip_legacy_header(body: str) -> Tuple[str, bool]:
    """
    1) Drop any YAML-looking block (real or escaped) near the top.
    2) Remove leading metadata 'key: value' lines.
    """
    changed = False
    s, c1 = remove_yaml_like_block(body)
    changed |= c1

    # Remove leading whitespace/BOM
    s = s.lstrip("\ufeff \t\r\n")

    # Remove leading key:value lines
    lines = s.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*", line)
        if m and m.group(1) in LEGACY_KEYS:
            idx += 1
            changed = True
            continue
        break
    cleaned = "\n".join(lines[idx:]).lstrip("\n")
    return cleaned, changed


# ---------- routing ----------

def decide_para(fm: Dict) -> Tuple[str, Optional[str], bool]:
    """Return (root, subfolder, fm_changed)."""
    fm_changed = False

    # para override
    para = (str(fm.get("para", "")).strip().lower() or "").replace("'", "")
    if para in {"project","projects"}: return "Projects", None, fm_changed
    if para in {"area","areas"}:
        area = str(fm.get("area", "")).strip()
        return "Areas", slugify(area) if area else "general", fm_changed
    if para in {"resource","resources"}: return "Resources", None, fm_changed
    if para in {"archive","archives","archived"}: return "Archives", None, fm_changed

    # normalize
    t_raw, s_raw = fm.get("type"), fm.get("status")
    ls_raw, ms_raw = fm.get("link_status"), fm.get("meta_status")
    a_raw = fm.get("area")
    rb_raw = fm.get("resource_bucket", fm.get("resources"))

    t = normalize_type(t_raw)
    s = normalize_status(s_raw)
    ls = normalize_link_status(ls_raw)
    ms = normalize_meta_status(ms_raw)
    a = normalize_area_list(a_raw)
    rb = normalize_resource_bucket(rb_raw)

    # write normalized lists back
    if _ensure_list_in_fm(fm, "type", [t]): fm_changed = True
    if _ensure_list_in_fm(fm, "status", [s]): fm_changed = True
    if ls or isinstance(ls_raw, list) or ls_raw:
        if _ensure_list_in_fm(fm, "link_status", ls or []): fm_changed = True
    if ms or isinstance(ms_raw, list) or ms_raw:
        if _ensure_list_in_fm(fm, "meta_status", ms or []): fm_changed = True
    if a or isinstance(a_raw, list) or a_raw:
        if _ensure_list_in_fm(fm, "area", a or []): fm_changed = True
    if rb or isinstance(rb_raw, list) or rb_raw:
        if _ensure_list_in_fm(fm, "resource_bucket", rb or []): fm_changed = True
        if "resources" in fm:
            del fm["resources"]; fm_changed = True

    if s in {"archived","completed"}: return "Archives", None, fm_changed
    if a: return "Areas", slugify(a[0]), fm_changed
    if t == "pitch": return "Projects", "Pitches", fm_changed
    if t == "insight":
        if str(fm.get("owner","")).strip() or str(fm.get("due","")).strip():
            return "Projects","Pitches", fm_changed
        return "Resources","Insights", fm_changed
    if t == "summary": return "Resources","Summaries", fm_changed
    if rb:
        folder = RESOURCE_BUCKETS.get(rb[0], rb[0])
        return "Resources", folder, fm_changed
    return "Resources", None, fm_changed


# ---------- discovery ----------

def candidate_files() -> List[Path]:
    roots = [
        VAULT_PATH / "00_Inbox",
        VAULT_PATH / "Summaries",
        VAULT_PATH / "Express" / "insights",
        VAULT_PATH / "Express" / "pitch",
        VAULT_PATH / "Resources",
        VAULT_PATH / "Projects",
        VAULT_PATH / "Areas",
    ]
    out: List[Path] = []
    for r in roots:
        if r.exists():
            for p in r.rglob("*.md"):
                try:
                    rel = p.relative_to(VAULT_PATH)
                except ValueError:
                    continue
                if any(part.lower() == "seeds" for part in rel.parts):
                    continue
                out.append(rel)
    return out


# ---------- main ops ----------

def rewrite_note(abs_path: Path, fm: Dict, body: str):
    fm_dump = dump_frontmatter(fm)
    new_md = f"---\n{fm_dump}\n---\n{body}"
    write_text(abs_path, new_md)

def router_run(fix_only: bool = False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"# PARA Router Log — {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    moved = 0; fm_fixed = 0; body_cleaned = 0

    for rel in candidate_files():
        try:
            abs_path = VAULT_PATH / rel
            txt = read_text(abs_path)
            fm, body, s, e = parse_frontmatter(txt)

            # skip seeds
            if truthy(fm.get("seed")):
                lines.append(f"- ⏭ Skipped (seed): {rel.as_posix()}")
                continue

            # normalize + routing
            root, sub, fm_changed = decide_para(fm)

            # body cleanup
            new_body, cleaned = strip_legacy_header(body)

            if fm_changed or cleaned:
                rewrite_note(abs_path, fm, new_body)
                if fm_changed: fm_fixed += 1
                if cleaned: body_cleaned += 1
                lines.append(f"- ✨ Normalized FM/body: {rel.as_posix()}")

            if fix_only:
                continue

            # idempotent move
            parts = [p.lower() for p in rel.parts]
            root_ok = root.lower() in parts
            sub_ok = (not sub) or (sub.lower() in parts)
            if root_ok and sub_ok:
                lines.append(f"- ⏭ Skipped (already in {root}{'/' + sub if sub else ''}): {rel.as_posix()}")
                continue

            # move
            dest_root = (VAULT_PATH / root) / (sub or "")
            dest_root.mkdir(parents=True, exist_ok=True)
            target = dest_root / rel.name
            if target.exists():
                stem, suf = target.stem, target.suffix
                i = 2
                while (dest_root / f"{stem}-{i}{suf}").exists():
                    i += 1
                target = dest_root / f"{stem}-{i}{suf}"
            shutil.move(str(abs_path), str(target))
            lines.append(f"- ✅ {rel.as_posix()} → {target.relative_to(VAULT_PATH).as_posix()}")
            moved += 1

        except Exception as ex:
            lines.append(f"- ❌ Error processing {rel.as_posix()}: {ex}")

    lines += ["", f"**Moved:** {moved}", f"**Front-matter fixed:** {fm_fixed}", f"**Body cleaned:** {body_cleaned}"]
    write_text(LOG, "\n".join(lines))
    print(f"[OK] PARA run complete — moved={moved}, fm_fixed={fm_fixed}, body_cleaned={body_cleaned}. Log -> {LOG}")


if __name__ == "__main__":
    fix_only = any(arg in {"--fix-frontmatter","--fix"} for arg in sys.argv[1:])
    router_run(fix_only=fix_only)
