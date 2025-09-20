# score_utils.py

import os
import sys
import json
from datetime import datetime

# --- Unicode-safe print setup ---
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        msg = " ".join(str(a) for a in args) + kwargs.get("end", "\n")
        sys.stdout.buffer.write(msg.encode(enc, errors="replace"))

# --- Memory paths and loading ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SYSTEM_DIR = os.path.join(BASE_DIR, "System")
os.makedirs(SYSTEM_DIR, exist_ok=True)

MEMORY_FILE = os.path.join(SYSTEM_DIR, "memory_feedback.json")
_memory = {}
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        _memory = json.load(f)

# --- Core functions ---
def record_feedback(note_id: str, score: float, reason: str = None):
    entry = _memory.get(note_id, {"scores": [], "reasons": []})
    entry["scores"] = entry.get("scores", []) + [score]
    if reason:
        entry["reasons"] = entry.get("reasons", []) + [reason]
    entry["last_updated"] = datetime.now().isoformat()
    _memory[note_id] = entry
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(_memory, f, ensure_ascii=False, indent=2)
    safe_print(f"[MEMORY] Recorded {note_id}: {score:.2f} ({reason or ''})")

def get_memory_boost(note_id: str, base_score: float) -> float:
    entry = _memory.get(note_id, {})
    scores = entry.get("scores", [])
    if scores:
        avg = sum(scores) / len(scores)
        boost = avg * 0.1
        final = base_score + boost
        safe_print(f"[MEMORY] Boosting '{note_id}': base={base_score:.2f}, boost={boost:.2f} → {final:.2f}")
        return final
    return base_score

def get_avg_memory_score():
    scores = [
        sum(entry.get("scores", [])) / len(entry["scores"])
        for entry in _memory.values() if entry.get("scores")
    ]
    return round(sum(scores) / len(scores), 2) if scores else None
