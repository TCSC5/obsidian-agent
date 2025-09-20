# -*- coding: utf-8 -*-
"""
agent_architect_agent.py — GPT-powered upgrade

Inputs:
- System/success_metrics.json
- data/reflection_log.md
- data/learning_loops.md
- System/decision_support.md

Outputs:
- System/agent_architect_report.md
"""

import os, json
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

SUCCESS_JSON = SYSTEM / "success_metrics.json"
REFLECTION = DATA / "reflection_log.md"
LOOPS = DATA / "learning_loops.md"
DECISION = SYSTEM / "decision_support.md"
OUT = SYSTEM / "agent_architect_report.md"

# --- OpenAI client (optional) ---
_use_gpt = False
client = None
try:
    from openai import OpenAI  # modern SDK; reads OPENAI_API_KEY from env
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

def gpt_report(success: str, refl: str, loops: str, decision: str) -> str:
    if not _use_gpt or client is None:
        return (
            "### Agent Architect Report (Heuristic)\n"
            "- GPT unavailable. Review success metrics and recent logs.\n"
            "- Quick wins: tighten YAML completeness checks; ensure router honors `type:`; add alerts for low-synergy items hogging time.\n"
            "- Long-term: evaluate scoring weights quarterly; add A/B on gating prompts.\n"
        )

    prompt = f"""
You are Agent Architect GPT. Analyze the following data and propose system improvements:

Success metrics (JSON or text):
{success}

Reflection log:
{refl[:2000]}

Learning loops:
{loops[:1000]}

Decision Support:
{decision[:1500]}

Deliver:
1. Top 3 system weaknesses (bullet list).
2. Suggested quick-win changes.
3. Suggested long-term changes.
4. New agent or rule ideas if needed.

Be concise and structured.
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.4,
        )
        return res.choices[0].message.content
    except Exception:
        return (
            "### Agent Architect Report\n"
            "⚠️ Could not run GPT, please check API key."
        )

def main():
    success = read_text(SUCCESS_JSON) if SUCCESS_JSON.exists() else "{}"
    refl = read_text(REFLECTION)
    loops = read_text(LOOPS)
    decision = read_text(DECISION)
    report = gpt_report(success, refl, loops, decision)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = f"# 🧩 Agent Architect — System Review ({now})\n\n{report}\n"
    OUT.write_text(md, encoding="utf-8")
    print(f"✅ Agent Architect report written to {OUT}")

if __name__ == "__main__":
    main()
