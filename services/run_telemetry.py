"""Structured run telemetry with stage timings."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class RunTelemetry:
    """Collect per-run stages and write latest/history telemetry artifacts."""

    def __init__(self, telemetry_dir: Path, *, run_id: str, flow_type: str, mode: str) -> None:
        self.telemetry_dir = telemetry_dir
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.flow_type = flow_type
        self.mode = mode
        self.started_at = time.time()
        self._current_stage: str | None = None
        self._stage_started_at: float | None = None
        self.stages: list[dict[str, Any]] = []

    def mark_stage(self, stage: str, message: str) -> None:
        now = time.time()
        if self._current_stage is not None and self._stage_started_at is not None:
            self.stages.append(
                {
                    "stage": self._current_stage,
                    "duration_seconds": round(now - self._stage_started_at, 3),
                    "message": message,
                }
            )
        self._current_stage = stage
        self._stage_started_at = now

    def finalize(self, *, status: str, error_code: str | None = None) -> dict[str, Any]:
        now = time.time()
        if self._current_stage is not None and self._stage_started_at is not None:
            self.stages.append(
                {
                    "stage": self._current_stage,
                    "duration_seconds": round(now - self._stage_started_at, 3),
                    "message": "completed",
                }
            )

        payload = {
            "run_id": self.run_id,
            "flow_type": self.flow_type,
            "mode": self.mode,
            "status": status,
            "error_code": error_code or "",
            "started_at_epoch": self.started_at,
            "finished_at_epoch": now,
            "total_duration_seconds": round(now - self.started_at, 3),
            "stages": self.stages,
        }

        latest_path = self.telemetry_dir / "latest_run_telemetry.json"
        latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        history_path = self.telemetry_dir / "run_telemetry_history.jsonl"
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

        return payload


def read_latest_telemetry(telemetry_dir: Path) -> dict[str, Any] | None:
    latest_path = telemetry_dir / "latest_run_telemetry.json"
    if not latest_path.exists():
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
