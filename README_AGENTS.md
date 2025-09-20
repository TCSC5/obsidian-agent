# Training Agents

This folder contains two optional agents that plug into `training_pipeline.py` when `TRAINING_USE_GPT=1` (default).

- `agents/summarizer_agent.py` — creates a concise cheat sheet from a note (markdown output).
- `agents/quiz_agent.py` — generates 5–10 Q&A pairs for a note (markdown output).
- `utils/openai_helpers.py` — tiny wrapper around the OpenAI Chat Completions REST API.

## Requirements
- Environment:
  - `OPENAI_API_KEY` (required)
  - `OPENAI_MODEL` (optional, default `gpt-4o-mini`)
  - `OPENAI_BASE_URL` (optional; Azure/OpenRouter/etc. compatible if path matches `/chat/completions`)
  - `TRAINING_USE_GPT=1` (to enable; set `0` to force stubs)

- Python deps:
  - `requests`
  - `pyyaml`

## Usage
1. Ensure your `.env` at repo root includes:
   ```
   VAULT_PATH=C:\Users\YourName\Sync
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   TRAINING_USE_GPT=1
   ```
2. Run `run_training.bat`.
3. On success:
   - Cheat sheets next to notes: `Resources/learning_inputs/NoteName.cheatsheet.md`
   - Quizzes under: `Quizzes/NoteName_quiz.md`
   - Links + YAML updated in source note.
