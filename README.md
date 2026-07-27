# Mobile Test Generator - Capstone Project

An end-to-end automation pipeline that converts mobile app screenshots into:

- structured SSM JSON,
- manual test cases,
- multi-strategy locator files,
- generated Appium scripts,
- review reports, and
- executed test HTML reports.

## Project Structure

```text
Project13_Captstone/
|-- agents/                            # AI and generation agents (vision, locator, appium, reviewer)
|-- artifacts/                         # Runtime outputs (kept via .gitkeep, generated at run time)
|   |-- input_screenshots/
|   |-- ssm_json_output/
|   |-- manual_testcases/
|   |-- locator_output/
|   |-- generated_appium_scripts/
|   |-- review_reports/
|   |-- test_execution_reports/
|-- config/                            # App configuration and environment-backed settings
|-- models/                            # Domain models (for example Screen Semantic Model)
|-- pipelines/                         # Stage runners and orchestration entry points
|   |-- run_all.py
|   |-- run_all_enhanced.py
|   |-- pipeline_composer.py
|   |-- stage_runners.py
|-- prompts/                           # Prompt templates used by agents
|-- services/                          # Shared services (config, prompt manager, llm client)
|-- tests/                             # Unit/integration tests and snapshots
|-- utils/                             # Self-healing and shared Appium session utilities
|-- web/
|   |-- templates/live_demo.html       # Live demo UI
|-- live_demo.py                       # Flask upload UI + enhanced pipeline execution
|-- README.md
|-- LIVE_DEMO_RUN_STEPS.md
|-- CHANGES_FROM_INITIAL_PRIYANKA_BASELINE.md
```

Important artifact folders:

- artifacts/input_screenshots/
- artifacts/ssm_json_output/
- artifacts/manual_testcases/
- artifacts/locator_output/
- artifacts/generated_appium_scripts/
- artifacts/review_reports/
- artifacts/test_execution_reports/

## Architecture Overview

The platform follows a staged artifact-driven architecture. Each stage writes outputs to an artifact folder and the next stage consumes those artifacts.

```mermaid
flowchart LR
		A[Uploaded Screenshot or Input Folder] --> B[Stage 1: Vision Analysis]
		B --> C[SSM JSON]
		C --> D[Stage 2: Testcase Generation]
		D --> E[Manual Testcases]
		C --> F[Stage 3: Locator Generation]
		E --> F
		F --> G[Locator JSON]
		G --> H[Stage 4: Appium Script Generation]
		H --> I[Generated Appium Scripts]
		I --> J[Stage 5: Review Agent]
		J --> K[Review Reports]
		I --> L[Stage 6: Reporter Agent]
		L --> M[Timestamped HTML Execution Report]
```

## System Architecture Diagram

```mermaid
flowchart TB
	subgraph UI[Interface Layer]
		LD[Live Demo UI - live_demo.py]
		CLI[CLI Entrypoints - run_all.py / run_all_enhanced.py]
	end

	subgraph ORCH[Orchestration Layer]
		PC[pipeline_composer.py]
		SR[stage_runners.py]
	end

	subgraph CORE[Agent Layer]
		VA[Vision Agent]
		TA[Testcase Agent]
		LA[Locator Agent]
		AA[Self-Healing Appium Generator]
		RA[Reviewer Agent]
		RPA[Reporter Agent]
	end

	subgraph DATA[Artifact Layer]
		IN[input_screenshots]
		SSM[ssm_json_output]
		MTC[manual_testcases]
		LOC[locator_output]
		SCR[generated_appium_scripts]
		REV[review_reports]
		REP[test_execution_reports]
	end

	LD --> PC
	CLI --> PC
	PC --> SR
	SR --> VA --> SSM
	SR --> TA --> MTC
	SR --> LA --> LOC
	SR --> AA --> SCR
	SR --> RA --> REV
	SR --> RPA --> REP
	IN --> VA
	SSM --> TA
	SSM --> LA
	MTC --> LA
	LOC --> AA
	SCR --> RA
	SCR --> RPA
```

## Component Responsibilities

- `live_demo.py`
	- Hosts Flask UI for screenshot upload and run trigger.
	- Starts Appium if needed.
	- Runs enhanced pipeline and exposes per-run artifact links.
	- Uses strict run-delta filtering so results only show files produced by the current upload.

