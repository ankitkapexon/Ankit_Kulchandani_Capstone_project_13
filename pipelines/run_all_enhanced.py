"""Enhanced end-to-end pipeline entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.enhanced_config import get_config
from pipelines.orchestration_helpers import parse_pipeline_args
from pipelines.pipeline_composer import run_pipeline
from pipelines.stage_runners import StageFeatureFlags
from services.prompt_manager import PromptManager


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    parsed = parse_pipeline_args(args, "Usage: python pipelines/run_all_enhanced.py <screenshots_folder> [--no-browser]")
    if parsed is None:
        return 2

    screenshots_dir, open_browser = parsed
    config = get_config()
    prompt_manager = PromptManager(ROOT)

    print("\n" + "=" * 70)
    print("ENHANCED MOBILE TEST GENERATOR PIPELINE")
    print("=" * 70)
    print("LangChain Integration: Enabled")
    print(f"Self-Healing: {config.self_healing_enabled}")
    print(f"AI Vision Healing: {config.ai_vision_healing}")
    print(f"Token Tracking: {config.enable_token_tracking}")
    print(f"LLM Caching: {config.enable_llm_cache}")
    print("=" * 70 + "\n")

    feature_flags = StageFeatureFlags(
        use_langchain_vision=True,
        use_multi_strategy_locator=True,
        use_self_healing_generator=True,
        enforce_non_empty_elements=True,
    )

    report_path = run_pipeline(
        project_root=ROOT,
        config=config,
        prompt_manager=prompt_manager,
        screenshots_dir=screenshots_dir,
        open_browser=open_browser,
        feature_flags=feature_flags,
    )

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"Execution Report: {report_path}")

    if config.healing_repository_enabled:
        healing_db = ROOT / "artifacts" / "healing_repository.db"
        if healing_db.exists():
            print(f"Healing Repository: {healing_db}")

    if config.enable_token_tracking:
        token_log = config.token_tracking_log
        if token_log.exists():
            print(f"Token Usage Log: {token_log}")

    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
