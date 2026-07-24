"""Generated Appium pytest script for Cart."""

import os
from typing import Any, Dict, List, Optional, Tuple
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestCart:
    """Example Appium test class for the Cart screen."""

    def setup_method(self) -> None:
        """Create the Appium driver and explicit wait before each test."""
        desired_caps = {
            "platformName": "Android",
    "automationName": "UiAutomator2",
    "deviceName": "Android Emulator",
    "app": "C:/Users/Reshma.R/MobileAppTesting/capstone-cross-platform-mobile-test-script-generator/demo_mobile_apps/mda-2.2.0-25.apk",
    "appPackage": "com.saucelabs.mydemoapp.android",
    "appActivity": "com.saucelabs.mydemoapp.android.view.activities.SplashActivity",
    "noReset": True,
        }
        self.driver = self._create_driver(desired_caps)
        self.wait = WebDriverWait(self.driver, 10) if WebDriverWait is not None else None

    def teardown_method(self) -> None:
        """Quit the Appium session after the test finishes."""
        if getattr(self, "driver", None):
            self.driver.quit()

    def tap(self, locator_strategy: str, locator_value: str) -> None:
        """Tap an element using a UiAutomator2 locator and an explicit wait."""
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.click()

    def type(self, locator_strategy: str, locator_value: str, text: str) -> None:
        """Type text into an editable field using a UiAutomator2 locator."""
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.clear()
        element.send_keys(text)

    def scroll(self, locator_strategy: str, locator_value: str) -> None:
        """Scroll until a target element is visible using UiAutomator2."""
        selector = self._build_uiautomator_selector(locator_strategy, locator_value)
        scroll_command = (
            f"new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView({self._build_uiautomator_selector(locator_strategy, locator_value)})"
        )
        self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, scroll_command)
        if self.wait is not None and EC is not None:
            self.wait.until(EC.visibility_of_element_located(self._build_locator(locator_strategy, locator_value)))

    def _create_driver(self, desired_caps: Dict[str, Any]) -> Any:
        """Create the Appium driver."""
        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        options = UiAutomator2Options().load_capabilities(desired_caps)

        return webdriver.Remote(
            "http://127.0.0.1:4723",
            options=options,
        )

    def _build_locator(self, locator_strategy: str, locator_value: str) -> Tuple[str, str]:
        """Convert a logical locator into an Appium locator tuple."""

        if locator_strategy == "resource_id":
            return (AppiumBy.ID, locator_value)

        if locator_strategy == "accessibility_id":
            return (AppiumBy.ACCESSIBILITY_ID, locator_value)

        return (
            AppiumBy.ANDROID_UIAUTOMATOR,
            self._build_uiautomator_selector(locator_strategy, locator_value),
    )

    def _build_uiautomator_selector(self, locator_strategy: str, locator_value: str) -> str:
        """Create a UiAutomator2 selector string without using fragile XPath."""
        strategy = (locator_strategy or "text").strip().lower()
        if strategy == "accessibility_id":
            return f'new UiSelector().description("{locator_value}")'
        if strategy == "resource_id":
            return f'new UiSelector().resourceId("{locator_value}")'
        return f'new UiSelector().text("{locator_value}")'

    def test_cart(self) -> None:
        """Exercise the screen actions discovered by the locator agent."""
        self.tap('resource_id', 'com.saucelabs.mydemoapp.android:id/cartIV')

        # Step 1: verify the Cart title element.
        self.wait.until(EC.visibility_of_element_located(self._build_locator('resource_id', 'com.saucelabs.mydemoapp.android:id/productTV')))

        # Step 2: verify the Checkout element.
        self.wait.until(EC.visibility_of_element_located(self._build_locator('resource_id', 'com.saucelabs.mydemoapp.android:id/cartBt')))

        # Step 3: scroll the Cart items element.
        self.scroll('resource_id', 'com.saucelabs.mydemoapp.android:id/cartIV')

        # Step 4: tap the Quantity controls element.
        self.tap('text', 'quantity controls')

        # Step 5: verify the Subtotal element.
        self.wait.until(EC.visibility_of_element_located(self._build_locator('resource_id', 'com.saucelabs.mydemoapp.android:id/totalPriceTV')))

        # Step 6: tap the Remove item element.
        self.tap('text', 'remove item')

