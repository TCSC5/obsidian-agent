
# -*- coding: utf-8 -*-
"""
orchestrator_agent_full.py — Full expanded chain including drafting, decision support, reflection summarizer, and architect.

Steps:
 1) Summarizer
 2) Drafting Enhancer (GPT)
 3) Prioritizer (GPT)
 4) Planner (GPT)
 5) Insight Evolution
 6) Synergy Refinement
 7) Reflection
 8) Reflection Summarizer (GPT)
 9) Decision Support (GPT)
 10) Agent Architect (GPT)
 11) Dashboard

CLI similar to before.
"""

import os, sys, shlex, subprocess, argparse, time
from pathlib import Path

BASE = Path(__file__).parent.resolve()
ENV = os.environ.copy()
ENV.setdefault("VAULT_PATH", r"C:\Users\top2e\Sync")
ENV.setdefault("PYTHONIOENCODING", "utf-8")
ENV.setdefault("PYTHONUTF8", "1")

def py(): return sys.executable or "python"

def run_step(cmd, name, retries=0):
    attempt=0
    while True:
        try:
            print(f"\n=== Step: {name} ===\nRunning: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, cwd=str(BASE), env=ENV)
            print(f"== OK: {name} ==")
            return
        except subprocess.CalledProcessError as e:
            if attempt>=retries: raise
            attempt+=1; time.sleep(2)

def exists(*names):
    for n in names:
        if (BASE/n).exists(): return str((BASE/n).name)
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", type=int)
    ap.add_argument("--continue-on-error", action="store_true")
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--summarizer-args", default="")
    args=ap.parse_args()

    steps=[]
    # 1) Summarizer
    summ=exists("summarizer_agent_v5.py") or exists("summarizer_agent_v4.py") or exists("summarizer_agent.py")
    cmd=[py(), summ] if summ else []
    if args.summarizer_args: cmd.extend(shlex.split(args.summarizer_args))
    if cmd: steps.append(("Summarizer",cmd))

    # 2) Drafting Enhancer
    if exists("drafting_enhancer_agent.py"): steps.append(("Drafting Enhancer",[py(),"drafting_enhancer_agent.py"]))

    # 3) Prioritizer
    if exists("prioritizer_agent.py"): steps.append(("Prioritizer",[py(),"prioritizer_agent.py"]))

    # 4) Planner
    if exists("planner_agent.py"): steps.append(("Planner",[py(),"planner_agent.py"]))

    # 5) Insight Evolution
    if exists("insight_evolution_agent.py"): steps.append(("Insight Evolution",[py(),"insight_evolution_agent.py"]))

    # 6) Synergy
    if exists("synergy_refinement.py"): steps.append(("Synergy Refinement",[py(),"synergy_refinement.py"]))

    # 7) Reflection
    if exists("reflection_agent.py"): steps.append(("Reflection",[py(),"reflection_agent.py"]))

    # 8) Reflection Summarizer
    if exists("reflection_summarizer_agent.py"): steps.append(("Reflection Summarizer",[py(),"reflection_summarizer_agent.py"]))

    # 9) Decision Support
    if exists("decision_support_agent.py"): steps.append(("Decision Support",[py(),"decision_support_agent.py"]))

    # 10) Agent Architect
    if exists("agent_architect_agent.py"): steps.append(("Agent Architect",[py(),"agent_architect_agent.py"]))

    # 11) Dashboard
    dash=exists("generate_dashboard_v3.py") or exists("generate_dashboard_v2.py") or exists("generate_dashboard.py")
    if dash: steps.append(("Dashboard",[py(),dash]))

    selected=list(range(1,len(steps)+1))
    if args.only: selected=[i for i in selected if i in args.only]

    for i,(name,cmd) in enumerate(steps,1):
        if i not in selected: continue
        try: run_step(cmd,f"{i}. {name}",retries=args.retries)
        except Exception as e:
            if not args.continue_on_error: raise
            print(f"!! Continuing after error in Step {i}: {name}")

if __name__=="__main__": main()
