import argparse, os, sys, json, time, traceback, re, hashlib
from datetime import date, timedelta
from pathlib import Path

# --- Optional dependency: PyYAML ---
try:
    import yaml  # pip install pyyaml
except Exception as e:
    print("[ERR] Missing dependency 'PyYAML'. Please run:")
    print("     pip install pyyaml")
    sys.exit(2)

# Try to import agents
USE_GPT = os.environ.get("TRAINING_USE_GPT", "1") not in ("0", "false", "False")
SUMMARIZER = None
QUIZGEN = None
if USE_GPT:
    try:
        from agents.summarizer_agent import summarize_note_to_cheatsheet_md
        SUMMARIZER = summarize_note_to_cheatsheet_md
    except Exception as e:
        print(f"[WARN] Summarizer agent not available: {e}")
    try:
        from agents.quiz_agent import generate_quiz_md
        QUIZGEN = generate_quiz_md
    except Exception as e:
        print(f"[WARN] Quiz agent not available: {e}")

FRONTMATTER_RE = re.compile(r'(?s)\A---\s*\n(.*?)\n---\s*\n?')

# NEW: broader bullet/numbered-list regex (handles -,*,+, • ▪ – —, and "1.")
BULLET_RE = re.compile(
    r'^(?P<indent>\s*)(?P<marker>(?:[-*+]|[•▪–—]|\d+\.))\s+(?P<text>.+?)(?P<id>\s+\^[A-Za-z0-9_-]+)?\s*$'
)

ROOT = Path(__file__).parent
ENV = ROOT / ".env"
LOGS = ROOT / "logs"
DATA = ROOT / "data"
QUIZZES = None  # resolved after env/vault
REPORT = LOGS / "training_report.md"

for p in [LOGS, DATA]:
    p.mkdir(parents=True, exist_ok=True)

# ------------------------- Bloom helpers -------------------------

HIGHER_ORDER = {"analyze", "evaluate"}  # Level 4–5 focus (reverse Bloom's core)

BLOOM_KEYWORDS = {
    "remember": ["define", "list", "name", "what is", "when is", "identify", "label", "recall", "state"],
    "understand": ["explain", "summarize", "classify", "describe", "paraphrase", "outline"],
    "apply": ["apply", "use", "execute", "demonstrate", "solve", "implement"],
    "analyze": ["analyze", "compare", "contrast", "differentiate", "distinguish", "why x not y", "pattern", "structure", "break down"],
    "evaluate": ["evaluate", "assess", "justify", "argue", "defend", "critique", "prioritize", "trade-off", "choose and justify", "which is strongest", "most important", "rank"],
    "create": ["design", "compose", "formulate", "propose", "develop", "construct", "invent", "plan"],
}

def classify_bloom(text: str) -> str:
    """Heuristic classifier for Bloom level from question text."""
    t = (text or "").lower().strip()
    # Keep explicit tag if present
    m = re.search(r'\[(remember|understand|apply|analyze|evaluate|create)\]', t)
    if m:
        return m.group(1)
    # Heuristic keyword match (prefer higher-order if multiple)
    scores = {}
    for level, kws in BLOOM_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                scores[level] = scores.get(level, 0) + 1
    if scores:
        order = ["evaluate", "analyze", "apply", "understand", "remember", "create"]
        return sorted(scores.keys(), key=lambda L: (order.index(L), -scores[L]))[0]
    # Fallback default to analyze if open-ended
    if t.endswith("?"):
        return "analyze"
    return "understand"

def blooms_is_higher(level: str) -> bool:
    return (level or "").lower() in HIGHER_ORDER

def blooms_counts_from_quiz_text(txt: str):
    """Parse Q lines and tally Bloom levels using classifier."""
    levels = []
    for line in txt.splitlines():
        m = re.match(r'^\s*-\s*Q(?:\d+)?:\s*(.*)', line, flags=re.IGNORECASE)
        if m:
            q = m.group(1).strip()
            levels.append(classify_bloom(q))
    counts = {}
    for lvl in levels:
        counts[lvl] = counts.get(lvl, 0) + 1
    total = sum(counts.values()) or 0
    higher = sum(counts.get(l, 0) for l in ["analyze", "evaluate"])
    pct = (higher / total) if total else 0.0
    return counts, pct, total

# ------------------------- Core pipeline -------------------------

