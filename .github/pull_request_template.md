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
REM Example smoke runs
.\run_all.bat --help
.\index_resources.bat --dry-run
.\run_summarizer.bat --max-notes 1 --dry-run --continue-on-error

## Testing / QA
- [ ] Local smoke run attached (output of `--help` or minimal run)
- [ ] Manual QA steps documented below (what you clicked/ran)
- [ ] Tests added/updated (if applicable)

**Evidence (paste logs / screenshots):**
```
Example:
.\index_resources.bat --dry-run
.\run_summarizer.bat --max-notes 1 --dry-run --continue-on-error
.\run_all.bat --help
```

## Breaking Changes (if any)
<!-- Describe impact, migration steps, or explain why N/A -->

## Affected Scripts
<!-- List touched files: e.g., orchestrator_agent.py, training_pipeline.py, resource_indexer.py -->

<details>
<summary><strong>CI Status (optional)</strong></summary>

- [ ] GitHub Actions CI passing (if configured)
- Notes:
</details>

<details>
<summary><strong>Multi-LLM Review Checklist (optional)</strong></summary>

- Reviewed by ChatGPT: ☐ Approved ☐ Changes Requested  
- Reviewed by Claude: ☐ Approved ☐ Changes Requested  
- Reviewed by [Other]: ☐ Approved ☐ Changes Requested  
- [ ] All LLM feedback addressed
</details>

## AI Disclosure
- [ ] Copilot (or similar) contributed. I reviewed and verified logic, security, and ran locally.

## Checklist
- [ ] No secrets committed; reads from `.env` only
- [ ] `--dry-run` supported for any file-writes (or N/A)
- [ ] CLI flags documented in script header or README (Usage section)
- [ ] Docs/usage examples updated if behavior changed
