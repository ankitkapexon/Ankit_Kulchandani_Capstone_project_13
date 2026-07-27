from __future__ import annotations

from io import BytesIO

import live_demo


def _stub_result(flow_type: str) -> dict[str, object]:
    return {
        "ok": True,
        "flow_type": flow_type,
        "report_path": "artifacts/test_execution_reports/demo/report.html",
        "logs": "smoke-ok",
        "stderr": "",
        "outcome": "passed",
        "flow_label": "Smoke Flow",
        "appium_state": "running",
        "self_healing": {},
        "artifacts": {},
    }


def test_screenshot_flow_smoke_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        live_demo,
        "_run_selected_flow",
        lambda mode, flow_type, run_dir, saved_path, run_id, progress_cb=None: _stub_result(flow_type),
    )

    client = live_demo.app.test_client()
    response = client.post(
        "/run-demo",
        data={
            "mode": "mock",
            "flow_type": "screenshot_pipeline",
            "screenshot": (BytesIO(b"fake-image"), "screen.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Smoke Flow" in body


def test_realtime_flow_smoke_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        live_demo,
        "_run_selected_flow",
        lambda mode, flow_type, run_dir, saved_path, run_id, progress_cb=None: _stub_result(flow_type),
    )

    client = live_demo.app.test_client()
    response = client.post(
        "/run-demo",
        data={
            "mode": "mock",
            "flow_type": "deterministic_realtime",
        },
    )

    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Smoke Flow" in body