def load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-notes", type=int, default=999)
    ap.add_argument("--dry-run", type=int, default=0)
    ap.add_argument("--daily-trainer", type=int, default=1)
    ap.add_argument("--continue-on-error", type=int, default=1)
    ap.add_argument("--quiz-items", type=int, default=7)
    # Overwrite/refresh controls
    ap.add_argument("--force-summarize", action="store_true", help="Overwrite existing cheat sheets (unless locked)")
    ap.add_argument("--force-quiz", action="store_true", help="Overwrite existing quizzes (unless locked)")
    ap.add_argument("--gpt-only", action="store_true", help="Fail if GPT agents are unavailable (no stubs)")
    ap.add_argument("--refresh-placeholders", type=int, default=1, help="Detect and replace placeholder outputs (default=1)")
    # Self-scoring
    ap.add_argument("--self-score", type=int, default=0, help="Prompt for per-note correctness during trainer session")
    # Bloom integration
    ap.add_argument("--blooms-focus", type=str, default="Analyze,Evaluate", help="Comma list of Bloom levels to prioritize")
    ap.add_argument("--min-higher-order-pct", type=float, default=0.5, help="Min fraction of Analyze+Evaluate Qs; if unmet, auto-append")
    ap.add_argument("--append-on-shortfall", type=int, default=1, help="If higher-order coverage below threshold, append synthetic Evaluate/Analyze Qs")
    return ap.parse_args()

def env_checks():
    vp = os.environ.get("VAULT_PATH", "").strip()
    if not vp:
        raise RuntimeError("VAULT_PATH missing in .env")
    if not Path(vp).exists():
        raise RuntimeError(f"VAULT_PATH not found: {vp}")
    li = Path(vp) / r"Resources/learning_inputs"
    if not li.exists():
        raise RuntimeError(f"Missing learning_inputs: {li}")
    if USE_GPT and not os.environ.get("OPENAI_API_KEY"):
        print("[WARN] OPENAI_API_KEY not present; GPT steps will fall back to placeholders.")
    return Path(vp)

def load_frontmatter(txt: str):
    m = FRONTMATTER_RE.match(txt)
    if not m:
        return {}, txt
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception:
        fm = {}
    body = txt[m.end():]
    return fm, body

def dump_frontmatter(fm: dict, body: str) -> str:
    return f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n{body}"

def ensure_uid(fm: dict, path: Path) -> dict:
    tr = fm.setdefault("training", {})
    if tr.get("uid"):
        return fm
    seed = str(path.resolve())
    try:
        stat = path.stat()
        seed += f"|{int(stat.st_mtime)}"
    except Exception:
        pass
    uid = "lrn-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    tr["uid"] = uid
    return fm

def is_locked(path: Path) -> bool:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        fm, _ = load_frontmatter(txt)
        tr = fm.get("training", {})
        val = tr.get("lock") or fm.get("training.lock") or fm.get("lock")
        return str(val).lower() in ("1", "true", "yes", "y")
    except Exception:
        return False

# NEW: robust block-id insertion for unordered/ordered bullets, Unicode bullets, and dash bullets
def ensure_block_ids_all_levels(cheat_path: Path):
    """Append ^bNN to ANY list item (unordered or ordered), skipping code blocks/callouts."""
    if not cheat_path.exists():
        return
    txt = cheat_path.read_text(encoding="utf-8", errors="ignore")
    lines = txt.splitlines()
    out = []
    in_code = False
    used = set()

    # Collect existing ids so we don't collide
    for line in lines:
        m = BULLET_RE.match(line)
        if m and m.group('id'):
            used.add(m.group('id').strip())

    def next_id(n=[1]):
        while True:
            bid = f"^b{n[0]:02d}"
            n[0] += 1
            if bid not in used:
                used.add(bid)
                return bid

    changed = False
    for line in lines:
        stripped = line.lstrip()
        # Handle code fences
        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        # Skip callouts/quoted lines
        if in_code or stripped.startswith(">"):
            out.append(line)
            continue

        m = BULLET_RE.match(line)
        if m:
            indent = m.group('indent')
            marker = m.group('marker')  # preserve "-" vs "1." etc.
            text = m.group('text').rstrip()
            ex_id = m.group('id')
            if not ex_id:
                bid = next_id()
                line = f"{indent}{marker} {text} {bid}"
                changed = True
        out.append(line)

    if changed:
        cheat_path.write_text("\n".join(out) + "\n", encoding="utf-8")

def patch_source_yaml(src_path: Path, cheatsheet_link: str, quiz_link: str, blooms_focus_list):
    txt = src_path.read_text(encoding="utf-8", errors="ignore")
    fm, body = load_frontmatter(txt)
    if not fm:
        fm = {}
    fm.setdefault("type", "learning_note")
    fm.setdefault("meta_status", "reference")
    fm.setdefault("training", {})
    fm["training"]["cheatsheet"] = cheatsheet_link
    fm["training"]["quiz"] = quiz_link
    fm["training"].setdefault("coverage", "none")
    fm["training"].setdefault("attempts", 0)
    fm["training"].setdefault("correct", 0)
    fm["training"].setdefault("accuracy", 0)
    fm["training"].setdefault("interval_days", 1)
    fm["training"]["blooms_focus"] = list(blooms_focus_list)
    fm = ensure_uid(fm, src_path)

    if "## Training" not in body:
        block = f"## Training\n- Cheat sheet: {cheatsheet_link}\n- Quiz: {quiz_link}\n\n"
        body = block + body

    src_path.write_text(dump_frontmatter(fm, body), encoding="utf-8")

