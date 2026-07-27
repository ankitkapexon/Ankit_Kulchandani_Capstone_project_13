"""Local Flask live demo UI for screenshot upload and enhanced pipeline execution."""

from __future__ import annotations

import io
import json
import html
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from pipelines.pipeline_composer import run_pipeline
from pipelines.stage_runners import StageFeatureFlags
from services.artifact_lifecycle import expire_old_artifacts, write_latest_indexes
from services.enhanced_config import get_config, load_environment
from services.prompt_manager import PromptManager
from services.run_telemetry import RunTelemetry, read_latest_telemetry
from utils.retry_policy import RetryPolicy, wait_until

PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_ROOT = PROJECT_ROOT / "artifacts"
UPLOADS_ROOT = ARTIFACTS_ROOT / "input_screenshots" / "live_demo_uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}
APPIUM_STATUS_URL = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723").rstrip("/") + "/status"
APPIUM_START_TIMEOUT_SECONDS = 45
DETERMINISTIC_PYTEST_TIMEOUT_SECONDS = int(os.getenv("DETERMINISTIC_PYTEST_TIMEOUT_SECONDS", "420"))
RUN_INACTIVITY_TIMEOUT_SECONDS = int(os.getenv("RUN_INACTIVITY_TIMEOUT_SECONDS", "900"))

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
_run_lock = threading.Lock()
_appium_process: subprocess.Popen[str] | None = None
_run_states_lock = threading.Lock()
_run_states: dict[str, dict[str, Any]] = {}
_RUN_STATE_TTL_SECONDS = 3600
_service_cache_lock = threading.Lock()
_cached_adb_ok = False
_cached_adb_msg = "ADB status not checked yet. Click Start / Restart Services."
_cached_adb_devices: list[str] = []


