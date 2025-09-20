# learning_loop_agent.py

import os
import re
from datetime import datetime
from collections import Counter

# Paths
vault_path = os.getenv("VAULT_PATH", "C:/Users/top2e/Sync")
base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")
feedback_path = os.path.join(data_dir, "feedback_log.md")
reflection_path = os.path.join(data_dir, "reflection_log.md")
learning_log_path = os.path.join(data_dir, "learning_loops.md")

# Extract suggestion sections using regex
def extract_suggestions(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r"##.*(Suggestions|Feedback)[\s\S]*?(?=\n##|\Z)"
    matches = re.findall(pattern, content, re.IGNORECASE)
    suggestions = []
    for block in matches:
        suggestions += re.findall(r"- (.+)", block)
    return suggestions

# Aggregate repeated suggestions
texts = extract_suggestions(feedback_path) + extract_suggestions(reflection_path)
counts = Counter(texts)
repeated = [(s, c) for s, c in counts.items() if c > 1]

# Build learning loop log
now = datetime.now().strftime("%Y-%m-%d %H:%M")
lines = [f"# 🔄 Long-Term Learning Loop — {now}", "", "## Repeating Suggestions/Issues"]
if repeated:
    for text, count in repeated:
        lines.append(f"- {text} ({count}×)")
else:
    lines.append("- No repeating patterns detected.")

lines.append("")
lines.append("## GPT Recommendations")
if repeated:
    lines.append("- Refactor pipeline around recurring issues.")
    lines.append("- Consider adding agents to handle the top 3 patterns.")
else:
    lines.append("- System is stable; no recurring issues found.")
lines.append("- Review this log weekly to ensure continuous improvement.")

# Write output
os.makedirs(data_dir, exist_ok=True)
with open(learning_log_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Learning loop written to: {learning_log_path}")