def ensure_cheatsheet_frontmatter(cheat_path: Path, src_path: Path, uid: str, blooms_focus_list):
    if not cheat_path.exists():
        return
    txt = cheat_path.read_text(encoding="utf-8", errors="ignore")
    fm, body = load_frontmatter(txt)
    fm.setdefault("type", "cheatsheet")
    tr = fm.setdefault("training", {})
    tr["uid"] = uid
    tr["source"] = f"[[Resources/learning_inputs/{src_path.stem}]]"
    tr["blooms_focus"] = list(blooms_focus_list)
    cheat_path.write_text(dump_frontmatter(fm, body), encoding="utf-8")

def ensure_quiz_frontmatter(quiz_path: Path, src_path: Path, uid: str, items: int, blooms_focus_list):
    if not quiz_path.exists():
        return
    txt = quiz_path.read_text(encoding="utf-8", errors="ignore")
    fm, body = load_frontmatter(txt)
    fm.setdefault("type", "quiz")
    tr = fm.setdefault("training", {})
    tr["uid"] = uid
    tr["source"] = f"[[Resources/learning_inputs/{src_path.stem}]]"
    tr["items"] = int(items)
    tr["blooms_focus"] = list(blooms_focus_list)
    quiz_path.write_text(dump_frontmatter(fm, body), encoding="utf-8")

# --- Placeholder detectors ---
PLACEHOLDER_PATTERNS_CHEAT = [
    r"-\s*Key idea 1",
    r"Application prompt:\s*[.…]+",
    r"#\s*Cheat Sheet:\s*.+\s*\Z",
    r"##\s*Evaluate\s*(?:first)?\s*\Z",  # trivial eval section only
]

PLACEHOLDER_PATTERNS_QUIZ = [
    r"-\s*Q\d+:\s*[.…]+",
    r"-\s*A:\s*[.…]+",
    r"#\s*Quiz:\s*.+\s*\Z",
]

def is_placeholder_cheatsheet(p: Path) -> bool:
    if not p.exists(): return True
    txt = p.read_text(encoding="utf-8", errors="ignore").strip()
    if len(txt.splitlines()) < 10:
        return True
    for pat in PLACEHOLDER_PATTERNS_CHEAT:
        if re.search(pat, txt, flags=re.IGNORECASE | re.MULTILINE):
            return True
    # Must include Evaluate/Analyze sections per reverse Bloom's
    if "## Evaluate first" not in txt and "## Evaluate" not in txt:
        return True
    if "## Analyze" not in txt:
        return True
    return False

def is_placeholder_quiz(p: Path) -> bool:
    if not p.exists(): return True
    txt = p.read_text(encoding="utf-8", errors="ignore")
    q_count = len(re.findall(r"(?m)^\s*-\s*Q(?:\d+)?:", txt))
    if q_count < 5:
        return True
    # If there are no higher-order cues at all, consider placeholder-ish
    counts, pct, total = blooms_counts_from_quiz_text(txt)
    if total >= 5 and pct < 0.20:
        return True
    for pat in PLACEHOLDER_PATTERNS_QUIZ:
        if re.search(pat, txt):
            return True
    return False

def write_cheatsheet_stub(src_path: Path, cheat_path: Path, uid: str, dry: bool, blooms_focus_list=("Analyze", "Evaluate")):
    if dry: return
    src_rel = f"[[Resources/learning_inputs/{src_path.stem}]]"
    focus_str = ", ".join(blooms_focus_list)
    content = (
        f"---\n"
        f"type: cheatsheet\n"
        f"training:\n"
        f"  uid: {uid}\n"
        f"  source: \"{src_rel}\"\n"
        f"  blooms_focus: [{focus_str}]\n"
        f"---\n"
        f"# Cheat Sheet: {src_path.stem}\n\n"
        f"## Evaluate first\n"
        f"- What matters most here, and why? ^b01\n"
        f"- Which argument or approach is strongest? Justify. ^b02\n"
        f"- What trade-offs or limitations should be prioritized? ^b03\n\n"
        f"## Analyze\n"
        f"- Compare/contrast the core concepts or methods. ^b04\n"
        f"- Map cause → effect relationships and assumptions. ^b05\n"
        f"- Identify patterns or categories that organize the ideas. ^b06\n\n"
        f"## Apply\n"
        f"- Given scenario X, how would you use the concept? ^b07\n\n"
        f"## Key Ideas (for memory)\n"
        f"- Bullet the essential definitions and facts. ^b08\n"
        f"- Application prompt: Write a short justification that would convince a skeptical peer. ^b09\n"
    )
    cheat_path.write_text(content, encoding="utf-8")

