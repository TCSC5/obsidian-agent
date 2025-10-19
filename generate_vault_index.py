#!/usr/bin/env python3
"""
Vault Scanner - Read-Only Vault Indexer

Scans entire vault for *.md files (except Archives/.obsidian) and generates:
- data/vault_index.json with basic metadata (path, folder, title, tags, mtime, size)

This is a READ-ONLY tool for general vault navigation/search.
For learning resource management with YAML validation, use resource_indexer.py instead.

Usage:
    python generate_vault_index.py
    python generate_vault_index.py --vault-path="C:\Your\Vault"

Environment Variables:
    VAULT_PATH: Vault location (defaults to C:\Users\top2e\Sync)

Output:
    - data/vault_index.json (full vault index)

Examples:
    # Use default vault path
    python generate_vault_index.py
    
    # Specify custom vault
    python generate_vault_index.py --vault-path="D:\MyVault"
    
    # Custom output location
    python generate_vault_index.py --output="reports\vault_scan.json"
"""

import os
import json
import argparse
from pathlib import Path

# Defaults
DEFAULT_VAULT = Path(os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync")
BASE = Path(__file__).parent
DEFAULT_OUTPUT = BASE / "data" / "vault_index.json"

SKIP_DIRS = {".obsidian", ".trash", "Archives"}


def read_yaml_frontmatter(text: str):
    """Extract YAML frontmatter from markdown text."""
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
    """Extract title from first markdown heading or use filename."""
    for line in text.splitlines():
        if line.strip().startswith("# "):
            return line.strip().lstrip("# ").strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, 
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--vault-path", 
        type=str,
        default=str(DEFAULT_VAULT),
        help="Path to Obsidian vault (defaults to VAULT_PATH env var)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output JSON file path (default: data/vault_index.json)"
    )
    args = parser.parse_args()
    
    vault = Path(args.vault_path).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    
    if not vault.exists():
        print(f"[error] Vault path does not exist: {vault}")
        return
    
    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[info] Scanning vault: {vault}")
    
    rows = []
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault).as_posix()
        parts = rel.split("/")
        
        # Skip configured directories
        if parts and parts[0] in SKIP_DIRS:
            continue
        
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[warn] Could not read {rel}: {e}")
            continue
            
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
    
    output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), 
        encoding="utf-8"
    )
    
    print(f"[ok] Indexed {len(rows)} notes to {output}")


if __name__ == "__main__":
    main()
