#!/usr/bin/env python3
"""
Resource Indexer - Learning Pipeline Metadata Manager

Scans Resources/learning_inputs/ for Markdown notes and:
- Adds YAML frontmatter if missing
- Validates/backfills required fields (domain, tags, relevance)
- Generates resource_index.md and resource_index.json

Usage:
    python resource_indexer.py --vault-path="C:\Your\Vault" --dry-run
    .\run_resource_indexer.bat

Environment Variables:
    VAULT_PATH: Default vault location if --vault-path not provided

Outputs:
    - Resources/resource_index.md (Markdown table)
    - Resources/resource_index.json (JSON metadata)
    - *.bak files (backups of modified notes, if --no-backup not set)

Examples:
    # Preview changes (safe, no modifications)
    python resource_indexer.py --vault-path="C:\Vault" --dry-run
    
    # Apply changes with backups
    python resource_indexer.py --vault-path="C:\Vault"
    
    # Apply without backups (faster)
    python resource_indexer.py --vault-path="C:\Vault" --no-backup
"""

from pathlib import Path
import re
import json
from datetime import datetime
import argparse
import os
import shutil

TEMPLATE_MD = """# 📚 Resource Index
_Last updated: {updated}_

| Title | Domain | Tags | Relevance | Date | Source | File |
|---|---|---|---:|---|---|---|
{rows}
"""

ROW_MD = "| {title} | {domain} | {tags} | {relevance} | {date} | {source} | {file_link} |"

# --- YAML parsing helpers (no external deps required) ---
YAML_RE = re.compile(r"^---\s*(.*?)\s*---\s*(.*)$", re.DOTALL)
YAML_ORDER = [
    "title", "type", "domain", "tags", "author", "date", "source", "relevance", "meta_status"
]

def parse_frontmatter(text: str):
    """
    Returns (frontmatter_dict, body_text, had_yaml: bool)
    Minimal parser: key: value and [a, b, c] lists only.
    """
    m = YAML_RE.match(text)
    if not m:
        return {}, text, False

    yaml_block = m.group(1)
    body = m.group(2)

    fm: dict[str, object] = {}
    for raw_line in yaml_block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        # Handle lists like [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                items = [i.strip() for i in inner.split(",")]
                fm[key] = items
            else:
                fm[key] = []
        else:
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            fm[key] = value

    return fm, body, True


def coerce_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [str(v)] if v != "" else []


def ensure_fields(fm: dict, filename: str | None = None) -> dict:
    """
    Normalize and fill missing fields with sensible defaults or placeholders.
    Try to infer title from filename when absent.
    """
    normalized = dict(fm)

    if not normalized.get("title"):
        if filename:
            normalized["title"] = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "(untitled)"
        else:
            normalized["title"] = "(untitled)"
    normalized["type"] = normalized.get("type") or "resource"
    normalized["domain"] = coerce_list(normalized.get("domain"))
    normalized["tags"] = coerce_list(normalized.get("tags"))
    normalized["author"] = normalized.get("author") or ""
    normalized["date"] = normalized.get("date") or ""
    normalized["source"] = normalized.get("source") or ""
    normalized["relevance"] = normalized.get("relevance") or ""
    normalized["meta_status"] = normalized.get("meta_status") or "reference"

    # Light inference: if domain is empty, try to infer from tags
    if not normalized["domain"] and normalized["tags"]:
        infer_map = {
            "trading": "finance",
            "stocks": "finance",
            "options": "finance",
            "supplychain": "supplychain",
            "logistics": "supplychain",
            "startup": "startup",
            "ai": "ai",
            "machinelearning": "ai",
            "learning": "learning",
            "productivity": "learning",
        }
        inferred = set()
        for t in normalized["tags"]:
            key = str(t).lower().replace("#", "").replace("-", "")
            if key in infer_map:
                inferred.add(infer_map[key])
        if inferred:
            normalized["domain"] = sorted(list(inferred))

    if not normalized["domain"]:
        normalized["domain"] = ["needs_domain"]

    return normalized


