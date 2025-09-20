@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set PYTHONUNBUFFERED=1

"%~dp0venv\Scripts\python.exe" -u training_pipeline.py ^
  --quiz-items 7 ^
  --min-higher-order-pct 0.5 ^
  --append-on-shortfall 1 ^
  --daily-trainer 1 ^
  --self-score 1

endlocal
