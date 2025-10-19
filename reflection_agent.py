#!/usr/bin/env python3
"""
reflection_agent.py
Produce a detailed reflection log from recent artifacts (metrics, logs, summaries, quizzes).
Writes a Markdown report to data/reflection_log.md by default.

Usage (examples):
  python reflection_agent.py --dry-run
  python reflection_agent.py --out data\reflection_log.md
  python reflection_agent.py --vault "%VAULT_PATH%" --continue-on-error

Conventions:
- UTC ISO timestamps in console logs and System/run_log.md
- Never writes without --dry-run being False
- Vault lives outside the repo (only read paths if needed)
"""

from __future__ import annotations
import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# -------------------------
# Common helpers
# -------------------------

def utc_ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def log_line(level: str, agent: str, msg: str) -> None:
    ts = utc_ts()
    print(f"{ts} | {level.upper()} | {agent} | {msg}")


def append_run_log(message: str, run_log_path: Path = Path("System/run_log.md")) -> None:
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with run_log_path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_ts()} | INFO | reflection_agent | {message}\n")


def safe_write(path: Path, content: str, *, dry_run: bool) -> None:
    size = len(content.encode("utf-8"))
    action = "DRY-RUN write" if dry_run else "write"
    log_line("info", "reflection_agent", f"{action}: {path} ({size} bytes)")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# -------------------------
# Data collection
# -------------------------

@dataclass
class Snapshot:
    notes_processed: int = 0
    summaries: int = 0
    quizzes: int = 0
    grades: int = 0
    coverage_pct: Optional[float] = None
    quiz_accuracy_pct: Optional[float] = None
    last_runs: List[str] = None


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log_line("error", "reflection_agent", f"failed to parse JSON {path}: {e}")
        return None


def tail_lines(path: Path, n: int = 50) -> List[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-n:]
    except Exception as e:
        log_line("error", "reflection_agent", f"failed to read {path}: {e}")
        return []


def count_files(root: Path, patterns: List[str]) -> int:
    if not root.exists():
        return 0
    total = 0
    for pat in patterns:
        total += sum(1 for _ in root.rglob(pat))
    return total


def gather_snapshot() -> Snapshot:
    snap = Snapshot(last_runs=[])

    # Summaries / quizzes / grades counts under data/
    data_dir = Path("data")
    snap.summaries = count_files(data_dir / "Summaries", ["summary.md", "cheatsheet.md"])
    snap.quizzes   = count_files(data_dir / "Quizzes", ["*.json"])
    snap.grades    = count_files(data_dir / "Grades", ["*.json"])

    # Try to infer "notes_processed" ~= unique summary folders
    summaries_root = data_dir / "Summaries"
    if summaries_root.exists():
        snap.notes_processed = sum(1 for p in summaries_root.iterdir() if p.is_dir())
    else:
        snap.notes_processed = 0

    # Metrics from System/success_metrics.json (if present)
    metrics = read_json(Path("System/success_metrics.json")) or {}
    cov = metrics.get("coverage_pct", metrics.get("coverage"))
    acc = metrics.get("quiz_accuracy_pct", metrics.get("quiz_accuracy"))
    try:
        snap.coverage_pct = float(cov) if cov is not None else None
    except Exception:
        snap.coverage_pct = None
    try:
        snap.quiz_accuracy_pct = float(acc) if acc is not None else None
    except Exception:
        snap.quiz_accuracy_pct = None

    # Last runs from System/run_log.md
    snap.last_runs = tail_lines(Path("System/run_log.md"), n=25)
    return snap


# -------------------------
# Report generation
# -------------------------

def md_percent(x: Optional[float]) -> str:
    if x is None:
        return "_n/a_"
    try:
        return f"{x:.1f}%"
    except Exception:
        return "_n/a_"


def suggestions_from_snapshot(s: Snapshot) -> List[str]:
    tips: List[str] = []
    if s.notes_processed < 5 and s.summaries == 0:
        tips.append("Process a small batch (3–5 notes) to warm up the pipeline.")
    if s.coverage_pct is not None and s.coverage_pct < 60:
        tips.append("Coverage is low; consider indexing more folders or adding tags.")
    if s.quiz_accuracy_pct is not None and s.quiz_accuracy_pct < 70:
        tips.append("Quiz accuracy is modest; schedule reinforcement on low-score notes.")
    if s.grades == 0 and s.quizzes > 0:
        tips.append("Quizzes exist without grades; run the scoring step.")
    if not tips:
        tips.append("System is healthy—continue your current cadence.")
    return tips


def build_report(s: Snapshot) -> str:
    ts = utc_ts()
    lines: List[str] = []
    lines.append(f"# Reflection Report")
    lines.append(f"_Generated: {ts}_")
    lines.append("")
    lines.append("## Snapshot")
    lines.append(f"- Notes processed: **{s.notes_processed}**")
    lines.append(f"- Summaries: **{s.summaries}**  |  Quizzes: **{s.quizzes}**  |  Grades: **{s.grades}**")
    lines.append(f"- Coverage: **{md_percent(s.coverage_pct)}**  |  Quiz accuracy: **{md_percent(s.quiz_accuracy_pct)}**")
    lines.append("")
    lines.append("## Recent Runs (tail)")
    if s.last_runs:
        lines.extend(f"- {ln}" for ln in s.last_runs)
    else:
        lines.append("_No recent runs logged._")
    lines.append("")
    lines.append("## Insights & Suggestions")
    for tip in suggestions_from_snapshot(s):
        lines.append(f"- {tip}")
    lines.append("")
    lines.append("## Next Actions (checklist)")
    lines.append("- [ ] Summarize 3 new notes")
    lines.append("- [ ] Regenerate dashboard")
    lines.append("- [ ] Review low-accuracy topics")
    lines.append("")
    return "\n".join(lines)


# -------------------------
# CLI
# -------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Produce detailed reflection log from recent metrics/logs.")
    p.add_argument("--vault", type=Path, default=os.getenv("VAULT_PATH"),
                   help="Path to your Obsidian vault (optional, not written by this script)."
                   )
    p.add_argument("--out", type=Path, default=Path("data/reflection_log.md"),
                   help="Output reflection log path (Markdown).")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview planned writes; do not modify files.")
    p.add_argument("--continue-on-error", action="store_true",
                   help="Log errors and continue execution.")
    return p


def main() -> int:
    args = build_parser().parse_args()
    log_line("info", "reflection_agent", "collecting snapshot")
    try:
        snap = gather_snapshot()
        report = build_report(snap)
        safe_write(args.out, report, dry_run=args.dry_run)
        append_run_log(f"wrote reflection log → {args.out}")
        return 0
    except Exception as e:
        log_line("error", "reflection_agent", f"{type(e).__name__}: {e}")
        if args.continue_on_error:
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
