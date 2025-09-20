# memory_feedback_agent.py — Memory + Feedback Agent with Unicode-safe printing

import os
import sys
import json
from datetime import datetime
from glob import glob

# 1. Enable UTF‑8 console output (Python 3.7+)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # Skip if not supported

# 2. Define safe_print() to avoid crashing on Unicode issues
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        msg = " ".join(str(a) for a in args) + kwargs.get("end", "\n")
        sys.stdout.buffer.write(msg.encode(enc, errors="replace"))

# 3. Setup paths
BASE = os.path.dirname(__file__)
SYSTEM = os.path.join(BASE, "System")
os.makedirs(SYSTEM, exist_ok=True)
MEMORY_PATH = os.path.join(SYSTEM, "memory_feedback.json")
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 4. Load persistent memory
memory = {}
if os.path.exists(MEMORY_PATH):
    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        memory = json.load(f)

# 5. Memory helper functions
def record_feedback(note_id, score: float, reason: str = None):
    entry = memory.get(note_id, {"scores": [], "reasons": []})
    entry["scores"] = entry.get("scores", []) + [score]
    if reason:
        entry["reasons"] = entry.get("reasons", []) + [reason]
    entry["last_updated"] = datetime.now().isoformat()
    memory[note_id] = entry
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    safe_print(f"[MEMORY] Recorded feedback for '{note_id}': score={score:.2f}, reason='{reason or ''}'")

def get_memory_boost(note_id, base_score: float) -> float:
    entry = memory.get(note_id, {})
    scores = entry.get("scores", [])
    if scores:
        avg = sum(scores) / len(scores)
        boost = avg * 0.1
        new_score = base_score + boost
        safe_print(f"[MEMORY] Note '{note_id}': base={base_score:.2f}, boost={boost:.2f}, final={new_score:.2f}")
        return new_score
    return base_score

# 6. Example feedback loop (replace with actual use case)
EXAMPLES_DIR = os.path.join(DATA_DIR, "examples")
for filepath in glob(os.path.join(EXAMPLES_DIR, "*.json")):
    note_id = os.path.basename(filepath)
    base_score = 1.0  # Replace with real logic
    final_score = get_memory_boost(note_id, base_score)
    record_feedback(note_id, final_score * 0.8, reason="simulated feedback")

safe_print("✅ Memory + Feedback Agent completed.")
