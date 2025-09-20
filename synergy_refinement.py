# -*- coding: utf-8 -*-
"""
Synergy Refinement Agent (Merged: Refined + Legacy + Composite + Time Series)
- Computes synergy for notes under Express/pitch and Express/insights.
- Refined: link density (normalized), tag overlap with neighbors, PARA ripple (2-hop).
- Legacy: degree from links_log, tag co-occurrence size, heuristic ripple = len(tags)*degree.
- Composite: alpha*refined + (1-alpha)*legacy_norm (percentile normalized per run).
- Outputs:
    * System/synergy_scores.csv (snapshot, overwritten each run)
    * System/synergy_timeseries.csv (append-only history with EMA)
    * System/success_metrics.json (append run summary + settings)
"""
import os
import json
import csv
from collections import defaultdict, Counter
from datetime import datetime

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

# ---------- Paths ----------
ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT, "data")
SYSTEM_DIR = os.path.join(ROOT, "System")
os.makedirs(SYSTEM_DIR, exist_ok=True)

GRAPH_JSON = os.path.join(DATA_DIR, "note_graph.json")
INDEX_JSON = os.path.join(DATA_DIR, "vault_index.json")
LINKS_LOG = os.path.join(DATA_DIR, "links_log.csv")

SCORES_CSV = os.path.join(SYSTEM_DIR, "synergy_scores.csv")
TS_CSV = os.path.join(SYSTEM_DIR, "synergy_timeseries.csv")
SUCCESS_JSON = os.path.join(SYSTEM_DIR, "success_metrics.json")

# ---------- Settings ----------
DEFAULT_WEIGHTS = {"link_density": 0.45, "tag_overlap": 0.30, "ripple": 0.25}
DEFAULT_BLEND = {"alpha_refined": 0.70, "ema_span": 5, "legacy_norm": "percentile", "links_identity": "auto", "write_aliases": False}
DISAGREE_THRESHOLD = 0.35
METHOD_VERSIONS = {"refined": "1.0.1", "legacy": "0.9.1", "composite": "1.0.1"}

PITCH_KEY = os.sep + "Express" + os.sep + "pitch" + os.sep
INSIGHT_KEY = os.sep + "Express" + os.sep + "insights" + os.sep

PARA_CUES = {
    "areas": ["Areas", "01_Areas"],
    "projects": ["Projects", "02_Projects"],
    "resources": ["Resources", "03_Resources"],
    "archives": ["Archives", "04_Archives"],
}

# ---------- Helpers ----------
def log(msg):
    print(f"[Synergy] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {msg}")

def safe_load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"⚠️  Could not read {path}: {e}. Using default.")
        return default

def detect_para_bucket(folder_path: str) -> str:
    if not folder_path:
        return ""
    norm = folder_path.replace("/", os.sep)
    for bucket, cues in PARA_CUES.items():
        for cue in cues:
            if (os.sep + cue + os.sep) in (os.sep + norm + os.sep):
                return bucket
    return ""

def normalize(v, max_v):
    if max_v <= 0:
        return 0.0
    return max(0.0, min(1.0, v / max_v))

def build_degree_and_adj(links):
    degree = Counter()
    adj = defaultdict(set)
    for e in links:
        s = e.get("source"); t = e.get("target")
        if not s or not t:
            continue
        degree[s] += 1; degree[t] += 1
        adj[s].add(t); adj[t].add(s)
    return degree, adj

def two_hop_neighbors(adj, node):
    first = adj.get(node, set())
    second = set()
    for n in first:
        second |= adj.get(n, set())
    return (first | second) - {node}

