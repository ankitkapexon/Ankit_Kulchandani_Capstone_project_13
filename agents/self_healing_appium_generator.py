"""Enhanced Appium script generator with self-healing support.

Generates pytest-style Appium test scripts that use:
- Multi-strategy locators with automatic fallback
- Self-healing driver for robust element location
- Centralized configuration management
- Proper logging (fixing the logger import bug)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.app_config import AppConfig, get_config
from agents.navigation_agent import NavigationAgent
from services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class SelfHealingAppiumGenerator:
    """Generate self-healing Appium test scripts from locator JSON."""
    
    def __init__(
        self,
        project_root: Optional[Path | str] = None,
        config: Optional[AppConfig] = None,
        prompt_manager: Optional[PromptManager] = None,
    ):
        """Initialize enhanced Appium generator.
        
        Args:
            project_root: Project root directory path
        """
        self.config = config or get_config()
        self.project_root = Path(project_root) if project_root else self.config.project_root
        self.prompt_manager = prompt_manager or PromptManager(self.project_root)
        self.prompt_template = self.prompt_manager.load("appium")
        self.navigation_agent = NavigationAgent()

        self.input_dir = self.config.locator_output_dir
        self.output_dir = self.config.generated_scripts_dir
    
    def generate_scripts_from_directory(
        self,
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ) -> List[Path]:
        """Generate all test scripts from locator JSON files.
        
        Args:
            input_dir: Input directory with locator JSON files
            output_dir: Output directory for generated scripts
        
        Returns:
            List of generated script file paths
        """
        source_dir = Path(input_dir) if input_dir else self.input_dir
        dest_dir = Path(output_dir) if output_dir else self.output_dir
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        if not source_dir.exists():
            logger.error(f"Locator directory not found: {source_dir}")
            return []
        
        locator_files = list(source_dir.glob("*.json"))
        if not locator_files:
            logger.warning(f"No locator files found in {source_dir}")
            return []
        
        logger.info(f"Found {len(locator_files)} locator files to process")
        
        generated_scripts = []
        
        for locator_file in locator_files:
            try:
                locator_data = json.loads(locator_file.read_text(encoding="utf-8"))
                script_content = self.generate_script(locator_data)
                
                screen_name = locator_data.get("screen", "unknown")
                script_filename = self._to_script_name(screen_name)
                script_path = dest_dir / script_filename
                
                script_path.write_text(script_content, encoding="utf-8")
                
                logger.info(f"✓ Generated self-healing script: {script_filename}")
                generated_scripts.append(script_path)
                
            except Exception as e:
                logger.error(f"Failed to generate script from {locator_file.name}: {e}")
                continue
        
        logger.info(f"Successfully generated {len(generated_scripts)} self-healing test scripts")
        return generated_scripts
    
    def generate_script(self, locator_payload: Dict[str, Any]) -> str:
        """Generate a single self-healing test script.
        
        Args:
            locator_payload: Locator JSON data with multi-strategy locators
        
        Returns:
            Generated Python test script content
        """
        screen_name = locator_payload.get("screen", "Unknown")
        elements = locator_payload.get("elements", [])
        
        if not elements:
            raise ValueError(f"No elements found in locator payload for {screen_name}")
        
        class_name = self._to_class_name(screen_name)
        test_name = self._to_test_name(screen_name)
        
        # Generate test steps
        test_steps = self._generate_test_steps(screen_name, elements)
        
        # Generate full script
        script = self._build_script_template(
            screen_name=screen_name,
            class_name=class_name,
            test_name=test_name,
            test_steps=test_steps
        )
        
        return script
    
    def _build_script_template(
        self,
        screen_name: str,
        class_name: str,
        test_name: str,
        test_steps: str
    ) -> str:
        """Build the complete self-healing test script template."""
        
        return f'''"""Self-healing Appium test for {screen_name} screen.

