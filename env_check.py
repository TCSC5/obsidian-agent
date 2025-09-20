# env_check.py
import os, sys
from pathlib import Path

print("=== env_check.py ===")
print("Python exe :", sys.executable)
print("CWD        :", Path.cwd())

# Try to import and load .env
env_path = None
try:
    from dotenv import load_dotenv, find_dotenv
    env_path = find_dotenv()
    print("find_dotenv:", env_path if env_path else "(not found)")
    if env_path:
        loaded = load_dotenv(env_path, override=False)
        print("Loaded dotenv:", env_path, "->", loaded)
    else:
        print("Loaded dotenv: False (no .env found)")
except Exception as e:
    print("python-dotenv import/load failed:", e)

# Show key presence (masked) and VAULT_PATH
key = os.environ.get("OPENAI_API_KEY")
masked = (key[:4] + "..." + key[-4:]) if key and len(key) > 8 else str(bool(key))
print("OPENAI_API_KEY:", masked)
print("VAULT_PATH     :", os.environ.get("VAULT_PATH"))

# Show nearby .env candidates
candidates = [
    Path.cwd() / ".env",
    Path(__file__).parent / ".env",
    Path.cwd().parent / ".env",
]
seen = set()
print("\n.env candidates:")
for p in candidates:
    p = p.resolve()
    if p in seen: 
        continue
    seen.add(p)
    print(" -", p, "exists:", p.exists())
    if p.exists():
        try:
            # print the first 2 lines (mask key if present)
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            head = lines[:5]
            preview = []
            for line in head:
                if line.strip().startswith("OPENAI_API_KEY"):
                    k = line.split("=",1)[-1].strip()
                    mask = (k[:4] + "..." + k[-4:]) if len(k) > 8 else ("present" if k else "missing")
                    preview.append("OPENAI_API_KEY=<" + mask + ">")
                else:
                    preview.append(line)
            print("   preview:", " | ".join(preview))
        except Exception as e:
            print("   (could not read)", e)