def percentile_rank(values, x):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    # count <= x via binary search
    lo, hi = 0, len(sorted_vals)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_vals[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return max(0.0, min(1.0, lo / len(sorted_vals)))

def is_target(path):
    if not path: return False
    norm = path.replace("/", os.sep)
    return (PITCH_KEY in norm) or (INSIGHT_KEY in norm)

# ---------- Main ----------
def main():
    log("Starting merged synergy computation (path-preferred)…")

    graph = safe_load_json(GRAPH_JSON, {"nodes": [], "links": []})
    index = safe_load_json(INDEX_JSON, [])
    success_base = safe_load_json(SUCCESS_JSON, {})
    weights = dict(DEFAULT_WEIGHTS)
    blend = dict(DEFAULT_BLEND)
    if isinstance(success_base, dict) and isinstance(success_base.get("settings"), dict):
        s = success_base["settings"]
        weights.update(s.get("synergy_weights", {})) if isinstance(s.get("synergy_weights"), dict) else None
        blend.update(s.get("blend", {})) if isinstance(s.get("blend"), dict) else None

    # Build lookups
    nodes = {n.get("id") for n in graph.get("nodes", []) if n.get("id")}
    links = graph.get("links", [])
    degree, adj = build_degree_and_adj(links)
    max_deg = max(degree.values()) if degree else 0

    meta_by_path = {}
    title_to_path = {}
    tags_by_path = {}
    for it in index:
        p = it.get("path")
        if not p: continue
        title = it.get("title") or os.path.splitext(os.path.basename(p))[0]
        meta_by_path[p] = {"tags": it.get("tags", []), "folder": it.get("folder", ""), "title": title}
        tags_by_path[p] = it.get("tags", [])
        title_to_path.setdefault(title, p)  # first-match

    # PARA bucket by node
    para_bucket = {}
    for p in nodes:
        folder = meta_by_path.get(p, {}).get("folder", "")
        para_bucket[p] = detect_para_bucket(folder)

    # Target notes
    target_nodes = [p for p in nodes if is_target(p)]
    log(f"Targets: {len(target_nodes)} notes.")

    # Refined components
    refined_rows = []
    for note in target_nodes:
        note_deg = degree.get(note, 0)
        link_density = normalize(note_deg, max_deg)
        note_tags = set(tags_by_path.get(note, []))

        # neighbor tags overlap
        neighbor_tags = set()
        for n in adj.get(note, set()):
            neighbor_tags |= set(tags_by_path.get(n, []))
        tag_overlap = (len(note_tags & neighbor_tags) / max(1, len(note_tags))) if note_tags else 0.0

        # ripple across PARA buckets within 2 hops
        reach = two_hop_neighbors(adj, note)
        buckets = {para_bucket.get(r, "") for r in reach if para_bucket.get(r, "")}
        ripple = normalize(len(buckets), 4)

        refined_score = (
            weights.get("link_density", DEFAULT_WEIGHTS["link_density"]) * link_density +
            weights.get("tag_overlap", DEFAULT_WEIGHTS["tag_overlap"]) * tag_overlap +
            weights.get("ripple", DEFAULT_WEIGHTS["ripple"]) * ripple
        )

        category = "pitch" if (PITCH_KEY in note.replace("/", os.sep)) else "insight"
        refined_rows.append({
            "note_path": note,
            "category": category,
            "ref_link_density": round(link_density, 6),
            "ref_tag_overlap": round(tag_overlap, 6),
            "ref_ripple": round(ripple, 6),
            "refined_score": round(refined_score, 6),
        })

    # Legacy components (prefer path-based degrees if present)
    links_identity = (blend.get("links_identity") or "auto").lower()
    deg_by_title = Counter(); deg_by_path = Counter()
    path_edges = 0; title_edges = 0

    if os.path.exists(LINKS_LOG):
        try:
            with open(LINKS_LOG, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                has_sp = "source_path" in fieldnames; has_tp = "target_path" in fieldnames
                has_st = "source" in fieldnames;    has_tt = "target" in fieldnames

                for row in reader:
                    s_path = (row.get("source_path") or "").strip()
                    t_path = (row.get("target_path") or "").strip()
                    s_title = (row.get("source") or "").strip()
                    t_title = (row.get("target") or "").strip()

                    use_path = (links_identity == "path") or (links_identity == "auto" and (s_path or t_path))

                    if use_path:
                        if s_path: deg_by_path[s_path] += 1; path_edges += 1
                        elif s_title: deg_by_title[s_title] += 1; title_edges += 1
                        if t_path: deg_by_path[t_path] += 1; path_edges += 1
                        elif t_title: deg_by_title[t_title] += 1; title_edges += 1
                    else:
                        if s_title: deg_by_title[s_title] += 1; title_edges += 1
                        if t_title: deg_by_title[t_title] += 1; title_edges += 1
        except Exception as e:
            log(f"⚠️  Could not parse links_log.csv: {e}")
    log(f"Legacy degree counts — used path edges: {path_edges}, title edges: {title_edges}")

    tag_map = defaultdict(set)    # tag -> set(titles)
    tags_by_title = defaultdict(list)
    for p, meta in meta_by_path.items():
        ttl = meta.get("title", "")
        for tg in meta.get("tags", []):
            tag_map[tg].add(ttl)
        tags_by_title[ttl] = meta.get("tags", [])

    def legacy_components_for_path(note_path):
        title = meta_by_path.get(note_path, {}).get("title", "")
        link_score = deg_by_path.get(note_path, deg_by_title.get(title, 0))
        tag_score = sum(len(tag_map[t]) for t in tags_by_title.get(title, []) if t in tag_map)
        ripple_effect = len(tags_by_title.get(title, [])) * link_score
        legacy_raw = 0.4 * link_score + 0.4 * tag_score + 0.2 * ripple_effect
        return link_score, tag_score, ripple_effect, legacy_raw

    # Merge refined + legacy with normalization
    legacy_raw_values = [legacy_components_for_path(r["note_path"])[-1] for r in refined_rows]

    def norm_legacy(raw):
        if (blend.get("legacy_norm") or "percentile").lower() == "percentile":
            return percentile_rank(legacy_raw_values, raw)
        # fallback: min-max
        if not legacy_raw_values: return 0.0
        mn, mx = min(legacy_raw_values), max(legacy_raw_values)
        return 0.0 if mx == mn else (raw - mn)/(mx - mn)

    alpha = float(blend.get("alpha_refined", 0.70))
    run_id = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    snapshot_rows = []
    for r in refined_rows:
        link_score, tag_score, ripple_effect, legacy_raw = legacy_components_for_path(r["note_path"])
        legacy_norm = norm_legacy(legacy_raw)
        composite = alpha * r["refined_score"] + (1.0 - alpha) * legacy_norm
        disagreement = abs(r["refined_score"] - legacy_norm)
        row = {
            **r,
            "leg_link_score": link_score,
            "leg_tag_score": tag_score,
            "leg_ripple_effect": ripple_effect,
            "legacy_score_raw": round(legacy_raw, 6),
            "legacy_score_norm": round(legacy_norm, 6),
            "composite_score": round(composite, 6),
            "disagreement_abs": round(disagreement, 6),
            "run_id": run_id,
            "timestamp": timestamp,
        }
        if blend.get("write_aliases"):
            row["synergy_score"] = row["composite_score"]
            row["synergy_refined"] = row["refined_score"]
            row["synergy_legacy_norm"] = row["legacy_score_norm"]
        snapshot_rows.append(row)

    # Write snapshot CSV
    fieldnames = [
        "note_path","category",
        "ref_link_density","ref_tag_overlap","ref_ripple","refined_score",
        "leg_link_score","leg_tag_score","leg_ripple_effect","legacy_score_raw","legacy_score_norm",
        "composite_score","disagreement_abs","run_id","timestamp"
    ]
    if DEFAULT_BLEND.get("write_aliases"):
        fieldnames += ["synergy_score","synergy_refined","synergy_legacy_norm"]
    with open(SCORES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in snapshot_rows:
            w.writerow(r)
    log(f"Snapshot -> {SCORES_CSV} ({len(snapshot_rows)} rows)")

    # Append time series with EMA (header even if empty file exists)
    write_header = (not os.path.exists(TS_CSV)) or (os.path.getsize(TS_CSV) == 0)
    last_ema = {}
    if not write_header:
        try:
            with open(TS_CSV, "r", encoding="utf-8") as f:
                rd = csv.DictReader(f)
                for row in rd:
                    last_ema[row["note_path"]] = (
                        float(row.get("ema_refined", 0) or 0),
                        float(row.get("ema_legacy", 0) or 0),
                        float(row.get("ema_composite", 0) or 0),
                    )
        except Exception:
            write_header = True  # recover by writing header anew

    alpha_ema = 2.0 / (blend.get("ema_span", 5) + 1.0) if blend.get("ema_span", 5) > 0 else 1.0
    with open(TS_CSV, "a", newline="", encoding="utf-8") as f:
        fn = [
            "note_path","category",
            "ref_link_density","ref_tag_overlap","ref_ripple","refined_score",
            "leg_link_score","leg_tag_score","leg_ripple_effect","legacy_score_raw","legacy_score_norm",
            "composite_score","disagreement_abs","run_id","timestamp",
            "ema_refined","ema_legacy","ema_composite"
        ]
        if blend.get("write_aliases"):
            fn += ["synergy_score","synergy_refined","synergy_legacy_norm"]
        w = csv.DictWriter(f, fieldnames=fn)
        if write_header:
            w.writeheader()
        for r in snapshot_rows:
            prev = last_ema.get(r["note_path"], (r["refined_score"], r["legacy_score_norm"], r["composite_score"]))
            ema_ref = prev[0] + alpha_ema*(r["refined_score"] - prev[0])
            ema_leg = prev[1] + alpha_ema*(r["legacy_score_norm"] - prev[1])
            ema_cmp = prev[2] + alpha_ema*(r["composite_score"] - prev[2])
            rec = dict(r)
            rec.update({
                "ema_refined": round(ema_ref, 6),
                "ema_legacy": round(ema_leg, 6),
                "ema_composite": round(ema_cmp, 6),
            })
            w.writerow(rec)
    log(f"Timeseries appended -> {TS_CSV}")

    # Summaries for success_metrics.json
    def stats(vals):
        if not vals: return {"mean":0,"p50":0,"p90":0}
        sv = sorted(vals); n = len(sv)
        p50 = sv[n//2] if n%2==1 else 0.5*(sv[n//2-1]+sv[n//2])
        p90 = sv[min(n-1, int(0.9*(n-1)))]
        return {"mean": round(sum(sv)/n, 6), "p50": round(p50,6), "p90": round(p90,6)}

    refined_vals = [r["refined_score"] for r in snapshot_rows]
    legacy_vals = [r["legacy_score_norm"] for r in snapshot_rows]
    comp_vals   = [r["composite_score"] for r in snapshot_rows]

    run_summary = {
        "run_id": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "counts": {
            "notes_scored": len(snapshot_rows),
            "pitches": sum(1 for r in snapshot_rows if r["category"]=="pitch"),
            "insights": sum(1 for r in snapshot_rows if r["category"]=="insight"),
            "high_disagreement": sum(1 for r in snapshot_rows if r["disagreement_abs"] > DISAGREE_THRESHOLD)
        },
        "refined_summary": stats(refined_vals),
        "legacy_summary": stats(legacy_vals),
        "composite_summary": stats(comp_vals),
        "method_versions": METHOD_VERSIONS
    }

    # persist success_metrics with settings if missing
    out = dict(success_base) if isinstance(success_base, dict) else {}
    hist = out.get("synergy_runs", [])
    if not isinstance(hist, list): hist = []
    hist.append(run_summary)
    out["synergy_runs"] = hist
    out.setdefault("settings", {})
    out["settings"].setdefault("synergy_weights", DEFAULT_WEIGHTS)
    out["settings"].setdefault("blend", DEFAULT_BLEND)
    with open(SUCCESS_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    log(f"Run summary appended -> {SUCCESS_JSON}")
    log("Done.")

if __name__ == "__main__":
    main()
