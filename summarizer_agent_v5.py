# -*- coding: utf-8 -*-
"""
summarizer_agent_v5.py — hardened + detailed run logging (patched)
- Loads .env automatically so OPENAI_API_KEY is available
- Robust YAML handling (tolerates BOM/whitespace, de-dupes all FM blocks)
- POSIX origin paths for Obsidian wiki-links
- Deterministic, smarter fallback so sections are ALWAYS populated (no markdown artifacts)
- Optional GPT summary (uses OPENAI_API_KEY if present)
- Debug logging (--debug) + persistent run log file
- Safer archiving (avoid overwrites)
- New flag: --require-gpt (fail loudly if GPT is not initialized)

CLI:
  python summarizer_agent_v5.py                       # intake + normalize + generate
  python summarizer_agent_v5.py --mode generate       # generate only
  python summarizer_agent_v5.py --intake-only         # create summaries from Inbox
  python summarizer_agent_v5.py --normalize-only      # normalize summary files only
  python summarizer_agent_v5.py --no-archive          # keep originals in Inbox
  python summarizer_agent_v5.py --max-bullets 5 --actions 3 --strip-yaml --debug
  python summarizer_agent_v5.py --mode generate --require-gpt --debug

Env:
  VAULT_PATH (defaults to C:\\Users\\top2e\\Sync)
  OPENAI_API_KEY (optional; if missing, deterministic fallback is used)
Outputs:
  <VAULT>/Summaries/summary_<slug>.md
  <VAULT>/data/summary_log.csv
  ./logs/summarizer_report.md
  ./logs/summarizer_run_YYYYMMDD_HHMMSS.log
"""

import os, re, argparse, datetime as dt, csv, shutil
from pathlib import Path

# --- Load .env early so OPENAI_API_KEY is visible ---
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# --- Optional deps ---
try:
    import yaml
except Exception:
    yaml = None

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
except Exception:
    _NLP = None

# --- OpenAI client (optional) ---
_OPENAI = None
_OPENAI_VER = None
try:
    import openai as _openai_pkg  # just to read version if present
    _OPENAI_VER = getattr(_openai_pkg, "__version__", None)
except Exception:
    _OPENAI_VER = None

try:
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        _OPENAI = OpenAI(api_key=key)
except Exception:
    _OPENAI = None

# --- Paths ---
VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\\Users\\top2e\\Sync")
INBOX_CANDIDATES = [VAULT / "00_Inbox", VAULT / "Inbox", VAULT / "_Inbox", VAULT / "0_Inbox"]
SUMMARIES = VAULT / "Summaries"
ARCHIVES = VAULT / "Archives"
DATA = VAULT / "data"
VLOGS = VAULT / "logs"
for p in (SUMMARIES, ARCHIVES, DATA, VLOGS):
    p.mkdir(parents=True, exist_ok=True)

# Script-local logs folder (repo-side) + run log file
LOGS = Path(__file__).parent / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
RUN_LOG = LOGS / f"summarizer_run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

def log(msg: str, echo: bool = True):
    """Print to console *and* append to a run log file."""
    if echo:
        print(msg)
    try:
        with RUN_LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

CSV_LOG = DATA / "summary_log.csv"
if not CSV_LOG.exists():
    with CSV_LOG.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "original_note", "summary_file", "status", "details"])

# --- YAML helpers ---
FM_BLOCK_RE = re.compile(r'^\ufeff?\s*---\s*\n.*?\n---\s*(?:\r?\n)?', re.DOTALL | re.MULTILINE)
FM_KEYS_DEDUPE = ["related", "see_also", "links", "references"]

def yload(text):
    if yaml is None: return {}
    try: return yaml.safe_load(text) or {}
    except Exception: return {}

def ydump(obj):
    if yaml is None:
        out = []
        for k, v in obj.items():
            if isinstance(v, list):
                out.append(f"{k}:")
                out += [f"  - {it}" for it in v]
            else:
                out.append(f"{k}: {v}")
        return "\n".join(out) + "\n"
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)

def strip_all_fm(raw: str) -> str:
    return FM_BLOCK_RE.sub("", raw)

def split_fm(raw: str):
    m = FM_BLOCK_RE.search(raw)
    fm = {}
    if m:
        fm_yaml = raw[m.start():m.end()]
        fm = yload(fm_yaml.strip("- \n\r"))
    body = strip_all_fm(raw)
    return (fm or {}), body.lstrip()

def ensure_one_fm(fm: dict, body: str, filename: str) -> str:
    title = fm.get("title")
    if not title:
        base = Path(filename).stem
        if base.lower().startswith("summary_"): base = base[8:]
        title = base.replace("_"," ").replace("-"," ").strip().title()
        fm["title"] = title
    fm["type"] = "summary"
    for k in FM_KEYS_DEDUPE:
        if isinstance(fm.get(k), list):
            seen=set(); out=[]
            for item in fm[k]:
                s=str(item).strip(); sig=s.lower()
                if s and sig not in seen:
                    seen.add(sig); out.append(s)
            fm[k]=out
    fm["last_run"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    return "---\n" + ydump(fm) + "---\n" + body.lstrip()

def strip_templater(text: str) -> str:
    text = re.sub(r'<%.*?%>', '', text, flags=re.DOTALL)
    return re.sub(r'\n{3,}', '\n\n', text)

def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9\-\s_]+', '', s)
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or "note"

