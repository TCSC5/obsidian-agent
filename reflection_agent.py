# reflection_agent.py — with UTF‑8 console support and safe printing

import os
import sys
import csv
import json
from collections import defaultdict, Counter
from datetime import datetime

# ─── 1. Configure Unicode-safe console output ───
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline=None)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", newline=None)
except AttributeError:
    # Fallback for Python <3.7
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", newline=None)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", newline=None)

# ─── 2. Safe-print utility ───
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        msg = sep.join(str(a) for a in args) + end
        sys.stdout.buffer.write(msg.encode(enc, errors="replace"))

# ─── 3. Paths setup ───
base_dir = os.path.dirname(__file__)
data_dir = os.path.join(base_dir, "data")
system_dir = os.path.join(base_dir, "System")

success_log = os.path.join(data_dir, "success_log.csv")
metrics_file = os.path.join(system_dir, "success_metrics.json")
reflection_log = os.path.join(data_dir, "reflection_log.md")
run_log = os.path.join(data_dir, "run_log.md")
synergy_scores = os.path.join(system_dir, "synergy_scores.csv")
synergy_timeseries = os.path.join(system_dir, "synergy_timeseries.csv")

# ─── 4. Load and compute stats ───
insight_scores, pitch_scores, legacy_synergy = [], [], []
by_reason, by_type = defaultdict(int), defaultdict(int)

if os.path.exists(success_log):
    with open(success_log, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kind = row.get("type","").strip()
            score = int(row.get("score") or 0)
            reason = row.get("reason","").strip()
            synergy = float(row.get("synergy") or 0.0)
            if kind == "insight": insight_scores.append(score)
            elif kind == "pitch": pitch_scores.append(score)
            if reason: by_reason[reason] += 1
            if kind: by_type[kind] += 1
            legacy_synergy.append(synergy)

# Load metrics (if any)
metrics = {}
if os.path.exists(metrics_file):
    with open(metrics_file, encoding="utf-8") as f:
        metrics = json.load(f)

# Snapshot info from run_log.md
note_count = link_count = last_snapshot = "N/A"
if os.path.exists(run_log):
    with open(run_log, encoding="utf-8") as f:
        for line in f:
            if "Snapshot Log —" in line:
                last_snapshot = line.split("—")[-1].strip(" )\n")
            elif "**Notes Indexed:**" in line:
                note_count = line.split(":",1)[1].strip()
            elif "**Links Created:**" in line:
                link_count = line.split(":",1)[1].strip()

# ─── 5. Synergy insights ───
def p90(vals):
    sv = sorted(vals)
    return sv[int(0.9*(len(sv)-1))] if vals else 0.0

synergy_section = []
top10_lines, hotlist_lines, trend_lines = [], [], []

if os.path.exists(synergy_scores):
    try:
        with open(synergy_scores, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        comps = [float(r.get("composite_score") or 0) for r in rows]
        avgc = sum(comps)/len(comps) if comps else 0
        p90c = p90(comps)
        synergy_section.extend([
            "## 🔗📈 Synergy Snapshot (Composite)",
            f"- Avg: {avgc:.2f} | P90: {p90c:.2f}", ""
        ])
        top10 = sorted(rows, key=lambda r: float(r.get("composite_score") or 0), reverse=True)[:10]
        top10_lines.append("### Top 10 by Composite")
        for r in top10:
            name = os.path.splitext(os.path.basename(r.get("note_path","")))[0]
            top10_lines.append(f"- {name}: {float(r.get('composite_score') or 0):.2f}")
        top10_lines.append("")
        hot = [r for r in rows if abs(float(r.get("disagreement_abs") or 0)) > 0.35]
        hot = sorted(hot, key=lambda r: abs(float(r.get("disagreement_abs") or 0)), reverse=True)[:10]
        if hot:
            hotlist_lines.append("### ⚠️ Disagreement Hotlist")
            for r in hot:
                name = os.path.splitext(os.path.basename(r.get("note_path","")))[0]
                hotlist_lines.append(f"- {name}: Δ={abs(float(r.get('disagreement_abs') or 0)):.2f}")
            hotlist_lines.append("")
    except Exception:
        synergy_section.extend(["## 🔗📈 Synergy Snapshot (Composite)", "- ⚠️ Could not parse synergy data.", ""])

if os.path.exists(synergy_timeseries):
    try:
        latest = {}
        with open(synergy_timeseries, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key, ts = row.get("note_path",""), row.get("timestamp","")
                if key and (key not in latest or ts > latest[key]["timestamp"]):
                    latest[key] = row
        ema = [float(r.get("ema_composite") or 0) for r in latest.values()]
        vault_ema = sum(ema)/len(ema) if ema else 0
        trend_lines.append("## 📈 Synergy Trend (EMA Composite)")
        trend_lines.append(f"- Vault-wide EMA (mean): {vault_ema:.2f}")
        trend_lines.append("")
    except Exception:
        trend_lines.extend(["## 📈 Synergy Trend (EMA Composite)", "- ⚠️ Could not parse trend data.", ""])

# ─── 6. Build reflection log output ───
now = datetime.now().strftime("%Y-%m-%d %H:%M")
lines = [
    "# 🔁 GPT Reflection Log", "", f"_Updated: {now}_", "",
    "## 📊 Summary Stats",
    f"- Notes Indexed: {note_count}",
    f"- Links Created: {link_count}",
    f"- Pitches scored: {len(pitch_scores)}",
    f"- Insights scored: {len(insight_scores)}",
    f"- Avg Pitch Score: {sum(pitch_scores)/len(pitch_scores):.2f}" if pitch_scores else "- Avg Pitch Score: N/A",
    f"- Avg Insight Score: {sum(insight_scores)/len(insight_scores):.2f}" if insight_scores else "- Avg Insight Score: N/A", ""
] + synergy_section + top10_lines + hotlist_lines + trend_lines + [
    "## 🔍 Top Reasons for Low Scores"
] + [f"- {r}: {c}" for r, c in Counter(by_reason).most_common(5)] + [
    "",
    "## 🤔 GPT Suggestions",
    "- Investigate root causes of repeated failures.",
    "- Monitor whether high-synergy items convert better and adjust weight accordingly.",
    "- Compare `run_log.md` snapshots to detect pipeline shifts.",
    "- If note/link counts drop, revisit summarization or linking steps.", "",
    "## 🧠 Proposed Metric Definitions",
    "```json",
    json.dumps(metrics, indent=2),
    "```",
    "_(Edit `System/success_metrics.json` as needed.)_"
]

with open(reflection_log, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

safe_print("✅ Reflection log updated with synergy insights:", reflection_log)
