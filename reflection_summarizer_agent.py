#!/usr/bin/env python3
"""
reflection_summarizer_agent.py
Summarize data/reflection_log.md into a brief executive summary.
Writes a repo copy and (optionally) mirrors into the vault.

Usage (examples):
  python reflection_summarizer_agent.py --dry-run --no-vault-mirror
  python reflection_summarizer_agent.py --in data\reflection_log.md --out data\reflection_summary.md
  python reflection_summarizer_agent.py --vault "%VAULT_PATH%" --mirror-dest System\reflection_summary.md
"""

from __future__ import annotations
import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List


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
        f.write(f"{utc_ts()} | INFO | reflection_summarizer | {message}\n")


def safe_write(path: Path, content: str, *, dry_run: bool) -> None:
    size = len(content.encode("utf-8"))
    action = "DRY-RUN write" if dry_run else "write"
    log_line("info", "reflection_summarizer", f"{action}: {path} ({size} bytes)")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def mirror_to_vault(vault: Path | None, repo_summary: Path, mirror_rel: Path, *, dry_run: bool) -> None:
    if vault is None:
        log_line("info", "reflection_summarizer", "no VAULT_PATH set; skipping mirror")
        return
    vault_path = (vault / mirror_rel).resolve()
    if not repo_summary.exists():
        log_line("error", "reflection_summarizer", f"repo summary missing: {repo_summary}")
        return
    content = repo_summary.read_text(encoding="utf-8")
    action = f"{'DRY-RUN ' if dry_run else ''}mirror to vault"
    log_line("info", "reflection_summarizer", f"{action}: {vault_path}")
    if dry_run:
        return
    vault_path.parent.mkdir(parents=True, exist_ok=True)
    vault_path.write_text(content, encoding="utf-8")


# -------------------------
# Summarization (heuristic; offline)
# -------------------------

def extract_bullets(md: str, max_items: int = 6) -> List[str]:
    bullets: List[str] = []
    for line in md.splitlines():
        l = line.strip()
        if l.startswith("- ") and not l.startswith("- ["):
            # skip checkboxes
            item = l[2:].strip()
            if item:
                bullets.append(item)
        if len(bullets) >= max_items:
            break
    return bullets


def extract_metrics(md: str) -> List[str]:
    """Look for 'Coverage: xx%' and 'Quiz accuracy: yy%' lines."""
    out: List[str] = []
    cov = re.search(r"Coverage:\s+\*\*(\d+(?:\.\d+)?)%?\*\*", md)
    acc = re.search(r"Quiz accuracy:\s+\*\*(\d+(?:\.\d+)?)%?\*\*", md)
    if cov:
        out.append(f"Coverage ~ {cov.group(1)}%")
    if acc:
        out.append(f"Quiz accuracy ~ {acc.group(1)}%")
    return out


def build_summary_text(md: str) -> str:
    ts = utc_ts()
    lines: List[str] = []
    lines.append(f"# Reflection Summary")
    lines.append(f"_Generated: {ts}_")
    lines.append("")
    metrics = extract_metrics(md)
    if metrics:
        lines.append("**Metrics:** " + " | ".join(metrics))
        lines.append("")
    bullets = extract_bullets(md, max_items=6)
    if bullets:
        lines.append("## Key Points")
        for b in bullets[:6]:
            lines.append(f"- {b}")
        lines.append("")
    # Grab next actions
    next_actions = []
    capture = False
    for line in md.splitlines():
        if line.strip().lower().startswith("## next actions"):
            capture = True
            continue
        if capture:
            if line.strip().startswith("## "):
                break
            if line.strip().startswith("- [ ]"):
                next_actions.append(line.strip().replace("- [ ]", "- [ ]"))
    if next_actions:
        lines.append("## Next Actions")
        lines.extend(next_actions[:6])
        lines.append("")
    # Fallback
    if not bullets and not metrics and not next_actions:
        lines.append("_No obvious highlights extracted from reflection log._")
    return "\n".join(lines)


# -------------------------
# CLI
# -------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Summarize reflection_log.md into an executive summary.")
    p.add_argument("--in", dest="inp", type=Path, default=Path("data/reflection_log.md"),
                   help="Input reflection log (Markdown).")
    p.add_argument("--out", type=Path, default=Path("data/reflection_summary.md"),
                   help="Output summary path (repo copy)." )
    p.add_argument("--vault", type=Path, default=os.getenv("VAULT_PATH"),
                   help="Vault path for optional mirror (default: env VAULT_PATH)." )
    p.add_argument("--mirror-dest", type=Path, default=Path("System/reflection_summary.md"),
                   help="Relative path inside the vault when mirroring.")
    p.add_argument("--no-vault-mirror", action="store_true",
                   help="Do not write a copy into the vault.")
    p.add_argument("--require-gpt", action="store_true",
                   help="Fail if LLM summarization is not available (offline fallback is default)." )
    p.add_argument("--dry-run", action="store_true",
                   help="Preview planned writes; do not modify files." )
    p.add_argument("--continue-on-error", action="store_true",
                   help="Log errors and continue execution." )
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.require_gpt and not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set but --require-gpt was passed.")
        if not args.inp.exists():
            raise FileNotFoundError(f"input not found: {args.inp}")
        md = args.inp.read_text(encoding="utf-8")
        summary = build_summary_text(md)
        safe_write(args.out, summary, dry_run=args.dry_run)
        append_run_log(f"wrote reflection summary → {args.out}")
        if not args.no_vault_mirror:
            mirror_to_vault(args.vault, args.out, args.mirror_dest, dry_run=args.dry_run)
        return 0
    except Exception as e:
        log_line("error", "reflection_summarizer", f"{type(e).__name__}: {e}")
        if args.continue_on_error:
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
