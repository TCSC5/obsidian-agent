import os, re, traceback, textwrap
from pathlib import Path

FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?')

def _strip_frontmatter(txt: str) -> str:
    m = FRONTMATTER_RE.match(txt)
    return txt[m.end():] if m else txt

def _title_from_path(p: Path) -> str:
    return p.stem.replace("_", " ").replace("-", " ").strip()

def _heuristic_key_points(text: str, k=12):
    bullets = re.findall(r'(?m)^\s*[-*+]\s+(.+)$', text)
    headings = re.findall(r'(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$', text)
    pts = bullets + headings
    pts = [re.sub(r'\s+\^[A-Za-z0-9_-]+\s*$', '', t).strip() for t in pts]
    uniq = []
    for t in pts:
        if t and t not in uniq:
            uniq.append(t)
    return uniq[:k] if uniq else []

BLOOM_KEYWORDS = {
    "evaluate": ["evaluate", "justify", "defend", "assess", "critique", "prioritize", "trade-off", "strongest"],
    "analyze":  ["analyze", "compare", "contrast", "distinguish", "pattern", "cause", "effect", "assumption"],
    "apply":    ["apply", "use", "execute", "demonstrate", "solve", "implement"],
    "understand": ["explain", "summarize", "describe", "outline", "paraphrase"],
}

def _classify_bloom(q: str) -> str:
    t = q.lower()
    for lvl, kws in BLOOM_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return lvl
    return "analyze" if q.endswith("?") else "understand"

def _ensure_exact_count(items, n, filler_topic):
    items = items[:n]
    while len(items) < n:
        q = f"[Evaluate]: Which interpretation of **{filler_topic}** is strongest in context, and why?"
        a = f"Justify a position using explicit criteria; note limitations for **{filler_topic}**."
        items.append((q, a))
    return items

# ---------- Tracing helpers ----------
def _tokenize(s: str):
    s = re.sub(r'[^a-z0-9\s]', ' ', (s or '').lower())
    words = [w for w in s.split() if len(w) >= 3]
    return set(words)

def _jaccard(a: set, b: set) -> float:
    if not a or not b: return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _load_cheat_blocks(cheat_path: Path):
    # returns [(block_text, block_id_str)]
    if not cheat_path.exists(): return []
    txt = cheat_path.read_text(encoding="utf-8", errors="ignore")
    blocks = []
    for line in txt.splitlines():
        m = re.match(r'^\s*-\s+(.*?)(\s+\^(?P<bid>[A-Za-z0-9_-]+))\s*$', line)
        if m:
            blocks.append((m.group(1).strip(), "^" + m.group("bid")))
    return blocks

def _best_traces(answer_text: str, cheat_blocks, min_overlap=0.10, topk=2):
    a = _tokenize(answer_text)
    scored = []
    for txt, bid in cheat_blocks:
        sim = _jaccard(a, _tokenize(txt))
        if sim >= min_overlap:
            scored.append((sim, bid))
    scored.sort(reverse=True)
    return [bid for sim, bid in scored[:topk]]

def _format_quiz(title: str, qa_pairs, src_path: Path):
    lines = [f"# Quiz: {title}", ""]
    # Locate cheatsheet next to source note: foo.md -> foo.cheatsheet.md
    cheat_path = src_path.with_suffix(".cheatsheet.md")
    cheat_stem = cheat_path.stem  # e.g., "foo.cheatsheet"
    blocks = _load_cheat_blocks(cheat_path)
    min_overlap = float(os.environ.get("TRACE_MIN_OVERLAP", "0.10"))
    topk = int(os.environ.get("TRACE_TOPK", "2"))

    for i, (q, a) in enumerate(qa_pairs, start=1):
        # ensure Bloom tag
        if not re.search(r'\[(Evaluate|Analyze|Apply|Understand)\]', q):
            lvl = _classify_bloom(q).capitalize()
            q = f"[{lvl}]: {q}"
        lines.append(f"- Q{i} {q}")
        lines.append(f"  - A: {a}")
        # Append non-hashing trace lines (pipeline ignores '> See:' in hashing)
        if blocks:
            bids = _best_traces(a, blocks, min_overlap=min_overlap, topk=topk)
            if bids:
                wikilinks = ", ".join(f"[[{cheat_stem}#{bid}]]" for bid in bids)
                lines.append(f"  > See: {wikilinks}")
    return "\n".join(lines).rstrip() + "\n"

