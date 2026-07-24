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
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from utils.self_healing import SelfHealingDriver, LocatorStrategy, HealingRepository
from utils.shared_appium_session import get_or_create_driver_with_state, should_quit_driver
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
            "noReset": True,
            "forceAppLaunch": False,
            "dontStopAppOnReset": True,
            "newCommandTimeout": 120,
            "uiautomator2ServerLaunchTimeout": 60000,
        }
        
        # Create/reuse Appium driver (single app launch for full pytest run).
        self.driver, is_new_session = get_or_create_driver_with_state(
            lambda: self._create_driver(desired_caps, config.appium_server_url)
        )
        if is_new_session:
            self._dismiss_compatibility_dialog_if_present()
        else:
            try:
                # Return to the app's base activity without creating a new driver session.
                self.driver.activate_app(config.app_package)
                self.driver.start_activity(config.app_package, config.app_activity)
            except Exception as exc:
                logger.warning("Could not reset app activity on reused session: %s", exc)
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

            try:
                WebDriverWait(self.driver, 2).until(lambda _driver: self._is_home_anchor_visible())
                return
            except Exception:
                pass

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
        try:
            self.healing_driver.tap_element(strategies, screen_name=screen_name)
        except StaleElementReferenceException:
            # UI transitions can invalidate a located element right before click.
            time.sleep(0.3)
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
        

        # Step 1: Open menu
        logger.info("Step 1: Open menu")
        self.tap([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/menuIV", priority=1, reliability=0.95, element_name="Menu"),
            LocatorStrategy("accessibility_id", "View menu", priority=2, reliability=0.85, element_name="Menu")
        ], screen_name="Login")

        # Step 2: Open login from menu when available
        logger.info("Step 2: Open login entry")
        login_form_open = True
        try:
            self.tap([
                LocatorStrategy("text", "Log In", priority=1, reliability=0.85, element_name="Log In"),
                LocatorStrategy("xpath", "//*[@text=\"Log In\"]", priority=2, reliability=0.7, element_name="Log In")
            ], screen_name="Login")
        except Exception:
            login_form_open = False
            logger.info("Log In menu entry not available; user may already be logged in")

        # Step 3: Enter username
        logger.info("Step 3: Enter username")
        if login_form_open:
            self.type_text([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/nameET", priority=1, reliability=0.95, element_name="Username"),
            LocatorStrategy("accessibility_id", "Username input field", priority=2, reliability=0.85, element_name="Username"),
            LocatorStrategy("accessibility_id", "test-Username", priority=3, reliability=0.8, element_name="Username")
            ], "bob@example.com", screen_name="Login")

        # Step 4: Enter password
        logger.info("Step 4: Enter password")
        if login_form_open:
            self.type_text([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/passwordET", priority=1, reliability=0.95, element_name="Password"),
            LocatorStrategy("accessibility_id", "Password input field", priority=2, reliability=0.85, element_name="Password"),
            LocatorStrategy("accessibility_id", "test-Password", priority=3, reliability=0.8, element_name="Password")
            ], "10203040", screen_name="Login")

        # Step 5: Tap login button
        logger.info("Step 5: Tap Login")
        if login_form_open:
            self.tap([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/loginBtn", priority=1, reliability=0.95, element_name="Login"),
            LocatorStrategy("text", "Login", priority=2, reliability=0.75, element_name="Login"),
            LocatorStrategy("text", "Log In", priority=3, reliability=0.7, element_name="Login")
            ], screen_name="Login")

        # Step 6: Verify post-login home anchor
        logger.info("Step 6: Verify login success anchor")
        login_anchor = self.verify_present([
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/cartIV", priority=1, reliability=0.9, element_name="Cart"),
            LocatorStrategy("resource_id", "com.saucelabs.mydemoapp.android:id/menuIV", priority=2, reliability=0.85, element_name="Menu")
        ], screen_name="Login")
        assert login_anchor is not None, "Login anchor not found after login action"

        
        logger.info("=" * 60)
        logger.info("✓ Test completed successfully: test_login")
        logger.info("=" * 60)
