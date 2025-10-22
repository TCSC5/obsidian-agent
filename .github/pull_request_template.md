## Summary
<!-- What changed and why? 1-2 sentences. Link design docs if relevant. -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor (no behavior change)
- [ ] Documentation
- [ ] Chore (tooling/infra)
- [ ] Breaking change

---

<!-- ================================================ -->
<!-- 💻 FOR CODE CHANGES (feature/bug/refactor) -->
<!-- Delete this section if chore/docs/tooling only -->
<!-- ================================================ -->

## How to Run Locally (Windows)
<!-- Exact commands to test this change -->
```bat
REM Set your vault path
set VAULT_PATH=C:\path\to\your\vault

REM Example smoke runs
.\run_all.bat --help
.\index_resources.bat --dry-run
.\run_summarizer.bat --max-notes 1 --dry-run --continue-on-error
```

## Testing / QA

### Local Smoke Tests (matches CI workflow)
<!-- Run these commands locally. Check each box as you complete them. -->

#### Core Pipeline Components (Required)
- [ ] **Vault Index**: `python generate_vault_index.py --dry-run`
- [ ] **Resource Indexer**: `python resource_indexer.py --vault "%VAULT_PATH%" --dry-run --verbose`
  - [ ] Tested with YAML frontmatter notes
  - [ ] Tested with non-YAML notes
- [ ] **Orchestrator**: `.\run_orchestrator.bat --profile decision --dry-run`

#### Optional Components (check if applicable to your changes)
- [ ] **Summarizer**: `.\run_summarizer.bat --max-notes 1 --dry-run --continue-on-error`
- [ ] **Dashboard**: `python generate_dashboard_v3.py --dry-run` (or v2 if v3 not present)
- [ ] **Reflection Agents**:
  - [ ] `python reflection_agent.py --dry-run`
  - [ ] `python reflection_summarizer_agent.py --dry-run --no-vault-mirror --max-items 3`

#### Policy Compliance
- [ ] **No deprecated launchers**: Verified no references to `run_orchestrator_v5.bat` in modified files
```bat
  REM Quick check:
  findstr /S /I "run_orchestrator_v5" *.bat *.py
```
- [ ] **No hardcoded paths**: All vault paths use `VAULT_PATH` environment variable or config
- [ ] **Dry-run compatible**: New code respects `--dry-run` flag (no writes when enabled)

### Evidence
<!-- Paste relevant output from smoke tests, error messages, or screenshots -->
<details>
<summary><strong>Local test output</strong></summary>
```text
Example:
.\index_resources.bat --dry-run
[DRY RUN] Processing 42 notes in C:\vault\Resources\learning_inputs
[DRY RUN] Would create metadata index at C:\vault\System\resource_metadata.json
✓ Validation complete

.\run_summarizer.bat --max-notes 1 --dry-run --continue-on-error
[DRY RUN] Would summarize: note1.md
✓ Dry-run complete
```

</details>

<details>
<summary><strong>run_log.md excerpt (if applicable)</strong></summary>
```markdown
<!-- Paste relevant sections from vault\System\run_log.md -->
```

</details>

### GitHub Actions CI
- [ ] All CI checks passing (see "Checks" tab above)
- [ ] Reviewed CI logs for warnings or deprecation notices
- [ ] No new workflow failures introduced

---

## Breaking Changes (if any)
<!-- Describe impact, migration steps, or explain why N/A -->
- [ ] N/A - No breaking changes
- [ ] Breaking changes documented below:

**Migration instructions:**
<!-- Provide step-by-step instructions for users to adapt to breaking changes -->

---

## Affected Scripts
<!-- List touched files: e.g., orchestrator_agent.py, training_pipeline.py, resource_indexer.py -->
- 
- 
- 

---

## Code Quality Checklist
- [ ] No secrets committed; reads from `.env` only
- [ ] `--dry-run` supported for any file-writes (or N/A)
- [ ] CLI flags documented in script header or README (Usage section)
- [ ] Self-review completed (checked diff before submitting)
- [ ] Comments added for complex logic
- [ ] Error handling added for new failure modes
- [ ] Logging statements use appropriate levels (DEBUG/INFO/ERROR)

## Documentation
- [ ] README.md updated (if user-facing changes)
- [ ] Code comments added/updated
- [ ] Configuration examples updated (if config changes)
- [ ] Docs/usage examples updated if behavior changed

---

<details>
<summary><strong>Multi-LLM Review (optional but recommended)</strong></summary>

Use multiple AI assistants to catch different types of issues:
- [ ] Reviewed by ChatGPT: Approved / Changes Requested
- [ ] Reviewed by Claude: Approved / Changes Requested
- [ ] Reviewed by [Other]: Approved / Changes Requested
- [ ] All LLM feedback addressed

**Summary of AI feedback:**
<!-- Brief notes on what each AI caught or suggested -->

</details>

---

## AI Disclosure
- [ ] AI assistant (Copilot/ChatGPT/Claude) contributed code or significant refactoring
- [ ] I reviewed and verified all AI-generated logic, security implications, and tested locally
- [ ] AI was used only for documentation/comments/minor edits

---

## For Reviewers

### Review Checklist
- [ ] Code changes align with PR summary
- [ ] Smoke test evidence provided is sufficient
- [ ] No security concerns (hardcoded secrets, unsafe file operations)
- [ ] Error messages are helpful and actionable
- [ ] Changes are backwards compatible (or migration path documented)
- [ ] CI workflow changes are valid (if workflow files modified)

### Quick Validation Commands
```powershell
# Copy-paste friendly smoke suite
$env:VAULT_PATH = "C:\path\to\your\vault"

# Core smoke tests
python generate_vault_index.py --dry-run
python resource_indexer.py --vault "$env:VAULT_PATH" --dry-run --verbose
.\run_orchestrator.bat --profile decision --dry-run

# Policy check
Select-String -Path .\*.bat,.\*.py -Pattern "run_orchestrator_v5"
```

---

<!-- 
Template version: 2.0 (aligned with smoke-windows.yml)
Last updated: 2025-10-21
Aligns with: .github/workflows/smoke-windows.yml
-->
