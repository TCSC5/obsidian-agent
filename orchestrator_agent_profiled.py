# -*- coding: utf-8 -*-
"""
orchestrator_agent_profiled.py — One entry point with profiles + skip logic

Profiles:
  - decision (fast, default): content-to-decision loop
  - full (weekly): includes heavy maintenance steps if present
  - maint (on-demand): index/link/graph/dashboard only (no GPT)

Flags:
  --profile decision|full|maint
  --continue-on-error
  --retries N
  --summarizer-args [ARGS ...]        # optional passthrough to summarizer (zero or more args)
  --skip <comma-separated step keys>  # e.g. --skip router,graph

Heavy steps auto-skip if script not found.
"""

import os, sys, subprocess, argparse, time
from pathlib import Path

BASE = Path(__file__).parent.resolve()
ENV = os.environ.copy()
ENV.setdefault("VAULT_PATH", r"C:\\Users\\top2e\\Sync")
ENV.setdefault("PYTHONIOENCODING", "utf-8")
ENV.setdefault("PYTHONUTF8", "1")

def py(): return sys.executable or "python"

def exists(name):
    return (BASE / name).exists()

def cmd_for(name, *args):
    return [py(), name] + list(args)

def list_available_scripts():
    names = [
        'summarizer_agent_v5.py','summarizer_agent_v4.py','summarizer_agent.py',
        'drafting_enhancer_agent.py','prioritizer_agent.py','planner_agent.py',
        'insight_evolution_agent.py','synergy_refinement.py','reflection_agent.py',
        'reflection_summarizer_agent.py','decision_support_agent.py','agent_architect_agent.py',
        'generate_vault_index.py','linking_agent.py','auto_enricher_agent.py','para_router.py',
        'graph_generator.py','mermaid_graph.py','areas_monitor_agent.py','clean_reviewed.py',
        'score_agent.py','snapshot_logger.py','evaluate_success.py','launch_obsidian.py',
        'generate_dashboard_v3.py','generate_dashboard_v2.py','generate_dashboard.py',
        'gating_pass.py'
    ]
    return {n: (BASE / n).exists() for n in names}

def run_step(cmd, name, retries=0):
    attempt=0
    while True:
        try:
            print(f"\\n=== {name} ===\\n> {' '.join(cmd)}")
            subprocess.run(cmd, check=True, cwd=str(BASE), env=ENV)
            print(f"== OK: {name} =="); return True
        except subprocess.CalledProcessError:
            if attempt>=retries: print(f"!! FAIL: {name}"); return False
            attempt+=1; time.sleep(2)

def add_if(steps, key, friendly, script, *args):
    if exists(script):
        steps.append((key, friendly, cmd_for(script, *args)))

