
# -*- coding: utf-8 -*-
"""
stamp_pitch_frontmatter.py — ensure all pitches have minimal FM:
- type: pitch
- created: YYYY-MM-DD
- origin_note: inferred from filename "pitch_summary_<slug>.md" -> "summary_<slug>.md"

Fix: default VAULT_PATH now C:\\Users\\top2e\\Sync, or auto-detect nearest vault structure.
"""

import os, re, time
from pathlib import Path

def detect_vault(default: Path) -> Path:
    # Try env first
    ev = os.getenv("VAULT_PATH")
    if ev and Path(ev).exists():
        return Path(ev)
    # Try to guess by walking up until a folder that contains Express or Summaries
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "Express").exists() or (p / "Summaries").exists():
            return p
    return default

DEFAULT_VAULT = Path(r"C:\\Users\\top2e\\Sync")
VAULT = detect_vault(DEFAULT_VAULT)

PITCH_DIR = VAULT / "Express" / "pitch"
SUMMARY_DIR = VAULT / "Summaries"

PITCH_DIR.mkdir(parents=True, exist_ok=True)

def ensure_frontmatter(text: str, origin: str):
    text = text.lstrip()
    if text.startswith("---"):
        # already has FM; just ensure required keys
        end = text.find("\\n---", 3)
        if end == -1:
            end = 0
        fm = text[:end+4]
        body = text[end+4:]
        # enforce minimal keys
        if "type:" not in fm:
            fm = fm[:-4] + "\\ntype: pitch\\n---"
        if "created:" not in fm:
            fm = fm[:-4] + f"\\ncreated: {time.strftime('%Y-%m-%d')}\\n---"
        if "origin_note:" not in fm:
            fm = fm[:-4] + f"\\norigin_note: {origin}\\n---"
        # strip area/resources if present later in body
        body = re.sub(r'^\\s*(area|areas|resources?):\\s*.*$', '', body, flags=re.I|re.M)
        return fm + body
    # no FM; create
    fm = [
        "---",
        "type: pitch",
        f"created: {time.strftime('%Y-%m-%d')}",
        f"origin_note: {origin}",
        "---",
        "",
    ]
    body = re.sub(r'^\\s*(area|areas|resources?):\\s*.*$', '', text, flags=re.I|re.M)
    return "\\n".join(fm) + body

def origin_from_filename(name: str) -> str:
    m = re.match(r'^pitch_summary_(.+)\\.md$', name, re.I)
    if not m:
        return ""
    return f"summary_{m.group(1)}.md"

def main():
    stamped, skipped = 0, 0
    if not PITCH_DIR.exists():
        print(f"[warn] Pitch dir not found: {PITCH_DIR}")
        return
    for md in PITCH_DIR.glob("pitch_summary_*.md"):
        src = md.read_text(encoding="utf-8", errors="replace")
        origin = origin_from_filename(md.name)
        new = ensure_frontmatter(src, origin)
        if new != src:
            md.write_text(new, encoding="utf-8")
            stamped += 1
            print(f"[ok] Stamped: {md.name} -> type: pitch")
        else:
            skipped += 1
            print(f"[skip] Already stamped: {md.name}")
    print(f"[done] stamped={stamped}, already_ok={skipped}")

if __name__ == "__main__":
    main()