def yaml_dump(data: dict) -> str:
    """
    Minimal YAML dumper for our simple schema.
    Lists are emitted in [a, b, c] form.
    Keys are ordered via YAML_ORDER with any extras appended.
    """
    def fmt_value(v):
        if isinstance(v, list):
            return "[" + ", ".join(str(i) for i in v) + "]"
        v = "" if v is None else str(v)
        return v

    keys = [k for k in YAML_ORDER if k in data] + [k for k in data.keys() if k not in YAML_ORDER]
    lines = []
    for k in keys:
        lines.append(f"{k}: {fmt_value(data.get(k))}")
    return "---\n" + "\n".join(lines) + "\n---\n"


def format_md_row(entry: dict, base_path: Path) -> str:
    title = str(entry.get("title","")).replace("|", r"\|")
    domain = ", ".join(entry.get("domain",[])).replace("|", r"\|")
    tags = ", ".join(entry.get("tags",[])).replace("|", r"\|")
    relevance = str(entry.get("relevance",""))
    date = str(entry.get("date",""))
    source = str(entry.get("source",""))
    source_md = f"[link]({source})" if source else ""

    rel_path = entry.get("_rel_path", entry.get("_path", ""))
    file_link = f"[open]({rel_path})" if rel_path else ""

    return ROW_MD.format(
        title=title or "(untitled)",
        domain=domain or "",
        tags=tags or "",
        relevance=relevance or "",
        date=date or "",
        source=source_md,
        file_link=file_link,
    )


def scan_resources(root_dir: Path, backfill_missing: bool, create_backups: bool, dry_run: bool) -> list[dict]:
    """
    Scan resources directory for markdown files and process YAML frontmatter.
    
    Args:
        root_dir: Directory to scan
        backfill_missing: Whether to add missing YAML fields to existing frontmatter
        create_backups: Whether to create .bak files before modifying
        dry_run: If True, preview changes without writing
        
    Returns:
        List of processed entry dictionaries
    """
    md_files = sorted(root_dir.rglob("*.md"))
    entries: list[dict] = []
    
    for p in md_files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        fm, body, had_yaml = parse_frontmatter(text)
        original_fm = dict(fm)

        if not had_yaml:
            fm = ensure_fields(fm, filename=str(p))
            new_text = yaml_dump(fm) + body.lstrip()
            
            if dry_run:
                print(f"[DRY-RUN] Would add YAML frontmatter to: {p.name}")
                print(f"[DRY-RUN] New fields: domain={fm['domain']}, tags={fm['tags']}")
            else:
                if create_backups:
                    shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
                p.write_text(new_text, encoding="utf-8")
                print(f"[WROTE] Added YAML to: {p.name}")
            updated = True
        else:
            updated = False
            if backfill_missing:
                merged = ensure_fields(fm, filename=str(p))
                if merged != fm:
                    fm = merged
                    new_text = yaml_dump(fm) + body
                    
                    if dry_run:
                        print(f"[DRY-RUN] Would backfill YAML in: {p.name}")
                        print(f"[DRY-RUN] Updated fields: {set(merged.keys()) - set(original_fm.keys())}")
                    else:
                        if create_backups:
                            shutil.copy2(p, p.with_suffix(p.suffix + ".bak"))
                        p.write_text(new_text, encoding="utf-8")
                        print(f"[WROTE] Backfilled YAML in: {p.name}")
                    updated = True

        fm["_path"] = str(p)
        fm["_updated"] = updated
        fm["_had_yaml"] = had_yaml
        fm["_original"] = original_fm
        entries.append(fm)
        
    return entries


