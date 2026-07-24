# Mobile Test Generator — Capstone Project — Team Steering Document

## Purpose

This project is a fully automated six-step pipeline that converts mobile app screenshots into executed Appium test scripts with an HTML test execution report.

1. **Screenshot → SSM JSON:** Vision LLM analyses a screenshot and produces a structured Screen Semantic Model.
2. **SSM JSON → Manual Test Cases:** Language model generates human-readable test cases from the SSM.
3. **SSM JSON → Locator JSON:** LocatorAgent extracts UI element locators (resource IDs, accessibility IDs).
4. **Locator JSON → Appium Scripts:** AppiumGeneratorAgent produces pytest-style Appium test scripts.
5. **Appium Scripts → Review Reports:** ReviewerAgent statically analyses scripts for best-practice issues.
6. **Run Scripts → HTML Report:** ReporterAgent executes the scripts via pytest, saves a timestamped HTML report, and opens it in the browser.

---

## Architecture at a Glance

```
artifacts/input_screenshots/
        │
        ▼  Step 1 — ssm_generator.py (Vision LLM)
artifacts/ssm_json_output/              ← SSM JSON per screen
        │
        ▼  Step 2 — testcase_generator.py (Language LLM)
artifacts/manual_testcases/             ← plain-text test cases per screen
        │
        ▼  Step 3 — locator_agent.py
artifacts/locator_output/               ← locator JSON per screen
        │
        ▼  Step 4 — appium_generator_agent.py
artifacts/generated_appium_scripts/     ← pytest Appium .py per screen
        │
        ▼  Step 5 — reviewer_agent.py
artifacts/review_reports/               ← Markdown review per script
        │
        ▼  Step 6 — reporter_agent.py
artifacts/test_execution_reports/
    └── YYYY-MM-DD_HH-MM-SS/
        └── report.html             ← HTML test execution report (auto-opened)
```

All steps are **loosely coupled** — each reads from and writes to `artifacts/` subdirectories and can be re-run independently.

---

## Folder Structure

