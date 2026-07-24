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

Open http://127.0.0.1:8080 and then:

1. Upload one screenshot.
2. Select mock or real mode.
3. Click Run Live Demo.
4. Open generated artifact links and the HTML execution report from the same page.

Notes:

- Uploaded files are stored under artifacts/input_screenshots/live_demo_uploads/<timestamp>/.
- UI run output includes pipeline logs and stderr block for quick troubleshooting.

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
- artifacts/test_execution_reports/<timestamp>/report.html

## 5) Validation Checklist

- Generated login script does not use hardcoded sleep for screen transitions.
- Login navigation flow uses actionable elements and avoids unnecessary taps on static UI.
- Report HTML exists in the latest timestamped execution folder.

## 6) Troubleshooting

- If imports or commands fail, reactivate venv and run pip install -r requirements.txt.
- If real mode fails, switch to mock mode or verify OPENAI_API_KEY and API base values.
- If Appium is not reachable, start it manually and rerun:

```powershell
appium --session-override
```

- If report does not open automatically, open report.html manually from artifacts/test_execution_reports/<timestamp>/.

## 7) Suggested Talk Track

1. Input screenshot is analyzed into SSM JSON.
2. Manual test cases are generated from SSM.
3. Multi-strategy locators are created.
4. Self-healing Appium script is generated.
5. Script review report is produced.
6. Test execution runs and creates a timestamped HTML report.

This gives an end-to-end screenshot-to-automation demonstration in one flow.
