@echo on
cd /d D:\MyScripts\obsidian-agent
call venv\Scripts\activate
python orchestrator_agent_profiled.py --profile maint --dry-run --verbose
pause
