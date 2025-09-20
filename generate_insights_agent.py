
# -*- coding: utf-8 -*-
"""
generate_insights_agent.py — create Insights with type: insight

- Writes to VAULT/Express/insights
- Front matter includes `type: insight`
"""

import os, time
from pathlib import Path

VAULT = Path(os.getenv("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
OUT   = VAULT / "Express" / "insights"
OUT.mkdir(parents=True, exist_ok=True)

def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = OUT / f"insight_{ts}.md"
    fm = [
        "---",
        f"title: GPT Insights — {ts}",
        "type: insight",
        "tags: [insights, gpt]",
        f"created: {time.strftime('%Y-%m-%d')}",
        "---",
        "",
        "_Write your insight here..._",
        "",
    ]
    out.write_text("\\n".join(fm), encoding="utf-8")
    print("[OK] Created", out)

if __name__ == "__main__":
    main()
