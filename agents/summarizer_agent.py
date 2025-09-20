import os, re, traceback
from pathlib import Path

# ---------- Helpers ----------
FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?')

def _strip_frontmatter(txt: str) -> str:
    m = FRONTMATTER_RE.match(txt)
    return txt[m.end():] if m else txt

def _title_from_path(p: Path) -> str:
    return p.stem.replace("_", " ").replace("-", " ").strip()

def _extract_key_points(text: str, k=10):
    bullets = re.findall(r'(?m)^\s*[-*+]\s+(.+)$', text)
    headings = re.findall(r'(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$', text)
    pts = bullets + headings
    pts = [re.sub(r'\s+\^[A-Za-z0-9_-]+\s*$', '', t).strip() for t in pts]
    uniq = []
    for t in pts:
        if t and t not in uniq:
            uniq.append(t)
    return uniq[:k]

def _heuristic_cheatsheet(body: str, title: str) -> str:
    ideas = _extract_key_points(body, k=8)
    lines = []
    lines.append(f"# Cheat Sheet: {title}")
    lines.append("")
    lines.append("## Evaluate first")
    lines.append("- What matters most here, and why?")
    lines.append("- Which interpretation is strongest? Justify criteria and trade-offs.")
    lines.append("- Where could this approach fail or mislead?")
    lines.append("")
    lines.append("## Analyze")
    lines.append("- Compare/contrast the core concepts or methods.")
    lines.append("- Map cause → effect relationships and note assumptions.")
    lines.append("- Identify patterns or categories that organize the ideas.")
    lines.append("")
    lines.append("## Apply")
    lines.append("- Given scenario X, how would you use the concept?")
    lines.append("- What changes if constraints A/B/C shift?")
    lines.append("")
    lines.append("## Key Ideas (for memory)")
    if ideas:
        for i in ideas[:8]:
            lines.append(f"- {i}")
    else:
        lines += ["- Fill in essential definition/fact here."] * 6
    return "\n".join(lines).rstrip() + "\n"

def _sections_present(md: str) -> bool:
    req = ["## Evaluate", "## Analyze", "## Apply", "## Key Ideas"]
    return all(s in md for s in req)

def _agent_log(agent: str, mode: str, title: str):
    import time
    logdir = os.environ.get("TRAINING_LOG_DIR") or os.path.join(os.path.dirname(__file__), "..", "logs")
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(os.path.join(logdir, "agent_mode.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | {agent:<10} | {mode:<9} | {title}\n")
    except Exception:
        pass  # never block generation on logging

# ---------- OpenAI driver (optional) ----------
def _call_openai(system: str, user: str, model: str = None, temperature: float = 0.2) -> str:
    try:
        try:
            from openai import OpenAI
            client = OpenAI()
            model = model or os.environ.get("TRAINING_MODEL", "gpt-4o-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception:
            import openai  # legacy
            openai.api_key = os.environ.get("OPENAI_API_KEY")
            model = model or os.environ.get("TRAINING_MODEL", "gpt-4o-mini")
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=temperature,
            )
            return resp.choices[0].message["content"]
    except Exception:
        return ""

# ---------- Public API ----------
def summarize_note_to_cheatsheet_md(src_path: Path, out_path: Path):
    """
    Reverse Bloom's cheatsheet: Evaluate → Analyze → Apply → Key Ideas.
    No frontmatter; pipeline adds it later.
    """
    try:
        raw = Path(src_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        traceback.print_exc()
        raw = ""
    body = _strip_frontmatter(raw)
    title = _title_from_path(Path(src_path))

    content = ""
    if os.environ.get("OPENAI_API_KEY"):
        max_chars = int(os.environ.get("TRAINING_MAX_CHARS", "30000"))
        body_trim = body[:max_chars]
        sys_prompt = (
            "You are a precise study-writer using Reverse Bloom's Taxonomy. "
            "Output STRICT markdown with these sections ONLY and in this order:\n"
            "## Evaluate first — 3–4 bullets (judgments, trade-offs, criteria, risks)\n"
            "## Analyze — 3–4 bullets (compare/contrast, cause→effect, patterns, assumptions)\n"
            "## Apply — 2–3 bullets (scenarios, parameters to watch, adaptations)\n"
            "## Key Ideas (for memory) — 5–8 bullets (definitions, formulas, facts)\n"
            "Rules: Keep language grounded in the source; no intro/outro; no frontmatter; no extra sections."
        )
        user_prompt = (
            f"Title: {title}\n"
            f"Source note follows between <note> tags. Extract structure and stay faithful; do not invent citations.\n"
            f"<note>\n{body_trim}\n</note>"
        )
        content = _call_openai(sys_prompt, user_prompt, temperature=0.2)

    if content and _sections_present(content):
        _agent_log("summarizer", "OpenAI", title)
    else:
        content = _heuristic_cheatsheet(body, title)
        _agent_log("summarizer", "Heuristic", title)

    Path(out_path).write_text(content, encoding="utf-8")
    return out_path
