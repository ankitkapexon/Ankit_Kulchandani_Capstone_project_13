"""Stable Appium login test used by CI Android workflow."""

import os
import time
from typing import Any, Dict, Tuple

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestLogin:
    """Appium E2E login test with fallback locators for Android demo app."""

    def setup_method(self) -> None:
        platform = os.getenv("PLATFORM_NAME", "Android")
        platform_version = os.getenv("PLATFORM_VERSION", "14.0")
        device_name = os.getenv("DEVICE_NAME", "Android Emulator")
        app_path = os.getenv("APP_PATH", "")
        appium_server = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

        desired_caps: Dict[str, Any] = {
            "platformName": platform,
            "deviceName": device_name,
            "app": app_path,
            "noReset": True,
        }

        if platform.lower() == "ios":
            desired_caps["automationName"] = "XCUITest"
            desired_caps["wdaLaunchTimeout"] = 180000
            desired_caps["wdaConnectionTimeout"] = 180000
            desired_caps["isHeadless"] = False
            desired_caps["usePrebuiltWDA"] = True
        else:
            desired_caps["automationName"] = "UiAutomator2"
            desired_caps["platformVersion"] = platform_version
            desired_caps["autoGrantPermissions"] = True
            desired_caps["appWaitActivity"] = "*"
            desired_caps["appWaitDuration"] = 60000
            desired_caps["androidInstallTimeout"] = 90000

        self.driver = self._create_driver(desired_caps, appium_server)
        self.wait = WebDriverWait(self.driver, 10)
        self.platform = platform

        if platform.lower() == "android":
            self._dismiss_android_popups()

    def teardown_method(self) -> None:
        if getattr(self, "driver", None):
            self.driver.quit()

    def _create_driver(self, desired_caps: Dict[str, Any], server_url: str) -> Any:
        from appium import webdriver

        platform = desired_caps.get("platformName", "Android")
        if platform.lower() == "ios":
            from appium.options.ios import XCUITestOptions

            options = XCUITestOptions().load_capabilities(desired_caps)
        else:
            from appium.options.android import UiAutomator2Options

            options = UiAutomator2Options().load_capabilities(desired_caps)

        last_error = None
        for attempt in range(1, 4):
            try:
                return webdriver.Remote(server_url, options=options)
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(5)
                else:
                    raise RuntimeError(
                        f"Failed to create Appium session after 3 attempts against {server_url}"
                    ) from last_error

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
            return f'new UiSelector().description("{locator_value}")'
        if strategy == "resource_id":
            return f'new UiSelector().resourceId("{locator_value}")'
        return f'new UiSelector().text("{locator_value}")'

    def _dismiss_android_popups(self) -> None:
        time.sleep(2)
        dismiss_buttons = ["Don't Show Again", "OK", "Allow", "Accept", "Continue", "Got it"]

        for button_text in dismiss_buttons:
            try:
                button_locator = (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{button_text}")')
                button = self.driver.find_element(*button_locator)
                if button.is_displayed():
                    button.click()
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _is_login_form_visible(self) -> bool:
        candidates = [
            (AppiumBy.ACCESSIBILITY_ID, "test-Username"),
            (AppiumBy.ACCESSIBILITY_ID, "Username input field"),
            (AppiumBy.XPATH, '//android.widget.EditText[@content-desc="test-Username"]'),
        ]

        for by, value in candidates:
            try:
                if self.driver.find_elements(by, value):
                    return True
            except Exception:
                continue
        return False

    def test_login(self) -> None:
        time.sleep(5)

        if not self._is_login_form_visible():
            hamburger_locators = [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ACCESSIBILITY_ID, "test-Menu"),
                (AppiumBy.ACCESSIBILITY_ID, "open menu"),
                (AppiumBy.XPATH, '//android.view.ViewGroup[@content-desc="test-Menu"]'),
                (AppiumBy.XPATH, '//android.widget.ImageView[contains(@content-desc, "menu")]'),
            ]

            menu_opened = False
            for by, value in hamburger_locators:
                try:
                    self.driver.find_element(by, value).click()
                    menu_opened = True
                    break
                except Exception:
                    continue

            if not menu_opened:
                self.driver.save_screenshot("android_menu_not_found.png")
                raise Exception("Could not find hamburger menu using fallback locators")

            time.sleep(1)
            login_menu_locators = [
                (AppiumBy.ACCESSIBILITY_ID, "menu item log in"),
                (AppiumBy.ACCESSIBILITY_ID, "Login Menu Item"),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Log In")'),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Login")'),
                (
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    'new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView(new UiSelector().text("Log In"))',
                ),
            ]

            login_menu_opened = False
            for by, value in login_menu_locators:
                try:
                    self.driver.find_element(by, value).click()
                    login_menu_opened = True
                    break
                except Exception:
                    continue

            if not login_menu_opened and not self._is_login_form_visible():
                self.driver.save_screenshot("android_login_menu_not_found.png")
                raise Exception("Could not find Login menu item using fallback locators")

        time.sleep(2)

        username_strategies = [
            ("accessibility_id", "Username input field"),
            ("accessibility_id", "test-Username"),
            ("xpath", '//android.widget.EditText[@content-desc="test-Username"]'),
            ("xpath", "//android.widget.EditText[1]"),
            ("class_name", "android.widget.EditText"),
        ]

        username_entered = False
        for strategy_type, strategy_value in username_strategies:
            try:
                if strategy_type == "accessibility_id":
                    username_field = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                elif strategy_type == "xpath":
                    username_field = self.driver.find_element(AppiumBy.XPATH, strategy_value)
                else:
                    username_field = self.driver.find_elements(AppiumBy.CLASS_NAME, strategy_value)[0]

                username_field.click()
                username_field.send_keys("bob@example.com")
                username_entered = True
                break
            except Exception:
                continue

        if not username_entered:
            raise Exception("Could not find username field with any strategy")

        password_strategies = [
            ("accessibility_id", "Password input field"),
            ("accessibility_id", "test-Password"),
            ("xpath", '//android.widget.EditText[@content-desc="test-Password"]'),
            ("xpath", "//android.widget.EditText[2]"),
        ]

        password_entered = False
        for strategy_type, strategy_value in password_strategies:
            try:
                if strategy_type == "accessibility_id":
                    password_field = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                else:
                    password_field = self.driver.find_element(AppiumBy.XPATH, strategy_value)

                password_field.click()
                password_field.send_keys("10203040")
                password_entered = True
                break
            except Exception:
                continue

        if not password_entered:
            raise Exception("Could not find password field with any strategy")

        login_button_strategies = [
            ("accessibility_id", "Login button"),
            ("accessibility_id", "test-LOGIN"),
            ("xpath", '//android.view.ViewGroup[@content-desc="test-LOGIN"]'),
            ("xpath", '//*[contains(@text, "Login")]'),
        ]

        login_tapped = False
        for strategy_type, strategy_value in login_button_strategies:
            try:
                if strategy_type == "accessibility_id":
                    login_button = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                else:
                    login_button = self.driver.find_element(AppiumBy.XPATH, strategy_value)

                login_button.click()
                login_tapped = True
                break
            except Exception:
                continue

        if not login_tapped:
            raise Exception("Could not find login button with any strategy")

        time.sleep(2)
