# -*- coding: utf-8 -*-
"""
gating_pass.py — post-processor that enforces checklists on Summaries, Pitches, and Insights.

- Scans VAULT for:
    Summaries/summary_*.md
    Express/pitch/*.md
    Express/insights/*.md

- For each note type, verifies required sections are present & non-empty.
- Injects/refreshes a "Gating Checklist" block tailored to the note type.
- Updates YAML:
    - meta_status: needs_review | enriched
    - last_run: timestamp (left alone if absent)

Relies on gating_utils.py helpers for frontmatter parsing and checks.
"""

import os, re, datetime as dt
from pathlib import Path
from typing import List, Dict, Tuple

from gating_utils import (
    read_text, write_text, parse_frontmatter, compose_frontmatter,
    sections_filled, checklist_passed
)

VAULT = Path(os.environ.get("VAULT_PATH") or r"C:\Users\top2e\Sync")

# Folders
SUMMARIES = VAULT / "Summaries"
PITCHES   = VAULT / "Express" / "pitch"
INSIGHTS  = VAULT / "Express" / "insights"

# Required sections per note type (flexible: accept alternate headings where common)
REQUIRED_SECTIONS: Dict[str, List[str]] = {
    "summary": ["TL;DR", "Summary", "Next Actions"],
    "pitch":   ["Problem|Context|Background", "Proposal|Solution|Plan", "Acceptance Criteria|Success Metrics", "Next Actions"],
    "insight": ["Insight|Summary", "Rationale|Why|Reasoning", "Implications|So What|Impact", "Next Actions"],
}

# Tailored gating checklists
CHECKLISTS: Dict[str, List[str]] = {
    "summary": [
        "Add 2–3 concrete Next Actions",
        "Add/verify tags in YAML",
        "Link 2–3 related notes (use [[wikilinks]])",
        "Mark `meta_status: enriched` when done",
    ],
    "pitch": [
        "State the Problem/Context clearly",
        "Define the Proposal/Plan with scope & owner",
        "Add measurable Acceptance Criteria / Success Metrics",
        "List dependencies/risks and timeline",
        "Add/verify tags & related links",
        "Mark `meta_status: enriched` when done",
    ],
    "insight": [
        "State the core Insight in one sentence",
        "Explain Rationale (evidence or reasoning)",
        "List Implications (decisions/actions enabled)",
        "Add 2–3 concrete Next Actions",
        "Add/verify tags & related links",
        "Mark `meta_status: enriched` when done",
    ]
}

def _compile_required_patterns(names: List[str]) -> List[re.Pattern]:
    """Convert OR headings (e.g., 'Problem|Context') to case-insensitive regex for section finding in sections_filled()."""
    pats = []
    for n in names:
        # We don't change gating_utils.sections_filled — it matches by substring in the heading text.
        # Here we pre-expand alternatives and later test any of them by reformatting body headings.
        pats.append(re.compile(n, flags=re.I))
    return pats

def _ensure_gate_block(body: str, lines: List[str]) -> str:
    gate = "## Gating Checklist\n" + "\n".join(f"- [ ] {lbl}" for lbl in lines) + "\n"
    # remove any old gating block then add the fresh one near the end (before EOF)
    body = re.sub(r"(?s)^## Gating Checklist.*?(?=^## |\Z)", "", body, flags=re.MULTILINE)
    if not body.endswith("\n"):
        body += "\n"
    return body.rstrip() + "\n\n" + gate

def _has_all_required_sections(body: str, section_specs: List[str]) -> bool:
    """Looser checker that respects alternative headings by mapping them to generic names and reusing sections_filled."""
    # Build a mapping list of representative names to test; sections_filled checks by substring after '## '.
    # We'll treat each alternative group as satisfied if any one is present.
    groups = [spec.split("|") for spec in section_specs]
    # Fast path: if all primary names are satisfied
    if sections_filled(body, [g[0] for g in groups]):
        return True
    # Otherwise, try all names from each group (flatten) and require at least one per group.
    # We'll scan headings and build a found set.
    found = set()
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*)", line.strip())
        if not m:
            continue
        h = m.group(1).strip().lower()
        for i, alts in enumerate(groups):
            for alt in alts:
                if alt.lower() in h:
                    found.add(i)
    return len(found) == len(groups)

def _checklist_done(body: str, labels: List[str]) -> bool:
    return checklist_passed(body, labels)

def process_one(md_path: Path, note_type: str) -> Tuple[bool, str]:
    """Return (changed, status)"""
    src = read_text(md_path)
    fm, body, s, e = parse_frontmatter(src)
    section_spec = REQUIRED_SECTIONS[note_type]
    checklist_labels = CHECKLISTS[note_type]

    # Ensure required sections exist & are filled
    has_sections = _has_all_required_sections(body, section_spec)

    changed = False
    # Insert or refresh Gating Checklist
    if not _checklist_done(body, checklist_labels) or not has_sections:
        new_body = _ensure_gate_block(body, checklist_labels)
        if new_body != body:
            body = new_body
            changed = True

    # Update meta_status
    if has_sections and _checklist_done(body, checklist_labels):
        status = "enriched"
    else:
        status = "needs_review"
    if fm.get("meta_status") != status:
        fm["meta_status"] = status
        changed = True

    # Preserve/refresh last_run if present
    if "last_run" in fm:
        fm["last_run"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    if changed:
        head = compose_frontmatter(fm)
        write_text(md_path, f"---\n{head}\n---\n{body}")
    return changed, status

def scan_folder(folder: Path, note_type: str) -> Tuple[int, int]:
    updated = ok = 0
    if not folder.exists():
        return updated, ok
    for p in sorted(folder.glob("*.md")):
        ch, status = process_one(p, note_type)
        updated += int(ch)
        ok += int(status == "enriched")
    return updated, ok

def main():
    print("=== Gating Pass ===")
    print(f"VAULT_PATH = {VAULT}")
    total_updated = total_ok = 0

    s_upd, s_ok = scan_folder(SUMMARIES, "summary")
    print(f"[Summaries] updated={s_upd} enriched={s_ok}")
    total_updated += s_upd; total_ok += s_ok

    p_upd, p_ok = scan_folder(PITCHES, "pitch")
    print(f"[Pitches]   updated={p_upd} enriched={p_ok}")
    total_updated += p_upd; total_ok += p_ok

    i_upd, i_ok = scan_folder(INSIGHTS, "insight")
    print(f"[Insights]  updated={i_upd} enriched={i_ok}")
    total_updated += i_upd; total_ok += i_ok

    print(f"=== Done: updated={total_updated}, enriched={total_ok} ===")

if __name__ == "__main__":
    main()
