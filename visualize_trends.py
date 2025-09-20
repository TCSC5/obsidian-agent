import os
import json
import matplotlib.pyplot as plt
from datetime import datetime

# Load memory
base_dir = os.path.abspath(os.path.dirname(__file__))
memory_path = os.path.join(base_dir, "System", "memory_feedback.json")
if not os.path.exists(memory_path):
    print("No memory data found, skipping trends visualization.")
    exit()

with open(memory_path, "r", encoding="utf-8") as f:
    memory = json.load(f)

# Aggregate average score over time
times = []
avg_scores = []
for note_id, entry in memory.items():
    ts = entry.get("last_updated")
    scores = entry.get("scores", [])
    if ts and scores:
        times.append(datetime.fromisoformat(ts))
        avg_scores.append(sum(scores) / len(scores))

# Sort by time
pairs = sorted(zip(times, avg_scores))
if not pairs:
    print("No scored entries to plot.")
    exit()

times_sorted, scores_sorted = zip(*pairs)

# Plotting trend
plt.figure(figsize=(10, 5))
plt.plot(times_sorted, scores_sorted, marker='o')
plt.title("Memory-Adjusted Score Trend Over Time")
plt.xlabel("Timestamp")
plt.ylabel("Average Score")
plt.grid(True)

output = os.path.join(base_dir, "data", "score_trend.png")
plt.savefig(output)
print(f"Score trend plotted to: {output}")
