# auto_enrich_pitch_notes.py
# -*- coding: utf-8 -*-

import os, sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Step 1: Try to reconfigure console encoding to UTF‑8 (Python 3.7+)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Step 2: Define safe_print wrapper
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8")
        msg = " ".join(str(a) for a in args)
        sys.stdout.buffer.write((msg + "\n").encode(enc, errors="replace"))

# Step 3: Load environment & set up directories
load_dotenv(find_dotenv())
VAULT = os.getenv("VAULT_PATH", "")
PITCH_DIR = os.path.join(VAULT, "Express", "pitch")
API_KEY = os.getenv("OPENAI_API_KEY")

safe_print("[OK] Pitch notes directory:", PITCH_DIR)

if not API_KEY:
    safe_print("[SKIP] OPENAI_API_KEY not set — skipping enrichment.")
    sys.exit(0)
if not os.path.isdir(PITCH_DIR):
    safe_print("[SKIP] Pitch directory not found — skipping enrichment.")
    sys.exit(0)

# Step 4: Loop through pitch files and enrich
for file in Path(PITCH_DIR).glob("pitch_*.md"):
    safe_print(f"[INFO] Enriching: {file.name}")
    content = file.read_text(encoding="utf-8")

    missing = []
    if "**Problem:**" in content and "Define manually" in content:
        missing.append("problem_definition")
    if "## Related Links" in content and "[[" not in content:
        missing.append("related_links")
    if "created: " not in content:
        missing.append("date")
    if "tags:" in content and "[]" in content:
        missing.append("tags")

    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("tags:"):
            base = line.rstrip("]")
            for flag in missing:
                base = base.replace("]", f", missing_{flag}]")
            lines[idx] = base

    if missing and "## Additional Info Needed" not in content:
        lines.append("\n## Additional Info Needed")
        for m in missing:
            lines.append(f"- Missing: {m}")

    file.write_text("\n".join(lines), encoding="utf-8")
    safe_print(f"[OK] Enriched {file.name} → Missing: {', '.join(missing) if missing else 'None'}")

safe_print("[OK] Step 10 (Auto‑enrich pitch notes) completed successfully.")
