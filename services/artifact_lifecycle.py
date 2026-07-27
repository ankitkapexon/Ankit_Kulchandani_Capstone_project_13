"""Artifact retention and latest-index helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def expire_old_artifacts(root: Path, retention_days: int) -> dict[str, int]:
    """Remove files older than retention window under artifacts root."""
    removed_files = 0
    removed_dirs = 0
    cutoff = time.time() - max(1, int(retention_days)) * 86400

    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_file() and path.stat().st_mtime < cutoff:
            try:
                path.unlink(missing_ok=True)
                removed_files += 1
            except Exception:
                continue
        elif path.is_dir() and path != root:
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    removed_dirs += 1
            except Exception:
                continue

    return {"removed_files": removed_files, "removed_dirs": removed_dirs}


def write_latest_indexes(
    *,
    artifacts_root: Path,
    flow_type: str,
    run_id: str,
    mode: str,
    result: dict[str, Any],
) -> dict[str, str]:
    """Write latest-per-flow and latest-per-run indexes for quick lookup."""
    index_root = artifacts_root / "indexes"
    index_root.mkdir(parents=True, exist_ok=True)

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    flow_entry = {
        "run_id": run_id,
        "flow_type": flow_type,
        "mode": mode,
        "report_path": result.get("report_path", ""),
        "outcome": result.get("outcome", "unknown"),
        "updated_at": now_iso,
    }

    latest_per_flow_path = index_root / "latest_per_flow.json"
    existing_flow: dict[str, Any] = {}
    if latest_per_flow_path.exists():
        try:
            existing_flow = json.loads(latest_per_flow_path.read_text(encoding="utf-8"))
        except Exception:
            existing_flow = {}
    existing_flow[str(flow_type)] = flow_entry
    latest_per_flow_path.write_text(json.dumps(existing_flow, indent=2), encoding="utf-8")

    latest_per_run_path = index_root / "latest_per_run.json"
    existing_runs: dict[str, Any] = {}
    if latest_per_run_path.exists():
        try:
            existing_runs = json.loads(latest_per_run_path.read_text(encoding="utf-8"))
        except Exception:
            existing_runs = {}
    existing_runs[str(run_id)] = flow_entry
    latest_per_run_path.write_text(json.dumps(existing_runs, indent=2), encoding="utf-8")

    return {
        "latest_per_flow": str(latest_per_flow_path.relative_to(artifacts_root.parent)).replace("\\", "/"),
        "latest_per_run": str(latest_per_run_path.relative_to(artifacts_root.parent)).replace("\\", "/"),
    }