def _agent_log(agent: str, mode: str, title: str):
    import time
    logdir = os.environ.get("TRAINING_LOG_DIR") or os.path.join(os.path.dirname(__file__), "..", "logs")
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(os.path.join(logdir, "agent_mode.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M')} | {agent:<10} | {mode:<9} | {title}\n")
    except Exception:
        pass

# ---------- OpenAI driver (optional) ----------
def _call_openai(system: str, user: str, model: str = None, temperature: float = 0.35) -> str:
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
            import openai
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

def _parse_quiz_block(md: str):
    """Return list of (q,a)."""
    qa = []
    q_re = re.compile(r'(?m)^\s*-\s*Q(\d+)\s+(.*)')
    a_re = re.compile(r'(?m)^\s*\-\s*A\s*:\s*(.*)')
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        m = q_re.match(lines[i])
        if m:
            q = m.group(2).strip()
            a = ""
            j = i + 1
            while j < len(lines):
                if q_re.match(lines[j]): break
                ma = a_re.match(lines[j])
                if ma:
                    a = ma.group(1).strip()
                    # capture continuation lines until next Q
                    k = j + 1
                    while k < len(lines) and not q_re.match(lines[k]):
                        if lines[k].strip().startswith("> See:"):
                            k += 1; continue
                        if lines[k].strip():
                            a += " " + lines[k].strip()
                        k += 1
                    j = k - 1
                j += 1
            qa.append((q, a))
            i = j
        i += 1
    return qa

# ---------- Public API ----------
def generate_quiz_md(src_path: Path, out_path: Path, n_items: int = 7):
    """
    Produce exactly n_items Q/A pairs with Bloom tags in the question label.
    Format:
      # Quiz: <Title>
      - Q1 [Evaluate]: ...
        - A: ...
      (plus optional '  > See: ' trace lines)
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
        sys_prompt = textwrap.dedent(f"""
            You are generating a higher-order quiz grounded ONLY in the provided note.
            Rules:
            - Create EXACTLY {n_items} questions.
            - First 4 must alternate [Evaluate] and [Analyze]. Remaining can be [Apply]/[Understand].
            - Strict format:
                # Quiz: <Title>
                - Q1 [Evaluate]: <question>
                  - A: <concise but substantive answer>
            - No frontmatter, no extra sections, no explanations.
            - Keep answers grounded in the note; avoid invented facts.
        """).strip()
        user_prompt = (
            f"Title: {title}\n"
            f"Note content is delimited by <note> tags. Use its claims, comparisons, causes/effects, assumptions, and mechanisms.\n"
            f"<note>\n{body_trim}\n</note>"
        )
        content = _call_openai(sys_prompt, user_prompt, temperature=0.35)

    qa = _parse_quiz_block(content) if content else []
    if len(qa) != n_items:
        # fallback heuristic generation
        kpts = _heuristic_key_points(body, k=max(6, n_items)) or [title]
        qa_pairs = []
        bias_topics = kpts[:4] if len(kpts) >= 4 else (kpts * 4)[:4]
        for i, tp in enumerate(bias_topics):
            if i % 2 == 0:
                q = f"[Evaluate]: Which interpretation of **{tp}** is strongest in context, and why?"
                a = f"Justify a position using explicit criteria; note limitations for **{tp}**."
            else:
                q = f"[Analyze]: Compare and contrast two plausible approaches to **{tp}**; identify trade-offs."
                a = f"Lay out distinctions, causes/effects, and key trade-offs related to **{tp}**."
            qa_pairs.append((q, a))
        for i in range(max(0, n_items - len(qa_pairs))):
            tp = kpts[(4 + i) % len(kpts)]
            if i % 2 == 0:
                q = f"[Apply]: Given a scenario involving **{tp}**, how would you proceed and what would you monitor?"
                a = f"Describe concrete steps, guardrails, and signals to watch when using **{tp}**."
            else:
                q = f"[Understand]: Explain **{tp}** in your own words and note any assumptions."
                a = f"Paraphrase the core idea of **{tp}** and surface assumptions clearly."
            qa_pairs.append((q, a))
        qa_pairs = _ensure_exact_count(qa_pairs, n_items, title)
        content = _format_quiz(title, qa_pairs, Path(src_path))
        _agent_log("quiz", "Heuristic", f"{title} ({n_items})")
    else:
        # normalize and add tracing
        content = _format_quiz(title, qa[:n_items], Path(src_path))
        _agent_log("quiz", "OpenAI", f"{title} ({n_items})")

    Path(out_path).write_text(content, encoding="utf-8")
    return out_path
