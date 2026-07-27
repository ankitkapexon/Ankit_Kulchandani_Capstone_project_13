# LiteLLM Testing Guide

This guide covers current LiteLLM-oriented validation for this project.

## Prerequisites

- Virtual environment active
- Dependencies installed
- Required provider or gateway environment variables set
- Live demo backend running at `http://127.0.0.1:8080/`

## Validation Flow

1. Run a screenshot pipeline demo from the UI.
2. Confirm generation artifacts are created.
3. Confirm HTML execution report is created.
4. Review logs for provider or gateway failures.

## Optional Checks

```bash
python scripts/task_runner.py check-server
python scripts/task_runner.py check-appium
python -m pytest tests/test_realtime_e2e_flow.py -q
```

## Troubleshooting

- If run startup fails, use **Start / Restart Services** and retry.
- If provider responses fail, validate gateway and environment values.
- If artifacts look stale, clear only run-generated files and rerun.