# --- Content extraction helpers ---
def clean_excerpt(text, strip_yaml=True):
    """Smarter fallback: drop headings, pure links, and section titles to avoid artifacts."""
    if strip_yaml: text = strip_all_fm(text)
    text = strip_templater(text)

    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")  # preserve paragraph breaks
            continue
        if s.startswith("#"):           # headings
            continue
        if s.startswith(("- [[", "* [[")):  # pure wikilink bullets
            continue
        if re.match(r"^\[\[.*\]\]$", s):  # standalone wikilinks
            continue
        if re.match(r"^##?\s+\w+", s, flags=re.I):  # generic section titles
            continue
        if re.match(r"^(Source|Sources)\s*:?$", s, flags=re.I):
            continue
        lines.append(line)

    cleaned = "\n".join(lines)
    paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if p.strip()]

    # Prefer a paragraph with a period or ≥8 words
    for p in paras:
        if "." in p or len(p.split()) >= 8:
            return p[:800] + ("…" if len(p) > 800 else "")
    return (paras[0][:800] + ("…" if paras and len(paras[0]) > 800 else "")) if paras else ""

def extract_actions(src_text, limit, strip_yaml=True):
    if strip_yaml: src_text = strip_all_fm(src_text)
    src_text = strip_templater(src_text)
    actions = []
    for m in re.finditer(r'(?m)^\s*[-\*]\s*\[[ xX]\]\s*(.+)$', src_text):
        t = m.group(1).strip().rstrip('.')
        if len(t.split()) >= 3:
            actions.append("- " + t)
        if len(actions) >= limit: return actions[:limit]
    return actions or ["- (add next action)"]

