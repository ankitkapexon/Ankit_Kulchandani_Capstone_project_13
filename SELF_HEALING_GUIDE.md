# Self-Healing Guide

## Current Scope

Self-healing support exists in generated Appium scripts and runtime helpers.

Current behavior:
- locator fallback strategies are available when primary locators fail
- generated scripts include resilient interaction patterns for unstable UI elements
- review pipeline validates generated scripts after creation

## Implementation Areas

- `agents/self_healing_appium_generator.py`
- `utils/self_healing.py`
- generated scripts under `artifacts/generated_appium_scripts/`

## Practical Validation

1. Run screenshot pipeline flow.
2. Inspect generated scripts for self-healing logic.
3. Execute report generation and verify outcome.

## Notes

Self-healing behavior is validated through generated scripts and execution results.
