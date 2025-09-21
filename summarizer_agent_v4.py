# -*- coding: utf-8 -*-
# summarizer_agent_v4.py — Intake + Normalize + (optional) Generate
import os, sys, re, argparse, datetime
from pathlib import Path
try:
    import yaml
except Exception:
    yaml = None

VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync")
SUMMARIES = VAULT / "Summaries"
PITCH_DIR = VAULT / "Express" / "pitch"
LOGS = Path(__file__).parent / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

INBOX_CANDIDATES = [VAULT / "00_Inbox", VAULT / "Inbox", VAULT / "_Inbox", VAULT / "0_Inbox"]
FM_KEYS_DEDUPE = ["related", "see_also", "links", "references"]
FM_PATTERN = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL | re.MULTILINE)

def yload(text):
    if yaml is None: return {}
    try: return yaml.safe_load(text) or {}
    except Exception: return {}

def ydump(obj):
    if yaml is None:
        out = []
        for k, v in obj.items():
            if isinstance(v, list):
                out.append(f"{k}:");  out += [f"  - {it}" for it in v]
            else:
                out.append(f"{k}: {v}")
        return "\n".join(out) + "\n"
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)

def strip_yaml_blocks(raw): return FM_PATTERN.sub("", raw)
def split_fm(raw):
    m = FM_PATTERN.match(raw)
    if not m: return {}, raw
    fm_yaml = raw[m.start()+4:m.end()-4]
    fm = yload(fm_yaml)
    body = FM_PATTERN.sub("", raw, count=1)
    body = FM_PATTERN.sub("", body)
    return fm or {}, body

def ensure_one_fm(fm, body, filename):
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
    fm.setdefault("last_run", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    return "---\n" + ydump(fm) + "---\n" + body

def strip_templater(text):
    text = re.sub(r'<%.*?%>','',text,flags=re.DOTALL)
    return re.sub(r'\n{3,}','\n\n',text)

def slugify(name):
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9\-\s_]+','',s)
    s = re.sub(r'\s+','-',s)
    s = re.sub(r'-{2,}','-',s).strip('-')
    return s or "note"

def find_pitch_for_summary(summary_name):
    base = Path(summary_name).stem
    slug = base[8:] if base.lower().startswith("summary_") else base
    for cand in [PITCH_DIR / f"pitch_summary_{slug}.md",
                 PITCH_DIR / f"pitch_summary_{slug.replace('_','-')}.md",
                 PITCH_DIR / f"pitch_summary_{slug.replace('-','_')}.md"]:
        if cand.exists(): return cand
    return None

def extract_bullets_from_pitch(pitch_path, limit):
    try: txt = pitch_path.read_text(encoding="utf-8",errors="replace")
    except Exception: return []
    bullets = re.findall(r'(?m)^\s*[-\*]\s+.+$', txt)
    uniq=[]; seen=set()
    for b in bullets:
        t=b.strip()
        if t not in seen:
            seen.add(t); uniq.append(t)
        if len(uniq)>=limit: break
    return [re.sub(r'^\s*[-\*]\s+','- ',b) for b in uniq]

def clean_excerpt(text, strip_yaml=True):
    if strip_yaml: text=strip_yaml_blocks(text)
    text=strip_templater(text)
    paras=[p.strip() for p in re.split(r'\n\s*\n',text) if p.strip()]
    for p in paras:
        if len(p.split())>=8 or '.' in p:
            return p[:800]+('…' if len(p)>800 else '')
    return paras[0][:800]+('…' if paras and len(paras[0])>800 else '') if paras else ""

