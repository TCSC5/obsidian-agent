# Usage: python tools/upgrade_links_log.py
import os, csv, json

BASE = os.path.dirname(os.path.dirname(__file__))
DATA = os.path.join(BASE, "data")
INDEX_JSON = os.path.join(DATA, "vault_index.json")
LINKS_IN   = os.path.join(DATA, "links_log.csv")
LINKS_OUT  = os.path.join(DATA, "links_log_upgraded.csv")

def main():
    if not os.path.exists(LINKS_IN):
        print("No data/links_log.csv found.")
        return
    index = []
    if os.path.exists(INDEX_JSON):
        index = json.load(open(INDEX_JSON, encoding="utf-8"))
    title_to_path = {}
    for it in index:
        p = it.get("path", "")
        title = it.get("title") or os.path.splitext(os.path.basename(p))[0]
        if title and p and title not in title_to_path:
            title_to_path[title] = p
    with open(LINKS_IN, encoding="utf-8") as f, open(LINKS_OUT, "w", newline="", encoding="utf-8") as g:
        r = csv.DictReader(f)
        fn = r.fieldnames or []
        fn = fn + [c for c in ("source_path","target_path") if c not in fn]
        w = csv.DictWriter(g, fieldnames=fn); w.writeheader()
        for row in r:
            s, t = row.get("source",""), row.get("target","")
            row["source_path"] = row.get("source_path") or title_to_path.get(s, "")
            row["target_path"] = row.get("target_path") or title_to_path.get(t, "")
            w.writerow(row)
    print("Upgraded ->", LINKS_OUT)

if __name__ == "__main__":
    main()
