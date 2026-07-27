from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import requests


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
LEGACY_MAP_PATH = Path("scripts/legacy_powershell_tasks.json")


def _find_first_screenshot(root: Path) -> Path | None:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            return path
    return None


def _extract_report_path(html: str) -> str:
    match = re.search(r"/artifacts/[^\"']*report\.html", html)
    if match:
        return match.group(0)
    return "REPORT_PATH=NOT_FOUND"


def _python_exe() -> str:
    venv_py = Path(".venv/Scripts/python.exe")
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _run_cmd(command: str, env: dict[str, str] | None = None) -> int:
    print(f"RUN={command}")
    completed = subprocess.run(command, shell=True, env=env, check=False)
    return completed.returncode


def _run_many(commands: list[str], env: dict[str, str] | None = None) -> int:
    code = 0
    for command in commands:
        command = command.strip()
        if not command:
            continue
        code = _run_cmd(command, env=env)
        if code != 0:
            return code
    return code


def _kill_processes_by_commandline_fragment(fragment: str) -> int:
    try:
        probe = subprocess.run(
            ["wmic", "process", "where", f"CommandLine like '%{fragment}%'", "get", "ProcessId"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("STOPPED=0")
        return 0

    pids = []
    for line in probe.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(line)

    killed = 0
    for pid in pids:
        if pid == str(os.getpid()):
            continue
        rc = subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True, check=False)
        if rc.returncode == 0:
            killed += 1
    print(f"STOPPED={killed}")
    return 0


def _check_page(url: str) -> tuple[int | None, str]:
    try:
        resp = requests.get(url, timeout=15)
        return resp.status_code, resp.text
    except Exception as exc:
        print(f"SERVER_ERROR={exc}")
        return None, ""


def _find_images(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]


def _copy_named_screens(names: list[str], run_dir: Path) -> None:
    src_dir = Path("artifacts/input_screenshots")
    if run_dir.exists():
        for p in run_dir.rglob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    files = [p for p in src_dir.glob("*") if p.is_file()]
    for name in names:
        match = next((f for f in files if f.stem.lower() == name.lower()), None)
        if match:
            out = run_dir / match.name
            out.write_bytes(match.read_bytes())
            print(f"ADDED={match.name}")
        else:
            print(f"MISSING={name}")


def _run_async_real_once() -> int:
    root = Path("artifacts/input_screenshots")
    images = _find_images(root)
    if not images:
        print("NO_SCREENSHOT_FOUND")
        return 0
    shot = images[0]
    print(f"USING={shot.resolve()}")
    with shot.open("rb") as fh:
        resp = requests.post(
            "http://127.0.0.1:8080/run-demo-async",
            data={"mode": "real", "flow_type": "screenshot_pipeline"},
            files={"screenshot": (shot.name, fh, "application/octet-stream")},
            timeout=120,
        )
    print(f"HTTP={resp.status_code}")
    print(resp.text)
    return 0 if resp.status_code == 200 else 1


def _cleanup_target_dir() -> Path:
    return Path(str(Path.cwd()) + "__main_cleanup")


def _print_cleanup_candidate_files(target: Path) -> None:
    name_re = re.compile(r"live_demo|demo|run_all_enhanced|pipeline_composer|stage_runners", re.IGNORECASE)
    ext_allow = {".py", ".md", ".txt", ".html", ".yml", ".yaml", ".json"}
    for f in target.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in ext_allow:
            continue
        rel = str(f.relative_to(target))
        if name_re.search(f.name) or "web\\templates" in rel.replace("/", "\\"):
            print(str(f))


def _run_cleanup_check(broad: bool = False) -> int:
    target = _cleanup_target_dir()
    if not target.exists():
        print("MISSING_PATH")
        print(str(target))
        return 0

    print("EXISTS_PATH")
    print(str(target))

    print("\nTOP_LEVEL:")
    for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        print(item.name)

    if broad:
        print("\nFILES_UNDER_TARGET:")
        for f in target.rglob("*"):
            if f.is_file():
                print(str(f))
        print("\nBROAD_CONTENT_HITS:")
        patterns = ["live_demo", "live demo", "flask", "run-demo", "run_all_enhanced", "pipeline_composer", "stage_runners", "demo"]
        ext_allow = {".py", ".md", ".txt", ".html", ".yml", ".yaml", ".json"}
        for f in target.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in ext_allow:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat in patterns:
                if re.search(re.escape(pat), text, flags=re.IGNORECASE):
                    print(f"{f}: {pat}")
                    break
        return 0

    print("\nCANDIDATE_FILES:")
    _print_cleanup_candidate_files(target)
    return 0


def _compile_paths(paths: list[Path]) -> int:
    existing = [str(p) for p in paths if p.exists()]
    missing = [str(p) for p in paths if not p.exists()]
    for p in missing:
        print(f"MISSING={p}")
    if not existing:
        print("COMPILE_SKIP_NO_EXISTING_FILES")
        return 0
    rc = subprocess.run([_python_exe(), "-m", "py_compile", *existing], check=False).returncode
    print("COMPILE_OK" if rc == 0 else f"COMPILE_FAIL={rc}")
    return rc


def _verify_live_demo_run_scope() -> int:
    response_file = "artifacts/live_demo_check.html"
    rc = cmd_run_demo(
        argparse.Namespace(
            server="http://127.0.0.1:8080",
            mode="mock",
            flow_type="screenshot_pipeline",
            screenshot_root="artifacts/input_screenshots",
            timeout=180,
            response_file=response_file,
        )
    )
    if rc != 0:
        return rc
    html = Path(response_file).read_text(encoding="utf-8", errors="ignore") if Path(response_file).exists() else ""
    print("HAS_MANUAL_TESTCASE=YES" if "manual_testcases" in html else "HAS_MANUAL_TESTCASE=NO")
    print("HAS_GENERATED_SCRIPT=YES" if "generated_appium_scripts" in html else "HAS_GENERATED_SCRIPT=NO")
    print("HAS_REPORT=YES" if "test_execution_reports" in html else "HAS_REPORT=NO")
    return 0


def _poll_run_status(run_id: str, attempts: int = 90, interval: float = 2.0) -> int:
    final = None
    for _ in range(attempts):
        payload = requests.get(f"http://127.0.0.1:8080/run-status/{run_id}", timeout=20).json()
        print(f"POLL={payload.get('status')}:{payload.get('stage')}")
        if payload.get("status") in {"completed", "failed"}:
            final = payload
            break
        time.sleep(interval)
    print("FINAL=" + json.dumps(final or {}))
    return 0


def _is_plain_shell_script(script: str) -> bool:
    banned = [
        "$", "Get-ChildItem", "Invoke-WebRequest", "Where-Object", "Write-Output", "Get-CimInstance",
        "Start-Process", "Test-Path", "Remove-Item", "New-Item", "Select-String", "ConvertFrom-Json",
        "Start-Sleep", "Join-Path", "Resolve-Path", "ConvertTo-Json", "Invoke-RestMethod",
    ]
    return not any(token in script for token in banned)


def _run_legacy_by_label(label: str) -> int:
    legacy = {}
    if LEGACY_MAP_PATH.exists():
        legacy = json.loads(LEGACY_MAP_PATH.read_text(encoding="utf-8"))
    script = legacy.get(label, "")

    # Dedicated non-PowerShell implementations for historically flaky tasks.
    if label in {"run-live-demo-mock-now-retry", "run-live-demo-mock-now", "run-live-demo-via-curl", "run-live-demo-via-iwr"}:
        return cmd_run_demo(
            argparse.Namespace(
                server="http://127.0.0.1:8080",
                mode="mock",
                flow_type="screenshot_pipeline",
                screenshot_root="artifacts/input_screenshots",
                timeout=180,
                response_file="artifacts/live_demo_last_response.html",
            )
        )

    if label in {"py-compile-live-demo", "compile-live-demo-dual-flow", "compile-live-demo-after-badges", "validate-live-demo-filter-change", "validate-live-demo-snapshot-filter"}:
        rc = subprocess.run([_python_exe(), "-m", "py_compile", "live_demo.py"], check=False).returncode
        print("LIVE_DEMO_OK" if rc == 0 else f"LIVE_DEMO_FAIL={rc}")
        return rc

    if label == "py-compile-pipeline-composer":
        rc = subprocess.run([_python_exe(), "-m", "py_compile", "pipelines/pipeline_composer.py"], check=False).returncode
        print("PIPELINE_COMPOSER_OK" if rc == 0 else f"PIPELINE_COMPOSER_FAIL={rc}")
        return rc

    if label == "validate-generator-syntax":
        rc = subprocess.run([_python_exe(), "-m", "py_compile", "agents/self_healing_appium_generator.py"], check=False).returncode
        print("GENERATOR_OK" if rc == 0 else f"GENERATOR_FAIL={rc}")
        return rc

    if label in {"recompile-generator-after-stability-fix", "recompile-generator-after-anchor-fix", "recompile-generator-after-login-state-fix"}:
        rc = subprocess.run([_python_exe(), "-m", "py_compile", "agents/self_healing_appium_generator.py"], check=False).returncode
        print("COMPILE_OK" if rc == 0 else f"COMPILE_FAIL={rc}")
        return rc

    if label in {"verify-jinja-template-parse", "verify-jinja-template-parse-retry", "verify-jinja-template-heredoc"}:
        code = "from jinja2 import Environment, FileSystemLoader; env=Environment(loader=FileSystemLoader('web/templates')); env.get_template('live_demo.html'); print('TEMPLATE_OK')"
        return subprocess.run([_python_exe(), "-c", code], check=False).returncode

    if label in {"check-cleanup-live-demo-flow", "check-cleanup-live-demo-flow-retry"}:
        return _run_cleanup_check(broad=False)

    if label == "check-cleanup-broad-sweep":
        return _run_cleanup_check(broad=True)

    if label in {"stop-live-demo-processes", "restart-live-demo-new-ui", "restart-live-demo-after-gitkeep-fix", "restart-live-demo-after-delta-filter"}:
        return _kill_processes_by_commandline_fragment("live_demo.py")

    if label == "start-live-demo-server-now":
        exe = _python_exe()
        creationflags = 0x00000008 if os.name == "nt" else 0
        subprocess.Popen([exe, "live_demo.py"], creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("LIVE_DEMO_STARTED=YES")
        return 0

    if label in {"verify-server-still-up", "check-live-demo-server", "verify-live-demo-new-ui-running", "verify-live-demo-updated-ui", "verify-removed-stats-section", "inspect-live-demo-body-tag", "inspect-live-demo-markers"}:
        status, html = _check_page("http://127.0.0.1:8080/")
        if status is None:
            return 1
        print(f"HTTP={status}")
        if "compact" in label or "updated-ui" in label or "new-ui" in label:
            print("TOGGLE_PRESENT=YES" if "Show compact filenames only" in html else "TOGGLE_PRESENT=NO")
        if label == "verify-removed-stats-section":
            old = bool(re.search(r"Input Type|Output Scope|Single Screenshot|Enhanced Flow", html))
            print("OLD_STATS_PRESENT=YES" if old else "OLD_STATS_PRESENT=NO")
            print("NEW_PAGE_LOADED=YES" if "Live Demo: Screenshot to Test Automation" in html else "NEW_PAGE_LOADED=NO")
        if label == "inspect-live-demo-markers":
            m = re.search(r"<body[^>]*>", html)
            print(f"BODY_TAG={m.group(0)}" if m else "BODY_TAG=NOT_FOUND")
            print("NEW_UI_FONT=YES" if "Space Grotesk" in html else "NEW_UI_FONT=NO")
        if label == "inspect-live-demo-body-tag":
            print("\n".join(html.splitlines()[:40]))
        return 0

    if label == "verify-live-demo-run-scope":
        return _verify_live_demo_run_scope()

    if label == "clean-manual-testcase-history":
        d = Path("artifacts/manual_testcases")
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)
        print(f"MANUAL_TESTCASE_FILES_NOW={len([x for x in d.glob('*') if x.is_file()])}")
        return 0

    if label == "clean-generated-scripts-history":
        d = Path("artifacts/generated_appium_scripts")
        d.mkdir(parents=True, exist_ok=True)
        for f in d.rglob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)
        print(f"GENERATED_SCRIPT_FILES_NOW={len([x for x in d.rglob('*') if x.is_file()])}")
        return 0

    if label == "precheck-emulator-and-appium":
        cmd_adb_devices(argparse.Namespace())
        cmd_check_appium(argparse.Namespace(url="http://127.0.0.1:4723/status", timeout=10))
        print("VISION_AGENT_PROVIDER=" + os.getenv("VISION_AGENT_PROVIDER", ""))
        print("TESTCASE_AGENT_PROVIDER=" + os.getenv("TESTCASE_AGENT_PROVIDER", ""))
        print("OPENAI_API_KEY_SET=" + str(bool(os.getenv("OPENAI_API_KEY"))))
        return 0

    if label == "run-one-shot-emulator-demo":
        src = _find_first_screenshot(Path("artifacts/input_screenshots"))
        if not src:
            print("NO_SCREENSHOT_FOUND")
            return 1
        run_dir = Path("artifacts/input_screenshots/tmp_one_run")
        run_dir.mkdir(parents=True, exist_ok=True)
        for f in run_dir.rglob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)
        out = run_dir / src.name
        out.write_bytes(src.read_bytes())
        env = os.environ.copy()
        env["VISION_AGENT_PROVIDER"] = "mock"
        env["TESTCASE_AGENT_PROVIDER"] = "mock"
        env["SINGLE_APP_SESSION"] = "1"
        return _run_many([f'"{_python_exe()}" pipelines/run_all_enhanced.py {run_dir} --no-browser'], env=env)

    if label in {
        "run-multi-screen-validation-demo",
        "run-multi-screen-validation-after-fix",
        "run-multi-screen-validation-after-stability-fix",
        "run-multi-screen-validation-after-anchor-fix",
        "run-multi-screen-validation-after-login-state-fix",
    }:
        dir_map = {
            "run-multi-screen-validation-demo": "tmp_validation_run",
            "run-multi-screen-validation-after-fix": "tmp_validation_run2",
            "run-multi-screen-validation-after-stability-fix": "tmp_validation_run3",
            "run-multi-screen-validation-after-anchor-fix": "tmp_validation_run4",
            "run-multi-screen-validation-after-login-state-fix": "tmp_validation_run5",
        }
        run_dir = Path("artifacts/input_screenshots") / dir_map[label]
        _copy_named_screens(["Cart", "Login", "Menu", "Product_detail", "Product_listing"], run_dir)
        env = os.environ.copy()
        env["VISION_AGENT_PROVIDER"] = "mock"
        env["TESTCASE_AGENT_PROVIDER"] = "mock"
        env["SINGLE_APP_SESSION"] = "1"
        return _run_many([f'"{_python_exe()}" pipelines/run_all_enhanced.py {run_dir} --no-browser'], env=env)

    if label == "inspect-latest-generated-and-reports":
        print("--- GENERATED SCRIPTS ---")
        for f in sorted(Path("artifacts/generated_appium_scripts").glob("*")):
            if f.is_file():
                print(f.name)
        print("--- LATEST TEST REPORT FOLDER ---")
        dirs = [d for d in Path("artifacts/test_execution_reports").glob("*") if d.is_dir()]
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        if dirs:
            latest = dirs[0]
            print(str(latest.resolve()))
            for f in latest.glob("*"):
                if f.is_file():
                    print(f.name)
        return 0

    if label == "inspect-latest-report-testids":
        dirs = [d for d in Path("artifacts/test_execution_reports").glob("*") if d.is_dir()]
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        if not dirs:
            print("NO_REPORT_DIR")
            return 0
        report = dirs[0] / "report.html"
        print(f"REPORT={report}")
        if not report.exists():
            print("REPORT_HTML_NOT_FOUND")
            return 0
        text = report.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if re.search(r"generated_appium_scripts/.*::Test", line):
                print(line.strip())
        return 0

    if label == "list-available-screenshots":
        for f in _find_images(Path("artifacts/input_screenshots")):
            print(str(f.resolve()))
        return 0

    if label == "find-key-screenshots-by-name":
        for f in _find_images(Path("artifacts/input_screenshots")):
            if re.search(r"login|menu|product|detail|listing|cart", f.stem, flags=re.IGNORECASE):
                print(f"{f.stem} | {f.resolve()}")
        return 0

    if label == "inspect-generated-flow-depth":
        print("--- TAP COUNTS ---")
        for f in Path("artifacts/generated_appium_scripts").glob("test_*_screen.py"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            print(f"{f.name} => tap_steps={text.count('self.tap(')}")
        print("--- TYPE COUNTS ---")
        for f in Path("artifacts/generated_appium_scripts").glob("test_*_screen.py"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            print(f"{f.name} => type_steps={text.count('self.type_text(')}")
        return 0

    if label == "compile-updated-scripts":
        return _compile_paths([
            Path("agents/self_healing_appium_generator.py"),
            Path("artifacts/generated_appium_scripts/test_product_detail_screen.py"),
        ])

    if label == "compile-generator-and-session-utils":
        return _compile_paths([
            Path("agents/self_healing_appium_generator.py"),
            Path("utils/shared_appium_session.py"),
        ])

    if label in {"poll-run-status-1b7076-ps", "poll-run-status-1b7076-ps2"}:
        return _poll_run_status("1b7076a052a44f138dbef319f404fbd1")

    if label == "stop-appium-node-processes-now":
        out = subprocess.run("netstat -ano | findstr :4723", shell=True, capture_output=True, text=True, check=False)
        pids = set()
        for line in out.stdout.splitlines():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
        killed = 0
        for pid in pids:
            rc = subprocess.run(["taskkill", "/F", "/PID", pid], check=False, capture_output=True, text=True)
            if rc.returncode == 0:
                killed += 1
        print(f"APPPIUM_STOPPED={killed}")
        return 0

    if label in {"run-screenshot-flow-after-login-fix", "run-screenshot-flow-after-login-fix-curl"}:
        return _run_async_real_once()

    # Generic fallback for git/python shell-like command sequences.
    if script and _is_plain_shell_script(script):
        commands = [c.strip() for c in script.split(";") if c.strip()]
        return _run_many(commands)

    print(f"UNMIGRATED_LABEL={label}")
    return 1


def cmd_run_demo(args: argparse.Namespace) -> int:
    screenshot_root = Path(args.screenshot_root)
    shot = _find_first_screenshot(screenshot_root)
    if shot is None:
        print("NO_SCREENSHOT_FOUND")
        return 0

    print(f"USING_SCREENSHOT={shot.resolve()}")

    endpoint = args.server.rstrip("/") + "/run-demo"
    with shot.open("rb") as fh:
        resp = requests.post(
            endpoint,
            data={"mode": args.mode, "flow_type": args.flow_type},
            files={"screenshot": (shot.name, fh, "application/octet-stream")},
            timeout=args.timeout,
        )

    print(f"HTTP_STATUS={resp.status_code}")

    content = resp.text
    if args.response_file:
        out = Path(args.response_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"RESPONSE_FILE={out}")

    report_path = _extract_report_path(content)
    if report_path.startswith("/artifacts/"):
        print(f"REPORT_PATH={report_path}")
    else:
        print(report_path)

    if "Demo run completed" in content:
        print("DEMO_STATUS=COMPLETED")
    else:
        print("DEMO_STATUS=UNKNOWN")

    return 0 if resp.status_code == 200 else 1


def cmd_http_status(args: argparse.Namespace) -> int:
    try:
        resp = requests.get(args.url, timeout=args.timeout)
        print(f"HTTP_STATUS={resp.status_code}")
        return 0
    except Exception as exc:
        print(f"HTTP_ERROR={exc}")
        return 1


def cmd_check_server(args: argparse.Namespace) -> int:
    try:
        resp = requests.get(args.url, timeout=args.timeout)
        print(f"SERVER_HTTP_STATUS={resp.status_code}")
        return 0
    except Exception as exc:
        print(f"SERVER_ERROR={exc}")
        return 1


def cmd_check_appium(args: argparse.Namespace) -> int:
    try:
        resp = requests.get(args.url, timeout=args.timeout)
        print(f"APPIUM_STATUS={resp.status_code}")
        return 0
    except Exception:
        print("APPIUM_STATUS=DOWN")
        return 1


def _iter_latest_files(root: Path, limit: int) -> Iterable[Path]:
    files = [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def cmd_list_artifacts(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.exists():
        print(f"MISSING_ARTIFACTS_ROOT={root}")
        return 1

    for file_path in _iter_latest_files(root, args.limit):
        timestamp = file_path.stat().st_mtime
        from datetime import datetime

        dt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        if args.detailed:
            print(f"{dt} | {file_path.resolve()}")
        else:
            print(f"{file_path.resolve()} | {dt}")
    return 0


def cmd_inspect_latest_report(args: argparse.Namespace) -> int:
    reports_root = Path(args.reports_root)
    report_files = [p for p in reports_root.rglob("report.html") if p.is_file()]
    if not report_files:
        print("NO_REPORT_FOUND")
        return 0

    report_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest = report_files[0]
    from datetime import datetime

    dt = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    print(f"LATEST_REPORT={latest.resolve()}")
    print(f"LATEST_REPORT_TIME={dt}")

    text = latest.read_text(encoding="utf-8", errors="ignore")
    for pattern in args.patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            print(f"MATCH={pattern}")
    return 0


def cmd_adb_devices(_: argparse.Namespace) -> int:
    completed = subprocess.run(["adb", "devices"], check=False)
    return completed.returncode


def cmd_run_label(args: argparse.Namespace) -> int:
    return _run_legacy_by_label(args.label)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portable project task runner")
    sub = parser.add_subparsers(dest="command", required=True)

    run_demo = sub.add_parser("run-demo")
    run_demo.add_argument("--server", default="http://127.0.0.1:8080")
    run_demo.add_argument("--mode", default="mock")
    run_demo.add_argument("--flow-type", default="screenshot_pipeline")
    run_demo.add_argument("--screenshot-root", default="artifacts/input_screenshots")
    run_demo.add_argument("--timeout", type=int, default=180)
    run_demo.add_argument("--response-file", default="artifacts/live_demo_last_response.html")
    run_demo.set_defaults(func=cmd_run_demo)

    check_server = sub.add_parser("check-server")
    check_server.add_argument("--url", default="http://127.0.0.1:8080/")
    check_server.add_argument("--timeout", type=int, default=10)
    check_server.set_defaults(func=cmd_check_server)

    check_appium = sub.add_parser("check-appium")
    check_appium.add_argument("--url", default="http://127.0.0.1:4723/status")
    check_appium.add_argument("--timeout", type=int, default=10)
    check_appium.set_defaults(func=cmd_check_appium)

    list_artifacts = sub.add_parser("list-artifacts")
    list_artifacts.add_argument("--root", default="artifacts")
    list_artifacts.add_argument("--limit", type=int, default=20)
    list_artifacts.add_argument("--detailed", action="store_true")
    list_artifacts.set_defaults(func=cmd_list_artifacts)

    inspect_report = sub.add_parser("inspect-latest-report")
    inspect_report.add_argument("--reports-root", default="artifacts/test_execution_reports")
    inspect_report.add_argument(
        "--patterns",
        nargs="+",
        default=["Total Tests", "Passed", "Failed", "Error", "Execution", "Status", "pytest", "Scenario", "Result"],
    )
    inspect_report.set_defaults(func=cmd_inspect_latest_report)

    adb_devices = sub.add_parser("check-adb")
    adb_devices.set_defaults(func=cmd_adb_devices)

    http_status = sub.add_parser("http-status")
    http_status.add_argument("--url", required=True)
    http_status.add_argument("--timeout", type=int, default=10)
    http_status.set_defaults(func=cmd_http_status)

    run_label = sub.add_parser("run-label")
    run_label.add_argument("--label", required=True)
    run_label.set_defaults(func=cmd_run_label)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