def write_quiz_stub(src_path: Path, quiz_path: Path, uid: str, dry: bool, n_items=7, blooms_focus_list=("Analyze", "Evaluate")):
    if dry: return
    n_items = max(5, min(int(n_items), 12))
    src_rel = f"[[Resources/learning_inputs/{src_path.stem}]]"
    # Bias to include higher-order first
    templates = []
    # Alternate Evaluate / Analyze prompts up front
    for i in range(min(4, n_items)):
        label = "Evaluate" if i % 2 == 0 else "Analyze"
        templates.append(f"- Q{i+1} [{label}]: Choose the strongest interpretation and justify.\n  - A: Justification citing key criteria")
    # Fill remaining with Apply/Understand mix
    for i in range(len(templates), n_items):
        label = "Apply" if i % 2 == 0 else "Understand"
        templates.append(f"- Q{i+1} [{label}]: …?\n  - A: …")
    items = "\n".join(templates)
    focus_str = ", ".join(blooms_focus_list)
    content = (
        f"---\n"
        f"type: quiz\n"
        f"training:\n"
        f"  uid: {uid}\n"
        f"  source: \"{src_rel}\"\n"
        f"  items: {n_items}\n"
        f"  blooms_focus: [{focus_str}]\n"
        f"---\n"
        f"# Quiz: {src_path.stem}\n\n" + items + "\n"
    )
    quiz_path.write_text(content, encoding="utf-8")

def mark_coverage(src_path: Path, cheatsheet_exists: bool, quiz_exists: bool):
    txt = src_path.read_text(encoding="utf-8", errors="ignore")
    fm, body = load_frontmatter(txt)
    fm.setdefault("training", {})
    cov = "none"
    if cheatsheet_exists and quiz_exists: cov = "summary+quiz"
    elif cheatsheet_exists: cov = "summary"
    elif quiz_exists: cov = "quiz"
    fm["training"]["coverage"] = cov
    src_path.write_text(dump_frontmatter(fm, body), encoding="utf-8")

def scan_learning_inputs(vault: Path):
    base = vault / r"Resources/learning_inputs"
    notes = []
    for p in base.rglob("*.md"):
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            fm, _ = load_frontmatter(txt)
            if (fm.get("meta_status") == "reference") or ("meta_status: reference" in txt):
                notes.append(p)
        except Exception:
            pass
    notes.sort()
    return notes

def write_manifest(notes):
    manifest = [{"path": str(p)} for p in notes]
    out = DATA / "training_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out

