from pathlib import Path

from live_demo import app


def test_reset_ui_state_endpoint_exists() -> None:
    client = app.test_client()
    response = client.post("/reset-ui-state")

    # 409 is valid if a run lock is active; 200 is expected otherwise.
    assert response.status_code in {200, 409}
    payload = response.get_json() or {}
    assert "ok" in payload
    assert "message" in payload


def test_template_contains_stale_result_reset_contract() -> None:
    template = Path("web/templates/live_demo.html").read_text(encoding="utf-8")

    expected_tokens = [
        "id=\"liveRunResultsContainer\"",
        "body.run-in-progress #liveRunResultsContainer",
        "id=\"runContext\"",
        "id=\"ctxScreenshotWrap\"",
        "id=\"ctxScreenshotName\"",
        "Previous results cleared for this run.",
        "fetch(\"/reset-ui-state\"",
        "clearPreviousRunResults();",
    ]

    for token in expected_tokens:
        assert token in template
