from __future__ import annotations

from pathlib import Path

from live_demo import app
from services.artifact_lifecycle import write_latest_indexes


def test_config_validation_endpoint_exists() -> None:
    client = app.test_client()
    response = client.get("/config-validation?mode=mock&flow_type=screenshot_pipeline")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert "ok" in payload
    assert "errors" in payload


def test_telemetry_latest_endpoint_contract() -> None:
    client = app.test_client()
    response = client.get("/telemetry/latest")
    assert response.status_code in {200, 404}
    payload = response.get_json() or {}
    assert "ok" in payload


def test_latest_index_files_written(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)

    paths = write_latest_indexes(
        artifacts_root=artifacts_root,
        flow_type="screenshot_pipeline",
        run_id="run-123",
        mode="mock",
        result={"report_path": "artifacts/test_execution_reports/x/report.html", "outcome": "passed"},
    )

    assert paths["latest_per_flow"].endswith("indexes/latest_per_flow.json")
    assert paths["latest_per_run"].endswith("indexes/latest_per_run.json")
    assert (artifacts_root / "indexes" / "latest_per_flow.json").exists()
    assert (artifacts_root / "indexes" / "latest_per_run.json").exists()
