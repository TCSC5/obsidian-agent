# -*- coding: utf-8 -*-
"""
prioritizer_agent.py — Auto-score Express notes with priority/urgency/actionability/relevance
"""

import os, json, re
from datetime import datetime
from pathlib import Path

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

VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
EXPRESS_DIRS = [VAULT / "Express" / "pitch", VAULT / "Express" / "insights"]

def extract_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def score_note(title: str, content: str):
    if not _use_gpt or client is None:
        # Heuristic fallback: mark everything medium
        return {"priority": "medium", "urgency": "medium", "actionability": "medium", "relevance": 5.0}

    prompt = f"""
Analyze this content and score the following attributes from 1–10. Return ONLY a JSON object like this:
{{
  "priority": "high|medium|low",
  "urgency": "high|medium|low",
  "actionability": "high|medium|low",
  "relevance": float
}}

# Title: {title}
# Content:
{content[:1200]}
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        print(f"❌ Failed to score {title}: {e}")
        return {}

def update_frontmatter(path: Path, scores: dict):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    if not lines or not lines[0].strip().startswith("---"):
        lines.insert(0, "---\n")
        lines.insert(1, "---\n")

    try:
        start = lines.index("---\n")
        end = lines.index("---\n", start + 1)
    except ValueError:
        start, end = 0, 1

    yaml_lines = lines[start+1:end]

    for key, val in scores.items():
        line = f"{key}: {val}\n"
        existing = [l for l in yaml_lines if l.startswith(f"{key}:")]
        if existing:
            i = yaml_lines.index(existing[0])
            yaml_lines[i] = line
        else:
            yaml_lines.append(line)

    lines = lines[:start+1] + yaml_lines + lines[end:]
    path.write_text("".join(lines), encoding="utf-8")
    print(f"✅ Prioritized: {path.name}")

def main():
    for folder in EXPRESS_DIRS:
        if not folder.exists():
            continue
        for fpath in folder.glob("*.md"):
            text = extract_text(fpath)
            scores = score_note(fpath.stem, text)
            if scores:
                update_frontmatter(fpath, scores)
    print("✅ Finished prioritizing notes.")

if __name__ == "__main__":
    main()
