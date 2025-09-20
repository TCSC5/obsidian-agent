
# -*- coding: utf-8 -*-
"""
launch_obsidian.py — open your vault in Obsidian on Windows
- Uses obsidian://open?path=<vault_path> if the URL scheme is registered.
- Falls back to startfile on the vault folder.
"""
import os, sys, urllib.parse, webbrowser

VAULT = os.getenv("VAULT_PATH") or r"C:\Users\top2e\Sync"

def main():
    # Try obsidian://open?path=
    url = "obsidian://open?path=" + urllib.parse.quote(VAULT, safe="")
    try:
        ok = webbrowser.open(url, new=0, autoraise=True)
        if ok:
            print("[OK] Launched Obsidian via URL:", url)
            return
    except Exception:
        pass
    # Fallback: open the vault folder (lets you double-click a note quickly)
    try:
        os.startfile(VAULT)
        print("[OK] Opened vault folder:", VAULT)
    except Exception as e:
        print("[warn] Could not open Obsidian or vault folder:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
