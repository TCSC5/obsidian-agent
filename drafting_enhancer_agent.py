# -*- coding: utf-8 -*-
"""
drafting_enhancer_agent.py — GPT fills initial drafts for insights & pitches

Inputs:
- Summaries/summary_*.md

Outputs:
- Express/insights/insight_<slug>.md with auto-filled Hypothesis/Implications/Actions
- Express/pitch/pitch_<slug>.md with auto-filled Summary/Problem/Solution/Value Prop
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
SUMMARIES = VAULT / "Summaries"
PITCH_DIR = VAULT / "Express" / "pitch"
INSIGHT_DIR = VAULT / "Express" / "insights"
for d in [PITCH_DIR, INSIGHT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# --- OpenAI client (optional) ---
_use_gpt = False
client = None
try:
    from openai import OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        client = OpenAI()  # reads key from env
        _use_gpt = True
except Exception:
    _use_gpt = False
    client = None

def read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "untitled"

def gpt_draft(summary: str, mode: str = "insight") -> str:
    if not _use_gpt or client is None:
        return f"Draft ({mode}) — GPT not available.\n\n> (Set OPENAI_API_KEY to enable drafting.)"

    if mode == "insight":
        prompt = (
            "From the following summary, propose: "
            "a 1-sentence Hypothesis, 2 Implications, and 2 Suggested Actions.\n\n"
            f"{summary[:1500]}"
        )
    else:
        prompt = (
            "From the following summary, draft: a 1-paragraph Summary, a Problem statement, "
            "a Proposed Solution, and a Value Proposition.\n\n"
            f"{summary[:1500]}"
        )

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"Draft generation failed: {e}"

def main():
    if not SUMMARIES.exists():
        print(f"⚠️ Summaries folder not found at {SUMMARIES}")
        return

    for p in SUMMARIES.glob("summary_*.md"):
        txt = read_text(p)
        m = re.search(r"^#\s+(.+)", txt, flags=re.M)
        title = (m.group(1).strip() if m else p.stem).strip()
        slug = slugify(title)

        # Insight draft
        insight_path = INSIGHT_DIR / f"insight_{slug}.md"
        if not insight_path.exists():
            draft = gpt_draft(txt, "insight")
            insight_path.write_text(
                f"# Insight: {title}\n\n{draft}\n\n## 🧭 Checklist\n"
                "- [ ] Review Hypothesis\n"
                "- [ ] Review Implications\n"
                "- [ ] Review Actions\n",
                encoding="utf-8",
            )
            print(f"[OK] Drafted insight -> {insight_path.name}")

        # Pitch draft
        pitch_path = PITCH_DIR / f"pitch_{slug}.md"
        if not pitch_path.exists():
            draft = gpt_draft(txt, "pitch")
            pitch_path.write_text(
                f"# Pitch: {title}\n\n{draft}\n\n## 🎯 Checklist\n"
                "- [ ] Review Summary\n"
                "- [ ] Review Problem\n"
                "- [ ] Review Solution\n"
                "- [ ] Review Value Prop\n",
                encoding="utf-8",
            )
            print(f"[OK] Drafted pitch -> {pitch_path.name}")

if __name__ == "__main__":
    main()
