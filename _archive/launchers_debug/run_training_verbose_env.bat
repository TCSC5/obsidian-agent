@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONUNBUFFERED=1

REM Ensure .env has OPENAI_API_KEY and TRAINING_MODEL (gpt-4o-mini)
REM Optional: set QUIZ_DIR=C:\Users\top2e\Sync\Quizzes-TEST

"%~dp0venv\Scripts\python.exe" -u training_pipeline.py ^
  --gpt-only --force-summarize --force-quiz ^
  --quiz-items 7 ^
  --min-higher-order-pct 0.5 ^
  --append-on-shortfall 1 ^
  --max-notes 1 > "logs\last_run_env.txt" 2>&1

echo Wrote verbose log to logs\last_run_env.txt
endlocal
