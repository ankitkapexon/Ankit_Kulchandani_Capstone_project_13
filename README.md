# Mobile Test Generator - Capstone Project

## Current Scope

This project converts mobile app screenshots into automated Appium testing assets and also supports a deterministic realtime validation flow.

Supported flows:
- `screenshot_pipeline`
- `deterministic_realtime`

## Current Live Demo Behavior

- Live demo URL: `http://127.0.0.1:8080/`
- Run context shows:
  - flow
  - started time
  - app package
  - screenshot name (screenshot flow only)
- Run context does not display Run ID in the UI.

## Pipeline Outputs

Run outputs are written under `artifacts/`:
- `ssm_json_output/`
- `manual_testcases/`
- `locator_output/`
- `generated_appium_scripts/`
- `review_reports/`
- `test_execution_reports/`

## Key Components

- `live_demo.py`: Flask routes and async run orchestration
- `pipelines/`: stage composition and orchestration
- `agents/`: SSM, testcase, locator, appium generation, review
- `services/`: config, prompts, LLM client helpers
- `utils/`: shared helpers and self-healing support

## Local Run

```bash
pip install -r requirements.txt
python live_demo.py
```

Then open `http://127.0.0.1:8080/` and click **Start / Restart Services** before running a flow.

## Health and Control Endpoints

- `GET /required-services-status`
- `POST /start-required-services`
- `POST /run-demo-async`
- `GET /run-status/<run_id>`

## Notes

- VS Code task automation is routed through `scripts/task_runner.py`.
- Runtime-generated artifacts are usually not meant for source commits.
