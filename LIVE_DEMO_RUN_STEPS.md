# Live Demo Run Steps

This guide covers the current live demo flow on main branch.

## Prerequisites

- Python virtual environment exists and is activated.
- Dependencies are installed from requirements.txt.
- At least one mobile screenshot is available in png, jpg, jpeg, webp, or bmp format.
- For real-provider runs, OPENAI or LiteLLM environment values are configured.
- For offline or safe demo runs, use mock providers in .env.
- Appium server can be started locally. The UI flow attempts to auto-start Appium if it is not already running.

## 1) Activate Environment

Windows PowerShell:

```powershell
Set-Location C:\Users\ankit.kulchandani\Desktop\Apexon\Project13_Captstone
.\.venv\Scripts\Activate.ps1
```

## 2) Configure Demo Mode

Option A: Real provider mode

```dotenv
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_BASE=https://api.openai.com/v1
```

Option B: Mock provider mode

```dotenv
VISION_AGENT_PROVIDER=mock
TESTCASE_AGENT_PROVIDER=mock
```

## 3) Choose Run Path

### Path A: HTML Upload UI (recommended for walkthroughs)

```powershell
python live_demo.py
```

Open http://127.0.0.1:8080/live-demo-fixed and then:

1. Select flow type:
	- Check Flow By Uploading A Screenshot, or
	- Realtime End To End Flow Of Application.
2. If upload flow is selected, upload one screenshot.
3. Select mock or real mode.
4. Click Run Live Demo.
5. Open generated artifact links and the HTML execution report from the same page.

Default UI behavior:

- Realtime End To End Flow Of Application is selected by default.
- Screenshot upload section is visible only when Check Flow By Uploading A Screenshot is selected.

Notes:

- Uploaded files are stored under artifacts/input_screenshots/live_demo_uploads/<timestamp>/.
- UI run output includes pipeline logs and stderr block for quick troubleshooting.
- The live demo now isolates output to the current run: manual testcase artifacts are reset before Stage 2 to avoid historical carry-over.
- Result panels are intended to show only files generated for the current run.
- Artifact panels use pre-run snapshots + post-run deltas to strictly scope SSM/manual/locator/script/review files to the current uploaded screenshot run.
- Placeholder and noise files (.gitkeep, hidden files, .pyc, __pycache__) are excluded from UI artifact links.
- The old decorative stats section (Input Type / Pipeline / Output Scope) has been removed from the header.
- Deterministic realtime flow executes `tests/test_realtime_e2e_flow.py` directly from the live demo backend.
- Reports are flow-scoped:
	- Screenshot flow: `artifacts/test_execution_reports/screenshot_pipeline/<timestamp>/report.html`
	- Realtime final: `artifacts/test_execution_reports/deterministic_realtime/<timestamp>/report.html`
	- Realtime artifact pass: `artifacts/test_execution_reports/deterministic_realtime/artifact_pipeline/<timestamp>/report.html`
- Deterministic flow captures step screenshots under:
	- `artifacts/input_screenshots/live_demo_uploads/deterministic_steps_<timestamp>/`
- Captured step screenshots are surfaced in the result UI under:
	- Captured Step Screenshots
- If deterministic run has no prior seed screenshot available, backend auto-captures one via adb screencap.

### Path A.1: One-click localhost launcher (new)

Windows CMD:

```cmd
scripts\start_live_demo_localhost.cmd
```

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_live_demo_localhost.ps1
```

Both launchers start live_demo if needed and open:

- `http://localhost:8080/live-demo-fixed`

### Path B: Enhanced CLI flow

Put one or more screenshots into artifacts/input_screenshots/ and run:

```powershell
python pipelines/run_all_enhanced.py artifacts/input_screenshots
```

Without auto-opening report:

```powershell
python pipelines/run_all_enhanced.py artifacts/input_screenshots --no-browser
```

## 4) Output Locations to Show in Demo

After completion, share these outputs:

- artifacts/ssm_json_output/
- artifacts/manual_testcases/
- artifacts/locator_output/
- artifacts/generated_appium_scripts/
- artifacts/review_reports/
- artifacts/test_execution_reports/screenshot_pipeline/<timestamp>/report.html
- artifacts/test_execution_reports/deterministic_realtime/<timestamp>/report.html
- artifacts/test_execution_reports/deterministic_realtime/artifact_pipeline/<timestamp>/report.html
- artifacts/input_screenshots/live_demo_uploads/deterministic_steps_<timestamp>/

## 5) Validation Checklist

- Generated login script does not use hardcoded sleep for screen transitions.
- Login navigation flow uses actionable elements and avoids unnecessary taps on static UI.
- Report HTML exists in the latest timestamped execution folder.
- Deterministic realtime E2E flow passes with one test run:

```powershell
python -m pytest tests/test_realtime_e2e_flow.py -q
```

- Expected output:
	- `1 passed`

## 6) Deterministic Realtime Flow (Strict Step Order)

When stakeholders ask for one fixed journey in one run, execute:

- `tests/test_realtime_e2e_flow.py`

Flow covered in order:

1. Relaunch app (if open, restart app state).
2. Dismiss popup if present.
3. Reach product listing/base screen.
4. Open product detail and add item to cart.
5. Open cart.
6. Open menu.
7. Open login, enter credentials, submit login.
8. Close app.

Additional realtime evidence:

- Step screenshots are captured during runtime and should be visible in UI results.
- Generated artifact set (SSM/manual/locator/script/review/report) is built from this run only.

## 6) Troubleshooting
## 7) Troubleshooting

- If imports or commands fail, reactivate venv and run pip install -r requirements.txt.
- If real mode fails, switch to mock mode or verify OPENAI_API_KEY and API base values.
- If Appium is not reachable, start it manually and rerun:

```powershell
appium --session-override
```

- If report does not open automatically, open report.html manually from artifacts/test_execution_reports/<timestamp>/.
- If UI appears stale after updates, stop all running live_demo.py processes, start one fresh server, then hard refresh the browser.
- If old scripts/reviews appear in UI, run one fresh upload after restart; result panels should now include only delta files created/updated by that run.

## 8) Suggested Talk Track

1. Input screenshot is analyzed into SSM JSON.
2. Manual test cases are generated from SSM.
3. Multi-strategy locators are created.
4. Self-healing Appium script is generated.
5. Script review report is produced.
6. Test execution runs and creates a timestamped HTML report.

This gives an end-to-end screenshot-to-automation demonstration in one flow.
