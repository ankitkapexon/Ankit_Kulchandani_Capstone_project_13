"""Reporter Agent — runs Appium pytest scripts, saves HTML report to a timestamped
directory, and opens it in the default browser."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional
import html

logger = logging.getLogger(__name__)


class ReporterAgent:
    """Execute generated Appium test scripts via pytest, save an HTML report to a
    timestamped directory under ``artifacts/test_execution_reports/``, and open
    the report in the default browser.

    Can be used standalone::

        agent = ReporterAgent()
        report_path = agent.run()

    Or triggered at the end of the full pipeline::

        agent = ReporterAgent(project_root="/path/to/project")
        agent.run(open_browser=True)
    """

    def __init__(self, project_root: Optional[Path | str] = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self.scripts_dir = self.project_root / "artifacts" / "generated_appium_scripts"
        self.reports_base = self.project_root / "artifacts" / "test_execution_reports"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        scripts_dir: Optional[Path | str] = None,
        open_browser: bool = True,
    ) -> Path:
        """Run pytest over the generated Appium scripts, save an HTML report, and
        optionally open it in the browser.

        Args:
            scripts_dir: Override the folder containing test scripts.
            open_browser: Whether to open the HTML report automatically.

        Returns:
            Path to the generated HTML report file.
        """
        source = Path(scripts_dir or self.scripts_dir)
        if not source.exists():
            raise FileNotFoundError(f"Scripts directory not found: {source}")

        # Timestamped output folder
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = self.reports_base / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        report_html = run_dir / "report.html"

        logger.info("[ReporterAgent] Running tests from: %s", source)
        logger.info("[ReporterAgent] Saving report to: %s", report_html)
        print(f"[ReporterAgent] Running tests from: {source}")
        print(f"[ReporterAgent] Saving report to:   {report_html}")

        preflight_issue = self._preflight_issue()
        if preflight_issue:
            self._write_preflight_report(report_html, preflight_issue)
            exit_code = 0
            status = "SKIPPED (PRECHECK)"
            logger.warning("[ReporterAgent] Preflight issue: %s", preflight_issue)
            print(f"[ReporterAgent] Preflight issue: {preflight_issue}")
            print("[ReporterAgent] Test execution skipped. A diagnostic HTML report was generated.")
        else:
            exit_code = self._run_pytest(source, report_html)
            status = "PASSED" if exit_code == 0 else "FAILED/ERRORS"

        logger.info("[ReporterAgent] Test run complete — %s (exit code %d)", status, exit_code)
        print(f"[ReporterAgent] Test run complete — {status} (exit code {exit_code})")
        print(f"[ReporterAgent] Report: {report_html}")

        if open_browser and report_html.exists():
            webbrowser.open(report_html.as_uri())

        return report_html

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_pytest(self, scripts_dir: Path, report_html: Path) -> int:
        """Invoke pytest as a subprocess and return the exit code."""
        cmd = [
            sys.executable, "-m", "pytest",
            str(scripts_dir),
            f"--html={report_html}",
            "--self-contained-html",
            "-v",                        # verbose: show each test name
            "--tb=long",                 # full traceback on failure
            "--log-cli-level=INFO",      # stream logger.info() calls live
            "--log-cli-format=%(asctime)s [%(levelname)s] %(message)s",
            "--capture=tee-sys",         # capture stdout/stderr AND show in report
        ]
        env = dict(os.environ)
        env["SINGLE_APP_SESSION"] = "1"
        result = subprocess.run(cmd, cwd=str(self.project_root), env=env)
        return result.returncode

    def _preflight_issue(self) -> Optional[str]:
        """Return a human-readable preflight issue, or None when execution can proceed."""
        if not self._has_connected_android_device():
            return (
                "No connected Android device/emulator was found. "
                "Connect a device or start an emulator (adb devices should list at least one 'device')."
            )
        return None

    def _has_connected_android_device(self) -> bool:
        """Check whether adb sees at least one online Android device."""
        adb_candidates = ["adb"]

        local_sdk = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"
        if local_sdk.exists():
            adb_candidates.append(str(local_sdk))

        for adb_cmd in adb_candidates:
            try:
                proc = subprocess.run(
                    [adb_cmd, "devices"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception:
                continue

            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            for line in output.splitlines():
                normalized = line.strip().lower()
                if not normalized or normalized.startswith("list of devices"):
                    continue
                if normalized.endswith("\tdevice"):
                    return True

        return False

    def _write_preflight_report(self, report_html: Path, reason: str) -> None:
        """Write a lightweight HTML report explaining why test execution was skipped."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_reason = html.escape(reason)
        body = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Appium Preflight Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; background: #f7f9fb; color: #1f2937; margin: 24px; }}
    .card {{ max-width: 920px; background: #fff; border: 1px solid #d8e1eb; border-radius: 12px; padding: 18px; box-shadow: 0 6px 18px rgba(0,0,0,0.06); }}
    h1 {{ margin: 0 0 8px 0; font-size: 1.4rem; }}
    .badge {{ display: inline-block; background: #f59e0b; color: #111827; border-radius: 999px; padding: 4px 10px; font-size: 0.78rem; font-weight: 700; }}
    .reason {{ margin-top: 14px; padding: 12px; background: #fff7ed; border-left: 4px solid #f59e0b; border-radius: 6px; }}
    ul {{ margin-top: 10px; }}
    code {{ background: #eef2f7; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Appium Test Execution Skipped</h1>
    <div class=\"badge\">Preflight Check</div>
    <p>Generated at: {timestamp}</p>
    <div class=\"reason\"><strong>Reason:</strong> {safe_reason}</div>
    <h2>How to Fix</h2>
    <ul>
      <li>Start an Android emulator or connect a physical Android device.</li>
      <li>Verify with <code>adb devices</code> that a device is listed with state <code>device</code>.</li>
      <li>Re-run the pipeline to execute tests and generate the full pytest HTML report.</li>
    </ul>
  </div>
</body>
</html>
"""
        report_html.write_text(body, encoding="utf-8")
