"""Reusable stage runners used by both standard and enhanced pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional

from config.app_config import AppConfig
from models.ssm import ScreenSemanticModel
from pipelines.contracts import SSMArtifact
from pipelines.orchestration_helpers import (
    list_image_files,
    write_json_timestamped,
    write_text_timestamped,
)
from services.prompt_manager import PromptManager


@dataclass(frozen=True)
class StageFeatureFlags:
    use_langchain_vision: bool
    use_multi_strategy_locator: bool
    use_self_healing_generator: bool
    enforce_non_empty_elements: bool


class Step1VisionStage:
    """Screenshots -> SSM JSON artifacts."""

    def __init__(
        self,
        config: AppConfig,
        prompt_manager: PromptManager,
        feature_flags: StageFeatureFlags,
    ) -> None:
        self.config = config
        self.prompt_manager = prompt_manager
        self.feature_flags = feature_flags

    def run(self, screenshots_dir: str | Path) -> list[SSMArtifact]:
        from agents.vision_agent import MockVisionAgent, OpenAIVisionAgent

        langchain_available = False
        LangChainVisionAgent = None
        if self.feature_flags.use_langchain_vision:
            try:
                from agents.langchain_vision_agent import LangChainVisionAgent as _LCVA

                LangChainVisionAgent = _LCVA
                langchain_available = True
            except ImportError:
                langchain_available = False

        vision_prompt = self.prompt_manager.load("vision")
        provider = self.config.vision_agent_provider

        if provider == "mock":
            vision_agent: Any = MockVisionAgent()
        else:
            vision_agent = None
            if self.feature_flags.use_langchain_vision and langchain_available and LangChainVisionAgent is not None:
                try:
                    vision_agent = LangChainVisionAgent(
                        prompt_template=vision_prompt,
                        model_name=self.config.openai_model,
                        enable_cache=self.config.enable_llm_cache,
                    )
                except Exception:
                    vision_agent = None

            if vision_agent is None:
                vision_agent = OpenAIVisionAgent(
                    prompt_template=vision_prompt,
                    model_name=self.config.openai_model,
                )

        image_files = list_image_files(screenshots_dir)
        results: list[SSMArtifact] = []

        for image in image_files:
            raw = vision_agent.analyze_image(str(image))
            if not isinstance(raw, dict):
                raw = {"screen_name": image.stem, "elements": []}

            if not raw.get("screen_name"):
                raw["screen_name"] = image.stem

            if self.feature_flags.enforce_non_empty_elements and not raw.get("elements"):
                raw["elements"] = self._default_elements_for_screen(str(raw.get("screen_name", image.stem)))
                metadata = raw.setdefault("metadata", {})
                metadata["auto_filled_elements"] = True
                metadata["auto_fill_reason"] = "pipeline_empty_elements_guard"

            ssm = ScreenSemanticModel.model_validate(raw)
            out_path = write_json_timestamped(
                output_dir=self.config.ssm_output_dir,
                prefix="ssm",
                logical_name=ssm.screen_name,
                payload_json=ssm.model_dump_json(indent=2),
            )
            results.append({"path": out_path, "data": ssm.model_dump()})

        return results

    def _default_elements_for_screen(self, screen_name: str) -> list[dict[str, Any]]:
        screen_key = (screen_name or "screen").lower()
        if "login" in screen_key:
            return [
                {"id": "username", "label": "Username", "type": "textfield", "actions": ["enter_text"]},
                {"id": "password", "label": "Password", "type": "textfield", "actions": ["enter_text"]},
                {"id": "login", "label": "Login", "type": "button", "actions": ["tap"]},
            ]
        if "cart" in screen_key:
            return [
                {"id": "cart_item", "label": "Cart Item", "type": "label", "actions": ["verify"]},
                {"id": "checkout", "label": "Checkout", "type": "button", "actions": ["tap"]},
            ]
        return [
            {"id": "primary_input", "label": "Primary Input", "type": "textfield", "actions": ["enter_text"]},
            {"id": "primary_action", "label": "Primary Action", "type": "button", "actions": ["tap"]},
        ]


class Step2TestCaseStage:
    """SSM JSON artifacts -> manual testcase files."""

    def __init__(self, config: AppConfig, prompt_manager: PromptManager) -> None:
        self.config = config
        self.prompt_manager = prompt_manager

    def run(self, ssm_results: list[SSMArtifact]) -> list[Path]:
        from agents.testcase_agent import create_testcase_agent

        prompt = self.prompt_manager.load("testcase")
        agent = create_testcase_agent(provider=self.config.testcase_agent_provider, prompt_template=prompt)

        output_paths: list[Path] = []
        for item in ssm_results:
            ssm_data = item["data"]
            ssm_path = item["path"]
            result_text = agent.generate_from_ssm(ssm_data, filename=ssm_path.stem)
            result_text = self._ensure_minimum_testcases(result_text, ssm_data, minimum_cases=4)
            out_path = write_text_timestamped(
                output_dir=self.config.manual_testcases_dir,
                prefix="manual_testcases",
                logical_name=ssm_path.stem,
                content=result_text,
            )
            output_paths.append(out_path)

        return output_paths

    def _ensure_minimum_testcases(self, result_text: str, ssm_data: dict[str, Any], minimum_cases: int) -> str:
        existing_count = self._count_manual_cases(result_text)
        if existing_count >= minimum_cases:
            return result_text

        missing = minimum_cases - existing_count
        supplement = self._build_supplemental_cases(ssm_data, start_index=existing_count + 1, count=missing)
        if not supplement:
            return result_text

        base = (result_text or "").rstrip()
        return f"{base}\n\n{supplement}\n"

    def _count_manual_cases(self, text: str) -> int:
        if not text:
            return 0
        pattern = re.compile(r"^\s*Test\s*Case\s*\d+\s*:", re.IGNORECASE)
        return sum(1 for line in text.splitlines() if pattern.match(line))

    def _build_supplemental_cases(self, ssm_data: dict[str, Any], start_index: int, count: int) -> str:
        screen_name = str(ssm_data.get("screen_name") or "Screen")
        screen_purpose = str(ssm_data.get("screen_purpose") or "")
        elements = [element for element in (ssm_data.get("elements") or []) if isinstance(element, dict)]

        labels = [str(el.get("label") or el.get("id") or "UI element") for el in elements]
        primary = labels[0] if labels else "primary UI element"
        secondary = labels[1] if len(labels) > 1 else primary

        templates = [
            (
                "Validate screen load and anchors",
                [
                    f"Open the {screen_name} screen.",
                    f"Verify the {primary} element is visible.",
                    f"Verify screen purpose context: {screen_purpose or 'Main workflow access'}.",
                ],
                "The screen loads and key anchors are visible without UI errors.",
            ),
            (
                "Validate primary interaction",
                [
                    f"Open the {screen_name} screen.",
                    f"Perform interaction on {primary}.",
                    f"Observe response around {secondary}.",
                ],
                "The primary interaction is accepted and the expected UI response is shown.",
            ),
            (
                "Validate navigation continuity",
                [
                    f"Open the {screen_name} screen.",
                    "Navigate away and return to the same screen.",
                    f"Verify {primary} is still interactable.",
                ],
                "State remains consistent after navigation and controls remain usable.",
            ),
            (
                "Validate resiliency and negative behavior",
                [
                    f"Open the {screen_name} screen.",
                    "Attempt an invalid or empty interaction path.",
                    "Verify validation or graceful handling is shown.",
                ],
                "The app handles invalid actions safely without crash or broken state.",
            ),
        ]

        lines: list[str] = []
        for i in range(count):
            idx = start_index + i
            title, steps, expected = templates[i % len(templates)]
            lines.extend(
                [
                    f"Test Case {idx}: {title} on {screen_name}",
                    f"Test ID: TC-{idx:03d}",
                    "Priority: Medium",
                    "Type: Functional",
                    f"Description: {title} for the {screen_name} screen.",
                    "Preconditions:",
                    f"  - The {screen_name} screen is available.",
                    "Steps:",
                ]
            )
            for step_num, step in enumerate(steps, start=1):
                lines.append(f"  {step_num}. {step}")
            lines.extend(["Expected Result:", f"  - {expected}", ""])

        return "\n".join(lines).rstrip()


class Step3LocatorStage:
    """Generate locator JSONs from Stage-1 and Stage-2 outputs."""

    def __init__(
        self,
        config: AppConfig,
        prompt_manager: PromptManager,
        feature_flags: StageFeatureFlags,
        project_root: Path,
    ) -> None:
        self.config = config
        self.prompt_manager = prompt_manager
        self.feature_flags = feature_flags
        self.project_root = project_root

    def run(self) -> list[Path]:
        if self.feature_flags.use_multi_strategy_locator:
            try:
                from agents.multi_strategy_locator_agent import MultiStrategyLocatorAgent

                agent = MultiStrategyLocatorAgent(project_root=self.project_root, config=self.config)
                return agent.run()
            except Exception:
                pass

        from agents.locator_agent import LocatorAgent

        agent = LocatorAgent(project_root=self.project_root, config=self.config, prompt_manager=self.prompt_manager)
        return agent.run()


class Step4AppiumStage:
    """Generate Appium scripts from locator JSONs."""

    def __init__(
        self,
        config: AppConfig,
        prompt_manager: PromptManager,
        feature_flags: StageFeatureFlags,
        project_root: Path,
    ) -> None:
        self.config = config
        self.prompt_manager = prompt_manager
        self.feature_flags = feature_flags
        self.project_root = project_root

    def run(self) -> list[Path]:
        if self.feature_flags.use_self_healing_generator:
            try:
                from agents.self_healing_appium_generator import SelfHealingAppiumGenerator

                agent = SelfHealingAppiumGenerator(
                    project_root=self.project_root,
                    config=self.config,
                    prompt_manager=self.prompt_manager,
                )
                return agent.generate_scripts_from_directory()
            except Exception:
                pass

        from agents.appium_generator_agent import AppiumGeneratorAgent

        agent = AppiumGeneratorAgent(project_root=self.project_root, config=self.config, prompt_manager=self.prompt_manager)
        return agent.generate_scripts_from_directory()


class Step5ReviewStage:
    """Generate review reports for Appium scripts."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def run(self) -> None:
        from agents.reviewer_agent import ReviewerAgent

        reviewer = ReviewerAgent(project_root=self.project_root)
        reviewer.review_scripts()


class Step6ReportStage:
    """Execute scripts and generate HTML report."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def run(
        self,
        open_browser: bool,
        report_scope: str | None = None,
        execute_tests: bool = True,
    ) -> Path:
        from agents.reporter_agent import ReporterAgent

        reporter = ReporterAgent(project_root=self.project_root)
        return reporter.run(
            open_browser=open_browser,
            report_scope=report_scope,
            execute_tests=execute_tests,
        )