def _hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return Windows-specific subprocess options to avoid opening console windows."""
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _set_cached_adb_status(ok: bool, msg: str, devices: list[str]) -> None:
    global _cached_adb_ok, _cached_adb_msg, _cached_adb_devices
    with _service_cache_lock:
        _cached_adb_ok = bool(ok)
        _cached_adb_msg = str(msg)
        _cached_adb_devices = list(devices)


def _get_cached_adb_status() -> tuple[bool, str, list[str]]:
    with _service_cache_lock:
        return _cached_adb_ok, _cached_adb_msg, list(_cached_adb_devices)


def _prune_run_states() -> None:
    now = time.time()
    to_delete: list[str] = []
    for run_id, state in _run_states.items():
        finished_at = state.get("finished_at")
        if finished_at and (now - float(finished_at)) > _RUN_STATE_TTL_SECONDS:
            to_delete.append(run_id)
    for run_id in to_delete:
        _run_states.pop(run_id, None)


def _set_run_state(run_id: str, **updates: Any) -> None:
    with _run_states_lock:
        state = _run_states.get(run_id)
        if state is None:
            state = {"run_id": run_id}
            _run_states[run_id] = state
        state.update(updates)
        _prune_run_states()


def _mark_run_failed_if_stale(state: dict[str, Any], now: float) -> None:
    status = str(state.get("status", "")).lower()
    if status not in {"queued", "running"}:
        return

    last_progress = state.get("last_progress_at") or state.get("started_at")
    if not last_progress:
        return

    if (now - float(last_progress)) <= RUN_INACTIVITY_TIMEOUT_SECONDS:
        return

    state.update(
        {
            "status": "failed",
            "stage": "Failed",
            "message": "Run timed out due to inactivity.",
            "error": "Demo run timed out. Check server logs for details and retry.",
            "finished_at": now,
        }
    )


def _get_run_state(run_id: str) -> dict[str, Any] | None:
    with _run_states_lock:
        _prune_run_states()
        state = _run_states.get(run_id)
        if state is None:
            return None
        _mark_run_failed_if_stale(state, time.time())
        return dict(state)


@contextmanager
def _temporary_env(overrides: dict[str, str]):
    previous: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _user_facing_run_error() -> str:
    return "Demo run failed. Check server logs for details and retry."


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


def _flow_label(flow_type: str) -> str:
    if flow_type == "deterministic_realtime":
        return "Realtime End To End Flow Of Application"
    return "Check Flow By Uploading A Screenshot"


def _appium_state(appium_msg: str) -> str:
    lower_msg = appium_msg.strip().lower()
    if "already running" in lower_msg:
        return "running"
    if "started" in lower_msg:
        return "started"
    return "unknown"


def _outcome_from_pipeline_logs(logs: str, stderr: str) -> str:
    text = f"{logs}\n{stderr}".lower()
    if "failed/errors" in text or " short test summary info " in text and "failed" in text:
        return "failed"
    if "= failed" in text or " failed " in text and "test session starts" in text:
        return "failed"
    if " passed" in text or "test completed successfully" in text:
        return "passed"
    return "unknown"


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
            **_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, f"Failed to start Appium: {exc}"

    appium_ready = wait_until(
        _is_appium_healthy,
        policy=RetryPolicy(
            attempts=max(3, APPIUM_START_TIMEOUT_SECONDS),
            initial_delay_seconds=1.0,
            max_delay_seconds=1.0,
            backoff_multiplier=1.0,
        ),
    )
    if appium_ready:
        return True, "Appium started by live demo"

    return False, "Appium did not become ready within timeout"


def _clear_runtime_cache() -> dict[str, Any]:
    """Clear lightweight runtime cache/state for a fresh demo session."""
    removed_pycache_dirs = 0

    for cache_dir in PROJECT_ROOT.rglob("__pycache__"):
        if ".venv" in cache_dir.parts:
            continue
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
            removed_pycache_dirs += 1
        except Exception:
            continue

    with _run_states_lock:
        run_state_count = len(_run_states)
        _run_states.clear()

    return {
        "removed_pycache_dirs": removed_pycache_dirs,
        "cleared_run_states": run_state_count,
    }


def _stop_appium_on_port(port: int = 4723) -> int:
    """Best-effort stop of any process listening on the given port (Windows netstat/taskkill)."""
    try:
        completed = subprocess.run(
            ["netstat", "-ano"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=8,
            **_hidden_subprocess_kwargs(),
        )
    except Exception:
        return 0

    if completed.returncode != 0:
        return 0

    killed = 0
    pids: set[str] = set()
    needle = f":{port}"
    for line in (completed.stdout or "").splitlines():
        if needle not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if parts:
            pid = parts[-1].strip()
            if pid.isdigit():
                pids.add(pid)

    for pid in pids:
        try:
            kill_result = subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=8,
                **_hidden_subprocess_kwargs(),
            )
            if kill_result.returncode == 0:
                killed += 1
        except Exception:
            continue

    return killed


def _force_restart_appium() -> tuple[bool, str, int]:
    """Force restart Appium so launcher can provide a fresh server session."""
    global _appium_process

    if _appium_process is not None:
        try:
            _appium_process.terminate()
            _appium_process.wait(timeout=5)
        except Exception:
            try:
                _appium_process.kill()
            except Exception:
                pass
        finally:
            _appium_process = None

    killed_on_port = _stop_appium_on_port(4723)
    time.sleep(1)

    appium_ok, appium_msg = _ensure_appium_running()
    return appium_ok, appium_msg, killed_on_port


def _ensure_adb_server_running() -> tuple[bool, str]:
    """Start adb server when available so emulator/device checks can succeed."""
    adb_path = shutil.which("adb")
    if not adb_path:
        return False, "adb CLI not found on PATH."

    try:
        completed = subprocess.run(
            [adb_path, "start-server"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
            **_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, f"Failed to start adb server: {exc}"

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "Unknown adb start-server error").strip()
        return False, f"adb start-server failed: {details}"

    return True, "adb server started"


def _adb_connected_devices() -> tuple[bool, str, list[str]]:
    """Return whether adb is available and has at least one connected device."""
    adb_path = shutil.which("adb")
    if not adb_path:
        return False, "adb CLI not found on PATH.", []

    try:
        completed = subprocess.run(
            [adb_path, "devices"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            **_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, f"Failed to query adb devices: {exc}", []

    if completed.returncode != 0:
        stderr_msg = (completed.stderr or "").strip() or "Unknown adb error"
        return False, f"adb devices failed: {stderr_msg}", []

    lines = [(line or "").strip() for line in (completed.stdout or "").splitlines()]
    connected = [line.split("\t", 1)[0] for line in lines if "\tdevice" in line]
    if not connected:
        return False, "No connected emulator/device found via adb.", []

    return True, "adb device connected", connected


def _adb_connected_emulators() -> list[str]:
    adb_ok, _msg, devices = _adb_connected_devices()
    if not adb_ok:
        return []
    return [serial for serial in devices if serial.startswith("emulator-")]


def _resolve_emulator_command() -> str | None:
    direct = shutil.which("emulator")
    if direct:
        return direct

    candidates: list[Path] = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.getenv(key, "").strip()
        if sdk_root:
            candidates.append(Path(sdk_root) / "emulator" / "emulator.exe")

    local_sdk = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "emulator" / "emulator.exe"
    candidates.append(local_sdk)

    for path in candidates:
        if path.exists() and path.is_file():
            return str(path)
    return None


def _resolve_android_tool(tool_name: str) -> str | None:
    """Resolve Android SDK command-line tools (avdmanager/sdkmanager)."""
    direct = shutil.which(tool_name)
    if direct:
        return direct

    candidates: list[Path] = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        sdk_root = os.getenv(key, "").strip()
        if sdk_root:
            root = Path(sdk_root)
            candidates.extend(
                [
                    root / "cmdline-tools" / "latest" / "bin" / f"{tool_name}.bat",
                    root / "cmdline-tools" / "latest" / "bin" / f"{tool_name}.exe",
                    root / "cmdline-tools" / "bin" / f"{tool_name}.bat",
                    root / "cmdline-tools" / "bin" / f"{tool_name}.exe",
                    root / "tools" / "bin" / f"{tool_name}.bat",
                    root / "tools" / "bin" / f"{tool_name}.exe",
                ]
            )

    local_sdk_root = Path.home() / "AppData" / "Local" / "Android" / "Sdk"
    candidates.extend(
        [
            local_sdk_root / "cmdline-tools" / "latest" / "bin" / f"{tool_name}.bat",
            local_sdk_root / "cmdline-tools" / "latest" / "bin" / f"{tool_name}.exe",
            local_sdk_root / "cmdline-tools" / "bin" / f"{tool_name}.bat",
            local_sdk_root / "cmdline-tools" / "bin" / f"{tool_name}.exe",
            local_sdk_root / "tools" / "bin" / f"{tool_name}.bat",
            local_sdk_root / "tools" / "bin" / f"{tool_name}.exe",
        ]
    )

    for path in candidates:
        if path.exists() and path.is_file():
            return str(path)
    return None


def _list_installed_system_images() -> list[str]:
    sdkmanager = _resolve_android_tool("sdkmanager")
    if not sdkmanager:
        return []

    try:
        completed = subprocess.run(
            [sdkmanager, "--list_installed"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            **_hidden_subprocess_kwargs(),
        )
    except Exception:
        return []

    if completed.returncode != 0:
        return []

    images: list[str] = []
    for line in (completed.stdout or "").splitlines():
        clean = (line or "").strip()
        if clean.startswith("system-images;"):
            images.append(clean.split()[0])

    return images


def _ensure_default_avd_exists() -> tuple[bool, str | None]:
    """Create a default AVD if none exists and SDK tools are available."""
    existing = _list_available_avds()
    if existing:
        return True, None

    avdmanager = _resolve_android_tool("avdmanager")
    if not avdmanager:
        return False, "No AVDs found and avdmanager is unavailable. Install Android SDK command-line tools."

    images = _list_installed_system_images()
    if not images:
        return False, "No installed Android system images found. Install one via SDK Manager first."

    selected_image = images[0]
    avd_name = os.getenv("LIVE_DEMO_AVD_NAME", "CopilotLiveDemo")
    command = [
        avdmanager,
        "create",
        "avd",
        "-n",
        avd_name,
        "-k",
        selected_image,
        "-d",
        "pixel",
        "--force",
    ]

    try:
        created = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            input="no\n",
            timeout=45,
            **_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, f"Failed to create default AVD: {exc}"

    if created.returncode != 0:
        details = (created.stderr or created.stdout or "unknown error").strip()
        return False, f"AVD auto-create failed: {details}"

    return True, f"Auto-created AVD '{avd_name}' using {selected_image}."


def _list_available_avds() -> list[str]:
    emulator_cmd = _resolve_emulator_command()
    if not emulator_cmd:
        return []

    try:
        completed = subprocess.run(
            [emulator_cmd, "-list-avds"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            **_hidden_subprocess_kwargs(),
        )
    except Exception:
        return []

    if completed.returncode != 0:
        return []

    return [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]


def _start_emulator_if_needed() -> tuple[bool, str, dict[str, Any]]:
    adb_cmd = _resolve_adb_command()
    if not adb_cmd:
        return False, (
            "ADB CLI not found. Install Android Platform Tools and ensure adb is on PATH."
        ), {
            "started": False,
            "emulators": [],
            "missing_requirements": ["adb"],
        }

    running_emulators = _adb_connected_emulators()
    if running_emulators:
        return True, "Emulator already running.", {
            "started": False,
            "emulators": running_emulators,
        }

    emulator_cmd = _resolve_emulator_command()
    if not emulator_cmd:
        return False, (
            "Android emulator CLI not found. Install Android SDK Emulator and ensure emulator is on PATH."
        ), {
            "started": False,
            "emulators": [],
            "missing_requirements": ["emulator"],
        }

    avd_note: str | None = None
    avds = _list_available_avds()
    if not avds:
        created_ok, created_message = _ensure_default_avd_exists()
        if not created_ok:
            return False, created_message or "No Android Virtual Device (AVD) found.", {
                "started": False,
                "emulators": [],
                "missing_requirements": ["avd_or_system_image"],
            }
        avd_note = created_message
        avds = _list_available_avds()

    if not avds:
        return False, "No Android Virtual Device (AVD) found after auto-create attempt.", {
            "started": False,
            "emulators": [],
        }

    selected_avd = avds[0]
    command = [
        emulator_cmd,
        "-avd",
        selected_avd,
        "-netdelay",
        "none",
        "-netspeed",
        "full",
    ]

    try:
        subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **_hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return False, f"Failed to start emulator: {exc}", {
            "started": False,
            "avd": selected_avd,
            "emulators": [],
        }

    # Emulator boot is asynchronous; return quickly with launch acknowledgment.
    launch_message = f"Launching emulator AVD '{selected_avd}'. It may take 30-90 seconds to appear in adb devices."
    if avd_note:
        launch_message = f"{avd_note} {launch_message}"

    return True, launch_message, {
        "started": True,
        "avd": selected_avd,
        "emulators": [],
        "auto_created_avd": bool(avd_note),
    }


def _wait_for_adb_emulator(timeout_seconds: int = 120, poll_interval: float = 3.0) -> tuple[bool, list[str]]:
    """Wait for at least one emulator-* device to appear in adb devices."""
    emulators: list[str] = []

    def _probe() -> bool:
        nonlocal emulators
        emulators = _adb_connected_emulators()
        return bool(emulators)

    ready = wait_until(
        _probe,
        policy=RetryPolicy(
            attempts=max(2, int(timeout_seconds / max(0.5, poll_interval))),
            initial_delay_seconds=poll_interval,
            max_delay_seconds=poll_interval,
            backoff_multiplier=1.0,
        ),
    )
    return ready, emulators


def _build_dynamic_journey_from_artifacts(captured_images: list[Path]) -> dict[str, Any]:
    """Build a compact deterministic journey plan from captured runtime screenshots."""
    steps: list[dict[str, Any]] = []
    for index, image_path in enumerate(captured_images, start=1):
        token = image_path.stem.replace("_", " ").strip().title() or f"Step {index}"
        steps.append(
            {
                "index": index,
                "screen": token,
                "anchor": image_path.name,
            }
        )

    return {
        "mode": "dynamic_journey",
        "steps": steps,
        "step_count": len(steps),
    }


def _read_self_healing_quality_signals(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "healing_success_rate": 0.0,
            "fallback_depth_estimate": 0.0,
            "recurring_failed_locators": 0,
            "top_unstable_elements": [],
        }

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*), SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) FROM healing_events")
        total_events, successful_events = cursor.fetchone() or (0, 0)
        total_events = int(total_events or 0)
        successful_events = int(successful_events or 0)

        cursor.execute(
            """
            SELECT element_name, failure_count, success_count, reliability_score
            FROM reliability_scores
            WHERE failure_count >= 2
            ORDER BY failure_count DESC, reliability_score ASC
            LIMIT 5
            """
        )
        unstable_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM reliability_scores
            WHERE failure_count >= 3 AND reliability_score < 0.6
            """
        )
        recurring_failed = int((cursor.fetchone() or [0])[0] or 0)

    top_unstable = [
        {
            "element": row[0],
            "failure_count": int(row[1] or 0),
            "success_count": int(row[2] or 0),
            "reliability": float(row[3] or 0.0),
        }
        for row in unstable_rows
    ]

    fallback_depth_estimate = 0.0
    if top_unstable:
        fallback_depth_estimate = round(sum(item["failure_count"] for item in top_unstable) / len(top_unstable), 2)

    healing_success_rate = round((successful_events / total_events) * 100, 2) if total_events else 0.0
    return {
        "healing_success_rate": healing_success_rate,
        "fallback_depth_estimate": fallback_depth_estimate,
        "recurring_failed_locators": recurring_failed,
        "top_unstable_elements": top_unstable,
    }