def update_status(notes):
    covered = 0
    for p in notes:
        if p.with_suffix(".cheatsheet.md").exists() and (QUIZZES / f"{p.stem}_quiz.md").exists():
            covered += 1
    status = {"total": len(notes), "covered": covered, "coverage_pct": (covered / max(1, len(notes))) * 100}
    (DATA / "training_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status

def trainer_pick(notes, k=5):
    return notes[:k]

def bump_interval_with_score(current: int, ratio: float) -> int:
    current = max(1, int(current or 1))
    if ratio >= 0.85:
        return min(current * 2, 21)
    if ratio >= 0.70:
        return min(current + 2, 14)
    if ratio >= 0.50:
        return max(2, current)
    return 1

def count_quiz_items(qfile: Path, default_items: int) -> int:
    if not qfile.exists():
        return max(5, min(default_items, 12))
    txt = qfile.read_text(encoding="utf-8", errors="ignore")
    q_count = len(re.findall(r"(?m)^\s*-\s*Q(?:\d+)?:", txt))
    return max(1, q_count)

def run_trainer(notes, dry: bool, self_score: bool, default_items: int):
    sample = trainer_pick(notes, k=5)
    log = LOGS / "learning_log.md"
    lines = [f"## {time.strftime('%Y-%m-%d %H:%M')} Trainer Session\n"]

    is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
    want_scores = bool(self_score) and is_interactive and not dry

    for p in sample:
        lines.append(f"- Quiz surfaced: **{p.stem}** (see: [[Quizzes/{p.stem}_quiz]])\n")
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            fm, body = load_frontmatter(txt)
            tr = fm.setdefault("training", {})
            tr["last_review"] = date.today().isoformat()
            interval = int(tr.get("interval_days", 1))
            next_interval = interval
        except Exception:
            traceback.print_exc()
            continue

        correct, total = None, None
        if want_scores:
            total = count_quiz_items(QUIZZES / f"{p.stem}_quiz.md", default_items)
            try:
                resp = input(f"Score for {p.stem} (0-{total}) or Enter to skip: ").strip()
                if resp != "":
                    c = int(resp)
                    if 0 <= c <= total:
                        correct = c
            except Exception:
                pass

        if correct is not None and total is not None:
            tr.setdefault("attempts", 0)
            tr.setdefault("correct", 0)
            tr["attempts"] = int(tr["attempts"]) + total
            tr["correct"] = int(tr["correct"]) + correct
            acc = (tr["correct"] / max(1, tr["attempts"]))
            tr["accuracy"] = round(acc, 3)

            ratio = correct / max(1, total)
            next_interval = bump_interval_with_score(interval, ratio)
            lines.append(f"  • {p.stem}: {correct}/{total} (session {ratio:.0%})\n")

        tr["interval_days"] = int(next_interval)
        tr["next_review"] = (date.today() + timedelta(days=next_interval)).isoformat()
        p.write_text(dump_frontmatter(fm, body), encoding="utf-8")

    lines.append("\n")
    with open(log, "a", encoding="utf-8") as f:
        f.writelines(lines)

def write_report(status, notes):
    sessions = 0
    log = LOGS / "learning_log.md"
    if log.exists():
        sessions = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.startswith("## "))

    ok_coverage = status["coverage_pct"] >= 60
    ok_sessions = sessions >= 3

    acc_values = []
    note_acc = []
    for p in notes:
        try:
            fm, _ = load_frontmatter(p.read_text(encoding="utf-8", errors="ignore"))
            tr = fm.get("training", {})
            attempts = int(tr.get("attempts", 0) or 0)
            correct = int(tr.get("correct", 0) or 0)
            if attempts > 0:
                acc = correct / attempts
                acc_values.append(acc)
                note_acc.append((p.stem, acc, attempts))
        except Exception:
            pass

    avg_acc = (sum(acc_values) / len(acc_values)) if acc_values else None
    weakest = sorted(note_acc, key=lambda x: (x[1], x[2]))[:3]

    manifest = json.loads((DATA / "training_manifest.json").read_text(encoding="utf-8"))
    missing = []
    for item in manifest:
        p = Path(item["path"])
        if not (p.with_suffix(".cheatsheet.md")).exists() or not (QUIZZES / f"{p.stem}_quiz.md").exists():
            missing.append(p.stem)
        if len(missing) >= 10: break

    # Bloom coverage snapshot across all quizzes
    all_counts = {"remember":0,"understand":0,"apply":0,"analyze":0,"evaluate":0,"create":0}
    ho_total_q = 0
    total_q = 0
    for item in manifest:
        qf = QUIZZES / (Path(item["path"]).stem + "_quiz.md")
        if qf.exists():
            body = FRONTMATTER_RE.sub("", qf.read_text(encoding="utf-8", errors="ignore"))
            counts, pct, t = blooms_counts_from_quiz_text(body)
            total_q += t
            ho_total_q += int(round(pct * t))
            for k, v in counts.items():
                all_counts[k] = all_counts.get(k, 0) + v
    ho_pct_global = (ho_total_q / max(1, total_q)) if total_q else 0.0

    report = [
        f"# Training Report — {time.strftime('%Y-%m-%d %H:%M')}\n\n",
        "## Snapshot\n",
        f"- Total notes: {status['total']}\n",
        f"- Covered (summary + quiz): {status['covered']}  → **{status['coverage_pct']:.1f}%**\n",
        f"- Trainer sessions logged: {sessions}\n",
    ]

    if avg_acc is not None:
        report.append(f"- Avg accuracy (lifetime): **{avg_acc*100:.1f}%** over {len(acc_values)} notes\n")
    else:
        report.append(f"- Avg accuracy (lifetime): (not tracked yet)\n")

    report += [
        "\n## MVP Verdict\n",
        f"- Coverage ≥ 60%: {'**OK**' if ok_coverage else '**NOT YET**'}\n",
        f"- Sessions ≥ 3/wk: {'**OK**' if ok_sessions else '**NOT YET**'}\n",
        f"- Second-pass accuracy ~70%: {'**OK**' if (avg_acc is not None and avg_acc >= 0.70) else '**NOT YET**'}\n",
        f"- Higher-order Qs (Analyze+Evaluate) share: **{ho_pct_global*100:.1f}%**\n",
        "\n## Bloom Distribution (all quizzes)\n",
        f"- remember: {all_counts['remember']}  • understand: {all_counts['understand']}  • apply: {all_counts['apply']}\n",
        f"- analyze: {all_counts['analyze']}  • evaluate: {all_counts['evaluate']}  • create: {all_counts['create']}\n",
        "\n## Next Actions\n",
    ]

    if missing:
        report.append("- Add or fix coverage for:\n")
        for name in missing:
            report.append(f"  - {name}\n")

    if weakest:
        report.append("\n- Review weakest notes (lowest accuracy):\n")
        for name, acc, att in weakest:
            report.append(f"  - {name}: {acc*100:.1f}% over {att} attempts\n")

    report.append("\n## Errors\n- (none recorded by orchestrator)\n")
    REPORT.write_text("".join(report), encoding="utf-8")

