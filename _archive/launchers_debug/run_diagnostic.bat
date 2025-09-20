@echo off
:: Diagnostic version of run_all.bat to troubleshoot file paths

cd /d D:\MyScripts\obsidian-agent

echo.
echo === [Diagnostic] Current Directory ===
cd

echo.
echo === [Diagnostic] Checking Python Path ===
if exist D:\MyScripts\obsidian-agent\.venv\Scripts\python.exe (
    echo ✅ Found Python at .venv\Scripts\python.exe
) else (
    echo ❌ Python not found at expected path.
)

echo.
echo === [Diagnostic] Checking orchestrator_agent.py ===
if exist orchestrator_agent.py (
    echo ✅ Found orchestrator_agent.py
) else (
    echo ❌ orchestrator_agent.py not found
)

echo.
echo === [Diagnostic] Checking generate_dashboard_v2.py ===
if exist generate_dashboard_v2.py (
    echo ✅ Found generate_dashboard_v2.py
) else (
    echo ❌ generate_dashboard_v2.py not found
)

echo.
echo === [Diagnostic] Checking data\ files ===
for %%F in (
    run_log.md
    success_report.md
    snapshot_log.md
    agent_performance_report.md
    reflection_log.md
    learning_loops.md
    agent_architect_report.md
    insight_evolution.md
    feedback_log.md
) do (
    if exist "data\%%F" (
        echo ✅ data\%%F found
    ) else (
        echo ❌ data\%%F missing
    )
)

echo.
echo === Done ===
pause