def _resolve_adb_command() -> str | None:
    return shutil.which("adb")


def _capture_emulator_frame_png() -> bytes | None:
    """Capture one emulator screenshot frame using adb exec-out screencap."""
    adb_path = _resolve_adb_command()
    if not adb_path:
        return None

    try:
        completed = subprocess.run(
            [adb_path, "exec-out", "screencap", "-p"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=8,
            **_hidden_subprocess_kwargs(),
        )
    except Exception:
        return None

    if completed.returncode != 0:
        return None

    data = completed.stdout or b""
    if not data.startswith(b"\x89PNG"):
        return None
    return data


def _list_supported_images(folder: Path) -> list[Path]:
    if not folder.exists():
        return []

    candidates: list[Path] = []
    for suffix in ALLOWED_EXTENSIONS:
        candidates.extend(folder.glob(f"*.{suffix}"))
    return sorted([p for p in candidates if p.is_file()], key=lambda p: p.stat().st_mtime)


def _select_seed_screenshot() -> Path | None:
    """Pick one local screenshot to seed deterministic artifact generation."""
    base_dir = ARTIFACTS_ROOT / "input_screenshots"
    if not base_dir.exists():
        return None

    candidates: list[Path] = []
    for suffix in ALLOWED_EXTENSIONS:
        candidates.extend(base_dir.rglob(f"*.{suffix}"))

    filtered = [p for p in candidates if p.is_file() and "live_demo_uploads" not in p.parts]
    if not filtered:
        filtered = [p for p in candidates if p.is_file()]

    if not filtered:
        return None

    filtered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return filtered[0]


def _prepare_deterministic_seed_input() -> tuple[Path, Path]:
    """Create a session-specific input folder for deterministic artifact pass."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = UPLOADS_ROOT / f"deterministic_seed_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    seed_source = _select_seed_screenshot()
    if seed_source is not None:
        target = run_dir / seed_source.name
        shutil.copy2(seed_source, target)
        return run_dir, target

    # Fallback when no screenshot exists: capture one directly from running emulator.
    frame = _capture_emulator_frame_png()
    if frame is None:
        raise RuntimeError(
            "Deterministic run could not find input screenshots and could not capture an emulator frame. "
            "Start an emulator/device and retry."
        )

    target = run_dir / "deterministic_seed_emulator.png"
    target.write_bytes(frame)
    return run_dir, target


def _prepare_realtime_step_capture_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capture_dir = UPLOADS_ROOT / f"deterministic_steps_{timestamp}"
    capture_dir.mkdir(parents=True, exist_ok=True)
    return capture_dir


def _required_services_status(start_appium: bool = False, probe_devices: bool = True) -> dict[str, Any]:
    """Compute runtime readiness for the live demo launcher page."""
    appium_ok = _is_appium_healthy()
    appium_msg = "Appium already running" if appium_ok else "Appium not running"

    if start_appium and not appium_ok:
        appium_ok, appium_msg = _ensure_appium_running()

    if probe_devices:
        adb_ok, adb_msg, adb_devices = _adb_connected_devices()
        _set_cached_adb_status(adb_ok, adb_msg, adb_devices)
    else:
        adb_ok, adb_msg, adb_devices = _get_cached_adb_status()
    emulator_devices = [serial for serial in adb_devices if serial.startswith("emulator-")]
    pipeline_idle = not _run_lock.locked()

    flask_service = {
        "name": "Flask live demo backend",
        "ok": True,
        "message": "Running (this page is served by Flask)",
    }
    appium_service = {
        "name": "Appium server",
        "ok": appium_ok,
        "message": appium_msg,
    }
    adb_service = {
        "name": "Android emulator/device",
        "ok": adb_ok,
        "message": adb_msg,
        "devices": adb_devices,
        "emulators": emulator_devices,
    }
    pipeline_service = {
        "name": "Live demo run lock",
        "ok": pipeline_idle,
        "message": "No run in progress" if pipeline_idle else "Another demo run is currently in progress",
    }

    services = [flask_service, appium_service, adb_service, pipeline_service]
    overall_ok = appium_ok and adb_ok
    return {
        "ok": overall_ok,
        "services": services,
        "message": "All required services are ready." if overall_ok else "Some required services are not ready yet.",
    }


def _script_uses_self_healing(script_path: Path) -> bool:
    try:
        content = script_path.read_text(encoding="utf-8")
    except Exception:
        return False

    has_driver = "SelfHealingDriver" in content
    has_driver_import = "from utils.self_healing import" in content or "import utils.self_healing" in content
    has_locator_strategy = "LocatorStrategy" in content
    has_fallback_usage = "fallback_strategies" in content or "healing_repository" in content

    return (has_driver and has_driver_import and has_fallback_usage) or (has_locator_strategy and has_fallback_usage)


def _collect_self_healing_details(
    script_artifacts: list[str],
    db_path: Path,
    db_mtime_before: float | None,
) -> dict[str, Any]:
    scripts_with_self_healing: list[str] = []
    for rel_path in script_artifacts:
        candidate = PROJECT_ROOT / rel_path
        if candidate.exists() and _script_uses_self_healing(candidate):
            scripts_with_self_healing.append(rel_path)

    db_updated = False
    if db_path.exists():
        try:
            current_mtime = db_path.stat().st_mtime
            db_updated = db_mtime_before is None or current_mtime > db_mtime_before + 1e-6
        except Exception:
            db_updated = True

    return {
        "enabled": True,
        "generated_scripts": len(script_artifacts),
        "scripts_with_self_healing": scripts_with_self_healing,
        "scripts_with_self_healing_count": len(scripts_with_self_healing),
        "healing_repository": "",
        "healing_repository_updated": db_updated,
        "quality_signals": _read_self_healing_quality_signals(db_path),
    }


def _validate_live_demo_config(mode: str, flow_type: str) -> list[str]:
    config = get_config()
    errors: list[str] = []

    if mode == "real":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_openai_api_key_here":
            errors.append("OPENAI_API_KEY is required for real mode.")

    if not config.appium_server_url.startswith("http"):
        errors.append("APPIUM_SERVER_URL must start with http:// or https://")

    if flow_type.startswith("deterministic"):
        if not config.app_package:
            errors.append("APP_PACKAGE is required for deterministic realtime flow.")
        if not config.app_activity:
            errors.append("APP_ACTIVITY is required for deterministic realtime flow.")
        if not config.app_path.exists():
            errors.append(f"APP_PATH does not exist: {config.app_path}")

    return errors


def _run_demo_pipeline(
    input_dir: Path,
    mode: str,
    report_scope: str = "screenshot_pipeline",
    execute_report_tests: bool = True,
    progress_cb: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    ssm_dir = ARTIFACTS_ROOT / "ssm_json_output"
    manual_dir = ARTIFACTS_ROOT / "manual_testcases"
    locator_dir = ARTIFACTS_ROOT / "locator_output"
    scripts_dir = ARTIFACTS_ROOT / "generated_appium_scripts"
    reviews_dir = ARTIFACTS_ROOT / "review_reports"
    healing_db = ARTIFACTS_ROOT / "healing_repository.db"

    ssm_before = _folder_snapshot(ssm_dir)
    manual_before = _folder_snapshot(manual_dir)
    locator_before = _folder_snapshot(locator_dir)
    scripts_before = _folder_snapshot(scripts_dir)
    reviews_before = _folder_snapshot(reviews_dir)
    healing_db_mtime_before = healing_db.stat().st_mtime if healing_db.exists() else None

    if progress_cb:
        progress_cb("Preparing", "Configuring pipeline mode and environment.")

    env_overrides: dict[str, str] = {}
    if mode == "mock":
        env_overrides = {
            "VISION_AGENT_PROVIDER": "mock",
            "TESTCASE_AGENT_PROVIDER": "mock",
        }
    else:
        # Keep user-provided real-provider settings from .env/environment.
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_openai_api_key_here":
            raise RuntimeError("Real mode requires OPENAI_API_KEY in environment or .env")

    # Reload config to pick up any mode/env changes before running.
    if progress_cb:
        progress_cb("Preparing", "Loading config and prompts.")
    with _temporary_env(env_overrides):
        load_environment()
        config = get_config()
        prompt_manager = PromptManager(PROJECT_ROOT)

        feature_flags = StageFeatureFlags(
            use_langchain_vision=True,
            use_multi_strategy_locator=True,
            use_self_healing_generator=config.is_reference_demo_profile,
            enforce_non_empty_elements=True,
        )

        std_buffer = io.StringIO()
        err_buffer = io.StringIO()
        report_path: Path | None = None

        if progress_cb:
            progress_cb("Executing", "Running screenshot pipeline stages.")

        with redirect_stdout(std_buffer), redirect_stderr(err_buffer):
            report_path = run_pipeline(
                project_root=PROJECT_ROOT,
                config=config,
                prompt_manager=prompt_manager,
                screenshots_dir=str(input_dir),
                open_browser=False,
                feature_flags=feature_flags,
                report_scope=report_scope,
                execute_report_tests=execute_report_tests,
            )

        output_logs = _normalize_pipeline_logs(std_buffer.getvalue())
        error_logs = err_buffer.getvalue()

    if progress_cb:
        progress_cb("Finalizing", "Collecting run-scoped artifacts.")

    # Show only files created or updated by this specific uploaded run.
    ssm_artifacts = _artifact_listing_delta(ssm_dir, ssm_before)
    manual_testcases = _artifact_listing_delta(manual_dir, manual_before)
    locator_artifacts = _artifact_listing_delta(locator_dir, locator_before)
    script_artifacts = _artifact_listing_delta(scripts_dir, scripts_before)
    review_artifacts = _artifact_listing_delta(reviews_dir, reviews_before)
    self_healing = _collect_self_healing_details(script_artifacts, healing_db, healing_db_mtime_before)

    self_healing_artifacts: list[str] = []

    return {
        "ok": True,
        "flow_type": "screenshot_pipeline",
        "report_path": str(report_path.relative_to(PROJECT_ROOT)).replace("\\", "/") if report_path else "",
        "logs": output_logs,
        "stderr": error_logs,
        "self_healing": self_healing,
        "artifacts": {
            "ssm": ssm_artifacts,
            "manual_testcases": manual_testcases,
            "locators": locator_artifacts,
            "scripts": script_artifacts,
            "reviews": review_artifacts,
            "self_healing": self_healing_artifacts,
        },
    }


def _run_deterministic_flow(
    mode: str,
    progress_cb: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    config = get_config()
    if progress_cb:
        progress_cb("Preparing", "Validating deterministic realtime prerequisites.")

    if mode == "real":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key == "your_openai_api_key_here":
            raise RuntimeError("Real mode requires OPENAI_API_KEY in environment or .env")

    capture_dir = _prepare_realtime_step_capture_dir()

    report_root = ARTIFACTS_ROOT / "test_execution_reports" / "deterministic_realtime"
    report_root.mkdir(parents=True, exist_ok=True)
    report_dir = report_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"

    python_exe = str((PROJECT_ROOT / ".venv" / "Scripts" / "python.exe").resolve())
    if not Path(python_exe).exists():
        python_exe = sys.executable

    env = os.environ.copy()
    env["SINGLE_APP_SESSION"] = "1"
    env["REALTIME_STEP_SCREENSHOT_DIR"] = str(capture_dir)
    if mode == "mock":
        env["VISION_AGENT_PROVIDER"] = "mock"
        env["TESTCASE_AGENT_PROVIDER"] = "mock"

    command = [
        python_exe,
        "-m",
        "pytest",
        "tests/test_realtime_e2e_flow.py",
        "-v",
        "-s",
        "--tb=short",
        "--log-cli-level=INFO",
        "--log-cli-format=%(asctime)s [%(levelname)s] %(message)s",
        "--capture=tee-sys",
        f"--html={report_path}",
        "--self-contained-html",
    ]

    if progress_cb:
        progress_cb("Executing", "Running deterministic realtime emulator flow.")

    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=DETERMINISTIC_PYTEST_TIMEOUT_SECONDS,
            **_hidden_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            args=command,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nDeterministic realtime pytest timed out.",
        )

    captured_images = _list_supported_images(capture_dir)

    if progress_cb:
        progress_cb("Preparing", "Generating full pipeline artifacts for this deterministic session.")

    if captured_images:
        seed_input_dir = capture_dir
        seed_input_file = captured_images[0]
    else:
        seed_input_dir, seed_input_file = _prepare_deterministic_seed_input()

    def _artifact_progress(stage: str, message: str) -> None:
        if progress_cb:
            progress_cb(stage, f"Artifact pass: {message}")

    pipeline_result = _run_demo_pipeline(
        seed_input_dir,
        mode,
        report_scope="deterministic_realtime/artifact_pipeline",
        execute_report_tests=False,
        progress_cb=_artifact_progress,
    )

    if progress_cb:
        progress_cb("Finalizing", "Publishing deterministic run report.")

    logs = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    artifacts = {
        "ssm": pipeline_result["artifacts"].get("ssm", []),
        "manual_testcases": pipeline_result["artifacts"].get("manual_testcases", []),
        "locators": pipeline_result["artifacts"].get("locators", []),
        "scripts": pipeline_result["artifacts"].get("scripts", []),
        "reviews": pipeline_result["artifacts"].get("reviews", []),
        "self_healing": pipeline_result["artifacts"].get("self_healing", []),
        "captured_screenshots": [
            str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            for path in captured_images
        ],
    }

    if "tests/test_realtime_e2e_flow.py" not in artifacts["scripts"]:
        artifacts["scripts"].append("tests/test_realtime_e2e_flow.py")

    dynamic_journey: dict[str, Any] = {"enabled": False, "mode": "disabled", "steps": [], "step_count": 0}
    if config.dynamic_journey_enabled:
        dynamic_journey = _build_dynamic_journey_from_artifacts(captured_images)
        dynamic_journey["enabled"] = True

    pipeline_logs = (pipeline_result.get("logs") or "").strip()
    pipeline_stderr = (pipeline_result.get("stderr") or "").strip()
    screenshot_source = (
        str(seed_input_dir.relative_to(PROJECT_ROOT)).replace("\\", "/")
        if seed_input_dir.exists()
        else "N/A"
    )

    combined_logs = (
        f"[Deterministic realtime test]\n{logs}\n\n"
        f"[Artifact pipeline pass]\n"
        f"Pipeline screenshot source: {screenshot_source}\n"
        f"Captured realtime screenshots: {len(captured_images)}\n"
        f"{pipeline_logs}"
    ).strip()
    stderr_sections: list[str] = []
    if pipeline_stderr:
        stderr_sections.append(f"[Artifact pipeline pass]\n{pipeline_stderr}")
    if stderr:
        stderr_sections.append(f"[Deterministic realtime test]\n{stderr}")
    combined_stderr = "\n\n".join(stderr_sections).strip()

    return {
        "ok": completed.returncode == 0,
        "flow_type": "deterministic_realtime",
        "report_path": str(report_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "logs": combined_logs,
        "stderr": combined_stderr,
        "self_healing": pipeline_result.get("self_healing", {}),
        "outcome": "passed" if completed.returncode == 0 else "failed",
        "seed_input_file": str(seed_input_file.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "dynamic_journey": dynamic_journey,
        "artifacts": artifacts,
    }


@app.get("/")
def index() -> str:
    preferred_flow = request.args.get("flow_type", "").strip().lower()
    if preferred_flow not in {"screenshot_pipeline", "deterministic_realtime"}:
        preferred_flow = "deterministic_realtime"
    return _render_live_demo(result=None, error=None, preferred_flow=preferred_flow)


@app.get("/Capstone_project_13_Cross-Platform-Mobile-Test-Script-Generator")
def live_demo_fixed() -> Any:
    """Cross-Platform Mobile Test Script Generator Live Demo launcher page."""
    static_dir = PROJECT_ROOT / "web" / "static"
    return send_from_directory(str(static_dir), "live_demo_entry.html")


@app.get("/live-demo-fixed")
def live_demo_fixed_legacy() -> Response:
    """Legacy route kept for backwards compatibility with older bookmarks/docs."""
    return redirect("/Capstone_project_13_Cross-Platform-Mobile-Test-Script-Generator", code=302)


@app.post("/start-required-services")
def start_required_services():
    if _run_lock.locked():
        return jsonify(
            {
                "ok": False,
                "message": "Cannot restart services while a demo run is in progress.",
                "fresh_restart_performed": False,
                "services": _required_services_status(start_appium=False).get("services", []),
            }
        )

    current = _required_services_status(start_appium=False)
    if current.get("ok"):
        adb_ok, adb_msg = _ensure_adb_server_running()
        cache_info = _clear_runtime_cache()
        appium_ok, appium_msg, killed_count = _force_restart_appium()
        emulator_ok, emulator_msg, emulator_details = _start_emulator_if_needed()
        if emulator_ok and emulator_details.get("started"):
            ready, emulators = _wait_for_adb_emulator(timeout_seconds=120, poll_interval=3.0)
            emulator_details["boot_ready"] = ready
            emulator_details["emulators"] = emulators
            if not ready:
                emulator_ok = False
                emulator_msg = "Emulator launch was triggered but it did not become adb-ready within 120 seconds."
        refreshed = _required_services_status(start_appium=False)
        refreshed["ok"] = bool(refreshed.get("ok")) and adb_ok and appium_ok and emulator_ok
        refreshed["fresh_restart_performed"] = True
        setup_errors = []
        if not adb_ok:
            setup_errors.append(adb_msg)
        if not appium_ok:
            setup_errors.append(appium_msg)
        if not emulator_ok:
            setup_errors.append(emulator_msg)
        refreshed["restart_details"] = {
            "adb_message": adb_msg,
            "appium_restart_message": appium_msg,
            "emulator_message": emulator_msg,
            "emulator_action": emulator_details,
            "setup_errors": setup_errors,
            "killed_processes_on_port": killed_count,
            "removed_pycache_dirs": cache_info.get("removed_pycache_dirs", 0),
            "cleared_run_states": cache_info.get("cleared_run_states", 0),
            "flask_note": "Flask serves this endpoint and remains active; refreshes use latest loaded code.",
        }
        if refreshed.get("ok"):
            refreshed["message"] = (
                "Services were already running. Cache cleared, Appium refreshed, and emulator readiness verified."
            )
        else:
            refreshed["message"] = (
                "Attempted fresh restart, but setup is incomplete: "
                + " | ".join(setup_errors)
                if setup_errors
                else "Attempted fresh restart, but one or more required services are still not ready."
            )
        return jsonify(refreshed)

    adb_ok, adb_msg = _ensure_adb_server_running()
    appium_ok, appium_msg = _ensure_appium_running()
    emulator_ok, emulator_msg, emulator_details = _start_emulator_if_needed()
    if emulator_ok and emulator_details.get("started"):
        ready, emulators = _wait_for_adb_emulator(timeout_seconds=120, poll_interval=3.0)
        emulator_details["boot_ready"] = ready
        emulator_details["emulators"] = emulators
        if not ready:
            emulator_ok = False
            emulator_msg = "Emulator launch was triggered but it did not become adb-ready within 120 seconds."
    status = _required_services_status(start_appium=False)
    status["ok"] = bool(status.get("ok")) and adb_ok and appium_ok and emulator_ok
    status["fresh_restart_performed"] = False
    setup_errors = []
    if not adb_ok:
        setup_errors.append(adb_msg)
    if not appium_ok:
        setup_errors.append(appium_msg)
    if not emulator_ok:
        setup_errors.append(emulator_msg)
    status["startup_details"] = {
        "adb_message": adb_msg,
        "appium_message": appium_msg,
        "emulator_message": emulator_msg,
        "emulator_action": emulator_details,
        "setup_errors": setup_errors,
    }
    status["message"] = (
        "Required services started."
        if status.get("ok")
        else (
            "Setup incomplete: " + " | ".join(setup_errors)
            if setup_errors
            else "Attempted to start required services, but some are still not ready."
        )
    )
    return jsonify(status)


@app.get("/required-services-status")
def required_services_status():
    quick = request.args.get("quick", "0").strip().lower() in {"1", "true", "yes", "on"}
    status = _required_services_status(start_appium=False, probe_devices=not quick)
    return jsonify(status)


@app.get("/config-validation")
def config_validation_status():
    mode = request.args.get("mode", _default_mode()).strip().lower() or _default_mode()
    flow_type = request.args.get("flow_type", "screenshot_pipeline").strip().lower() or "screenshot_pipeline"
    errors = _validate_live_demo_config(mode, flow_type)
    return jsonify(
        {
            "ok": not errors,
            "mode": mode,
            "flow_type": flow_type,
            "errors": errors,
            "message": "Configuration is valid." if not errors else "Configuration validation failed.",
        }
    )


@app.post("/start-emulator")
def start_emulator():
    if _run_lock.locked():
        return jsonify(
            {
                "ok": False,
                "message": "Cannot start emulator while a demo run is in progress.",
                "services": _required_services_status(start_appium=False).get("services", []),
            }
        ), 409

    ok, message, details = _start_emulator_if_needed()
    status = _required_services_status(start_appium=False)
    status["ok"] = bool(status.get("ok")) and ok
    status["message"] = message
    status["emulator_action"] = details
    return jsonify(status), (200 if ok else 500)


@app.post("/reset-ui-state")
def reset_ui_state():
    """Clear stale completed run states so a new run starts from a clean UI context."""
    if _run_lock.locked():
        return jsonify(
            {
                "ok": False,
                "message": "Cannot reset UI state while a demo run is in progress.",
            }
        ), 409

    with _run_states_lock:
        cleared_runs = len(_run_states)
        _run_states.clear()

    return jsonify(
        {
            "ok": True,
            "message": "UI run state reset.",
            "cleared_runs": cleared_runs,
        }
    )


def _validate_run_inputs(mode: str, flow_type: str) -> str | None:
    if mode not in {"mock", "real"}:
        return "Invalid mode. Use mock or real."
    if flow_type not in {"screenshot_pipeline", "deterministic_realtime"}:
        return "Invalid flow type. Use screenshot_pipeline or deterministic_realtime."
    return None


def _default_mode() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key and api_key != "your_openai_api_key_here":
        return "real"
    return "mock"


def _render_live_demo(
    *,
    result: dict[str, Any] | None,
    error: str | None,
    preferred_flow: str | None = None,
) -> str:
    config = get_config()
    flow_hint = (preferred_flow or "").strip().lower()
    if flow_hint not in {"screenshot_pipeline", "deterministic_realtime"}:
        flow_hint = ""

    return render_template(
        "live_demo.html",
        result=result,
        error=error,
        default_mode=_default_mode(),
        preferred_flow=flow_hint,
        app_package=config.app_package,
    )


def _resolve_requested_mode() -> str:
    requested = request.form.get("mode", "").strip().lower()
    return requested if requested else _default_mode()


def _prepare_upload_for_flow(flow_type: str):
    upload = request.files.get("screenshot")
    if flow_type != "screenshot_pipeline":
        return None, None

    if upload is None or upload.filename is None or upload.filename.strip() == "":
        raise ValueError("Please upload a screenshot file.")

    if not _allowed_file(upload.filename):
        raise ValueError("Unsupported file type. Use png, jpg, jpeg, webp, or bmp.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = UPLOADS_ROOT / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(upload.filename)
    saved_path = run_dir / filename
    upload.save(saved_path)
    return run_dir, saved_path


def _run_selected_flow(
    mode: str,
    flow_type: str,
    run_dir: Path | None,
    saved_path: Path | None,
    run_id: str,
    progress_cb: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    config = get_config()
    lifecycle_info = expire_old_artifacts(ARTIFACTS_ROOT, config.artifact_retention_days)

    if progress_cb:
        progress_cb("Preparing", "Ensuring Appium server is ready.")

    appium_ok, appium_msg = _ensure_appium_running()
    if not appium_ok:
        raise RuntimeError(f"{appium_msg}. Cannot execute mobile tests.")

    if flow_type == "screenshot_pipeline":
        if run_dir is None or saved_path is None:
            raise RuntimeError("Screenshot run is missing uploaded input file.")
        result = _run_demo_pipeline(run_dir, mode, progress_cb=progress_cb)
        result["input_file"] = str(saved_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        result["outcome"] = _outcome_from_pipeline_logs(result.get("logs", ""), result.get("stderr", ""))
    else:
        result = _run_deterministic_flow(mode, progress_cb=progress_cb)
        result["input_file"] = result.get(
            "seed_input_file",
            "N/A (deterministic flow does not require screenshot upload)",
        )

    result["mode"] = mode
    result["appium_status"] = appium_msg
    result["flow_label"] = _flow_label(flow_type)
    result["appium_state"] = _appium_state(appium_msg)
    result["artifact_lifecycle"] = {
        "retention_days": config.artifact_retention_days,
        **lifecycle_info,
    }
    result["app_profile_preset"] = config.app_profile_preset
    index_paths = write_latest_indexes(
        artifacts_root=ARTIFACTS_ROOT,
        flow_type=flow_type,
        run_id=run_id,
        mode=mode,
        result=result,
    )
    result["artifact_indexes"] = index_paths
    if not result.get("outcome"):
        result["outcome"] = "unknown"
    return result


def _execute_async_run(
    run_id: str,
    mode: str,
    flow_type: str,
    run_dir: Path | None,
    saved_path: Path | None,
) -> None:
    if not _run_lock.acquire(blocking=False):
        _set_run_state(
            run_id,
            status="failed",
            stage="Rejected",
            message="Another demo run is already in progress.",
            finished_at=time.time(),
        )
        return

    try:
        telemetry: RunTelemetry | None = None
        cfg = get_config()
        if cfg.telemetry_enabled:
            telemetry = RunTelemetry(cfg.telemetry_dir, run_id=run_id, flow_type=flow_type, mode=mode)

        _set_run_state(
            run_id,
            status="running",
            stage="Preparing",
            message="Starting demo run.",
            last_progress_at=time.time(),
        )

        def progress_cb(stage: str, message: str) -> None:
            if telemetry is not None:
                telemetry.mark_stage(stage, message)
            _set_run_state(run_id, status="running", stage=stage, message=message, last_progress_at=time.time())

        result = _run_selected_flow(mode, flow_type, run_dir, saved_path, run_id, progress_cb=progress_cb)
        if telemetry is not None:
            result["telemetry"] = telemetry.finalize(status="completed")
        _set_run_state(
            run_id,
            status="completed",
            stage="Completed",
            message="Demo run finished successfully.",
            result=result,
            last_progress_at=time.time(),
            finished_at=time.time(),
        )
    except Exception:
        traceback.print_exc()
        cfg = get_config()
        if cfg.telemetry_enabled:
            failed_telemetry = RunTelemetry(cfg.telemetry_dir, run_id=run_id, flow_type=flow_type, mode=mode)
            failed_telemetry.mark_stage("Failed", "Demo run failed")
            failed_telemetry.finalize(status="failed", error_code="demo_run_exception")
        _set_run_state(
            run_id,
            status="failed",
            stage="Failed",
            message="Demo run failed.",
            error=_user_facing_run_error(),
            last_progress_at=time.time(),
            finished_at=time.time(),
        )
    finally:
        if _run_lock.locked():
            _run_lock.release()


@app.post("/run-demo")
def run_demo() -> str:
    mode = _resolve_requested_mode()
    flow_type = request.form.get("flow_type", "screenshot_pipeline").strip().lower()
    validation_error = _validate_run_inputs(mode, flow_type)
    if validation_error:
        return _render_live_demo(result=None, error=validation_error, preferred_flow=flow_type)

    config_errors = _validate_live_demo_config(mode, flow_type)
    if get_config().strict_config_validation and config_errors:
        return _render_live_demo(
            result=None,
            error="Configuration validation failed: " + " | ".join(config_errors),
            preferred_flow=flow_type,
        )

    if not _run_lock.acquire(blocking=False):
        return _render_live_demo(
            result=None,
            error="A demo run is already in progress. Please wait for it to finish and try again.",
            preferred_flow=flow_type,
        )

    try:
        run_dir, saved_path = _prepare_upload_for_flow(flow_type)
        run_id = uuid.uuid4().hex
        result = _run_selected_flow(mode, flow_type, run_dir, saved_path, run_id)
        if get_config().telemetry_enabled:
            sync_telemetry = RunTelemetry(get_config().telemetry_dir, run_id=run_id, flow_type=flow_type, mode=mode)
            sync_telemetry.mark_stage("Completed", "Synchronous run completed")
            result["telemetry"] = sync_telemetry.finalize(status="completed")
        return _render_live_demo(result=result, error=None, preferred_flow=flow_type)
    except ValueError as exc:
        return _render_live_demo(result=None, error=str(exc), preferred_flow=flow_type)
    except Exception:
        traceback.print_exc()
        return _render_live_demo(result=None, error=_user_facing_run_error(), preferred_flow=flow_type)
    finally:
        if _run_lock.locked():
            _run_lock.release()


@app.post("/run-demo-async")
def run_demo_async():
    mode = _resolve_requested_mode()
    flow_type = request.form.get("flow_type", "screenshot_pipeline").strip().lower()
    validation_error = _validate_run_inputs(mode, flow_type)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    config_errors = _validate_live_demo_config(mode, flow_type)
    if get_config().strict_config_validation and config_errors:
        return jsonify({"ok": False, "error": "Configuration validation failed", "details": config_errors}), 400

    if _run_lock.locked():
        return jsonify({"ok": False, "error": "A demo run is already in progress."}), 409

    try:
        run_dir, saved_path = _prepare_upload_for_flow(flow_type)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    run_id = uuid.uuid4().hex
    _set_run_state(
        run_id,
        status="queued",
        stage="Queued",
        message="Run accepted and queued.",
        mode=mode,
        flow_type=flow_type,
        started_at=time.time(),
        last_progress_at=time.time(),
    )

    thread = threading.Thread(
        target=_execute_async_run,
        args=(run_id, mode, flow_type, run_dir, saved_path),
        daemon=True,
    )
    thread.start()

    return jsonify({"ok": True, "run_id": run_id})


@app.get("/run-status/<run_id>")
def run_status(run_id: str):
    state = _get_run_state(run_id)
    if state is None:
        return jsonify({"ok": False, "error": "Run id not found."}), 404
    return jsonify(
        {
            "ok": True,
            "run_id": run_id,
            "status": state.get("status", "unknown"),
            "stage": state.get("stage", "Unknown"),
            "message": state.get("message", ""),
            "flow_type": state.get("flow_type", ""),
            "mode": state.get("mode", ""),
        }
    )


@app.get("/telemetry/latest")
def telemetry_latest():
    latest = read_latest_telemetry(get_config().telemetry_dir)
    if latest is None:
        return jsonify({"ok": False, "error": "No telemetry available yet."}), 404
    return jsonify({"ok": True, "telemetry": latest})


@app.get("/telemetry-dashboard")
def telemetry_dashboard() -> Response:
    latest = read_latest_telemetry(get_config().telemetry_dir) or {}
    rows = "".join(
        f"<tr><td>{html.escape(str(item.get('stage', '')))}</td><td>{html.escape(str(item.get('duration_seconds', '')))}</td><td>{html.escape(str(item.get('message', '')))}</td></tr>"
        for item in latest.get("stages", [])
    )
    if not rows:
        rows = "<tr><td colspan='3'>No telemetry captured yet.</td></tr>"

    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Run Telemetry Dashboard</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;background:#f5f9fc;margin:24px;}"
        "table{width:100%;border-collapse:collapse;background:#fff;}th,td{padding:10px;border:1px solid #d7e3ef;text-align:left;}"
        "th{background:#eef5fc;} .meta{margin-bottom:12px;color:#1f3b52;}</style></head><body>"
        f"<h1>Run Telemetry Dashboard</h1><p class='meta'>Run ID: {html.escape(str(latest.get('run_id', 'N/A')))} | Flow: {html.escape(str(latest.get('flow_type', 'N/A')))} | Status: {html.escape(str(latest.get('status', 'N/A')))}</p>"
        "<table><thead><tr><th>Stage</th><th>Duration (s)</th><th>Message</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )
    return Response(body, mimetype="text/html")


@app.get("/run-result/<run_id>")
def run_result(run_id: str) -> str:
    state = _get_run_state(run_id)
    if state is None:
        abort(404)

    status = state.get("status")
    if status == "completed":
        flow_type = str((state.get("result") or {}).get("flow_type") or "").strip().lower()
        return _render_live_demo(result=state.get("result"), error=None, preferred_flow=flow_type)
    if status == "failed":
        flow_type = str(state.get("flow_type") or "").strip().lower()
        return _render_live_demo(
            result=None,
            error=state.get("error", "Demo run failed."),
            preferred_flow=flow_type,
        )

    flow_type = str(state.get("flow_type") or "").strip().lower()
    return _render_live_demo(
        result=None,
        error=(
            "Demo run is still in progress. "
            f"Current stage: {state.get('stage', 'Unknown')} - {state.get('message', '')}"
        ),
        preferred_flow=flow_type,
    )


@app.get("/emulator-frame")
def emulator_frame() -> Response:
    frame = _capture_emulator_frame_png()
    if frame is not None:
        return Response(
            frame,
            mimetype="image/png",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )

    placeholder_svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'>"
        "<rect width='100%' height='100%' fill='#0f172a'/>"
        "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
        "fill='#e2e8f0' font-size='18' font-family='Segoe UI, sans-serif'>"
        "Emulator frame unavailable. Ensure adb device is connected."
        "</text></svg>"
    )
    return Response(
        placeholder_svg,
        mimetype="image/svg+xml",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/artifacts/<path:subpath>")
def serve_artifact(subpath: str):
    normalized = Path(subpath)
    # Backward compatibility: allow both
    # - /artifacts/<relative-to-artifacts>
    # - /artifacts/artifacts/<relative-to-artifacts>
    parts = normalized.parts
    if parts and parts[0] == "artifacts":
        normalized = Path(*parts[1:]) if len(parts) > 1 else Path()

    absolute_path = (ARTIFACTS_ROOT / normalized).resolve()
    if not str(absolute_path).startswith(str(ARTIFACTS_ROOT.resolve())):
        abort(403)
    if not absolute_path.exists() or not absolute_path.is_file():
        abort(404)
    return send_from_directory(str(absolute_path.parent), absolute_path.name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