# --- Quiz fingerprint utilities (unchanged logic, extended to store Bloom stats) ---
def _quiz_pairs_and_hashes(txt: str):
    """
    Parse Q/A pairs and compute stable hashes.
    - Accepts questions starting with '- Q' or '- Q<digits>:'
    - Takes the first '- A:' that follows
    - Ignores 'See:' trace lines and blank lines when hashing
    Returns: pairs ([(q, a), ...]) and hashes ([sha1, ...])
    """
    lines = txt.splitlines()
    pairs = []
    i = 0
    Q = re.compile(r'^\s*-\s*Q(?:\d+)?:\s*(.*)')
    A = re.compile(r'^\s*-\s*A\s*:\s*(.*)')
    while i < len(lines):
        m_q = Q.match(lines[i])
        if m_q:
            q_text = m_q.group(1).strip()
            a_text = ""
            j = i + 1
            while j < len(lines):
                if Q.match(lines[j]):
                    break
                m_a = A.match(lines[j])
                if m_a and a_text == "":
                    a_text = m_a.group(1).strip()
                else:
                    if a_text != "":
                        cont = lines[j].rstrip()
                        if cont.strip().startswith("> See:"):
                            j += 1
                            continue
                        if cont.strip() == "":
                            j += 1
                            continue
                        a_text += " " + cont.strip()
                j += 1
            canon = (re.sub(r'\s+', ' ', q_text.lower()).strip()
                     + " || "
                     + re.sub(r'\s+', ' ', a_text.lower()).strip())
            h = hashlib.sha1(canon.encode('utf-8')).hexdigest()
            pairs.append((q_text, a_text, h))
            i = j
        else:
            i += 1
    return [(q, a) for q, a, _ in pairs], [h for _, __, h in pairs]

def _update_quiz_hashes_in_frontmatter(qpath: Path):
    try:
        raw = qpath.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return None
    m = re.match(r'(?s)\A---\s*\n(.*?)\n---\s*\n?(.*)\Z', raw)
    if not m:
        return None
    fm_txt, body = m.group(1), m.group(2)
    try:
        fm = yaml.safe_load(fm_txt) or {}
    except Exception:
        fm = {}
    pairs, hashes = _quiz_pairs_and_hashes(body)
    tr = fm.setdefault("training", {})
    prev = tr.get("hashes") or []
    changed_idxs = []
    if prev and len(prev) == len(hashes):
        for i, (old, new) in enumerate(zip(prev, hashes)):
            if old != new:
                changed_idxs.append(i + 1)
    elif prev:
        changed_idxs = list(range(1, max(len(prev), len(hashes)) + 1))
    ver = int(tr.get("version", 0) or 0)
    if prev != hashes:
        ver += 1

    # Bloom counts and higher-order pct
    counts, pct, total = blooms_counts_from_quiz_text(body)
    tr["version"] = ver
    tr["hashes"] = hashes
    tr["blooms_counts"] = counts
    tr["higher_order_pct"] = round(pct, 3)
    new_fm = f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n"
    qpath.write_text(new_fm + body, encoding="utf-8")
    return {"version": ver, "changed": changed_idxs, "count": len(hashes), "higher_order_pct": pct}

def _log_quiz_changes(log_dir: Path, note_stem: str, info: dict):
    if not info:
        return
    path = log_dir / "quiz_change_log.md"
    lines = []
    lines.append(f"### {time.strftime('%Y-%m-%d %H:%M')} — {note_stem}\n")
    lines.append(f"- Questions: {info.get('count', 0)}\n")
    lines.append(f"- Version: {info.get('version', 0)}\n")
    if "higher_order_pct" in info:
        lines.append(f"- Higher-order share: {info['higher_order_pct']*100:.0f}%\n")
    changed = info.get("changed") or []
    if changed:
        lines.append(f"- Changed Qs: {', '.join('Q'+str(i) for i in changed)}\n\n")
    else:
        lines.append(f"- Changed Qs: (none)\n\n")
    with open(path, "a", encoding="utf-8") as f:
        f.writelines(lines)

