# Live Demo Run Steps

This guide documents the current supported live demo flow.

## 1) Start Backend

```bash
python live_demo.py
```

Open `http://127.0.0.1:8080/`.

## 2) Prepare Services

Click **Start / Restart Services** in the UI.

Expected ready state:
- Flask backend
- Appium server
- Android emulator/device
- No run lock in progress

## 3) Choose Flow

Supported flow options:
- `screenshot_pipeline`
- `deterministic_realtime`

### Screenshot Pipeline
- Upload one screenshot.
- Run context shows uploaded screenshot name.
- Start run and wait for completion.

### Deterministic Realtime
- No screenshot upload required.
- Start run and wait for completion.

## 4) Review Outputs

Run outputs are written to `artifacts/`:
- `ssm_json_output/`
- `manual_testcases/`
- `locator_output/`
- `generated_appium_scripts/`
- `review_reports/`
- `test_execution_reports/`

## 5) Quick Checks

```bash
python scripts/task_runner.py check-server
python scripts/task_runner.py check-appium
python scripts/task_runner.py check-adb
```
