
# -*- coding: utf-8 -*-
"""
cleanup_review_log.py — safe, non-interactive cleanup for orchestrator runs

Usage:
  python cleanup_review_log.py                      # interactive (legacy)
  python cleanup_review_log.py --auto keep          # keep all, no prompt
  python cleanup_review_log.py --auto purge         # purge all entries, no prompt
  python cleanup_review_log.py --pattern "pitch"    # operate only on lines matching pattern
"""

import re, sys, argparse
from pathlib import Path

BASE = Path(__file__).parent
SYSTEM = BASE / "System"
LOG = SYSTEM / "review_needed_log.md"

def load_lines():
    if not LOG.exists():
        return []
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()

def save_lines(lines):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", choices=["keep","purge"], help="Non-interactive mode")
    ap.add_argument("--pattern", help="Regex to filter lines for action")
    args = ap.parse_args()

    lines = load_lines()
    if not lines:
        print("[INFO] No review log found; skipping clean step.")
        return

    if args.auto:
        pat = re.compile(args.pattern, re.I) if args.pattern else None
        if args.auto == "keep":
            # just ensure newline normalization
            save_lines(lines if not pat else [ln for ln in lines if pat.search(ln)])
            print("[OK] Kept review log (auto).")
        elif args.auto == "purge":
            if pat:
                new_lines = [ln for ln in lines if not pat.search(ln)]
                save_lines(new_lines)
                print("[OK] Purged matching lines (auto).")
            else:
                save_lines([])
                print("[OK] Purged entire review log (auto).")
        return

    # legacy interactive mode
    print("[interactive] Current review log has", len(lines), "lines.")
    print("Nothing done. Use --auto keep|purge for CI runs.")

if __name__ == "__main__":
    main()
