
# -*- coding: utf-8 -*-
"""
generate_pitch_deck.py — create Pitches from Summaries with type: pitch

- Reads VAULT/Summaries/summary_*.md
- Creates VAULT/Express/pitch/pitch_<summary_slug>.md
- Front matter includes `type: pitch` so stamping is optional.
"""

import os, time, re
from pathlib import Path

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
SUM   = VAULT / "Summaries"
OUT   = VAULT / "Express" / "pitch"
OUT.mkdir(parents=True, exist_ok=True)

def slugify(name: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9\\-_.]+', '-', name.strip().lower())
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or "untitled"

def read_yaml_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\\n---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end]
    body = text[end+4:]
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\\\"")
    return meta, body

def main():
    created = 0
    for md in SUM.glob("summary_*.md"):
        base = md.stem  # summary_foo
        slug = slugify(base.replace("summary_", ""))
        out = OUT / f"pitch_summary_{slug}.md"
        if out.exists():
            # create a numbered variant to avoid overwrite
            i = 2
            while True:
                alt = OUT / f"pitch_summary_{slug}-{i}.md"
                if not alt.exists():
                    out = alt
                    break
                i += 1

        src = md.read_text(encoding="utf-8", errors="replace")
        meta, body = read_yaml_frontmatter(src)
        title = meta.get("title") or base.replace("_"," ").replace("-"," ").title()

        fm_lines = [
            "---",
            f"title: {title}",
            "type: pitch",
            "tags: [pitch_deck, express]",
            f"source_note: [[{md.name}]]",
            f"origin_note: {md.name}",
            f"created: {time.strftime('%Y-%m-%d')}",
            "---",
            "",
        ]
        out.write_text("\\n".join(fm_lines) + body, encoding="utf-8")
        created += 1
        print(f"[OK] Created pitch -> {out}")

    print(f"[OK] Generated {created} pitch file(s) in: {OUT}")

if __name__ == "__main__":
    main()
