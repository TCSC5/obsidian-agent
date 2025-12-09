#!/bin/bash
# cleanup_final_safe.sh - Ultra-safe cleanup

set -e
echo "=========================================="
echo "  Obsidian Agent Cleanup (Ultra-Safe)"
echo "=========================================="

mkdir -p _archive/legacy_agents
mkdir -p _archive/legacy_launchers
mkdir -p _archive/legacy_folders

echo ""
echo "[1/3] Archiving legacy Python agents..."
for f in orchestrator_agent.py summarizer_agent_v4.py; do
    if [ -f "$f" ]; then
        mv "$f" _archive/legacy_agents/
        echo "  ✓ $f"
    fi
done
echo "  (Keeping auto_enricher_v4.py - general enricher, still needed)"
echo "  (Keeping agents/ folder - used by training_pipeline.py)"

echo ""
echo "[2/3] Archiving redundant launchers..."
for f in run_all.bat run_all_with_architect.bat run_decision.bat run_full.bat \
         run_maint.bat run_orchestrator_v5.bat run_summarizer.bat \
         run_main_with_venv.bat run_fixed_main.bat run_planner_agent.bat \
         run_pitch_deck.bat run_insights_agent.bat \
         run_memory_feedback.bat run_learning_loop.bat run_agent_performance.bat; do
    if [ -f "$f" ]; then
        mv "$f" _archive/legacy_launchers/
        echo "  ✓ $f"
    fi
done

echo ""
echo "[3/3] Archiving old src/ folder..."
if [ -d "src" ]; then
    mv src/ _archive/legacy_folders/
    echo "  ✓ src/"
fi

echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo "  Archived agents:    $(ls _archive/legacy_agents/ 2>/dev/null | wc -l)"
echo "  Archived launchers: $(ls _archive/legacy_launchers/ 2>/dev/null | wc -l)"
echo "  Archived folders:   $(ls _archive/legacy_folders/ 2>/dev/null | wc -l)"
echo ""
echo "  PRESERVED:"
echo "  - auto_enricher_v4.py (general metadata enricher)"
echo "  - agents/quiz_agent.py (quiz generation)"
echo "  - agents/summarizer_agent.py (cheatsheet generation)"
echo ""
echo "  USE: run_orchestrator.bat --profile decision|full|maint"
echo "=========================================="
