# Changes From Initial Priyanka Baseline

Baseline used for comparison:
- First full synced project commit: e076648 ("Sync capstone code from local branch")
- Current state includes updates up to: 301ce07

## Latest Documentation Sync Addendum (Jul 2026)

- Task automation migration completed for legacy PowerShell labels:
  - `.vscode/tasks.json` migrated legacy `powershell` task entries to Python-based dispatch.
  - Added `scripts/task_runner.py` as centralized portable task executor.
  - Added migration/support utilities:
    - `scripts/_migrate_powershell_tasks_to_runner.py`
    - `scripts/legacy_powershell_tasks.json`
    - `scripts/_dump_ps_tasks.py`
    - `scripts/_extract_legacy_ps_tasks.py`

- Live demo UI contract updated:
  - Run Context now shows screenshot name for screenshot flow.
  - Run ID was removed from Run Context UI contract.
  - UI contract test updated in `tests/test_live_demo_ui_state_contract.py` to assert `ctxScreenshotWrap` and `ctxScreenshotName`.

- Live demo result summary simplification:
  - removed frontend rows for Telemetry, App Profile Preset, Artifact lifecycle, and self-healing quality signal details.
  - backend telemetry/lifecycle/index endpoints remain intact for non-UI operational use.

- Locator and login-generation regressions addressed:
  - locator strategy preference restored to resource_id-first in `agents/locator_agent.py`.
  - login generation path hardened to deterministic minimum steps in `agents/self_healing_appium_generator.py`.

## 1) What We Changed Since Initial Baseline

- CI branch coverage expanded:
  - Added Ankit_Kulchandani branch to CI triggers for push and pull_request.
  - File: .github/workflows/ci.yml

- Unit-test scope corrected:
  - Excluded E2E tests from unit-test stage using --ignore=tests/e2e.
  - File: .github/workflows/ci.yml

- GitHub Actions upgraded:
  - Upgraded checkout/setup-python/upload/download artifact actions from v4 to v5.
  - Upgraded setup-node from v4 to v5.
  - File: .github/workflows/ci.yml

- Android CI runtime upgraded and stabilized:
  - Node version for Appium job changed from 20 to 24.
  - Added pytest-rerunfailures dependency in CI.
  - Added Android emulator stabilization commands (disable animations, unlock, launcher settle wait).
  - File: .github/workflows/ci.yml

- Appium driver install flow hardened:
  - Appium driver install made tolerant with verification/logging improvements.
  - File: .github/workflows/ci.yml

- E2E test source standardized:
  - CI switched from generated script path to committed test path: tests/e2e/test_login_screen.py.
  - File: .github/workflows/ci.yml

- Android login E2E robustness added:
  - New dedicated and resilient login test added under tests/e2e.
  - Driver session creation now retries up to 3 attempts.
  - Added fallback locator strategy flow and popup handling for flaky UI states.
  - Added better failure screenshots and deterministic waits.
  - File: tests/e2e/test_login_screen.py

- Test artifact/reporting significantly improved:
  - Per-run report directory creation under artifacts/test_execution_reports.
  - Added JUnit XML output and richer Appium log/screenshot collection.
  - Added generated report.html index linking all report files.
  - Added separate report-generation job that creates a reports portal with a View Reports button.
  - File: .github/workflows/ci.yml

- LiteLLM/LangChain CI resilience improved:
  - Added explicit LiteLLM API key detection step.
  - Added fallback mock environment path when key is missing.
  - Gateway test now skips gracefully if key is not present.
  - LangChain integration now runs in key-aware mode and prints traceback on failure.
  - File: .github/workflows/ci.yml

