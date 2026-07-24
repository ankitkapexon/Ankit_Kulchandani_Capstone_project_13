"""Pipeline entry-point: run the ReporterAgent standalone.

Usage:
    python pipelines/reporter.py
    python pipelines/reporter.py artifacts/generated_appium_scripts --no-browser
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.reporter_agent import ReporterAgent


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    scripts_dir = args[0] if args else None
    open_browser = "--no-browser" not in args

    agent = ReporterAgent(project_root=ROOT)
    report_path = agent.run(scripts_dir=scripts_dir, open_browser=open_browser)
    print(f"Done. Report → {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
