#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resource Indexer - Learning Pipeline Metadata Manager (Patched Version)

This version:
- Automatically loads .env, matching orchestrator + auto-enricher behavior
- Uses VAULT_PATH from .env/environment if --vault-path is not provided
- Safely creates YAML for notes with no frontmatter
- Backfills missing metadata fields
- Infers domain from tags when possible
- Generates resource_index.md and resource_index.json

Usage:
    python resource_indexer.py --verbose --dry-run
    python resource_indexer.py --vault-path="C:/Users/.../Vault"
"""

from pathlib import Path
import re
import json
from datetime import datetime
import argparse
import os
import shutil

# -------------------------------------------------------------------
# PATCH: Auto-load .env so VAULT_PATH is available consistently
# -------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()        # Loads .env in current repo directory
except Exception:
    pass

# -------------------------------------------------------------------
# Markdown templates for index outputs
# -------------------------------------------------------------------
TEMPLATE_MD = """# 📚 Resource Index
_Last updated: {updated}_

| Title | Domain | Tags | Relevance | Date | Source | File |
|---|---|---|---:|---|---|---|
{rows}
"""

ROW_MD = "| {title} | {domain} | {tags} | {relevance} | {date} | {source} | {file_link} |"

# -------------------------------------------------------------------
# YAML parsing helpers
# -------------------------------------------------------------------
YAML_RE = re.compile(r"^---\s*(.*?)\s*---\s*(.*)$", re.DOTALL)
YAML_ORDER = [
    "title", "type", "domain", "tags", "author", "date", "source", "relevance", "meta_status"
]


def parse_frontmatter(text: str):
    """Parse YAML frontmatter into dict + body."""
    m = YAML_RE.match(text)
    if not m:
        return {}, text, False

    yaml_block = m.group(1)
    body = m.group(2)

    fm = {}
    for raw_line in yaml_block.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [i.strip() for i in inner.split(",")] if inner else []
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


def ensure_fields(fm: dict, filename: str | None = None, verbose: bool = False) -> dict:
    """Backfill missing metadata with defaults & inference."""
    normalized = dict(fm)

    if not normalized.get("title"):
        if filename:
            normalized["title"] = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "(untitled)"
        else:
            normalized["title"] = "(untitled)"
        if verbose:
            print(f"  [verbose] Inferred title from filename: {normalized['title']}")

    normalized["type"] = normalized.get("type") or "resource"
    normalized["domain"] = coerce_list(normalized.get("domain"))
    normalized["tags"] = coerce_list(normalized.get("tags"))
    normalized["author"] = normalized.get("author") or ""
    normalized["date"] = normalized.get("date") or ""
    normalized["source"] = normalized.get("source") or ""
    normalized["relevance"] = normalized.get("relevance") or ""
    normalized["meta_status"] = normalized.get("meta_status") or "reference"

    # Domain inference from tags
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
        inferred = []
        for t in normalized["tags"]:
            key = str(t).lower().replace("#", "").replace("-", "")
            if key in infer_map and infer_map[key] not in inferred:
                inferred.append(infer_map[key])

        if inferred:
            normalized["domain"] = inferred
            if verbose:
                print(f"  [verbose] Inferred domain: {normalized['domain']}")

    if not normalized["domain"]:
        normalized["domain"] = ["needs_domain"]
        if verbose:
            print("  [verbose] No domain found → using default 'needs_domain'")

    return normalized


def yaml_dump(data: dict) -> str:
    """Generate minimal YAML frontmatter."""
    def fmt_value(v):
        if isinstance(v, list):
            return "[" + ", ".join(str(i) for i in v) + "]"
        return "" if v is None else str(v)

    keys = [k for k in YAML_ORDER if k in data] + [k for k in data.keys() if k not in YAML_ORDER]
    return "---\n" + "\n".join(f"{k}: {fmt_value(data.get(k))}" for k in keys) + "\n---\n"


def format_md_row(entry: dict, base_path: Path) -> str:
    title = entry.get("title", "").replace("|", r"\|")
    domain = ", ".join(entry.get("domain", [])).replace("|", r"\|")
    tags = ", ".join(entry.get("tags", [])).replace("|", r"\|")
    relevance = entry.get("relevance", "")
    date = entry.get("date", "")
    source = entry.get("source", "")
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


def scan_resources(root_dir: Path, backfill_missing: bool, create_backups: bool, dry_run: bool, verbose: bool = False) -> list[dict]:
    """Scan resource notes and backfill metadata."""
    md_files = sorted(root_dir.rglob("*.md"))
    entries = []

    if verbose:
        print(f"[verbose] Found {len(md_files)} markdown files")

    for i, p in enumerate(md_files, 1):
        if verbose:
            print(f"[verbose] Processing {i}/{len(md_files)}: {p.name}")

        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            if verbose:
                print(f"  [verbose] Read failed: {e}")
            continue

        fm, body, had_yaml = parse_frontmatter(text)
        original_fm = dict(fm)

        if not had_yaml:
            fm = ensure_fields(fm, filename=str(p), verbose=verbose)
            new_text = yaml_dump(fm) + body.lstrip()

            if dry_run:
                print(f"[DRY] Would add YAML -> {p.name}")
            else:
                if create_backups:
                    shutil.copy2(p, p.with_suffix(".md.bak"))
                p.write_text(new_text, encoding="utf-8")
                print(f"[WROTE] Added YAML -> {p.name}")
            updated = True

        else:
            updated = False
            if backfill_missing:
                merged = ensure_fields(fm, filename=str(p), verbose=verbose)
                if merged != fm:
                    fm = merged
                    new_text = yaml_dump(fm) + body

                    if dry_run:
                        print(f"[DRY] Would backfill YAML -> {p.name}")
                    else:
                        if create_backups:
                            shutil.copy2(p, p.with_suffix(".md.bak"))
                        p.write_text(new_text, encoding="utf-8")
                        print(f"[WROTE] Backfilled YAML -> {p.name}")
                    updated = True

        fm["_path"] = str(p)
        fm["_updated"] = updated
        fm["_had_yaml"] = had_yaml
        fm["_original"] = original_fm
        entries.append(fm)

    return entries


def write_indexes(entries: list[dict], index_md_path: Path, index_json_path: Path, dry_run: bool, verbose: bool = False):
    """Write index Markdown + JSON."""
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
        print(f"[DRY] Would write index -> {index_md_path}")
        print(f"[DRY] Would write JSON -> {index_json_path}")
    else:
        index_md_path.write_text(md, encoding="utf-8")
        index_json_path.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"[WROTE] Index MD -> {index_md_path}")
        print(f"[WROTE] Index JSON -> {index_json_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault-path", "--vault", type=str, default=os.environ.get("VAULT_PATH", ""),
                        help="Path to Obsidian vault")
    parser.add_argument("--resources-folder", type=str, default="Resources/learning_inputs")
    parser.add_argument("--index-path", type=str, default="Resources/resource_index.md")
    parser.add_argument("--json-path", type=str, default="Resources/resource_index.json")
    parser.add_argument("--no-backfill", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # ------------------------------------------------------------
    # PATCH: Use VAULT_PATH from .env if no --vault-path provided
    # ------------------------------------------------------------
    if not args.vault_path:
        env_vault = os.environ.get("VAULT_PATH", "").strip()
        if env_vault:
            args.vault_path = env_vault
        else:
            print("[error] No --vault-path and VAULT_PATH not found in environment/.env")
            return

    vault = Path(args.vault_path).expanduser().resolve()
    resources_dir = (vault / args.resources_folder).resolve()
    index_md = (vault / args.index_path).resolve()
    index_json = (vault / args.json_path).resolve()

    if not resources_dir.exists():
        print(f"[warn] Missing resources folder: {resources_dir}")
        resources_dir.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"[verbose] Vault: {vault}")
        print(f"[verbose] Resources: {resources_dir}")
        print(f"[verbose] Index MD: {index_md}")
        print(f"[verbose] Index JSON: {index_json}")

    entries = scan_resources(
        resources_dir,
        backfill_missing=not args.no_backfill,
        create_backups=False if args.dry_run else (not args.no_backup),
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Only include type: resource
    filtered = []
    for e in entries:
        t = e.get("type", "resource")
        if isinstance(t, list):
            include = any(str(x).lower() == "resource" for x in t)
        else:
            include = str(t).lower() == "resource"
        if include:
            filtered.append(e)

    # Sort by date desc, title asc
    def sort_key(e):
        d = e.get("date", "")
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            dt = datetime(1970, 1, 1)
        return (-dt.toordinal(), str(e.get("title", "")).lower())

    filtered.sort(key=sort_key)

    index_md.parent.mkdir(parents=True, exist_ok=True)
    write_indexes(filtered, index_md, index_json, dry_run=args.dry_run, verbose=args.verbose)

    print(f"\n[summary] scanned={len(entries)} newly_yaml={sum(not e.get('_had_yaml') for e in entries)} updated_yaml={sum(e.get('_updated') for e in entries)}")

    if args.dry_run:
        print("\n[OK] Dry run complete.")


if __name__ == "__main__":
    main()
