# Mobile Test Generator — Capstone Project

A six-step automated pipeline that turns mobile app screenshots into executed Appium test scripts with an HTML execution report.

---

## Project Structure

```
Project13_CapstoneMobileTestGenerator/
├── agents/
│   ├── core/
│   │   ├── vision_agent.py           # Abstract base for vision agents
│   │   └── testcase_agent.py         # Abstract base for test case agents
│   ├── vision_agent.py               # OpenAIVisionAgent + MockVisionAgent + factory
│   ├── locator_agent.py              # Extracts UI element locators from SSM JSON
│   ├── appium_generator_agent.py     # Generates Appium pytest scripts from locators
│   ├── reviewer_agent.py             # Reviews generated scripts for best-practice issues
│   ├── reporter_agent.py             # Runs scripts via pytest, saves timestamped HTML report
│   ├── navigation_agent.py           # Provides navigation steps per screen
│   └── __init__.py
├── models/
│   └── ssm.py                        # Single canonical Screen Semantic Model (Pydantic)
├── services/
│   ├── config.py                     # Loads .env environment variables
│   └── testcase_agent.py             # OpenAITestCaseAgent + MockTestCaseAgent + factory
├── pipelines/
│   ├── ssm_generator.py              # Step 1 – screenshots → SSM JSON
│   ├── testcase_generator.py         # Step 2 – SSM JSON → manual test cases
│   ├── reporter.py                   # Step 6 standalone – run reporter agent
│   └── run_all.py                    # End-to-end runner (all 6 steps)
├── prompts/
│   ├── vision_analysis.txt
│   ├── test_generation.txt
│   ├── locator_prompt.txt
│   └── review_prompt.txt
├── artifacts/
│   ├── input_screenshots/            # Drop screenshots here
│   ├── ssm_json_output/              # Step 1 output
│   ├── manual_testcases/             # Step 2 output
│   ├── locator_output/               # Step 3 output
│   ├── generated_appium_scripts/     # Step 4 output
│   ├── review_reports/               # Step 5 output
│   └── test_execution_reports/       # Step 6 output (timestamped HTML)
```

---

## Setup

### 1. Create a virtual environment

**Windows PowerShell:**
```powershell
cd C:\Users\priyanka.pattewar\MobileTestGeneratorPOC
.\scripts\setup_env.ps1 -PythonExe python
```

**macOS / Linux:**
```bash
cd /path/to/MobileTestGeneratorPOC
bash scripts/setup_env.sh
```

> Use Python 3.11 or 3.12. Python 3.15+ may not support all dependencies cleanly.

### 2. Configure your `.env` file

```dotenv
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_BASE=https://api.openai.com/v1   # Optional – override for custom gateways
```

To test without an API key, set both providers to `mock`:
```dotenv
VISION_AGENT_PROVIDER=mock
TESTCASE_AGENT_PROVIDER=mock
```

---

## Running the Pipeline

### Full end-to-end (recommended)

Place screenshots in `artifacts/input_screenshots/`, then run:

```powershell
python pipelines/run_all.py artifacts/input_screenshots
```

This runs all 6 steps and opens the HTML test execution report in your browser.

To skip auto-opening the browser:
```powershell
python pipelines/run_all.py artifacts/input_screenshots --no-browser
```

---

## Live Demo Mode (HTML Upload UI)

Run the interactive HTML demo server:

```powershell
python live_demo.py
```

Open http://127.0.0.1:8080 in your browser, then:

1. Upload one screenshot (`png`, `jpg`, `jpeg`, `webp`, `bmp`)
2. Start the run from the page
3. View generated outputs and open the HTML execution report directly from links

The live demo executes the enhanced pipeline (`pipelines/run_all_enhanced.py`) with your uploaded screenshot and shows pipeline logs on the page.

---

### Run individual steps

**Step 1 – Screenshots → SSM JSON**
```powershell
python pipelines/ssm_generator.py artifacts/input_screenshots artifacts/ssm_json_output --clean
```

**Step 2 – SSM JSON → Manual Test Cases**
```powershell
python pipelines/testcase_generator.py artifacts/ssm_json_output artifacts/manual_testcases --clean
```

**Step 3 – SSM JSON → Locator JSON** (via `LocatorAgent` directly)

**Step 4 – Locator JSON → Appium Scripts** (via `AppiumGeneratorAgent` directly)

**Step 5 – Appium Scripts → Review Reports** (via `ReviewerAgent` directly)

**Step 6 – Run tests and save HTML report**
```powershell
python pipelines/reporter.py
# or with custom scripts dir:
python pipelines/reporter.py artifacts/generated_appium_scripts
```

Output saved to: `artifacts/test_execution_reports/YYYY-MM-DD_HH-MM-SS/report.html`

---

## Supported Image Formats

`png`, `jpg`, `jpeg`, `webp`, `bmp`

---

## Running Tests

```powershell
python -m unittest tests.test_ssm_model
```

---

## Architecture Notes

- **All steps are loosely coupled.** Each step reads from and writes to `artifacts/` subdirectories. Any step can be re-run independently.
- **Providers are swappable.** Set `VISION_AGENT_PROVIDER` or `TESTCASE_AGENT_PROVIDER` to `openai` or `mock`.
- **Single canonical model.** All screen data uses `models/ssm.py` — no duplicate schema files.
- **Prompts are externalized.** Edit files in `prompts/` to tune LLM behaviour without touching code.
- **ReporterAgent** uses `pytest-html` to produce a self-contained HTML report saved in a timestamped directory under `artifacts/test_execution_reports/`.
- **End-to-end runner:** `pipelines/run_all.py` executes all 6 steps in sequence and opens the report at the end.