Generated with multi-strategy locators and automatic fallback.
Uses centralized configuration and proper logging.
"""

import logging
import time
from typing import Any, Dict, List
from pathlib import Path

# Import self-healing utilities
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait

from utils.self_healing import SelfHealingDriver, LocatorStrategy, HealingRepository
from utils.shared_appium_session import get_or_create_driver, should_quit_driver
from services.enhanced_config import get_config

# Configure logging
logger = logging.getLogger(__name__)


class {class_name}:
    """Self-healing test class for {screen_name} screen."""
    
    def setup_method(self) -> None:
        """Initialize Appium driver with self-healing capabilities."""
        config = get_config()
        
        # Prepare desired capabilities from config
        desired_caps = {{
            "platformName": config.platform_name,
            "automationName": config.automation_name,
            "deviceName": config.device_name,
            "app": str(config.app_path),
            "appPackage": config.app_package,
            "appActivity": config.app_activity,
            "noReset": False,
            "forceAppLaunch": True,
            "dontStopAppOnReset": False,
            "newCommandTimeout": 120,
            "uiautomator2ServerLaunchTimeout": 60000,
        }}
        
        # Create/reuse Appium driver (single app launch for full pytest run)
        self.driver = get_or_create_driver(lambda: self._create_driver(desired_caps, config.appium_server_url))
        self._dismiss_compatibility_dialog_if_present()
        self._stabilize_startup_state()
        
        # Wrap with self-healing driver
        healing_config = {{
            "max_retries": config.healing_max_retries,
            "ai_vision_healing": config.ai_vision_healing,
            "explicit_wait_timeout": config.explicit_wait_timeout,
            "primary_strategy_timeout": min(config.explicit_wait_timeout, 4),
            "fallback_strategy_timeout": 1.2,
        }}
        
        self.healing_driver = SelfHealingDriver(
            driver=self.driver,
            config=healing_config
        )
        self.wait = WebDriverWait(self.driver, config.explicit_wait_timeout)
        
        logger.info(f"✓ Test setup complete for {screen_name}")
    
    def teardown_method(self) -> None:
        """Clean up after test execution."""
        if should_quit_driver() and hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except Exception as exc:
                logger.warning("Driver quit raised error during teardown: %s", exc)
            logger.info("✓ Test teardown complete")
    
    def _create_driver(self, desired_caps: Dict[str, Any], server_url: str) -> Any:
        """Create Appium driver instance."""
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
        
        options = UiAutomator2Options().load_capabilities(desired_caps)
        return webdriver.Remote(server_url, options=options)

    def _dismiss_compatibility_dialog_if_present(self) -> None:
        """Dismiss emulator compatibility dialog when it appears on startup."""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            short_wait = WebDriverWait(self.driver, 3)
            title = short_wait.until(EC.presence_of_element_located((By.ID, "android:id/alertTitle")))
            title_text = (title.text or "").strip().lower()
            if "compatibility" not in title_text:
                return

            # Prefer "Don't Show Again" when available to avoid repeated popups.
            for button_id in ("android:id/button1", "android:id/button2"):
                try:
                    btn = self.driver.find_element(By.ID, button_id)
                    if btn and btn.is_displayed():
                        btn.click()
                        logger.info("Dismissed Android compatibility dialog via %s", button_id)
                        return
                except Exception:
                    continue
        except Exception:
            # Dialog may not appear; continue without failing setup.
            return

    def _is_home_anchor_visible(self) -> bool:
        """Check whether the app is on a stable home screen with top bar anchors."""
        home_ids = (
            "com.saucelabs.mydemoapp.android:id/menuIV",
            "com.saucelabs.mydemoapp.android:id/cartIV",
            "com.saucelabs.mydemoapp.android:id/cartRL",
        )
        for element_id in home_ids:
            try:
                candidates = self.driver.find_elements(AppiumBy.ID, element_id)
                if any(el.is_displayed() for el in candidates):
                    return True
            except Exception:
                continue
        return False

    def _stabilize_startup_state(self) -> None:
        """Ensure app reaches an interactive base state before test navigation begins."""
        for attempt in range(3):
            self._dismiss_compatibility_dialog_if_present()
            if self._is_home_anchor_visible():
                return

            # If a screen from a previous flow is open, back out to the base screen.
            try:
                self.driver.back()
            except Exception:
                pass

            time.sleep(1)

        logger.warning("Home anchors not visible after startup stabilization retries")

    def _strategy_to_by(self, strategy: LocatorStrategy) -> str:
        """Map strategy type to a primary AppiumBy value for logs and diagnostics."""
        mapping = {{
            "resource_id": AppiumBy.ID,
            "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
            "content_desc": AppiumBy.ACCESSIBILITY_ID,
            "xpath": AppiumBy.XPATH,
            "text": AppiumBy.ANDROID_UIAUTOMATOR,
            "class_text": AppiumBy.ANDROID_UIAUTOMATOR,
        }}
        return mapping.get(strategy.type, AppiumBy.ANDROID_UIAUTOMATOR)

    def _wait_for_element(self, strategies: List[LocatorStrategy], screen_name: str):
        """Use explicit wait while delegating actual lookup to self-healing logic."""
        def _find(_driver):
            try:
                return self.healing_driver.find_element(strategies, screen_name=screen_name)
            except Exception:
                return False

        return self.wait.until(_find)

    def tap(self, strategies: List[LocatorStrategy], screen_name: str) -> None:
        """Tap using self-healing locators after explicit wait."""
        by_value = self._strategy_to_by(strategies[0])
        logger.info("Tap using primary strategy: %s", by_value)
        self.healing_driver.tap_element(strategies, screen_name=screen_name)

    def type_text(self, strategies: List[LocatorStrategy], text: str, screen_name: str) -> None:
        """Type text using self-healing locators after explicit wait."""
        by_value = self._strategy_to_by(strategies[0])
        logger.info("Type using primary strategy: %s", by_value)
        self.healing_driver.type_text(strategies, text, screen_name=screen_name)

    def verify_present(self, strategies: List[LocatorStrategy], screen_name: str):
        """Verify element is present with explicit wait and self-healing lookup."""
        by_value = self._strategy_to_by(strategies[0])
        logger.info("Verify using primary strategy: %s", by_value)
        return self.healing_driver.find_element(strategies, screen_name=screen_name)

    def scroll_to(self, strategies: List[LocatorStrategy], screen_name: str):
        """Scroll/find using self-healing fallback stack."""
        by_value = self._strategy_to_by(strategies[0])
        logger.info("Scroll/find using primary strategy: %s", by_value)
        return self.healing_driver.find_element(strategies, screen_name=screen_name)
    
    def {test_name}(self) -> None:
        """Execute {screen_name} screen test with self-healing."""
        logger.info("=" * 60)
        logger.info("Starting test: {test_name}")
        logger.info("=" * 60)
        
{test_steps}
        
        logger.info("=" * 60)
        logger.info("✓ Test completed successfully: {test_name}")
        logger.info("=" * 60)
'''
    
    def _generate_test_steps(self, screen_name: str, elements: List[Dict[str, Any]]) -> str:
        """Generate test step code with multi-strategy locators.
        
        Args:
            screen_name: Name of the screen
            elements: List of element locator entries
        
        Returns:
            Indented Python code for test steps
        """
        steps = []
        screen_literal = self._py_string(screen_name)
        step_number = 1

        # Ensure screen-level navigation is performed before element interactions.
        nav_steps = self.navigation_agent.get_navigation_steps(screen_name)
        for nav_action, nav_strategy, nav_value in nav_steps:
            strategy_block = (
                f"[LocatorStrategy({self._py_string(nav_strategy)}, {self._py_string(nav_value)}, priority=1, reliability=0.95, element_name={self._py_string(nav_value)})]"
            )

            if nav_value == "com.saucelabs.mydemoapp.android:id/menuIV":
                strategy_block = (
                    "["
                    f"LocatorStrategy({self._py_string('resource_id')}, {self._py_string(nav_value)}, priority=1, reliability=0.95, element_name={self._py_string('menu')}),"
                    f"LocatorStrategy({self._py_string('accessibility_id')}, {self._py_string('View menu')}, priority=2, reliability=0.85, element_name={self._py_string('menu')})"
                    "]"
                )
            elif nav_value == "com.saucelabs.mydemoapp.android:id/cartIV":
                strategy_block = (
                    "["
                    f"LocatorStrategy({self._py_string('resource_id')}, {self._py_string(nav_value)}, priority=1, reliability=0.95, element_name={self._py_string('cart')}),"
                    f"LocatorStrategy({self._py_string('resource_id')}, {self._py_string('com.saucelabs.mydemoapp.android:id/cartRL')}, priority=2, reliability=0.9, element_name={self._py_string('cart')}),"
                    f"LocatorStrategy({self._py_string('accessibility_id')}, {self._py_string('View cart')}, priority=2, reliability=0.85, element_name={self._py_string('cart')})"
                    "]"
                )
            elif nav_strategy == "text":
                strategy_block = (
                    "["
                    f"LocatorStrategy({self._py_string('text')}, {self._py_string(nav_value)}, priority=1, reliability=0.85, element_name={self._py_string(nav_value)}),"
                    f"LocatorStrategy({self._py_string('xpath')}, {self._py_string(f'//*[@text=\"{nav_value}\"]')}, priority=2, reliability=0.7, element_name={self._py_string(nav_value)})"
                    "]"
                )

            if nav_action == "tap":
                steps.append(
                    f"        # Navigation: tap {nav_value}\n"
                    f"        self.tap({strategy_block}, screen_name={screen_literal})\n"
                )
            elif nav_action == "scroll":
                steps.append(
                    f"        # Navigation: scroll to {nav_value}\n"
                    f"        self.scroll_to({strategy_block}, screen_name={screen_literal})\n"
                )

        if nav_steps:
            steps.append("")

        # For login flows, fill fields before tapping login CTA.
        if screen_name.strip().lower() == "login":
            type_elements = [e for e in elements if str(e.get("action", "")).strip().lower() == "type"]
            other_elements = [e for e in elements if e not in type_elements]
            elements = type_elements + other_elements
        
        for element_entry in elements:
            element_name = element_entry.get("element", "unknown")
            action = element_entry.get("action", "verify")
            step_desc = element_entry.get("step_description", "")

            if not self._has_stable_strategy(element_entry):
                continue

            # Skip redundant taps that target the same screen label.
            normalized_screen = screen_name.strip().lower()
            normalized_element = str(element_name).strip().lower()
            if action == "tap" and (
                normalized_element == normalized_screen
                or (normalized_screen == "product listing" and normalized_element in {"products", "product listing"})
                or (normalized_screen == "cart" and normalized_element == "cart")
            ):
                continue
            
            # Build locator strategies list
            strategies_code = self._build_strategies_code(element_entry)
            is_optional_cart_action = (
                normalized_screen == "cart"
                and action == "tap"
                and normalized_element in {"remove item", "proceed to checkout"}
            )
            
            # Generate action code based on action type
            if action == "tap":
                if is_optional_cart_action:
                    step_code = f'''        # Step {step_number}: Tap {element_name}
        logger.info({self._py_string(f"Step {step_number}: Tapping '{element_name}'")})
        strategies = {strategies_code}
        try:
            self.tap(strategies, screen_name={screen_literal})
            logger.info("✓ Step {step_number} complete")
        except Exception as exc:
            logger.warning("Skipping optional cart step '{element_name}': %s", exc)
'''
                else:
                    step_code = f'''        # Step {step_number}: Tap {element_name}
        logger.info({self._py_string(f"Step {step_number}: Tapping '{element_name}'")})
        strategies = {strategies_code}
        self.tap(strategies, screen_name={screen_literal})
        logger.info("✓ Step {step_number} complete")
'''
            
            elif action == "type":
                step_code = f'''        # Step {step_number}: Type into {element_name}
        logger.info({self._py_string(f"Step {step_number}: Typing into '{element_name}'")})
        strategies = {strategies_code}
        self.type_text(strategies, "test_value", screen_name={screen_literal})
        logger.info("✓ Step {step_number} complete")
'''
            
            elif action == "verify":
                step_code = f'''        # Step {step_number}: Verify {element_name} is present
        logger.info({self._py_string(f"Step {step_number}: Verifying '{element_name}'")})
        strategies = {strategies_code}
        element = self.verify_present(strategies, screen_name={screen_literal})
        assert element is not None, {self._py_string(f"{element_name} not found")}
        logger.info("✓ Step {step_number} complete - {element_name} verified")
'''
            
            elif action == "scroll":
                step_code = f'''        # Step {step_number}: Scroll to {element_name}
        logger.info({self._py_string(f"Step {step_number}: Scrolling to '{element_name}'")})
        strategies = {strategies_code}
        self.scroll_to(strategies, screen_name={screen_literal})
        logger.info("✓ Step {step_number} complete")
'''
            
            else:
                # Generic action
                step_code = f'''        # Step {step_number}: Interact with {element_name}
        logger.info({self._py_string(f"Step {step_number}: Action '{action}' on '{element_name}'")})
        strategies = {strategies_code}
        self.verify_present(strategies, screen_name={screen_literal})
        logger.info("✓ Step {step_number} complete")
'''
            
            steps.append(step_code)
            step_number += 1
        
        return "\n".join(steps)

    def _has_stable_strategy(self, element_entry: Dict[str, Any]) -> bool:
        """Keep only interactions that have stable locator types."""
        stable_types = {"resource_id", "id", "accessibility_id", "content_desc"}

        primary = element_entry.get("primary_strategy") or {}
        if str(primary.get("type", "")).strip().lower() in stable_types:
            return True

        for fallback in element_entry.get("fallback_strategies", []) or []:
            if str((fallback or {}).get("type", "")).strip().lower() in stable_types:
                return True

        return False
    
    def _build_strategies_code(self, element_entry: Dict[str, Any]) -> str:
        """Build Python list code for locator strategies.
        
        Args:
            element_entry: Element locator entry with strategies
        
        Returns:
            Python code string for list of LocatorStrategy objects
        """
        element_name = element_entry.get("element", "unknown")
        
        # Get multi-strategy data
        primary = element_entry.get("primary_strategy")
        fallbacks = element_entry.get("fallback_strategies", [])
        
        # Fallback to legacy format if multi-strategy not available
        if not primary:
            primary = {
                "type": element_entry.get("locator_strategy", "text"),
                "value": element_entry.get("locator_value", element_name),
                "priority": 5,
                "reliability": 0.5
            }
        
        all_strategies = [primary] + fallbacks
        
        # Build Python code for LocatorStrategy objects
        strategy_lines = []
        for strategy in all_strategies:
            strategy_type = self._py_string(str(strategy.get("type", "text")))
            strategy_value = self._py_string(str(strategy.get("value", element_name)))
            strategy_element_name = self._py_string(element_name)
            strategy_lines.append(
                f'            LocatorStrategy('
                f'{strategy_type}, '
                f'{strategy_value}, '
                f'priority={strategy.get("priority", 5)}, '
                f'reliability={strategy.get("reliability", 0.5)}, '
                f'element_name={strategy_element_name})'
            )
        
        return "[\n" + ",\n".join(strategy_lines) + "\n        ]"
    
    def _to_class_name(self, screen_name: str) -> str:
        """Convert screen name to class name (e.g., 'Login' → 'TestLogin')."""
        clean_name = screen_name.replace(" ", "").replace("_", "")
        return f"Test{clean_name}"
    
    def _to_test_name(self, screen_name: str) -> str:
        """Convert screen name to test method name (e.g., 'Login' → 'def test_login')."""
        clean_name = screen_name.lower().replace(" ", "_").replace("-", "_")
        return f"test_{clean_name}"

    def _py_string(self, value: str) -> str:
        """Return a safely escaped Python string literal."""
        return json.dumps(value, ensure_ascii=True)
    
    def _to_script_name(self, screen_name: str) -> str:
        """Convert screen name to script filename (e.g., 'Login' → 'test_login_screen.py')."""
        clean_name = screen_name.lower().replace(" ", "_").replace("-", "_")
        return f"test_{clean_name}_screen.py"