# --- GPT summarization (optional) ---
def gpt_summarize(masked_note, model="gpt-4o-mini", debug=False):
    if _OPENAI is None:
        if debug:
            ver = _OPENAI_VER or "unknown"
            key_present = bool(os.environ.get("OPENAI_API_KEY"))
            log(f"[debug] GPT disabled: client=None, openai_version={ver}, key_present={key_present}.")
        return ""
    prompt = (
        "You are a professional summarizer.\n"
        "Summarize clearly in a few bullets and a concise paragraph.\n\n"
        f"{masked_note}"
    )
    try:
        resp = _OPENAI.chat.completions.create(
            model=model,
            messages=[{"role": "system","content": "Summarize notes."},
                      {"role": "user","content": prompt}],
            temperature=0.3
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        if debug: log(f"[debug] GPT call failed: {e}")
        return ""

def _is_meaningful(text: str) -> bool:
    if not text: return False
    return len(re.sub(r'\s+','',text)) >= 40

# --- Core workflow ---
def intake_from_inbox(debug=False):
    created=0
    for inbox in INBOX_CANDIDATES:
        if not inbox.exists(): continue
        for p in sorted(inbox.glob("*.md")):
            slug=slugify(p.stem)
            target=SUMMARIES / f"summary_{slug}.md"
            if target.exists(): continue
            raw=p.read_text(encoding="utf-8",errors="replace")
            fm_src, _ = split_fm(raw)
            title=fm_src.get("title") or p.stem
            now=dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            origin=p.relative_to(VAULT).as_posix()
            fm_new={"title":title,"type":"summary","origin":origin,
                    "status":"intake","created":now,"last_run":now}
            yaml_block="---\n"+ydump(fm_new)+"---\n"
            content=(f"# {title}\n\n## TL;DR\n\n## Summary\n\n## Next Actions\n\n## Source\n- [[{origin}]]\n\n## Excerpt\n\n")
            target.write_text(yaml_block+content,encoding="utf-8"); created+=1
            log(f"[OK] Created summary -> {target.name}")
    return created

def write_sections(sum_path, bullets, actions, excerpt, summary_text, origin):
    raw=sum_path.read_text(encoding="utf-8",errors="replace")
    fm, body=split_fm(raw)
    def replace_section(title, lines):
        pat=re.compile(r'(?ims)^(#+)\s*'+re.escape(title)+r'\s*$([\s\S]*?)(?=^#{2,}|\Z)')
        m=pat.search(body)
        txt="\n".join(lines)+"\n" if lines else ""
        if not m: return body+f"\n## {title}\n\n{txt}"
        return body[:m.start(2)] + ("\n"+txt) + body[m.end(2):]
    if summary_text: body=replace_section("Summary",[summary_text])
    if bullets: body=replace_section("TL;DR",bullets)
    if actions: body=replace_section("Next Actions",actions)
    if excerpt: body=replace_section("Excerpt",[excerpt])
    if origin: body=replace_section("Source",[f"- [[{origin}]]"])
    fm["status"]="summarized"
    fm["last_run"]=dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_text=ensure_one_fm(fm,body,sum_path.name)
    sum_path.write_text(new_text,encoding="utf-8")
    log(f"[OK] Populated sections -> {sum_path.name}")

def generate_content(max_bullets, actions_count, archive=True, debug=False):
    gen=0
    for sum_path in sorted(SUMMARIES.glob("summary_*.md")):
        raw=sum_path.read_text(encoding="utf-8",errors="replace")
        fm, body=split_fm(raw)
        origin=fm.get("origin"); src_text=""; src_path=None
        if origin:
            src_path=VAULT / Path(origin)
            if src_path.exists():
                src_text=src_path.read_text(encoding="utf-8",errors="replace")

        # Try GPT first
        summary_text=gpt_summarize(src_text or body,debug=debug)
        if not _is_meaningful(summary_text):
            # fallback to cleaned excerpt paragraph
            summary_text=clean_excerpt(src_text or body)

        # Build bullets carefully (avoid headings/links)
        bullets = []
        if summary_text:
            parts = re.split(r'(?<=[.!?])\s+|;\s+', summary_text)
            for part in parts[:3]:
                part = part.strip().lstrip("-*#").strip()
                if part and not part.lower().startswith(("## ", "source", "[[")):
                    bullets.append(f"- {part}")
        if not bullets:
            bullets = ["- High-level summary not available; add a few sentences above."]

        actions=extract_actions(src_text or body,actions_count)
        excerpt=clean_excerpt(src_text or body)
        write_sections(sum_path,bullets,actions,excerpt,summary_text,origin or "")
        with CSV_LOG.open("a",newline="",encoding="utf-8") as f:
            writer=csv.writer(f); writer.writerow([dt.datetime.now().isoformat(),origin or "",sum_path.name,"generated",""])
        if archive and src_path and src_path.exists():
            dest=ARCHIVES/src_path.name
            if dest.exists():
                dest=ARCHIVES/f"{src_path.stem}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}{src_path.suffix}"
            shutil.move(str(src_path),str(dest))
        gen+=1
    return gen

def normalize_all(debug=False):
    updated=skipped=0
    for p in sorted(SUMMARIES.glob("*.md")):
        if not p.name.lower().startswith("summary_"): continue
        try:
            if ensure_one_fm(*split_fm(p.read_text(encoding="utf-8")),p.name):
                updated+=1
        except Exception as e:
            log(f"[error] {p.name}: {e}")
    return updated,skipped

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--normalize-only",action="store_true")
    ap.add_argument("--intake-only",action="store_true")
    ap.add_argument("--mode",choices=["generate"])
    ap.add_argument("--max-bullets",type=int,default=5)
    ap.add_argument("--actions",type=int,default=3)
    ap.add_argument("--no-archive",action="store_true")
    ap.add_argument("--debug",action="store_true")
    ap.add_argument("--require-gpt",action="store_true", help="error out if OPENAI_API_KEY/client is not initialized")
    args=ap.parse_args()

    log("=== Summarizer v5 run start ===")
    if args.debug:
        masked = "yes" if os.environ.get("OPENAI_API_KEY") else "no"
        log(f"[debug] openai_package_version={_OPENAI_VER or 'unknown'}; key_present={masked}; client_initialized={'yes' if _OPENAI else 'no'}")

    if args.require_gpt and _OPENAI is None:
        log("[error] --require-gpt set but OPENAI client not initialized (missing key or wrong package).")
        raise SystemExit(2)

    created=updated=skipped=generated=0
    if args.mode=="generate":
        if not any(SUMMARIES.glob("summary_*.md")):
            created=intake_from_inbox(debug=args.debug)
            u,s=normalize_all(debug=args.debug); updated+=u; skipped+=s
        generated=generate_content(args.max_bullets,args.actions,archive=(not args.no_archive),debug=args.debug)
    elif args.normalize_only:
        updated,skipped=normalize_all(debug=args.debug)
    elif args.intake_only:
        created=intake_from_inbox(debug=args.debug)
    else:
        created=intake_from_inbox(debug=args.debug); u,s=normalize_all(debug=args.debug); updated+=u; skipped+=s
        generated=generate_content(args.max_bullets,args.actions,archive=(not args.no_archive),debug=args.debug)
    report=LOGS/"summarizer_report.md"
    report.write_text(f"# Summarizer v5 Report\n\n- Created: {created}\n- Updated: {updated}\n- Skipped: {skipped}\n- Generated: {generated}\n- Run at: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n- Run log: {RUN_LOG.name}\n",encoding="utf-8")
    log(f"[OK] Wrote {report}")
    log("=== Summarizer v5 run end ===")


if __name__=="__main__":
    main()