import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.navigation_agent import NavigationAgent
from config.app_config import AppConfig, get_config
from services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class AppiumGeneratorAgent:
    """Generate Android/iOS Appium pytest scripts from locator JSON artifacts."""

    def __init__(
        self,
        project_root: Optional[Path | str] = None,
        config: Optional[AppConfig] = None,
        prompt_manager: Optional[PromptManager] = None,
    ) -> None:
        self.config = config or get_config()
        self.project_root = Path(project_root) if project_root else self.config.project_root
        self.prompt_manager = prompt_manager or PromptManager(self.project_root)
        self.prompt_template = self.prompt_manager.load("appium")

        self.input_dir = self.config.locator_output_dir
        self.output_dir = self.config.generated_scripts_dir
        self.navigation_agent = NavigationAgent()

    def _use_reference_demo_login_shortcuts(self) -> bool:
        return self.config.app_specific_navigation_enabled and self.config.is_reference_demo_profile

    def generate_script_for_locator(self, locator_payload: Dict[str, Any]) -> str:
        screen_name = self._screen_name_from_payload(locator_payload)
        class_name = self._to_class_name(screen_name)
        test_name = self._to_test_name(screen_name)

        elements = locator_payload.get("elements") or []
        if not elements:
            raise ValueError("Locator payload does not contain any elements.")

        step_lines = self._build_step_lines(screen_name, elements)

        return f'''"""Generated Appium pytest script for {screen_name}."""

import os
from typing import Any, Dict, Tuple

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utils.shared_appium_session import get_or_create_driver, should_quit_driver


class {class_name}:
    """Example Appium test class for the {screen_name} screen."""

    def setup_method(self) -> None:
        """Create the Appium driver and explicit wait before each test."""
        platform = os.getenv("PLATFORM_NAME", "Android")
        platform_version = os.getenv("PLATFORM_VERSION", "14.0")
        device_name = os.getenv("DEVICE_NAME", "Android Emulator")
        app_path = os.getenv("APP_PATH", "")
        appium_server = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

        desired_caps = {{
            "platformName": platform,
            "deviceName": device_name,
            "app": app_path,
            "noReset": True,
        }}

        if platform.lower() == "ios":
            desired_caps["automationName"] = "XCUITest"
        else:
            desired_caps["automationName"] = "UiAutomator2"
            desired_caps["platformVersion"] = platform_version
            app_package = os.getenv("APP_PACKAGE", "").strip()
            app_activity = os.getenv("APP_ACTIVITY", "").strip()
            if app_package:
                desired_caps["appPackage"] = app_package
            if app_activity:
                desired_caps["appActivity"] = app_activity

        self.driver = get_or_create_driver(lambda: self._create_driver(desired_caps, appium_server))
        self.wait = WebDriverWait(self.driver, 10) if WebDriverWait is not None else None
        self.platform = platform

    def teardown_method(self) -> None:
        """Quit the Appium session after the test finishes."""
        if should_quit_driver() and getattr(self, "driver", None):
            self.driver.quit()

    def tap(self, locator_strategy: str, locator_value: str) -> None:
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.click()

    def type(self, locator_strategy: str, locator_value: str, text: str) -> None:
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.clear()
        element.send_keys(text)

    def scroll(self, locator_strategy: str, locator_value: str) -> None:
        if self.platform.lower() == "android":
            scroll_command = (
                f"new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView({{self._build_uiautomator_selector(locator_strategy, locator_value)}})"
            )
            self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, scroll_command)
        if self.wait is not None and EC is not None:
            self.wait.until(EC.visibility_of_element_located(self._build_locator(locator_strategy, locator_value)))

    def _create_driver(self, desired_caps: Dict[str, Any], server_url: str) -> Any:
        from appium import webdriver

        platform = desired_caps.get("platformName", "Android")
        if platform.lower() == "ios":
            from appium.options.ios import XCUITestOptions

            options = XCUITestOptions().load_capabilities(desired_caps)
        else:
            from appium.options.android import UiAutomator2Options

            options = UiAutomator2Options().load_capabilities(desired_caps)

        return webdriver.Remote(server_url, options=options)

    def _build_locator(self, locator_strategy: str, locator_value: str) -> Tuple[str, str]:
        if locator_strategy == "resource_id":
            return (AppiumBy.ID, locator_value)

        if locator_strategy == "accessibility_id":
            return (AppiumBy.ACCESSIBILITY_ID, locator_value)

        if self.platform.lower() == "android":
            return (
                AppiumBy.ANDROID_UIAUTOMATOR,
                self._build_uiautomator_selector(locator_strategy, locator_value),
            )

        return (AppiumBy.NAME, locator_value)

    def _build_uiautomator_selector(self, locator_strategy: str, locator_value: str) -> str:
        strategy = (locator_strategy or "text").strip().lower()
        if strategy == "accessibility_id":
            return f'new UiSelector().description("{{locator_value}}")'
        if strategy == "resource_id":
            return f'new UiSelector().resourceId("{{locator_value}}")'
        return f'new UiSelector().text("{{locator_value}}")'

    def {test_name}(self) -> None:
        """Exercise the screen actions discovered by the locator agent."""
{step_lines}
'''

    def generate_scripts_from_directory(
        self,
        input_dir: Optional[Path | str] = None,
        output_dir: Optional[Path | str] = None,
    ) -> List[Path]:
        source_dir = Path(input_dir or self.input_dir)
        destination_dir = Path(output_dir or self.output_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)

        generated_files: List[Path] = []
        for locator_path in sorted(source_dir.glob("*.json")):
            with locator_path.open("r", encoding="utf-8") as handle:
                locator_payload = json.load(handle)

            script_content = self.generate_script_for_locator(locator_payload)
            screen = self._screen_name_from_payload(locator_payload)
            output_path = destination_dir / self._to_script_name(screen)
            with output_path.open("w", encoding="utf-8") as handle:
                handle.write(script_content)

            logger.info("[AppiumGeneratorAgent] Script generated for screen: '%s' -> %s", screen, output_path.name)
            generated_files.append(output_path)

        return generated_files

    def _build_step_lines(self, screen_name: str, elements: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        use_reference_shortcuts = self._use_reference_demo_login_shortcuts()

        navigation_steps = self.navigation_agent.get_navigation_steps(screen_name)
        for nav_action, strategy, value in navigation_steps:
            if nav_action == "tap":
                lines.append(f"        self.tap('{strategy}', '{value}')")
            elif nav_action == "scroll":
                lines.append(f"        self.scroll('{strategy}', '{value}')")

        if navigation_steps:
            lines.append("")

        for index, element in enumerate(elements, start=1):
            label = str(element.get("element") or f"Element {index}")
            action = str(element.get("action") or "verify").strip().lower()
            locator_strategy = str(element.get("locator_strategy") or "text")
            locator_value = str(element.get("locator_value") or label)

            if use_reference_shortcuts and screen_name.lower() == "login" and action == "tap" and label.lower() == "login":
                continue

            lines.append(f"        # Step {index}: {action.replace('_', ' ')} the {label} element.")

            if action == "tap":
                lines.append(f"        self.tap('{locator_strategy}', '{locator_value}')")
            elif action == "type":
                input_value = str(element.get("input_value", ""))
                lines.append(f"        self.type('{locator_strategy}', '{locator_value}', '{input_value}')")
            elif action == "scroll":
                lines.append(f"        self.scroll('{locator_strategy}', '{locator_value}')")
            else:
                lines.append(
                    f"        self.wait.until(EC.visibility_of_element_located(self._build_locator('{locator_strategy}', '{locator_value}')))"
                )

            lines.append("")

        if use_reference_shortcuts and screen_name.lower() == "login":
            lines.append("        # Submit login")
            lines.append(f"        self.tap('resource_id', '{self.config.app_package}:id/loginBtn')")
            lines.append("")

        if not lines:
            return "        pass\n"

        return "\n".join(lines).rstrip() + "\n"

    def _screen_name_from_payload(self, locator_payload: Dict[str, Any]) -> str:
        return str(locator_payload.get("screen") or "Screen")

    def _to_class_name(self, screen_name: str) -> str:
        parts = re.split(r"[^0-9A-Za-z]+", screen_name)
        cleaned = [part.capitalize() for part in parts if part]
        return "Test" + "".join(cleaned) if cleaned else "TestScreen"

    def _to_test_name(self, screen_name: str) -> str:
        return "test_" + self._slugify(screen_name)

    def _to_script_name(self, screen_name: str) -> str:
        return f"test_{self._slugify(screen_name)}_screen.py"

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
        return slug or "screen"


def main() -> List[Path]:
    agent = AppiumGeneratorAgent()
    agent.output_dir.mkdir(parents=True, exist_ok=True)
    generated_files = agent.generate_scripts_from_directory(input_dir=agent.input_dir, output_dir=agent.output_dir)

    for path in generated_files:
        print(f"Generated {path}")
    return generated_files


if __name__ == "__main__":
    main()
