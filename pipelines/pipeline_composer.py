"""Shared pipeline composition used by both entrypoint scripts."""

from __future__ import annotations

from pathlib import Path

from config.app_config import AppConfig
from pipelines.orchestration_helpers import reset_directory, reset_directories
from pipelines.stage_runners import (
    StageFeatureFlags,
    Step1VisionStage,
    Step2TestCaseStage,
    Step3LocatorStage,
    Step4AppiumStage,
    Step5ReviewStage,
    Step6ReportStage,
)
from services.prompt_manager import PromptManager


def run_pipeline(
    *,
    project_root: Path,
    config: AppConfig,
    prompt_manager: PromptManager,
    screenshots_dir: str,
    open_browser: bool,
    feature_flags: StageFeatureFlags,
) -> Path:
    """Run the full 6-stage pipeline and return report path."""

    reset_directory(config.ssm_output_dir)

    step1 = Step1VisionStage(config=config, prompt_manager=prompt_manager, feature_flags=feature_flags)
    ssm_results = step1.run(screenshots_dir)

    step2 = Step2TestCaseStage(config=config, prompt_manager=prompt_manager)
    step2.run(ssm_results)

    reset_directories([config.locator_output_dir, config.generated_scripts_dir, config.review_reports_dir])

    step3 = Step3LocatorStage(
        config=config,
        prompt_manager=prompt_manager,
        feature_flags=feature_flags,
        project_root=project_root,
    )
    step3.run()

    step4 = Step4AppiumStage(
        config=config,
        prompt_manager=prompt_manager,
        feature_flags=feature_flags,
        project_root=project_root,
    )
    step4.run()

    step5 = Step5ReviewStage(project_root=project_root)
    step5.run()

    step6 = Step6ReportStage(project_root=project_root)
    return step6.run(open_browser=open_browser)