def ensure_min_higher_order(qfile: Path, min_pct: float, append_on_shortfall: bool, note_title: str):
    """If quiz lacks sufficient Analyze/Evaluate, optionally append synthetic Qs to reach threshold."""
    try:
        raw = qfile.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return
    # Split fm/body
    m = re.match(r'(?s)\A---\s*\n(.*?)\n---\s*\n?(.*)\Z', raw)
    if not m:
        body = raw
        fm = {}
    else:
        fm_txt, body = m.group(1), m.group(2)
        try:
            fm = yaml.safe_load(fm_txt) or {}
        except Exception:
            fm = {}

    counts, pct, total = blooms_counts_from_quiz_text(body)
    if total == 0 or pct >= (min_pct or 0):
        return  # already sufficient

    if not append_on_shortfall:
        return

    # Append Analyze/Evaluate questions until threshold is met (cap at +6)
    added = 0
    q_index = total
    while total > 0 and (pct < min_pct) and (added < 6):
        q_index += 1
        label = "Evaluate" if added % 2 == 0 else "Analyze"
        snippet = (
            f"- Q{q_index} [{label}]: For **{note_title}**, pick the most defensible position and justify key trade-offs.\n"
            f"  - A: A short justification comparing criteria, noting limitations\n"
        )
        body = body.rstrip() + "\n" + snippet
        added += 1
        counts, pct, total = blooms_counts_from_quiz_text(body)

    # Write back with updated fm
    fm.setdefault("training", {})
    fm["training"]["blooms_counts"] = counts
    fm["training"]["higher_order_pct"] = round(pct, 3)
    new_fm = f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n"
    qfile.write_text(new_fm + body, encoding="utf-8")

def regenerate_if_placeholder(cheat: Path, qfile: Path, src: Path, uid: str, args, blooms_focus_list):
    regen_cheat = args.force_summarize or (args.refresh_placeholders and is_placeholder_cheatsheet(cheat))
    regen_quiz  = args.force_quiz or (args.refresh_placeholders and is_placeholder_quiz(qfile))

    if regen_cheat and cheat.exists() and is_locked(cheat):
        print(f"[SKIP] Cheat sheet locked: {cheat.name}")
        regen_cheat = False
    if regen_quiz and qfile.exists() and is_locked(qfile):
        print(f"[SKIP] Quiz locked: {qfile.name}")
        regen_quiz = False

    if regen_cheat:
        try:
            if USE_GPT and SUMMARIZER:
                print(f"[FIXUP] Regenerating cheat sheet (GPT): {cheat.name}")
                SUMMARIZER(src, cheat)
            else:
                if args.gpt_only:
                    raise RuntimeError("GPT summarizer unavailable but --gpt-only set.")
                print(f"[FIXUP] Regenerating cheat sheet (stub): {cheat.name}")
                write_cheatsheet_stub(src, cheat, uid, bool(args.dry_run), blooms_focus_list=blooms_focus_list)
        except Exception as e:
            print(f"[WARN] Cheat sheet regeneration failed for {src.name}: {e}")
    ensure_cheatsheet_frontmatter(cheat, src, uid, blooms_focus_list=blooms_focus_list)
    # NEW: always tag bullets after any regen/frontmatter write
    ensure_block_ids_all_levels(cheat)

    if regen_quiz:
        try:
            if USE_GPT and QUIZGEN:
                print(f"[FIXUP] Regenerating quiz (GPT): {qfile.name}")
                QUIZGEN(src, qfile, n_items=args.quiz_items)
            else:
                if args.gpt_only:
                    raise RuntimeError("GPT quiz generator unavailable but --gpt-only set.")
                print(f"[FIXUP] Regenerating quiz (stub): {qfile.name}")
                write_quiz_stub(src, qfile, uid, bool(args.dry_run), n_items=args.quiz_items, blooms_focus_list=blooms_focus_list)
        except Exception as e:
            print(f"[WARN] Quiz regeneration failed for {src.name}: {e}")
    ensure_quiz_frontmatter(qfile, src, uid, args.quiz_items, blooms_focus_list=blooms_focus_list)

