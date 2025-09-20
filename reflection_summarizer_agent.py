# -*- coding: utf-8 -*-
"""
reflection_summarizer_agent.py — GPT-powered executive summary of Reflection logs.

Inputs:
- data/reflection_log.md
- (optional) System/synergy_scores.csv

Outputs:
- data/reflection_summary.md
- System/reflection_summary.md (synced)

Env:
- VAULT_PATH
- OPENAI_API_KEY (optional; fallback = heuristic summarization)
"""

import os, re
from pathlib import Path
from datetime import datetime

# --- Robust .env loader ---
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
except Exception:
    pass

# Diagnostic
_k = os.getenv("OPENAI_API_KEY")
print(f"[env] OPENAI_API_KEY loaded? {'yes' if _k else 'no'}")

VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
BASE = Path(__file__).parent.resolve()
DATA = BASE / "data"
SYSTEM = VAULT / "System"
DATA.mkdir(parents=True, exist_ok=True)
SYSTEM.mkdir(parents=True, exist_ok=True)

REFLECTION_LOG = DATA / "reflection_log.md"
SYNERGY_CSV = SYSTEM / "synergy_scores.csv"
OUT = DATA / "reflection_summary.md"
OUT_VAULT = SYSTEM / "reflection_summary.md"

# --- OpenAI client (optional) ---
_use_gpt = False
client = None
try:
    from openai import OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        client = OpenAI()
        _use_gpt = True
except Exception:
    _use_gpt = False
    client = None

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def fallback_summary(txt: str) -> str:
    # Extract first lines and top 3 reasons
    lines = txt.splitlines()
    bullets = [l for l in lines if l.strip().startswith("- ")]
    out = ["- " + l[2:] for l in bullets[:5]]
    if not out:
        out = ["- Reflection log exists but no bullets found."]
    return "\n".join(out)

def gpt_summary(txt: str) -> str:
    if not _use_gpt or client is None:
        return fallback_summary(txt)

    prompt = f"""
Summarize the following reflection log into:
1. 3–5 bullet executive summary of pipeline health
2. "What changed since last run" (if possible)
3. 1–2 high-level recommendations

Reflection log:
\"\"\"{txt[:3000]}\"\"\"
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.3,
        )
        return res.choices[0].message.content
    except Exception:
        return fallback_summary(txt)

def main():
    if not REFLECTION_LOG.exists():
        OUT.write_text("# Reflection Summary\n\n_No reflection log found._", encoding="utf-8")
        return
    txt = read_text(REFLECTION_LOG)
    summary = gpt_summary(txt)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = f"# 🪞 Reflection Executive Summary — {now}\n\n{summary}\n"
    OUT.write_text(md, encoding="utf-8")
    try:
        OUT_VAULT.write_text(md, encoding="utf-8")
    except Exception:
        pass
    print(f"✅ Reflection summary written to {OUT} and {OUT_VAULT}")

if __name__ == "__main__":
    main()
