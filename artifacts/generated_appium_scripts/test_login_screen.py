"""Self-healing Appium test for Login screen.

Generated with multi-strategy locators and automatic fallback.
Uses centralized configuration and proper logging.
"""

import logging
from typing import Any, Dict, List
from pathlib import Path

# Import self-healing utilities
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait

from utils.self_healing import SelfHealingDriver, LocatorStrategy
from utils.shared_appium_session import get_or_create_driver, should_quit_driver
from services.enhanced_config import get_config

# Configure logging
logger = logging.getLogger(__name__)


class TestLogin:
    """Self-healing test class for Login screen."""
    
    def setup_method(self) -> None:
        """Initialize Appium driver with self-healing capabilities."""
        config = get_config()
        
        # Prepare desired capabilities from config
        desired_caps = {
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
        }
        
        # Create/reuse Appium driver (single app launch for full pytest run)
        self.driver = get_or_create_driver(lambda: self._create_driver(desired_caps, config.appium_server_url))
        self._dismiss_compatibility_dialog_if_present()
        self._stabilize_startup_state()
        
        # Wrap with self-healing driver
        healing_config = {
            "max_retries": config.healing_max_retries,
            "ai_vision_healing": config.ai_vision_healing,
            "explicit_wait_timeout": config.explicit_wait_timeout,
            "primary_strategy_timeout": min(config.explicit_wait_timeout, 4),
            "fallback_strategy_timeout": 1.2,
        }
        
        self.healing_driver = SelfHealingDriver(
            driver=self.driver,
            config=healing_config
        )
        self.wait = WebDriverWait(self.driver, config.explicit_wait_timeout)
        
        logger.info(f"✓ Test setup complete for Login")
    
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

            # Wait briefly for UI to settle after navigating back.
            try:
                WebDriverWait(self.driver, 2).until(lambda _driver: self._is_home_anchor_visible())
                return
            except Exception:
                continue

        logger.warning("Home anchors not visible after startup stabilization retries")

    def _strategy_to_by(self, strategy: LocatorStrategy) -> str:
        """Map strategy type to a primary AppiumBy value for logs and diagnostics."""
        mapping = {
            "resource_id": AppiumBy.ID,
            "accessibility_id": AppiumBy.ACCESSIBILITY_ID,
            "content_desc": AppiumBy.ACCESSIBILITY_ID,
            "xpath": AppiumBy.XPATH,
            "text": AppiumBy.ANDROID_UIAUTOMATOR,
            "class_text": AppiumBy.ANDROID_UIAUTOMATOR,
        }
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
    
    def test_login(self) -> None:
        """Execute Login screen test with self-healing."""
        logger.info("=" * 60)
        logger.info("Starting test: test_login")
        logger.info("=" * 60)
        
        # Navigation: tap com.saucelabs.mydemoapp.android:id/menuIV
        self.tap([LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/menuIV", priority=1, reliability=0.95, element_name="menu"),LocatorStrategy("accessibility_id", "View menu", priority=2, reliability=0.85, element_name="menu")], screen_name="Login")

        # Navigation: tap Login menu item using stable button-oriented locators.
        self.tap([
            LocatorStrategy("accessibility_id", "menu item log in", priority=1, reliability=0.95, element_name="login_menu_item"),
            LocatorStrategy("accessibility_id", "Login Menu Item", priority=2, reliability=0.9, element_name="login_menu_item"),
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/nameET", priority=3, reliability=0.8, element_name="username_field"),
        ], screen_name="Login")

        # Verify login form is visible after navigation instead of tapping non-actionable text.
        self.verify_present([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/nameET", priority=1, reliability=0.95, element_name="username_field"),
            LocatorStrategy("accessibility_id", "Username input field", priority=2, reliability=0.85, element_name="username_field"),
        ], screen_name="Login")


        
        logger.info("=" * 60)
        logger.info("✓ Test completed successfully: test_login")
        logger.info("=" * 60)