def main():
    args = parse_args()
    sys.path.insert(0, str((Path(__file__).parent).resolve()))
    load_env()
    try:
        vault = env_checks()
    except Exception as e:
        print(f"[ERR] {e}")
        sys.exit(2)

    # Parse blooms focus
    blooms_focus_list = tuple([s.strip().capitalize() for s in (args.blooms_focus or "").split(",") if s.strip()]) or ("Analyze", "Evaluate")

    global QUIZZES
    qdir_env = os.environ.get("QUIZ_DIR", "").strip()
    if qdir_env:
        QUIZZES = Path(qdir_env)
    else:
        QUIZZES = vault / "Quizzes"
    QUIZZES.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Quizzes directory: {QUIZZES}")

    notes = scan_learning_inputs(vault)
    notes = notes[:args.max_notes]
    manifest = write_manifest(notes)
    print(f"[INFO] Found {len(notes)} notes. Manifest: {manifest}")

    errors = 0
    for p in notes:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            fm, body = load_frontmatter(txt)
            fm = ensure_uid(fm or {}, p)
            p.write_text(dump_frontmatter(fm, body), encoding="utf-8")
            uid = fm["training"]["uid"]

            cheat = p.with_suffix(".cheatsheet.md")
            qfile = QUIZZES / f"{p.stem}_quiz.md"

            # Even if cheatsheet already exists, fix missing block ids
            if cheat.exists():
                ensure_block_ids_all_levels(cheat)

            if (not cheat.exists() or args.force_summarize) and not (cheat.exists() and is_locked(cheat)):
                if USE_GPT and SUMMARIZER:
                    try:
                        SUMMARIZER(p, cheat)
                    except Exception as e:
                        if args.gpt_only: raise
                        print(f"[WARN] Summarizer failed for {p.name}: {e}. Writing stub.")
                        write_cheatsheet_stub(p, cheat, uid, bool(args.dry_run), blooms_focus_list=blooms_focus_list)
                else:
                    if args.gpt_only:
                        raise RuntimeError("GPT summarizer unavailable but --gpt-only set.")
                    write_cheatsheet_stub(p, cheat, uid, bool(args.dry_run), blooms_focus_list=blooms_focus_list)
                ensure_cheatsheet_frontmatter(cheat, p, uid, blooms_focus_list=blooms_focus_list)
                ensure_block_ids_all_levels(cheat)  # ensure ids after any generation

            if (not qfile.exists() or args.force_quiz) and not (qfile.exists() and is_locked(qfile)):
                if USE_GPT and QUIZGEN:
                    try:
                        QUIZGEN(p, qfile, n_items=args.quiz_items)
                    except Exception as e:
                        if args.gpt_only: raise
                        print(f"[WARN] Quiz generation failed for {p.name}: {e}. Writing stub.")
                        write_quiz_stub(p, qfile, uid, bool(args.dry_run), n_items=args.quiz_items, blooms_focus_list=blooms_focus_list)
                else:
                    if args.gpt_only:
                        raise RuntimeError("GPT quiz generator unavailable but --gpt-only set.")
                    write_quiz_stub(p, qfile, uid, bool(args.dry_run), n_items=args.quiz_items, blooms_focus_list=blooms_focus_list)
                ensure_quiz_frontmatter(qfile, p, uid, args.quiz_items, blooms_focus_list=blooms_focus_list)
                info = _update_quiz_hashes_in_frontmatter(qfile)
                _log_quiz_changes(LOGS, p.stem, info)

            # Reverse Bloom regen checks (and ensure block IDs after)
            regenerate_if_placeholder(cheat, qfile, p, uid, args, blooms_focus_list)
            ensure_block_ids_all_levels(cheat)

            # Enforce minimum higher-order coverage by appending if shortfall
            if qfile.exists():
                ensure_min_higher_order(qfile, args.min_higher_order_pct, bool(args.append_on_shortfall), note_title=p.stem)
                info = _update_quiz_hashes_in_frontmatter(qfile)  # refresh fm stats after append
                _log_quiz_changes(LOGS, p.stem, info)

            patch_source_yaml(
                p,
                cheatsheet_link=f"[[{cheat.stem}]]",
                quiz_link=f"[[Quizzes/{p.stem}_quiz]]",
                blooms_focus_list=blooms_focus_list,
            )

            mark_coverage(p, cheat.exists(), qfile.exists())

        except Exception:
            errors += 1
            traceback.print_exc()
            if not args.continue_on_error:
                break

    status = update_status(notes)

    # post-fingerprint sweep: capture manual edits to quizzes and log
    for p in notes:
        try:
            qfile = QUIZZES / f"{p.stem}_quiz.md"
            if qfile.exists():
                info = _update_quiz_hashes_in_frontmatter(qfile)
                _log_quiz_changes(LOGS, p.stem, info)
        except Exception:
            pass

    if args.daily_trainer:
        run_trainer(notes, bool(args.dry_run), bool(args.self_score), args.quiz_items)

    write_report(status, notes)

    if errors:
        print(f"[WARN] Completed with {errors} errors.")
        sys.exit(1)
    print("[OK] Training pipeline (Bloom-integrated) finished.")
    sys.exit(0)

if __name__ == "__main__":
    main()