def write_indexes(entries: list[dict], index_md_path: Path, index_json_path: Path, dry_run: bool):
    """
    Write the index files (Markdown and JSON).
    
    Args:
        entries: List of resource entries
        index_md_path: Path to write Markdown index
        index_json_path: Path to write JSON index
        dry_run: If True, preview without writing
    """
    base_dir = index_md_path.parent
    for e in entries:
        try:
            rel = Path(e["_path"]).relative_to(base_dir)
        except Exception:
            rel = Path(e["_path"])
        e["_rel_path"] = str(rel).replace("\\", "/")

    rows = [format_md_row(e, base_dir) for e in entries]
    md = TEMPLATE_MD.format(updated=datetime.now().strftime("%Y-%m-%d %H:%M"), rows="\n".join(rows))

    if dry_run:
        print(f"\n[DRY-RUN] Would write Markdown index to: {index_md_path}")
        print(f"[DRY-RUN] Would write JSON index to: {index_json_path}")
        print(f"[DRY-RUN] Index would contain {len(entries)} entries")
    else:
        index_md_path.write_text(md, encoding="utf-8")
        index_json_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[WROTE] Markdown index: {index_md_path}")
        print(f"[WROTE] JSON index: {index_json_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault-path", type=str, default=os.environ.get("VAULT_PATH", ""),
                        help="Path to your Obsidian vault (defaults to VAULT_PATH env var).")
    parser.add_argument("--resources-folder", type=str, default="Resources/learning_inputs",
                        help="Folder (relative to vault) to scan for resource summaries.")
    parser.add_argument("--index-path", type=str, default="Resources/resource_index.md",
                        help="Where to write the Markdown index (relative to vault).")
    parser.add_argument("--json-path", type=str, default="Resources/resource_index.json",
                        help="Where to write the JSON index (relative to vault).")
    parser.add_argument("--no-backfill", action="store_true",
                        help="Do not add missing YAML fields to notes that already have YAML.")
    parser.add_argument("--no-backup", action="store_true",
                        help="Do not write .bak backups before modifying files.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without modifying any files.")
    args = parser.parse_args()

    if not args.vault_path:
        print("[error] No --vault-path provided and VAULT_PATH env var not set.")
        return

    vault = Path(args.vault_path).expanduser().resolve()
    resources_dir = (vault / args.resources_folder).resolve()
    index_md = (vault / args.index_path).resolve()
    index_json = (vault / args.json_path).resolve()

    if not resources_dir.exists():
        print(f"[warn] Resources folder does not exist: {resources_dir}")
        resources_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("[DRY-RUN MODE] No files will be modified\n")
    
    print(f"[info] Scanning: {resources_dir}")
    entries = scan_resources(
        resources_dir, 
        backfill_missing=(not args.no_backfill), 
        create_backups=(not args.no_backup),
        dry_run=args.dry_run
    )

    # Filter to include only 'resource' type
    filtered = []
    for e in entries:
        t = e.get("type", "resource")
        if isinstance(t, list):
            include = any(str(x).lower() == "resource" for x in t)
        else:
            include = str(t).lower() == "resource"
        if include:
            filtered.append(e)

    # Safe sort: use toordinal() and a safe fallback date to avoid Windows negative timestamp issues
    def sort_key(e):
        d = e.get("date", "")
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            dt = datetime(1970, 1, 1)
        return (-dt.toordinal(), str(e.get("title","")).lower())

    filtered.sort(key=sort_key)

    index_md.parent.mkdir(parents=True, exist_ok=True)
    write_indexes(filtered, index_md, index_json, dry_run=args.dry_run)

    total = len(entries)
    created = sum(1 for e in entries if not e.get("_had_yaml"))
    updated = sum(1 for e in entries if e.get("_updated"))
    
    print(f"\n[summary] scanned={total} newly_yaml={created} updated_yaml={updated}")
    
    if args.dry_run:
        print("\n✓ Dry run complete. Run without --dry-run to apply changes.")

if __name__ == "__main__":
    main()