- Repository artifact hygiene improved:
  - Removed committed runtime-generated artifacts from artifacts/ directories.
  - Added .gitkeep placeholders to keep required folders present without polluting git history.
  - Files: artifacts/*, .gitignore

- Ignore rules expanded for runtime cleanliness:
  - Added ignores for test/cache/log/runtime artifact outputs.
  - Preserved .gitkeep exceptions for expected artifact directories.
  - File: .gitignore

- Naming consistency standards documented:
  - Added naming convention section for modules, classes, functions, constants, and generated artifact naming.
  - File: CONTRIBUTING.md

- Artifact naming implementation standardized in code:
  - Added to_artifact_token utility to generate safe snake_case artifact tokens.
  - Applied tokenized naming for timestamped JSON/TXT artifacts.
  - Files: pipelines/orchestration_helpers.py, pipelines/testcase_generator.py

- Locator generation determinism and matching improved:
  - Sorted SSM file iteration for deterministic processing.
  - Added slug/token fallback matching for manual testcase files.
  - Standardized locator output file names using slugified screen token.
  - File: agents/multi_strategy_locator_agent.py

- Live demo capability called out and aligned with enhanced pipeline:
  - README documents a live demo mode for quick screenshot upload/run experience.
  - Enhanced execution path is implemented via pipelines/run_all_enhanced.py using shared stage composition.
  - Files: README.md, pipelines/run_all_enhanced.py, pipelines/pipeline_composer.py, pipelines/stage_runners.py

- Live demo run isolation and UI cleanup:
  - Pipeline now resets manual testcase artifacts before Stage 2, preventing reuse of historical testcase files in a new run.
  - Live demo artifact listing is scoped to the current run window and upload context.
  - Live demo UI readability was improved and overlapping blocks were reduced with layout hardening.
  - Removed non-functional decorative stats section (Input Type / Pipeline / Output Scope) from live demo page.
  - Files: pipelines/pipeline_composer.py, live_demo.py, web/templates/live_demo.html

- Live demo artifact panel hardening and strict run-delta scoping:
  - Artifact panel filtering now excludes .gitkeep and runtime noise files (hidden files, .pyc, __pycache__) from generated links.
  - Live demo artifact lists now use pre-run folder snapshots with post-run delta comparison, so generated scripts/review reports/locator outputs shown in UI are limited to the current uploaded screenshot run.
  - Files: live_demo.py

- Self-healing generated startup flow stability update:
  - Removed hardcoded sleep in generated startup stabilization path and replaced with explicit wait behavior.
  - This removes reviewer findings about hardcoded sleep in generated scripts like product detail flows.
  - Files: agents/self_healing_appium_generator.py

- Login script review issues fixed in generated flow:
  - Removed hardcoded sleep usage from generated login script flow.
  - Replaced unnecessary static-element tap with presence verification and navigation-safe actions.
  - Committed in main as: e908739.
  - File: artifacts/generated_appium_scripts/test_login_screen.py

- Realtime deterministic flow made truly single-run (latest):
  - Deterministic live demo run now executes Appium/pytest once per user trigger.
  - Artifact pipeline report generation no longer launches a second mobile test execution.
  - Post-completion artifact publishing now uses explicit report-only execution and does not relaunch app pages before UI result redirect.
  - Implemented with scoped reporter skip flag in live demo deterministic artifact pass.
  - Files: live_demo.py, agents/reporter_agent.py

- Realtime screenshot policy narrowed to business pages only (latest):
  - Deterministic flow now captures screenshots only for:
    - Product Listing page
    - Product Details page
    - Cart page
    - Menu page
    - Login page
  - Removed pre-launch, transitional, and close-app screenshot points.
  - Added page-anchor validation before capture to avoid blank/black screenshots.
  - Files: tests/test_realtime_e2e_flow.py

- Live demo self-healing visibility + reliability hardening (latest):
  - Added run-result Self-Healing Output panel and badges in UI.
  - Added stricter self-healing script detection heuristics in backend.
  - Added scoped env override handling to prevent cross-run provider leakage.
  - Added deterministic realtime pytest timeout handling.
  - Added async run inactivity watchdog behavior in run-state access.
  - Replaced user-facing traceback dumps with concise failure messages while keeping server-side traceback logging.
  - Refactored duplicated artifact panel template blocks into a Jinja macro (no behavior change).
  - Files: live_demo.py, web/templates/live_demo.html

- Validation and branch sync (latest):
  - `py_compile` and template parse checks passed after hardening.
  - Screenshot upload and deterministic realtime demo flows completed through live demo UI.
  - Realtime deterministic test passed via `pytest tests/test_realtime_e2e_flow.py -q -s`.
  - Latest doc + hardening updates pushed to `main`.

- Live demo diagnostics and logging clarity improved (latest):
  - UI now labels stderr as diagnostics stream and clarifies it may include warnings/tool messages.
  - Deterministic run no longer shows a synthetic stderr section when there is no real stderr output.
  - Deterministic pytest invocation upgraded to verbose + CLI logging capture for richer HTML report context.
  - Files: web/templates/live_demo.html, live_demo.py

- Live demo mode/preview UX simplified (latest):
  - Removed Mode selector from page UI and standardized form submission behavior.
  - Screenshot flow now shows uploaded screenshot preview and does not show live emulator stream.
  - Deterministic realtime flow now shows live emulator stream while run is active.
  - Files: web/templates/live_demo.html

- Self-healing generated script quality hardened (latest):
  - Removed hardcoded retry sleep for stale-element taps in generator template.
  - Replaced with explicit wait re-resolution before re-tap.
  - Enabled INFO logger level in generated scripts for visible runtime logs.
  - Files: agents/self_healing_appium_generator.py, artifacts/generated_appium_scripts/*.py

- Reviewer output updated after fixes (latest):
  - Re-ran reviewer agent after generated-script stabilization update.
  - Prior hardcoded sleep finding for cart screen review now resolved (issues detected: 0).
  - File: artifacts/review_reports/test_05_step_5_cart_opened_screen_review.md

- Live demo report accessibility and run-reset UX fixes (latest):
  - Artifact route serving now resolves from artifacts root and supports both URL styles:
    - `/artifacts/artifacts/...` (legacy)
    - `/artifacts/...` (normalized)
  - Flow switch actions now refresh to a clean page state (`/?flow_type=...`) so each run starts without stale previous-run result panels.
  - Direct `healing_repository.db` link exposure was removed from the live demo result panel to avoid non-actionable 404s.
  - Files: live_demo.py, web/templates/live_demo.html

- Cross-app profile hardening + stale-result cleanup (latest):
  - Added config-backed app profile flags:
    - `is_reference_demo_profile`
    - `app_specific_locator_hints_enabled`
    - `app_specific_navigation_enabled`
  - Added env toggles in `.env.example` for app-specific heuristics:
    - `ENABLE_APP_SPECIFIC_LOCATOR_HINTS`
    - `ENABLE_APP_SPECIFIC_NAVIGATION`
  - Locator and navigation logic now gates SauceLabs-style assumptions behind profile-aware config checks.
  - Generated Appium capabilities now use env-provided `APP_PACKAGE` and `APP_ACTIVITY` instead of unconditional hardcoded values.
  - Screenshot pipeline now disables self-healing generator for non-reference app profiles to avoid app-specific script bias.
  - Live demo UI now removes old result sections immediately on flow change or run submit to eliminate interim stale report/screenshot visibility.
  - Files: config/app_config.py, .env.example, agents/locator_agent.py, agents/multi_strategy_locator_agent.py, agents/navigation_agent.py, agents/appium_generator_agent.py, live_demo.py, web/templates/live_demo.html

- Reliability/productization completion pack (latest):
  - Added profile preset model for app types (`auto/generic/ecommerce/banking/social`) and preset-aware locator/navigation bias.
  - Added strict config validation gating for selected mode/flow and dedicated endpoint:
    - `GET /config-validation`
  - Added artifact governance lifecycle:
    - age-based expiration via `ARTIFACT_RETENTION_DAYS`
    - latest index files: `artifacts/indexes/latest_per_flow.json`, `artifacts/indexes/latest_per_run.json`
  - Added structured run telemetry with stage durations:
    - `GET /telemetry/latest`
    - `GET /telemetry-dashboard`
  - Added dynamic journey output for deterministic flow from captured step screenshots.
  - Added self-healing quality metrics surface:
    - healing success rate
    - fallback depth estimate
    - recurring failed locators
    - top unstable elements
  - Added reusable retry/backoff policy utility and integrated runtime usage.
  - Added flow-specific CI smoke jobs:
    - screenshot flow smoke
    - realtime flow smoke
  - Added governance and smoke tests:
    - `tests/test_live_demo_flow_smoke_contract.py`
    - `tests/test_live_demo_governance_contract.py`
  - Added production readiness checklist:
    - `PRODUCTION_READINESS_CHECKLIST.md`
  - Added live demo preflight readiness card in UI (manual + auto check on page load).
  - Files: .github/workflows/ci.yml, config/app_config.py, live_demo.py, web/templates/live_demo.html, agents/navigation_agent.py, agents/locator_agent.py, agents/multi_strategy_locator_agent.py, utils/retry_policy.py, services/artifact_lifecycle.py, services/run_telemetry.py, tests/test_live_demo_flow_smoke_contract.py, tests/test_live_demo_governance_contract.py, PRODUCTION_READINESS_CHECKLIST.md, README.md, LIVE_DEMO_RUN_STEPS.md

## 2) New Things Implemented

- New Android-focused stable E2E login test framework in:
  - tests/e2e/test_login_screen.py

- New consolidated report index generation in Appium job:
  - report.html inside each run artifact folder.

- New report portal job:
  - report-generation job builds reports_portal/index.html with clickable links to generated outputs.

- New LiteLLM key-aware CI behavior:
  - Automatic mode switch between real gateway validation and mock fallback mode.

- New artifact tokenization helper utility:
  - to_artifact_token in pipelines/orchestration_helpers.py

- New live-demo style execution path:
  - Enhanced end-to-end pipeline runner with LangChain, self-healing, token tracking, and cache-aware execution flags.
  - Shared pipeline composition/stage runners make demo runs and production-style runs consistent.
  - Files: pipelines/run_all_enhanced.py, pipelines/pipeline_composer.py, pipelines/stage_runners.py

- Updated generated login Appium test implementation:
  - Uses self-healing locator strategy wrappers and startup stabilization flow.
  - Ensures login path validation without flaky fixed sleeps.
  - File: artifacts/generated_appium_scripts/test_login_screen.py

- Shared Appium session lifecycle and startup optimization updates (latest):
  - Added shared session state helper to identify newly created vs reused driver sessions.
  - Generator setup now applies startup stabilization on reused sessions while avoiding unnecessary full reinitialization work.
  - Added stale-element retry for tap actions in generated scripts to reduce transient emulator failures.
  - Files: utils/shared_appium_session.py, agents/self_healing_appium_generator.py

- Login de-duplication and flow hardening updates (latest):
  - Removed duplicate login typing/tap behavior from generated login flows.
  - Login minimum steps now run in deterministic sequence and tolerate already-logged-in state.
  - File: agents/self_healing_appium_generator.py

- Deterministic realtime E2E run added (latest):
  - Added dedicated one-pass emulator test implementing strict business sequence:
    open/relaunch app -> popup handling -> product listing -> product detail/add to cart -> cart -> menu -> login -> close app.
  - File: tests/test_realtime_e2e_flow.py
  - Latest local result: `1 passed`.

- Deterministic realtime logging and diagnostics refinements (latest):
  - Test logs now include explicit INFO milestones for each captured business page.
  - HTML report content for deterministic runs is now richer and easier to troubleshoot.
  - Files: tests/test_realtime_e2e_flow.py, live_demo.py

- Reporter/pipeline report execution control refinement (latest):
  - Added explicit report execution control flags through reporter, stage runner, and pipeline composer.
  - Deterministic artifact pass now uses report-only mode via explicit function parameters rather than environment-only signaling.
  - Files: agents/reporter_agent.py, pipelines/stage_runners.py, pipelines/pipeline_composer.py, live_demo.py

## 3) How These Changes Help Us

- Higher CI reliability:
  - Unit pipeline no longer fails because of Appium E2E dependencies.
  - Android pipeline is less flaky due to emulator and retry hardening.

- Better debuggability:
  - Richer artifacts (HTML, JUnit XML, logs, screenshot copies, appium tail logs) speed up root-cause analysis.
  - LangChain traceback output makes integration failures actionable.

- Better CI compatibility and future readiness:
  - Actions/runtime upgrades reduce deprecation risk and warning noise.

- Cleaner repository and easier reviews:
  - Runtime artifacts are no longer committed.
  - Git diffs stay focused on source changes.

- More deterministic pipeline outputs:
  - Stable artifact naming and sorted processing reduce non-deterministic behavior.

- Better team maintainability:
  - Explicit naming conventions and standardized output formats simplify onboarding and collaboration.

- Faster stakeholder walkthroughs:
  - Live demo flow allows showing screenshot-to-report automation in one run, making it easier to demo business value.

## 4) What Has Improved (Outcome Summary)

- Test stages are now logically separated (unit vs E2E), reducing false failures.
- Android Appium execution is more stable and repeatable in CI.
- Failure investigation is faster due to centralized, structured reports.
- LiteLLM/LangChain checks fail less noisily and provide clearer diagnostics.
- CI configuration is aligned with newer GitHub Actions runtime expectations.
- Generated artifact management is production-friendly and repository-safe.
- Live demo and enhanced runner flow provide an easier, presentation-friendly way to showcase the full automation pipeline.
- Generated login test quality now aligns with latest review expectations for reliability and action correctness.
