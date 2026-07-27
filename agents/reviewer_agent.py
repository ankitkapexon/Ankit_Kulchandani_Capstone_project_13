import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """Review generated Appium scripts for common best-practice issues."""

    def __init__(self, project_root: Optional[Path | str] = None) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[1])
        self.input_dir = self.project_root / "artifacts" / "generated_appium_scripts"
        self.output_dir = self.project_root / "artifacts" / "review_reports"

    def review_scripts(self, input_dir: Optional[Path | str] = None, output_dir: Optional[Path | str] = None) -> List[Path]:
        """Review every generated Appium script and write a Markdown report for each."""
        source_dir = Path(input_dir or self.input_dir)
        destination_dir = Path(output_dir or self.output_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        reviewed_files: List[Path] = []
        for script_path in sorted(source_dir.glob("*.py")):
            report_path = self._review_script(script_path, destination_dir)
            logger.info("[ReviewerAgent] Reviewed script: '%s' → %s", script_path.name, report_path.name)
            reviewed_files.append(report_path)

        print(f"Reviewed {len(reviewed_files)} scripts successfully.")
        return reviewed_files

    def _review_script(self, script_path: Path, output_dir: Path) -> Path:
        """Inspect one script and write a markdown review report."""
        content = script_path.read_text(encoding="utf-8")
        issues = self._collect_issues(content)
        report_path = output_dir / f"{script_path.stem}_review.md"
        report_path.write_text(self._format_report(script_path, content, issues), encoding="utf-8")
        return report_path

    def _collect_issues(self, content: str) -> List[Tuple[str, str]]:
        """Collect review findings as (category, message) tuples."""
        issues: List[Tuple[str, str]] = []

        if re.search(r"\bsleep\s*\(", content):
            issues.append(("Hardcoded sleep", "The script uses time.sleep(), which can make tests flaky."))

        if re.search(r"find_element\s*\(\s*['\"]//", content):
            issues.append(("XPath usage", "XPath locators were detected; prefer UiAutomator2 selectors instead."))

        if not re.search(r"WebDriverWait", content):
            issues.append(("Missing WebDriverWait", "The script does not use WebDriverWait for explicit waits."))

        if not re.search(r"AppiumBy", content):
            issues.append(("Missing AppiumBy", "The script does not import or use AppiumBy."))

        return issues

    def _count_repeated_code_blocks(self, content: str) -> int:
        """Estimate repeated inline interaction code in test methods only."""
        in_test = False
        interaction_lines: List[str] = []

        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()

            if re.match(r"def\s+test_", stripped):
                in_test = True
                continue

            # Exit when another method begins at class indentation level.
            if in_test and re.match(r"def\s+", stripped) and not re.match(r"def\s+test_", stripped):
                in_test = False

            if not in_test:
                continue

            if stripped.startswith("self.healing_driver.") or stripped.startswith("self.driver."):
                interaction_lines.append(stripped)

        return sum(1 for line in set(interaction_lines) if interaction_lines.count(line) > 1)

    def _has_inline_tap_actions(self, content: str) -> bool:
        """Detect inline tap/click calls inside test methods instead of helper usage."""
        in_test = False
        for raw_line in content.splitlines():
            stripped = raw_line.strip()

            if re.match(r"def\s+test_", stripped):
                in_test = True
                continue

            if in_test and re.match(r"def\s+", stripped) and not re.match(r"def\s+test_", stripped):
                in_test = False

            if in_test and (
                "self.healing_driver.tap_element(" in stripped
                or ".click(" in stripped
            ):
                return True

        return False

    def _format_report(self, script_path: Path, content: str, issues: List[Tuple[str, str]]) -> str:
        """Render a Markdown review report for one script."""
        lines = [
            f"# Review Report: {script_path.name}",
            "",
            "## Summary",
            "",
            f"- Script reviewed: {script_path.name}",
            f"- Issues detected: {len(issues)}",
            "",
            "## Findings",
            "",
        ]

        if issues:
            for category, message in issues:
                lines.append(f"- **{category}**: {message}")
        else:
            lines.append("- No actionable issues detected.")

        lines.extend([
            "",
            "## Notes",
            "",
            "- Prefer UiAutomator2 selectors over XPath.",
            "- Use WebDriverWait with explicit waits instead of hardcoded sleeps.",
            "- Keep page actions in helper methods to reduce repetition.",
            "- Avoid tapping static text or image elements unless the UI requires it.",
        ])

        return "\n".join(lines) + "\n"


def main() -> List[Path]:
    """Review every generated Appium script and write Markdown reports."""
    agent = ReviewerAgent()
    agent.output_dir.mkdir(parents=True, exist_ok=True)
    return agent.review_scripts()


if __name__ == "__main__":
    main()