- `pipelines/pipeline_composer.py`
	- Central orchestrator for the 6-stage flow.
	- Handles stage ordering and directory reset behavior for deterministic runs.

- `pipelines/stage_runners.py`
	- Implements reusable stage classes (Vision, Testcase, Locator, Appium, Review, Report).
	- Shared by standard and enhanced pipeline entrypoints.

- `agents/self_healing_appium_generator.py`
	- Generates robust Appium scripts with multi-strategy locator healing.
	- Startup stabilization uses explicit wait behavior (no hardcoded sleep in generated flow).

- `agents/reviewer_agent.py`
	- Reviews generated scripts for common anti-patterns.
	- Produces markdown reports in `artifacts/review_reports/`.

## Setup

### 1) Create and activate virtual environment

Windows PowerShell:

```powershell
Set-Location C:\Users\ankit.kulchandani\Desktop\Apexon\Project13_Captstone
.\scripts\setup_env.ps1 -PythonExe python
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
cd /path/to/Project13_Captstone
bash scripts/setup_env.sh
source .venv/bin/activate
```

Recommended Python version: 3.11 or 3.12.

### 2) Configure environment variables

Use .env for provider configuration.

Real-provider example:

```dotenv
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_BASE=https://api.openai.com/v1
```

Mock-provider example:

```dotenv
VISION_AGENT_PROVIDER=mock
TESTCASE_AGENT_PROVIDER=mock
```

## Running the Pipeline

### Recommended: Enhanced all-steps run

```powershell
python pipelines/run_all_enhanced.py artifacts/input_screenshots
```

Without auto-opening report:

```powershell
python pipelines/run_all_enhanced.py artifacts/input_screenshots --no-browser
```

### Standard all-steps run

```powershell
python pipelines/run_all.py artifacts/input_screenshots
```

Execution modes:

- `run_all.py`: baseline pipeline behavior.
- `run_all_enhanced.py`: preferred mode with latest orchestration/stability improvements.
- `live_demo.py`: upload-driven walkthrough mode for stakeholders.

## Live Demo Mode (HTML Upload UI)

Run the local demo UI:

```powershell
python live_demo.py
```

Open http://127.0.0.1:8080 or the fixed launcher URL http://127.0.0.1:8080/live-demo-fixed and:

1. Select flow type:
	- Check Flow By Uploading A Screenshot, or
	- Realtime End To End Flow Of Application (strict sequence, no upload required).
2. Select mock or real mode.
3. Run the demo.
4. Review generated artifacts and open report links from the page.

Live UI defaults:

- Realtime End To End Flow Of Application is selected by default on first page load.
- Screenshot upload section is shown only when Check Flow By Uploading A Screenshot is selected.

Current live demo behavior:

- stores uploads under artifacts/input_screenshots/live_demo_uploads/<timestamp>/,
- attempts to auto-start Appium when needed,
- runs the enhanced pipeline,
- resets manual testcase artifacts before Stage 2 so downstream generation uses only the current upload run,
- shows run-scoped artifacts in the results (no historical testcase carry-over),
- computes artifact lists using pre-run folder snapshots plus post-run deltas, so scripts/reviews/locators shown in UI are only from the current uploaded screenshot run,
- hides non-user artifacts such as .gitkeep, hidden files, .pyc, and __pycache__ from result panels,
- displays pipeline logs and stderr in the UI,
- labels stderr as diagnostics stream (warnings/tool output may appear even when tests pass),
- uses a cleaner header layout (removed non-functional stats section),
- supports compact filename display in result sections.

Localhost launcher scripts (new):

- PowerShell one-click launcher: scripts/start_live_demo_localhost.ps1

These scripts start the Flask demo server (if needed) and open:

- http://localhost:8080/live-demo-fixed

Live demo now supports both execution paths in one UI:

- `screenshot_pipeline`: Check Flow By Uploading A Screenshot (upload one screenshot and run the full six-stage pipeline).
- `deterministic_realtime`: run strict emulator flow (`tests/test_realtime_e2e_flow.py`) and publish an HTML report from that run.

Report output is flow-scoped:

