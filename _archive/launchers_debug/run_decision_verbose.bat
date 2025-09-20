
@echo on
cd /d D:\MyScripts\obsidian-agent
call venv\Scripts\activate
python orchestrator_agent_profiled.py --profile decision --dry-run --verbose --summarizer-args "--no-archive"
pause
