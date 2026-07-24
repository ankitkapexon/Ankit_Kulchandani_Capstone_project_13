"""Local Flask live demo UI for screenshot upload and enhanced pipeline execution."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from pipelines.pipeline_composer import run_pipeline
from pipelines.stage_runners import StageFeatureFlags
from services.enhanced_config import get_config, load_environment
from services.prompt_manager import PromptManager

PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
UPLOADS_ROOT = ARTIFACTS_ROOT / "input_screenshots" / "live_demo_uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
APPIUM_STATUS_URL = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723").rstrip("/") + "/status"
APPIUM_START_TIMEOUT_SECONDS = 45

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
_run_lock = threading.Lock()
_appium_process: subprocess.Popen[str] | None = None


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _is_user_facing_artifact(path: Path) -> bool:
    """Filter out placeholder and runtime-noise files from UI artifact lists."""
    name = path.name
    if name == ".gitkeep":
        return False
    if name.startswith("."):
        return False
    if name.endswith(".pyc"):
        return False
    if "__pycache__" in path.parts:
        return False
    return True


def _safe_artifact_listing(folder: Path, limit: int = 10) -> list[str]:
    if not folder.exists():
        return []
    files = [p for p in folder.glob("*") if p.is_file() and _is_user_facing_artifact(p)]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in files[:limit]]


def _artifact_listing_since(folder: Path, since_epoch: float, limit: int = 25) -> list[str]:
    """Return files created/updated after this run started."""
    if not folder.exists():
        return []

    # Small clock-skew buffer helps include files written near run start.
    threshold = since_epoch - 1.0
    files = [
        p for p in folder.glob("*")
        if p.is_file() and p.stat().st_mtime >= threshold and _is_user_facing_artifact(p)
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in files[:limit]]


def _artifact_listing_by_name_tokens(folder: Path, name_tokens: set[str], limit: int = 25) -> list[str]:
    """Return files whose names contain one of the provided run-specific tokens."""
    if not folder.exists() or not name_tokens:
        return []

    files = [
        p for p in folder.glob("*")
        if p.is_file() and _is_user_facing_artifact(p) and any(token in p.name for token in name_tokens)
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in files[:limit]]


def _folder_snapshot(folder: Path) -> dict[str, float]:
    """Capture file mtimes for one folder to compute per-run delta."""
    if not folder.exists():
        return {}

    snapshot: dict[str, float] = {}
    for path in folder.glob("*"):
        if path.is_file() and _is_user_facing_artifact(path):
            snapshot[str(path.resolve())] = path.stat().st_mtime
    return snapshot


def _artifact_listing_delta(folder: Path, before_snapshot: dict[str, float], limit: int = 25) -> list[str]:
    """Return only files created/updated by this run compared to pre-run snapshot."""
    if not folder.exists():
        return []

    changed_files: list[Path] = []
    for path in folder.glob("*"):
        if not path.is_file() or not _is_user_facing_artifact(path):
            continue

        key = str(path.resolve())
        mtime = path.stat().st_mtime
        previous_mtime = before_snapshot.get(key)
        if previous_mtime is None or mtime > previous_mtime + 1e-6:
            changed_files.append(path)

    changed_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in changed_files[:limit]]


def _normalize_pipeline_logs(log_text: str) -> str:
    """Normalize known warning variants so UI output stays stable across runs."""
    normalized = log_text.replace("LangChain integration smoke test failed.", "LangChain smoke test failed.")
    normalized = normalized.replace("LangChain agent initialized successfully", "LangChain agent initialized")
    return normalized


def _is_appium_healthy() -> bool:
    try:
        with urllib.request.urlopen(APPIUM_STATUS_URL, timeout=2) as response:
            return response.status == 200
    except urllib.error.URLError:
        return False
    except TimeoutError:
        return False


def _resolve_appium_command() -> list[str] | None:
    for candidate in ("appium", "appium.cmd"):
        path = shutil.which(candidate)
        if path:
            return [path]
    return None


def _ensure_appium_running() -> tuple[bool, str]:
    global _appium_process

    if _is_appium_healthy():
        return True, "Appium already running"

    appium_cmd = _resolve_appium_command()
    if not appium_cmd:
        return False, "Appium CLI not found. Install Appium and ensure it is on PATH."

    try:
        _appium_process = subprocess.Popen(
            [*appium_cmd, "--session-override", "--log-level", "warn"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception as exc:
        return False, f"Failed to start Appium: {exc}"

    deadline = time.time() + APPIUM_START_TIMEOUT_SECONDS
    while time.time() < deadline:
        if _is_appium_healthy():
            return True, "Appium started by live demo"
        time.sleep(1)

    return False, "Appium did not become ready within timeout"


def _run_demo_pipeline(input_dir: Path, mode: str) -> dict[str, Any]:
    ssm_dir = ARTIFACTS_ROOT / "ssm_json_output"
    manual_dir = ARTIFACTS_ROOT / "manual_testcases"
    locator_dir = ARTIFACTS_ROOT / "locator_output"
    scripts_dir = ARTIFACTS_ROOT / "generated_appium_scripts"
    reviews_dir = ARTIFACTS_ROOT / "review_reports"

    ssm_before = _folder_snapshot(ssm_dir)
    manual_before = _folder_snapshot(manual_dir)
    locator_before = _folder_snapshot(locator_dir)
    scripts_before = _folder_snapshot(scripts_dir)
    reviews_before = _folder_snapshot(reviews_dir)

    if mode == "mock":
        os.environ["VISION_AGENT_PROVIDER"] = "mock"
        os.environ["TESTCASE_AGENT_PROVIDER"] = "mock"
    else:
        # Keep user-provided real-provider settings from .env/environment.
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_openai_api_key_here":
            raise RuntimeError("Real mode requires OPENAI_API_KEY in environment or .env")

    # Reload config to pick up any mode/env changes before running.
    load_environment()
    config = get_config()
    prompt_manager = PromptManager(PROJECT_ROOT)

    feature_flags = StageFeatureFlags(
        use_langchain_vision=True,
        use_multi_strategy_locator=True,
        use_self_healing_generator=True,
        enforce_non_empty_elements=True,
    )

    std_buffer = io.StringIO()
    err_buffer = io.StringIO()
    report_path: Path | None = None

    with redirect_stdout(std_buffer), redirect_stderr(err_buffer):
        report_path = run_pipeline(
            project_root=PROJECT_ROOT,
            config=config,
            prompt_manager=prompt_manager,
            screenshots_dir=str(input_dir),
            open_browser=False,
            feature_flags=feature_flags,
        )

    output_logs = _normalize_pipeline_logs(std_buffer.getvalue())
    error_logs = err_buffer.getvalue()

    # Show only files created or updated by this specific uploaded run.
    ssm_artifacts = _artifact_listing_delta(ssm_dir, ssm_before)
    manual_testcases = _artifact_listing_delta(manual_dir, manual_before)
    locator_artifacts = _artifact_listing_delta(locator_dir, locator_before)
    script_artifacts = _artifact_listing_delta(scripts_dir, scripts_before)
    review_artifacts = _artifact_listing_delta(reviews_dir, reviews_before)

    return {
        "ok": True,
        "report_path": str(report_path.relative_to(PROJECT_ROOT)).replace("\\", "/") if report_path else "",
        "logs": output_logs,
        "stderr": error_logs,
        "artifacts": {
            "ssm": ssm_artifacts,
            "manual_testcases": manual_testcases,
            "locators": locator_artifacts,
            "scripts": script_artifacts,
            "reviews": review_artifacts,
        },
    }


@app.get("/")
def index() -> str:
    return render_template("live_demo.html", result=None, error=None)


@app.post("/run-demo")
def run_demo() -> str:
    try:
        if not _run_lock.acquire(blocking=False):
            return render_template(
                "live_demo.html",
                result=None,
                error="A demo run is already in progress. Please wait for it to finish and try again.",
            )

        upload = request.files.get("screenshot")
        mode = request.form.get("mode", "mock").strip().lower()

        if mode not in {"mock", "real"}:
            return render_template("live_demo.html", result=None, error="Invalid mode. Use mock or real.")

        if upload is None or upload.filename is None or upload.filename.strip() == "":
            return render_template("live_demo.html", result=None, error="Please upload a screenshot file.")

        if not _allowed_file(upload.filename):
            return render_template(
                "live_demo.html",
                result=None,
                error="Unsupported file type. Use png, jpg, jpeg, webp, or bmp.",
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = UPLOADS_ROOT / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        filename = secure_filename(upload.filename)
        saved_path = run_dir / filename
        upload.save(saved_path)

        appium_ok, appium_msg = _ensure_appium_running()
        if not appium_ok:
            return render_template("live_demo.html", result=None, error=f"{appium_msg}. Cannot execute mobile tests.")

        result = _run_demo_pipeline(run_dir, mode)
        result["input_file"] = str(saved_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        result["mode"] = mode
        result["appium_status"] = appium_msg
        return render_template("live_demo.html", result=result, error=None)

    except Exception:
        return render_template(
            "live_demo.html",
            result=None,
            error=f"Demo run failed:\n{traceback.format_exc()}",
        )
    finally:
        if _run_lock.locked():
            _run_lock.release()


@app.get("/artifacts/<path:subpath>")
def serve_artifact(subpath: str):
    normalized = Path(subpath)
    absolute_path = (PROJECT_ROOT / normalized).resolve()
    if not str(absolute_path).startswith(str(PROJECT_ROOT.resolve())):
        abort(403)
    if not absolute_path.exists() or not absolute_path.is_file():
        abort(404)
    return send_from_directory(str(absolute_path.parent), absolute_path.name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