def extract_bullets_from_source(src_text, limit, strip_yaml=True):
    if strip_yaml: src_text=strip_yaml_blocks(src_text)
    src_text=strip_templater(src_text)
    bullets=re.findall(r'(?m)^\s*[-\*]\s+.+$',src_text)
    out=[]; seen=set()
    for b in bullets:
        t=re.sub(r'^\s*[-\*]\s+','',b).strip()
        if len(t.split())<3: continue
        key=t.lower()
        if key not in seen:
            seen.add(key); out.append("- "+t)
        if len(out)>=limit: return out
    sentences=re.split(r'(?<=[\.\!\?])\s+',src_text)
    for s in sentences:
        st=s.strip()
        if len(st.split())<6: continue
        if re.match(r'^[#>\-\*]',st): continue
        key=st.lower()
        if key not in seen:
            seen.add(key); out.append("- "+st)
        if len(out)>=limit: break
    return out

def extract_actions(src_text, limit, strip_yaml=True):
    if strip_yaml: src_text=strip_yaml_blocks(src_text)
    src_text=strip_templater(src_text)
    tasks=re.findall(r'(?m)^\s*[-\*]\s*\[[ xX]\]\s*(.+)$',src_text)
    out=[]; seen=set()
    for t in tasks:
        s=t.strip().rstrip('.')
        if len(s.split())<2: continue
        key=s.lower()
        if key not in seen:
            seen.add(key); out.append("- "+s)
        if len(out)>=limit: return out
    m=re.search(r'(?ims)^\#{2,}\s*(next steps|next actions|follow-?ups?)\s*$([\s\S]+?)(^\#{2,}|\Z)',src_text)
    if m:
        sec=m.group(2)
        for b in re.findall(r'(?m)^\s*[-\*]\s+.+$',sec):
            s=re.sub(r'^\s*[-\*]\s+','',b).strip().rstrip('.')
            key=s.lower()
            if key not in seen:
                seen.add(key); out.append("- "+s)
            if len(out)>=limit: return out
    return ["- Confirm scope and desired outcome.",
            "- Identify stakeholders and required resources.",
            "- Define the next milestone and target date."][:limit]

def normalize_summary_file(path: Path):
    raw=path.read_text(encoding="utf-8",errors="replace")
    fm, body = split_fm(raw)
    body=strip_templater(body)
    if "## TL;DR" not in body: body="## TL;DR\n\n- …\n\n"+body
    if "## Next Actions" not in body and "## Follow-ups" not in body: body+="\n## Next Actions\n\n- …\n"
    new_text=ensure_one_fm(fm, body, path.name)
    if new_text!=raw:
        path.write_text(new_text,encoding="utf-8"); return True
    return False

def write_generated_sections(sum_path: Path, bullets, actions, excerpt):
    raw=sum_path.read_text(encoding="utf-8",errors="replace")
    fm, body = split_fm(raw)
    def replace_section(title, lines):
        pat=re.compile(r'(?ims)^(#+)\s*'+re.escape(title)+r'\s*$([\s\S]*?)(?=^\#{2,}|\Z)')
        m=pat.search(body)
        if not m:
            return body + f"\n## {title}\n\n" + "\n".join(lines) + "\n"
        start,end=m.start(2), m.end(2)
        return body[:start] + ("\n" + "\n".join(lines) + "\n") + body[end:]
    body=replace_section("TL;DR", bullets)
    body=replace_section("Next Actions", actions)
    if excerpt: body=replace_section("Excerpt",[excerpt])
    new_text=ensure_one_fm(fm, body, sum_path.name)
    if new_text!=raw: sum_path.write_text(new_text,encoding="utf-8")

def intake_from_inbox():
    created=0
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    for inbox in INBOX_CANDIDATES:
        if not inbox.exists(): continue
        for p in sorted(inbox.glob("*.md")):
            slug=slugify(p.stem)
            target=SUMMARIES / f"summary_{slug}.md"
            if target.exists(): continue
            raw=p.read_text(encoding="utf-8",errors="replace")
            fm, body = split_fm(raw) if raw.startswith("---") else ({}, raw)
            title=fm.get("title") or p.stem
            now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            fm_new={"title":title,"type":"summary","origin":str(p.relative_to(VAULT)),"status":"intake","created":now,"last_run":now}
            yaml_block="---\n"+ydump(fm_new)+"---\n"
            content="# "+title+"\n\n## TL;DR\n- …\n\n## Next Actions\n- …\n\n## Source\n- [[" + fm_new["origin"] + "]]\n"
            target.write_text(yaml_block+content,encoding="utf-8"); created+=1
            print(f"[OK] Created summary -> {target.name}")
    return created