def build_steps(profile, args_skip, summarizer_args, retries):
    skip = set([s.strip().lower() for s in (args_skip or "").split(",") if s.strip()])
    steps = []

    def add(key, friendly, script, *sargs):
        if key in skip: return
        add_if(steps, key, friendly, script, *sargs)

    # --- Common building blocks ---
    add("index",  "Rebuild Vault Index",           "generate_vault_index.py")
    add("link",   "Main Linking Agent",            "linking_agent.py")
    add("autoen", "Auto-Enricher",                 "auto_enricher_agent.py")
    add("router", "PARA Router",                   "para_router.py")
    add("graph",  "Graph JSON/CSV",                "graph_generator.py")
    add("merm",   "Mermaid Graph",                 "mermaid_graph.py")
    add("areas",  "Monitor Areas",                 "areas_monitor_agent.py")
    add("clean",  "Cleanup Reviewed Items",        "clean_reviewed.py")
    add("score",  "Score Pitches/Insights",        "score_agent.py")
    add("snap",   "Snapshot Log",                  "snapshot_logger.py")
    add("eval",   "Evaluate Success",              "evaluate_success.py")
    add("launch", "Launch Obsidian",               "launch_obsidian.py")

    # Summarizer (v5 preferred)
    if "summarizer" not in skip:
        if exists("summarizer_agent_v5.py"):
            steps.append(("summarizer","Summarizer (v5)", cmd_for("summarizer_agent_v5.py", *summarizer_args)))
        elif exists("summarizer_agent_v4.py"):
            steps.append(("summarizer","Summarizer (v4)", cmd_for("summarizer_agent_v4.py","--mode","generate","--max-bullets","5","--actions","3","--strip-yaml", *summarizer_args)))
        elif exists("summarizer_agent.py"):
            steps.append(("summarizer","Summarizer (legacy)", cmd_for("summarizer_agent.py", *summarizer_args)))

    # Express/GPT phases
    add("draft",  "Drafting Enhancer (GPT)",       "drafting_enhancer_agent.py")
    add("prior",  "Prioritizer (GPT)",             "prioritizer_agent.py")
    add("plan",   "Planner (GPT)",                 "planner_agent.py")
    add("evolve", "Insight Evolution",             "insight_evolution_agent.py")
    add("syn",    "Synergy Refinement",            "synergy_refinement.py")
    add("refl",   "Reflection",                    "reflection_agent.py")
    add("rsum",   "Reflection Summarizer (GPT)",   "reflection_summarizer_agent.py")
    add("decide", "Decision Support (GPT)",        "decision_support_agent.py")
    add("arch",   "Agent Architect (GPT)",         "agent_architect_agent.py")

    # Gating Pass (enforces checklists & meta_status on summaries/pitches/insights)
    add("gate",   "Gating Pass",                   "gating_pass.py")

    # Dashboard (prefer v3)
    if "dash" not in skip:
        if exists("generate_dashboard_v3.py"):
            steps.append(("dash","Dashboard v3", cmd_for("generate_dashboard_v3.py")))
        elif exists("generate_dashboard_v2.py"):
            steps.append(("dash","Dashboard v2", cmd_for("generate_dashboard_v2.py")))
        elif exists("generate_dashboard.py"):
            steps.append(("dash","Dashboard", cmd_for("generate_dashboard.py")))

    # Profile order
    if profile == "decision":
        key_order = ["summarizer","gate","draft","prior","plan","evolve","syn","refl","rsum","decide","arch","dash"]
    elif profile == "full":
        key_order = ["index","link","autoen","router","summarizer","gate","draft","prior","plan","evolve","syn","refl","rsum","decide","arch","graph","merm","snap","eval","dash","launch"]
    elif profile == "maint":
        key_order = ["index","link","graph","merm","dash"]
    else:
        key_order = [k for (k,_,_) in steps]

    ordered = [(k,n,c) for (k,n,c) in steps if k in key_order]
    return [(k,n,c,retries) for (k,n,c) in ordered]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["decision","full","maint"], default="decision")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true")
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--summarizer-args", nargs=argparse.REMAINDER, default=[],
                    help="Arguments to pass to the summarizer agent (place at the end).")
    ap.add_argument("--skip", default="")
    ap.add_argument("--only", default="", help="Comma-separated step keys to run (e.g., prior,plan)")
    args = ap.parse_args()

    steps = build_steps(args.profile, args.skip, args.summarizer_args, args.retries)
    avail = list_available_scripts()

    if args.verbose or args.dry_run:
        print(f"Profile: {args.profile}")
        print("Available scripts:")
        for k,v in sorted(avail.items()):
            print(f"  - {k}: {'OK' if v else 'missing'}")
        print("Selected steps:")
        for i,(key,name,cmd,_) in enumerate(steps,1):
            print(f"  {i:>2}. {key:10s} — {name}")

    if not steps:
        print("No steps selected/found."); sys.exit(0)

    only_set = set([s.strip().lower() for s in (args.only or "").split(",") if s.strip()])
    if only_set:
        steps = [t for t in steps if t[0] in only_set]
        if not steps:
            print(f"No matching steps for --only={','.join(sorted(only_set))}"); sys.exit(0)

    if args.dry_run:
        print("\\n(DRY RUN) No steps executed.")
        return

    for i,(key,name,cmd,retries) in enumerate(steps,1):
        try:
            ok = run_step(cmd, f"{i}. {name}", retries=retries)
            if not ok and not args.continue_on_error:
                sys.exit(1)
        except Exception as e:
            print(f"!! Error in step {i}: {name} — {e}")
            if not args.continue_on_error:
                raise

if __name__ == "__main__":
    main()
