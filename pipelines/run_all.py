"""Standard end-to-end pipeline entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.app_config import get_config
from pipelines.orchestration_helpers import parse_pipeline_args
from pipelines.pipeline_composer import run_pipeline
from pipelines.stage_runners import StageFeatureFlags
from services.prompt_manager import PromptManager


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = parse_pipeline_args(args, "Usage: python pipelines/run_all.py <screenshots_folder> [--no-browser]")
    if parsed is None:
        return 2

    screenshots_dir, open_browser = parsed
    config = get_config()
    prompt_manager = PromptManager(ROOT)

    feature_flags = StageFeatureFlags(
        use_langchain_vision=False,
        use_multi_strategy_locator=False,
        use_self_healing_generator=False,
        enforce_non_empty_elements=False,
    )

    report_path = run_pipeline(
        project_root=ROOT,
        config=config,
        prompt_manager=prompt_manager,
        screenshots_dir=screenshots_dir,
        open_browser=open_browser,
        feature_flags=feature_flags,
    )

    print(f"\nAll steps complete. Execution report -> {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
