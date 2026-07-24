"""conftest.py — pytest-html report customisation and logging setup."""

from __future__ import annotations

import datetime
import logging
import platform
import sys
from pathlib import Path

import pytest

# ── Logging configuration ─────────────────────────────────────────────────────
# Do NOT call logging.basicConfig() here — pytest manages its own log handlers.
# Log level and format are controlled via --log-cli-level in reporter_agent.py.
# This prevents duplicate log entries in the HTML report.
logger = logging.getLogger(__name__)


# ── Environment table shown at top of report ──────────────────────────────────

def pytest_configure(config):
    config._metadata = {
        "Project": "Mobile Test Generator — Capstone",
        "Platform": platform.system() + " " + platform.release(),
        "Python": sys.version.split()[0],
        "Appium Server": "http://127.0.0.1:4723",
        "App Package": "com.saucelabs.mydemoapp.android",
        "Run Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── Report title ──────────────────────────────────────────────────────────────

@pytest.hookimpl(optionalhook=True)
def pytest_html_report_title(report):
    report.title = "Appium Test Execution Report — Mobile Test Generator"


# ── Custom CSS injected into the self-contained HTML ─────────────────────────

@pytest.hookimpl(optionalhook=True)
def pytest_html_results_summary(prefix, summary, postfix):
    prefix.extend([
        "<style>"
        "body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; color: #2c3e50; }"
        "h1 { background: #2c3e50; color: #fff; padding: 16px 24px; border-radius: 6px; }"
        "#environment td, #environment th { padding: 8px 14px; border: 1px solid #dce1e7; }"
        "#environment th { background: #34495e; color: #fff; }"
        "#environment tr:nth-child(even) { background: #eaf0fb; }"
        ".passed  { color: #27ae60; font-weight: bold; }"
        ".failed  { color: #e74c3c; font-weight: bold; }"
        ".error   { color: #e67e22; font-weight: bold; }"
        "td.col-name { font-family: monospace; font-size: 0.9em; }"
        "td.col-duration { color: #7f8c8d; }"
        ".summary-passes  { background:#eafaf1; border-left:4px solid #27ae60; padding:8px 16px; border-radius:4px; margin:4px 0; }"
        ".summary-failures { background:#fdedec; border-left:4px solid #e74c3c; padding:8px 16px; border-radius:4px; margin:4px 0; }"
        "</style>"
    ])
