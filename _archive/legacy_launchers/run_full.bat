
@echo off
cd /d D:\MyScripts\obsidian-agent
call venv\Scripts\activate
python orchestrator_agent_profiled.py --profile full --continue-on-error --retries 1
