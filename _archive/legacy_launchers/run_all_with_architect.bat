@echo off
cd /d D:\MyScripts\obsidian-agent

echo Activating virtual environment...
call venv\Scripts\activate.bat

REM === Step 1: Rebuild vault index ===
python generate_vault_index.py

REM === Step 2: Run main linking agent ===
python src\main.py

REM === Step 3: Run summarizer ===
python summarizer_agent.py

REM === Step 4: Build graph files ===
python generate_graph.py
python generate_mermaid_graph.py

REM === Step 5: Build dashboard with visuals and sync ===
python generate_dashboard_v2.py

REM === Step 6: Express Phase — Pitch Decks ===
python generate_pitch_deck.py

REM === Step 7: Express Phase — GPT-Originated Insights ===
python generate_insights_agent.py

REM === Step 8: Success Scoring Agent ===
python evaluate_success.py

REM === Step 9: Reflection Agent ===
python reflection_agent.py

REM === Step 10: Memory + Feedback Agent ===
python memory_feedback_agent.py

REM === Step 11: Long-Term Learning Loop Agent ===
python learning_loop_agent.py

REM === Step 12: Agent Performance GPT ===
python agent_performance_gpt.py

REM === Step 12a: Sync Performance Report to Vault ===
copy /Y "D:\MyScripts\obsidian-agent\data\agent_performance_report.md" "C:\Users\top2e\Sync\System\agent_performance_report.md"

REM === Step 13: Enhanced Agent Architect ===
python agent_architect_gpt.py

REM === Step 13a: Sync Architect Report to Vault ===
copy /Y "D:\MyScripts\obsidian-agent\data\agent_architect_report.md" "C:\Users\top2e\Sync\System\agent_architect_report.md"

REM === Step 14: Snapshot Logging Agent (kept last so it captures full run) ===
python generate_snapshot_log.py

REM === Final: Launch dashboard in Obsidian ===
start "" "obsidian://open?path=C:/Users/top2e/Sync/dashboard.md"

pause
