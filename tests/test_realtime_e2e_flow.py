"""Deterministic end-to-end emulator flow.

Flow:
1) Relaunch app (even if already open)
2) Dismiss startup popup if present
3) Open product listing (base page)
4) Open product details and add to cart
5) Open cart
6) Open menu -> Log In
7) Enter credentials and submit
8) Close application
"""

from __future__ import annotations

from typing import Iterable, Tuple

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from services.enhanced_config import get_config


Locator = Tuple[str, str]


class TestRealtimeE2EFlow:
    """Single-pass realtime emulator validation flow."""

    def setup_method(self) -> None:
        config = get_config()
        self.app_package = config.app_package
        self.app_activity = config.app_activity

        desired_caps = {
            "platformName": config.platform_name,
            "automationName": config.automation_name,
            "deviceName": config.device_name,
            "app": str(config.app_path),
            "appPackage": config.app_package,
            "appActivity": config.app_activity,
            "newCommandTimeout": 120,
            "uiautomator2ServerLaunchTimeout": 60000,
            "noReset": True,
            "dontStopAppOnReset": True,
        }

        options = UiAutomator2Options().load_capabilities(desired_caps)
        self.driver = webdriver.Remote(config.appium_server_url, options=options)
        self.wait = WebDriverWait(self.driver, max(6, int(config.explicit_wait_timeout)))

    def teardown_method(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass

    def _first_visible(self, locators: Iterable[Locator], timeout: float = 4):
        last_exc = None
        for by, value in locators:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((by, value))
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if last_exc:
            raise last_exc
        raise TimeoutException("No locators provided")

    def _tap_first(self, locators: Iterable[Locator], timeout: float = 4) -> None:
        for _ in range(3):
            element = self._first_visible(locators, timeout=timeout)
            try:
                element.click()
                return
            except StaleElementReferenceException:
                continue
        element = self._first_visible(locators, timeout=timeout)
        element.click()

    def _type_first(self, locators: Iterable[Locator], text: str, timeout: float = 4) -> None:
        for _ in range(3):
            element = self._first_visible(locators, timeout=timeout)
            try:
                element.clear()
                element.send_keys(text)
                return
            except StaleElementReferenceException:
                continue
        element = self._first_visible(locators, timeout=timeout)
        element.clear()
        element.send_keys(text)

    def _dismiss_popup_if_any(self) -> None:
        # Handles emulator compatibility popup when it appears.
        try:
            title = WebDriverWait(self.driver, 2).until(
                EC.presence_of_element_located((AppiumBy.ID, "android:id/alertTitle"))
            )
            if "compatibility" not in (title.text or "").lower():
                return
            for button_id in ("android:id/button1", "android:id/button2"):
                try:
                    self.driver.find_element(AppiumBy.ID, button_id).click()
                    return
                except Exception:
                    continue
        except Exception:
            return

    def _relaunch_app(self) -> None:
        try:
            self.driver.terminate_app(self.app_package)
        except Exception:
            pass
        try:
            self.driver.activate_app(self.app_package)
            self.driver.start_activity(self.app_package, self.app_activity)
        except Exception:
            pass

    def test_realtime_e2e_flow(self) -> None:
        # Step 1: Open app and relaunch if already open.
        self._relaunch_app()

        # Step 2: Close popup if any.
        self._dismiss_popup_if_any()

        # Step 3: Open product listing page (base page).
        self._first_visible(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartIV"),
            ],
            timeout=6,
        )

        # Step 4: Open product details page and add product to cart.
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productTV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/titleTV"),
            ],
            timeout=5,
        )

        try:
            self._tap_first(
                [
                    (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/addToCartBtn"),
                    (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartBt"),
                ],
                timeout=4,
            )
        except Exception:
            # If already in carted state, remove button indicates item already added.
            self._first_visible(
                [(AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/removeBt")],
                timeout=4,
            )

        # Step 5: Open cart.
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartRL"),
            ],
            timeout=5,
        )

        # Step 6: Open menu.
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ACCESSIBILITY_ID, "View menu"),
            ],
            timeout=5,
        )

        # Step 7: Click login; if already logged in, logout first then login.
        try:
            self._tap_first(
                [
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Log Out")'),
                    (AppiumBy.XPATH, '//*[@text="Log Out"]'),
                ],
                timeout=2,
            )
            self._tap_first(
                [
                    (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                    (AppiumBy.ACCESSIBILITY_ID, "View menu"),
                ],
                timeout=4,
            )
        except Exception:
            pass

        self._tap_first(
            [
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Log In")'),
                (AppiumBy.XPATH, '//*[@text="Log In"]'),
            ],
            timeout=5,
        )

        self._type_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameET"),
                (AppiumBy.ACCESSIBILITY_ID, "Username input field"),
            ],
            text="bob@example.com",
            timeout=5,
        )
        self._type_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/passwordET"),
                (AppiumBy.ACCESSIBILITY_ID, "Password input field"),
            ],
            text="10203040",
            timeout=5,
        )
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/loginBtn"),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Login")'),
            ],
            timeout=5,
        )

        # Verify login landed on interactive page.
        self._first_visible(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartIV"),
            ],
            timeout=6,
        )

        # Step 8: Close the application.
        self.driver.terminate_app(self.app_package)
