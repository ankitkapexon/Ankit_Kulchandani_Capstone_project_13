"""Typed contracts shared across pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict


class SSMArtifact(TypedDict):
    """Stage-1 output contract: one validated SSM artifact."""

    path: Path
    data: dict[str, Any]


class StageMetrics(TypedDict, total=False):
    """Optional stage-level telemetry contract."""

    duration_ms: int
    item_count: int
    notes: str
