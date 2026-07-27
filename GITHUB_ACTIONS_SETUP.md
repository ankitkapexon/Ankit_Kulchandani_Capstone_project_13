# GitHub Actions Setup Guide

This file documents current CI expectations.

## CI Objectives

- Validate core tests and contracts.
- Catch regressions in live demo and pipeline behavior.
- Keep run outputs and contracts stable across pushes.

## Recommended Coverage

- Unit tests for agents and models.
- Live demo UI/contract tests.
- Realtime flow test coverage according to CI capacity.

## Local Pre-CI Command

```bash
python -m pytest
```

## Alignment Rule

When behavior changes in live demo flow, task runner, or artifact structure:
- update CI workflow files
- update corresponding docs

in the same change.
