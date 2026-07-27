# Production Readiness Checklist

Use this checklist before demo or handover.

## Environment

- [ ] Virtual environment is active.
- [ ] Dependencies are installed from `requirements.txt`.
- [ ] Required environment variables are configured.

## Service Readiness

- [ ] Live demo backend responds on `http://127.0.0.1:8080/`.
- [ ] UI **Start / Restart Services** reports all services ready.
- [ ] Appium server is reachable.
- [ ] Android emulator/device is connected.

## Functional Validation

- [ ] Screenshot pipeline run completes.
- [ ] Deterministic realtime run completes.
- [ ] Expected artifacts are generated under `artifacts/`.
- [ ] HTML test execution report is generated.

## Quality Gates

- [ ] Relevant pytest suite passes.
- [ ] UI contract checks pass.
- [ ] No unintended runtime artifact files are staged.

## Release Hygiene

- [ ] Docs match current behavior.
- [ ] Commit contains only intended source/config/doc changes.
- [ ] Push to `main` is verified.
