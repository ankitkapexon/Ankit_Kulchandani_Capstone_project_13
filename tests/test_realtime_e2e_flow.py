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

import logging
import os
import time
from pathlib import Path
from typing import Iterable, Tuple

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from services.enhanced_config import get_config


Locator = Tuple[str, str]
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TestRealtimeE2EFlow:
    """Single-pass realtime emulator validation flow."""

    def setup_method(self) -> None:
        config = get_config()
        self.app_package = config.app_package
        self.app_activity = config.app_activity
        self._step_index = 0
        self._capture_dir: Path | None = None

        capture_dir_raw = os.getenv("REALTIME_STEP_SCREENSHOT_DIR", "").strip()
        if capture_dir_raw:
            capture_dir = Path(capture_dir_raw)
            capture_dir.mkdir(parents=True, exist_ok=True)
            self._capture_dir = capture_dir

        desired_caps = {
            "platformName": config.platform_name,
            "automationName": config.automation_name,
            "deviceName": config.device_name,
            "app": str(config.app_path),
            "appPackage": config.app_package,
            "appActivity": config.app_activity,
            "newCommandTimeout": 120,
            "uiautomator2ServerLaunchTimeout": 120000,
            "uiautomator2ServerInstallTimeout": 120000,
            "adbExecTimeout": 120000,
            "androidInstallTimeout": 120000,
            "appWaitActivity": "*",
            "appWaitDuration": 120000,
            "autoGrantPermissions": True,
            "noReset": True,
            "dontStopAppOnReset": True,
        }

        options = UiAutomator2Options().load_capabilities(desired_caps)
        self.driver = self._create_driver_with_retry(config.appium_server_url, options)
        self.wait = WebDriverWait(self.driver, max(6, int(config.explicit_wait_timeout)))

    def _create_driver_with_retry(self, server_url: str, options: UiAutomator2Options):
        last_error = None
        for attempt in range(1, 4):
            try:
                return webdriver.Remote(server_url, options=options)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < 3:
                    time.sleep(5)
                else:
                    raise RuntimeError(
                        "Failed to create Appium session after 3 attempts "
                        f"against {server_url}"
                    ) from last_error

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

        # Ensure app is foregrounded before continuing flow actions.
        launched = False
        for _ in range(2):
            try:
                self.driver.activate_app(self.app_package)
                launched = True
                break
            except Exception:
                time.sleep(1)

        if not launched:
            try:
                self.driver.start_activity(self.app_package, self.app_activity)
            except Exception:
                pass

    def _capture_step_screenshot(self, name: str, expected_locators: Iterable[Locator], timeout: float = 6) -> None:
        if not self._capture_dir:
            return

        page_ready = True
        try:
            self._first_visible(expected_locators, timeout=timeout)
        except Exception:
            # Capture anyway as a fallback when anchors are transiently unavailable.
            page_ready = False

        # Small settle delay reduces transitional/blank captures.
        time.sleep(0.4 if page_ready else 1.0)

        self._step_index += 1
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name.lower())
        filename = f"{self._step_index:02d}_{safe_name}.png"
        target = self._capture_dir / filename
        try:
            self.driver.save_screenshot(str(target))
        except Exception:
            # Screenshot capture is best-effort and must not fail the run.
            return

    def test_realtime_e2e_flow(self) -> None:
        logger.info("Starting deterministic realtime E2E flow")

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
        self._capture_step_screenshot(
            "product_listing_page",
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartIV"),
            ],
            timeout=6,
        )
        logger.info("Captured page screenshot: Product Listing")

        # Step 4: Open product details page and add product to cart.
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productIV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/productTV"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/titleTV"),
            ],
            timeout=5,
        )
        self._capture_step_screenshot(
            "product_details_page",
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/addToCartBtn"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartBt"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/removeBt"),
            ],
            timeout=5,
        )
        logger.info("Captured page screenshot: Product Details")

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
        self._capture_step_screenshot(
            "cart_page",
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/cartRL"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/noTV"),
            ],
            timeout=5,
        )
        logger.info("Captured page screenshot: Cart")

        # Step 6: Open menu.
        self._tap_first(
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/menuIV"),
                (AppiumBy.ACCESSIBILITY_ID, "View menu"),
            ],
            timeout=5,
        )
        self._capture_step_screenshot(
            "menu_page",
            [
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Log In")'),
                (AppiumBy.XPATH, '//*[@text="Log In"]'),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Catalog")'),
                (AppiumBy.XPATH, '//*[@text="Catalog"]'),
            ],
            timeout=5,
        )
        logger.info("Captured page screenshot: Menu")

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
        self._capture_step_screenshot(
            "login_page",
            [
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/nameET"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/passwordET"),
                (AppiumBy.ID, "com.saucelabs.mydemoapp.android:id/loginBtn"),
            ],
            timeout=5,
        )
        logger.info("Captured page screenshot: Login")

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
        logger.info("Deterministic realtime E2E flow completed")
