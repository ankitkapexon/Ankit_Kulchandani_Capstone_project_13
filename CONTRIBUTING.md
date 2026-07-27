# Contributing

## Goal

Keep code, tests, and documentation aligned with current project behavior.

## Setup

```bash
pip install -r requirements.txt
python -m pytest
```

## Live Demo Contract Rules

When changing live demo behavior, update docs and tests in the same change.

Current contract highlights:
- Run context includes screenshot name for screenshot flow.
- Run context does not display Run ID.
- Both flows remain supported: screenshot pipeline and deterministic realtime.

## Task Automation Rules

- Keep `.vscode/tasks.json` and `scripts/task_runner.py` aligned.
- Prefer Python task dispatch over shell-specific task logic.

## Artifact Hygiene

- Do not commit runtime-generated outputs unless explicitly required.
- Review `artifacts/` changes before staging.

## Pull Request Expectations

- Describe what changed and why.
- Include verification steps and test results.
- Keep documentation consistent with final behavior.