def normalize_all():
    updated=0; skipped=0
    if not SUMMARIES.exists(): return 0,0
    for p in sorted(SUMMARIES.glob("*.md")):
        if not p.name.lower().startswith("summary_"): continue
        try:
            if normalize_summary_file(p):
                print(f"[OK] Normalized -> {p.name}"); updated+=1
            else:
                print(f"[skip] Already clean -> {p.name}"); skipped+=1
        except Exception as e:
            print(f"[error] Failed {p.name}: {e}")
    return updated, skipped

def generate_content(max_bullets, actions_count, strip_yaml_flag):
    gen=0
    for sum_path in sorted(SUMMARIES.glob("summary_*.md")):
        raw=sum_path.read_text(encoding="utf-8",errors="replace")
        fm, body = split_fm(raw)
        origin=fm.get("origin"); src_text=""
        if origin:
            src=VAULT / origin
            if src.exists():
                try: src_text=src.read_text(encoding="utf-8",errors="replace")
                except Exception: src_text=""
        pitch_path=find_pitch_for_summary(sum_path.name)
        if pitch_path:
            bullets=extract_bullets_from_pitch(pitch_path, max_bullets)
        else:
            bullets=[]
        if not bullets and src_text:
            bullets=extract_bullets_from_source(src_text, max_bullets, strip_yaml_flag)
        if not bullets:
            b=re.findall(r'(?m)^\s*[-\*]\s+.+$', body)
            bullets=[re.sub(r'^\s*[-\*]\s+','- ',x).strip() for x in b[:max_bullets]] or ["- …"]
        actions=extract_actions(src_text or body, actions_count, strip_yaml_flag)
        excerpt=clean_excerpt(src_text or body, strip_yaml_flag)
        write_generated_sections(sum_path, bullets, actions, excerpt)
        print(f"[OK] Generated TL;DR/Actions -> {sum_path.name}"); gen+=1
    return gen

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--normalize-only", action="store_true")
    ap.add_argument("--intake-only", action="store_true")
    ap.add_argument("--mode", choices=["generate"], help="Enable content generation mode")
    ap.add_argument("--max-bullets", type=int, default=5)
    ap.add_argument("--actions", type=int, default=3)
    ap.add_argument("--strip-yaml", action="store_true")
    args=ap.parse_args()

    # Enhanced permissions checking
    try:
        from permissions_utils import preflight_check
        vault_path = VAULT  # Use the global VAULT variable
        required_dirs = ["Summaries", "Express/pitch", "logs"]
        if not preflight_check(vault_path, required_dirs):
            print("❌ Permission check failed for Summarizer Agent")
            print("   Please run prep_summarizer_dirs.bat or check vault permissions.")
            return
    except ImportError:
        print("⚠️  Permissions utilities not available, proceeding without validation...")

    created=updated=skipped=generated=0
    if args.mode=="generate":
        if not SUMMARIES.exists() or not any(SUMMARIES.glob("summary_*.md")):
            created=intake_from_inbox(); u,s=normalize_all(); updated+=u; skipped+=s
        generated=generate_content(args.max_bullets, args.actions, args.strip_yaml)
    elif args.normalize_only:
        updated, skipped = normalize_all()
    elif args.intake_only:
        created = intake_from_inbox()
    else:
        created = intake_from_inbox(); u,s=normalize_all(); updated+=u; skipped+=s

    report=LOGS / "gating_report.md"
    report.write_text(
        "# Summarizer v4 Report\n\n"
        f"- Created: {created}\n- Updated: {updated}\n- Skipped: {skipped}\n- Generated: {generated}\n"
        f"- Run at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n", encoding="utf-8"
    )
    print(f"[OK] Wrote {report}")

if __name__ == "__main__":
    main()