- Screenshot flow report: artifacts/test_execution_reports/screenshot_pipeline/<timestamp>/report.html
- Realtime final report: artifacts/test_execution_reports/deterministic_realtime/<timestamp>/report.html
- Realtime artifact pipeline report: artifacts/test_execution_reports/deterministic_realtime/artifact_pipeline/<timestamp>/report.html

Deterministic run execution contract:

- One live-demo trigger performs one realtime Appium/pytest run.
- Realtime artifact pipeline reporting does not start a second mobile test execution.

## Deterministic Realtime E2E Flow (Latest)

To support a strict single-pass emulator journey (without repeated login typing and with explicit ordered actions), a dedicated deterministic test was added:

- `tests/test_realtime_e2e_flow.py`

Implemented sequence:

1. Open app and relaunch if already open.
2. Dismiss startup popup if present.
3. Open product listing/base page.
4. Open product details and add product to cart.
5. Open cart.
6. Open menu.
7. Open login, enter username/password, submit login.
8. Close application.

Latest deterministic screenshot behavior:

- Realtime flow captures step screenshots during execution (business pages only) and stores them under:
	- artifacts/input_screenshots/live_demo_uploads/deterministic_steps_<timestamp>/
- Captured pages are restricted to:
	- Product Listing
	- Product Details
	- Cart
	- Menu
	- Login
- These captured step screenshots are shown in the live demo result page under:
	- Captured Step Screenshots
- Capture attempts are page-anchor validated to avoid blank/black pre-launch or transitional frames.
- If no pre-existing input screenshot is available for deterministic artifact generation,
	the backend now falls back to adb frame capture and creates a seed PNG automatically.

Run command:

```powershell
python -m pytest tests/test_realtime_e2e_flow.py -q
```

Latest validation result:

- `1 passed` on local emulator run.

## Running Individual Steps

Step 1 - Screenshots to SSM JSON:

```powershell
python pipelines/ssm_generator.py artifacts/input_screenshots artifacts/ssm_json_output --clean
```

Step 2 - SSM JSON to manual test cases:

```powershell
python pipelines/testcase_generator.py artifacts/ssm_json_output artifacts/manual_testcases --clean
```

Step 3 - SSM JSON to locator JSON: via LocatorAgent pipeline stage.

Step 4 - Locator JSON to Appium scripts: via AppiumGeneratorAgent pipeline stage.

Step 5 - Appium scripts to review reports: via ReviewerAgent pipeline stage.

Step 6 - Run tests and create HTML report:

```powershell
python pipelines/reporter.py
python pipelines/reporter.py artifacts/generated_appium_scripts
```

Report output format:

- artifacts/test_execution_reports/YYYY-MM-DD_HH-MM-SS/report.html

## Current Notable Updates on Main

- Live demo run scoping and UI readability were improved in `live_demo.py`, `pipelines/pipeline_composer.py`, and `web/templates/live_demo.html`.
- The live demo no longer reuses historical manual testcase files during a new run.
- Reporter output now supports report scopes so screenshot and realtime report folders stay separated.
- Deterministic realtime flow now generates artifact pipeline inputs from captured step screenshots.
- A fixed launcher page is available at `/live-demo-fixed` and includes startup prerequisite/status visibility.
- The old decorative "Input Type / Pipeline / Output Scope" section was removed from the page.
- Artifact panels now use strict per-run delta filtering, so old generated scripts and review reports are not shown for new uploads.
- Self-healing script startup stabilization removed hardcoded sleep in generator output and relies on explicit wait logic.
- Stale-element retry in generated self-healing scripts now re-waits on target locators instead of fixed sleep.
- Deterministic realtime report logging now includes verbose pytest CLI output and explicit INFO milestones.

## Supported Image Formats

- png
- jpg
- jpeg
- webp
- bmp

## Running Tests

```powershell
python -m unittest tests.test_ssm_model
```

## Architecture Notes

- Stages are loosely coupled and communicate through artifact contracts.
- Providers are swappable between openai and mock via environment settings.
- Prompts are externalized in `prompts/` and can be tuned without code changes.
- Reporter output is timestamped for traceable test execution history.
- Live demo output lists are run-scoped and filtered for user-facing artifacts only.
