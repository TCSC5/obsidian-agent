import os
import csv
import re
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
vault_path = os.getenv("VAULT_PATH", "C:/Users/top2e/Sync")

base_dir = os.path.dirname(__file__)
log_path = os.path.join(base_dir, "data", "links_log.csv")
output_path = os.path.join(base_dir, "note_graph.md")

# prefer path-based identity; fall back to titles
def label_for(path_or_title: str) -> str:
    # use filename without extension when a path is provided, else the title
    base = os.path.basename(path_or_title).rsplit(".", 1)[0] if ("/" in path_or_title or "\\" in path_or_title) else path_or_title
    # sanitize for Mermaid node id
    base = re.sub(r"[^A-Za-z0-9_]", "_", base.strip())
    if not base:
        base = "Node"
    return base

edges = set()

with open(log_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames or []
    has_sp = "source_path" in fields; has_tp = "target_path" in fields
    for row in reader:
        src = (row.get("source_path") or "").strip() if has_sp else ""
        dst = (row.get("target_path") or "").strip() if has_tp else ""
        if not src:
            src = (row.get("source") or "").strip()
        if not dst:
            dst = (row.get("target") or "").strip()
        if not src or not dst:
            continue
        edges.add((label_for(src), label_for(dst)))

with open(output_path, "w", encoding="utf-8") as f:
    f.write("# Note Link Graph\n\n")
    f.write("```mermaid\ngraph TD\n")
    for s, t in sorted(edges):
        f.write(f"    {s} --> {t}\n")
    f.write("```\n")

print(f"Mermaid graph written to {output_path}")