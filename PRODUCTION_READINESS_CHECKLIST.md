# Production Readiness Checklist

Use this checklist before demoing, handing over, or promoting a build.

## Environment

- [ ] `.env` exists and all mandatory keys are set.
- [ ] `STRICT_CONFIG_VALIDATION=true` is enabled.
- [ ] `APP_PROFILE_PRESET` matches target app (`generic`, `ecommerce`, `banking`, `social`).
- [ ] `ENABLE_DYNAMIC_JOURNEY_MODE=true` is set for cross-app deterministic artifacts.

## Mobile Runtime

- [ ] Appium server is reachable at `APPIUM_SERVER_URL`.
- [ ] At least one device/emulator is visible in `adb devices`.
- [ ] Target app package/activity are valid (`APP_PACKAGE`, `APP_ACTIVITY`).
- [ ] `APP_PATH` points to an existing app binary.

## Live Demo Flows

- [ ] Screenshot flow smoke passes (`tests/test_live_demo_flow_smoke_contract.py -k screenshot`).
- [ ] Realtime flow smoke passes (`tests/test_live_demo_flow_smoke_contract.py -k realtime`).
- [ ] Preflight Readiness card shows services/config ready for target flow.
- [ ] UI state reset works on flow switch and run submit.
- [ ] Telemetry dashboard is available at `/telemetry-dashboard`.

## Artifact Governance

- [ ] `ARTIFACT_RETENTION_DAYS` is set to a team-approved value.
- [ ] Latest index files exist:
  - `artifacts/indexes/latest_per_flow.json`
  - `artifacts/indexes/latest_per_run.json`
- [ ] Old artifacts are being expired as expected.

## Self-Healing Quality Signals

- [ ] Healing success rate is visible in run results.
- [ ] Top unstable elements list is visible and reviewed.
- [ ] Recurring failed locator count is tracked and trending down.

## CI/CD

- [ ] Core tests pass.
- [ ] Screenshot flow smoke job passes.
- [ ] Realtime flow smoke job passes.
- [ ] Security and lint jobs complete without critical issues.

## Operational Handover

- [ ] Team has reviewed `README.md` and `LIVE_DEMO_RUN_STEPS.md`.
- [ ] Known app-profile assumptions are documented.
- [ ] Troubleshooting runbook is available to demo operators.
