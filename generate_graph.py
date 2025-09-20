
# -*- coding: utf-8 -*-
"""
generate_graph.py — path-based graph with `links` (not `edges`)

Inputs (if present):
  data/vault_index.json       — index rows with at least {"path","title"}
  data/links_log.csv          — link rows; prefers source_path/target_path columns

Outputs:
  data/note_graph.json        — {"nodes":[{"id": "<path>"}], "links":[{"source":"<path>","target":"<path>"}]}
  data/note_graph.dot         — Graphviz DOT with path labels

This aligns with synergy_refinement.py, which expects:
  - graph["links"]  (not "edges")
  - path-based IDs to detect Express/pitch|insights and PARA buckets.
"""

import os, json, csv, sys
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True, parents=True)

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync")

index_path = DATA / "vault_index.json"
links_csv = DATA / "links_log.csv"
json_out = DATA / "note_graph.json"
dot_out  = DATA / "note_graph.dot"

# Load vault index (optional, used for title→path fallback and node attrs)
title_to_path = {}
paths = set()
if index_path.exists():
    try:
        rows = json.loads(index_path.read_text(encoding="utf-8"))
        for row in rows:
            p = row.get("path") or row.get("relpath") or row.get("file")
            t = (row.get("title") or "").strip()
            if p:
                paths.add(p)
                if t and t not in title_to_path:
                    title_to_path[t] = p
    except Exception as e:
        print("[warn] Could not read vault_index.json:", e)

# Load links
links = []
if links_csv.exists():
    with links_csv.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            sp = (row.get("source_path") or "").strip()
            tp = (row.get("target_path") or "").strip()
            if not sp or not tp:
                # fallback to titles if needed
                st = (row.get("source") or "").strip()
                tt = (row.get("target") or "").strip()
                sp = sp or title_to_path.get(st, st)
                tp = tp or title_to_path.get(tt, tt)
            if sp and tp:
                links.append({"source": sp, "target": tp})
                paths.add(sp); paths.add(tp)
else:
    print("[warn] links_log.csv not found; graph will be empty unless built from index only.")

# Create node list from all paths seen
nodes = [{"id": p} for p in sorted(paths)]

graph = {"nodes": nodes, "links": links}
json_out.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

# DOT (simple)
with dot_out.open("w", encoding="utf-8") as f:
    f.write("digraph NoteGraph {\n")
    for p in paths:
        label = p.replace("\\", "/")
        f.write(f'  "{p}" [label="{label}"];\n')
    for e in links:
        f.write(f'  "{e["source"]}" -> "{e["target"]}";\n')
    f.write("}\n")

print(f"Exported graph: {len(nodes)} nodes, {len(links)} links.")
print("DOT path:", dot_out)
print("JSON path:", json_out)
