import os, re, sys
from pathlib import Path

BULLET_RE = re.compile(r'^(?P<indent>\s*)[-*+]\s+(?P<text>.+?)(?P<id>\s+\^[A-Za-z0-9_-]+)?\s*$')

ROOT = Path(__file__).parent
ENV = ROOT / ".env"

def load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k,v = line.split("=",1)
                os.environ.setdefault(k.strip(), v.strip())

def find_cheatsheets():
    load_env()
    vault = os.environ.get("VAULT_PATH","").strip()
    if not vault:
        print("[ERR] VAULT_PATH missing in .env"); sys.exit(2)
    base = Path(vault)
    # Cheat sheets are alongside learning_inputs; scan entire vault
    cheats = list(base.rglob("*.cheatsheet.md"))
    return cheats

def add_block_ids_all_levels(path: Path) -> int:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    lines = txt.splitlines()
    out = []
    in_code = False
    added = 0
    used = set()

    # collect existing ids
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

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line); continue
        if line.lstrip().startswith(">"):
            out.append(line); continue

        m = BULLET_RE.match(line)
        if m:
            indent = m.group('indent')
            text = m.group('text').rstrip()
            ex_id = m.group('id')
            if not ex_id:
                bid = next_id()
                line = f"{indent}- {text} {bid}"
                added += 1
        out.append(line)

    if added:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return added

def main():
    cheats = find_cheatsheets()
    total = 0
    files = 0
    for c in cheats:
        a = add_block_ids_all_levels(c)
        total += a
        if a: files += 1
    print(f"[OK] Added {total} block IDs across {files} cheat sheets ({len(cheats)} scanned).")

if __name__ == "__main__":
    main()