```
Project13_CapstoneMobileTestGenerator/
├── agents/
│   ├── core/
│   │   ├── vision_agent.py           # Abstract base: VisionAgent
│   │   └── testcase_agent.py         # Abstract base: TestCaseAgent
│   ├── vision_agent.py               # Concrete: OpenAIVisionAgent, MockVisionAgent, factory
│   ├── locator_agent.py              # Step 3: extracts locators from SSM JSON
│   ├── appium_generator_agent.py     # Step 4: generates Appium pytest scripts
│   ├── reviewer_agent.py             # Step 5: static analysis of generated scripts
│   ├── reporter_agent.py             # Step 6: runs tests, saves timestamped HTML report
│   ├── navigation_agent.py           # Provides navigation steps per screen
│   └── __init__.py
├── models/
│   └── ssm.py                        # Single Pydantic schema for ScreenSemanticModel
├── services/
│   ├── config.py                     # Loads .env into the environment
│   └── testcase_agent.py             # Concrete: OpenAITestCaseAgent, MockTestCaseAgent
├── pipelines/
│   ├── ssm_generator.py              # Step 1 entry point
│   ├── testcase_generator.py         # Step 2 entry point
│   ├── reporter.py                   # Step 6 standalone entry point
│   └── run_all.py                    # End-to-end runner (all 6 steps)
├── prompts/
│   ├── vision_analysis.txt           # LLM prompt for Step 1
│   ├── test_generation.txt           # LLM prompt for Step 2
│   ├── locator_prompt.txt            # Prompt for Step 3
│   └── review_prompt.txt             # Prompt for Step 5
├── artifacts/
│   ├── input_screenshots/            # DROP SCREENSHOTS HERE
│   ├── ssm_json_output/              # Step 1 writes here
│   ├── manual_testcases/             # Step 2 writes here
│   ├── locator_output/               # Step 3 writes here
│   ├── generated_appium_scripts/     # Step 4 writes here
│   ├── review_reports/               # Step 5 writes here
│   └── test_execution_reports/       # Step 6 writes here (timestamped per run)
├── demo_mobile_apps/
│   └── <app>.apk                     # Android APK for emulator testing
├── tests/                            # Unit tests
├── scripts/
│   ├── setup_env.ps1                 # Windows setup
│   └── setup_env.sh                  # macOS/Linux setup
├── .env                              # API keys — NEVER commit
├── requirements.txt
└── README.md
```
├── artifacts/
│   ├── input_screenshots/          # DROP SCREENSHOTS HERE before running Step 1
│   ├── ssm_json_output/            # Step 1 writes here (auto-created)
│   └── manual_testcases/           # Step 2 writes here (auto-created)
├── tests/
│   └── test_ssm_model.py           # Unit tests — run before committing changes
├── scripts/
│   ├── setup_env.ps1               # Windows: creates .venv and installs deps
│   └── setup_env.sh                # macOS/Linux: creates .venv and installs deps
├── .venv/                          # Active virtual environment (Python 3.11)
├── .env                            # API keys — NEVER commit this file
├── requirements.txt                # Runtime dependencies
└── README.md                       # Quick-start guide
```

---

## How to Run

### Prerequisites
- Python 3.11 or 3.12 (3.14+ not recommended — see `requirements.txt`)
- An OpenAI-compatible API key OR use `mock` mode for offline testing

### 1 — Set up the environment (first time only)

**Windows:**
```powershell
.\scripts\setup_env.ps1 -PythonExe python
```
**macOS / Linux:**
```bash
bash scripts/setup_env.sh
```

### 2 — Configure `.env`

Copy `.env.example` (or create `.env`) with:
```dotenv
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_BASE=https://api.openai.com/v1   # override for internal gateways
```

For offline / no-key testing:
```dotenv
VISION_AGENT_PROVIDER=mock
TESTCASE_AGENT_PROVIDER=mock
```

### 3 — Place screenshots

Drop your `.png` / `.jpg` / `.jpeg` / `.webp` / `.bmp` screenshots into:
```
artifacts/input_screenshots/
```

### 4 — Run Step 1 (screenshots → SSM JSON)

```powershell
python pipelines/ssm_generator.py artifacts/input_screenshots artifacts/ssm_json_output --clean
```

### 5 — Run Step 2 (SSM JSON → manual test cases)

```powershell
python pipelines/testcase_generator.py artifacts/ssm_json_output artifacts/manual_testcases --clean
```

### Full end-to-end (single command)

```powershell
python pipelines/ssm_generator.py artifacts/input_screenshots artifacts/ssm_json_output --clean ; python pipelines/testcase_generator.py artifacts/ssm_json_output artifacts/manual_testcases --clean
```

---

## How to Change the LLM Behaviour

All LLM instructions are externalised as plain text files. **No code changes needed.**

| File | Controls |
|---|---|
| `prompts/vision_analysis.txt` | How the vision model describes screens and elements |
| `prompts/test_generation.txt` | How the language model formats and writes test cases |

Edit either file, re-run the corresponding step, and compare outputs.

---

## How to Switch Providers

Set the environment variables before running:

| Variable | Values |
|---|---|
| `VISION_AGENT_PROVIDER` | `openai` \| `mock` |
| `TESTCASE_AGENT_PROVIDER` | `openai` \| `mock` |
| `OPENAI_MODEL` | Any chat-completion model name (e.g. `gpt-4o`, `gpt-4o-mini`) |
| `OPENAI_API_BASE` | Override the base URL for internal API gateways |

Adding a new provider (e.g. Azure, Anthropic) requires only:
1. Create a new class that extends `agents/vision_agent.py::VisionAgent` or `agents/testcase_agent.py::TestCaseAgent`
2. Register it in the `create_vision_agent()` / `create_testcase_agent()` factory function

---

## Data Model

The **Screen Semantic Model (SSM)** is the shared contract between Step 1 and Step 2.  
Schema is defined in `models/ssm.py`.

```json
{
  "screen_name": "Login",
  "screen_purpose": "Authenticate the user",
  "elements": [
    { "label": "Username", "type": "textfield", "actions": ["enter_text"] },
    { "label": "Password", "type": "textfield", "actions": ["enter_text"] },
    { "label": "Login",    "type": "button",    "actions": ["tap"] }
  ]
}
```

---

## Running Tests

```powershell
python -m unittest tests.test_ssm_model
```

Run this before merging any changes that touch `models/ssm.py` or `agents/vision_agent.py`.

---

## What is Implemented vs Pending

| Capability | Status |
|---|---|
| SSM generation (Step 1) | ✅ Done |
| Manual test case generation (Step 2) | ✅ Done |
| Locator agent (Step 3) | ✅ Done |
| Appium script generation (Step 4) | ✅ Done |
| Reviewer agent (Step 5) | ✅ Done |
| Reporter agent — HTML execution report (Step 6) | ✅ Done |
| End-to-end runner (`run_all.py`) | ✅ Done |
| CI/CD integration | ❌ Not started |
| Multi-app / multi-platform support | ❌ Not started |

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| Single `models/ssm.py` schema | Eliminated 4 duplicate model files; one source of truth |
| Abstract base classes in `agents/` | Allows new LLM providers without changing pipeline code |
| Prompts as `.txt` files | QA / non-developer team members can tune output without touching Python |
| `--clean` flag on runners | Explicitly clears output before a run; safe for reruns |
| `mock` provider mode | Full pipeline runs offline for demos or CI without an API key |
| `.venv` (Python 3.11) as active env | Stable; all dependencies install cleanly; tested end to end |

---

## Contact / Ownership

Update this section with team contacts, Jira board links, and repo details before sharing.
