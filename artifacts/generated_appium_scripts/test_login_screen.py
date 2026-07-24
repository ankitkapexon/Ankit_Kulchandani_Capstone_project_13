"""Generated Appium pytest script for Login."""

import os
from typing import Any, Dict, Tuple

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestLogin:
    """Example Appium test class for the Login screen."""

    def setup_method(self) -> None:
        """Create the Appium driver and explicit wait before each test."""
        # Read configuration from environment
        platform = os.getenv("PLATFORM_NAME", "Android")
        platform_version = os.getenv("PLATFORM_VERSION", "14.0")
        device_name = os.getenv("DEVICE_NAME", "Android Emulator")
        app_path = os.getenv("APP_PATH", "")
        appium_server = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
        
        desired_caps = {
            "platformName": platform,
            "deviceName": device_name,
            "app": app_path,
            "noReset": True,
        }
        
        # Platform-specific capabilities
        if platform.lower() == "ios":
            desired_caps["automationName"] = "XCUITest"
            # platformVersion is optional for iOS and can cause SDK mismatch issues
            # iOS-specific XCUITest options for better stability
            desired_caps["wdaLaunchTimeout"] = 180000  # 3 minutes for WDA launch
            desired_caps["wdaConnectionTimeout"] = 180000  # 3 minutes for WDA connection
            desired_caps["isHeadless"] = False  # Run with UI (already pre-booted)
            desired_caps["usePrebuiltWDA"] = True  # Use prebuilt WDA if available
        else:  # Android
            desired_caps["automationName"] = "UiAutomator2"
            desired_caps["platformVersion"] = platform_version
            # Let Appium auto-detect appPackage and appActivity from APK manifest
            # This is more reliable than hardcoding activity names
            # Android-specific options for better app startup
            desired_caps["autoGrantPermissions"] = True  # Auto-grant runtime permissions
            desired_caps["appWaitActivity"] = "*"  # Wait for any activity to start
            desired_caps["appWaitDuration"] = 60000  # Wait up to 60 seconds for app to start
            desired_caps["androidInstallTimeout"] = 90000  # 90 seconds for app installation
        
        self.driver = self._create_driver(desired_caps, appium_server)
        self.wait = WebDriverWait(self.driver, 10) if WebDriverWait is not None else None
        self.platform = platform
        
        # Dismiss Android compatibility popups (16 KB page size warning)
        if platform.lower() == "android":
            self._dismiss_android_popups()

    def teardown_method(self) -> None:
        """Quit the Appium session after the test finishes."""
        if getattr(self, "driver", None):
            self.driver.quit()

    def tap(self, locator_strategy: str, locator_value: str) -> None:
        """Tap an element using a platform-appropriate locator and an explicit wait."""
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.click()

    def type(self, locator_strategy: str, locator_value: str, text: str) -> None:
        """Type text into an editable field using a platform-appropriate locator."""
        locator = self._build_locator(locator_strategy, locator_value)
        if self.wait is not None and EC is not None:
            element = self.wait.until(EC.element_to_be_clickable(locator))
        else:
            element = self.driver.find_element(*locator)
        element.clear()
        element.send_keys(text)

    def scroll(self, locator_strategy: str, locator_value: str) -> None:
        """Scroll until a target element is visible (Android only)."""
        if self.platform.lower() == "android":
            selector = self._build_uiautomator_selector(locator_strategy, locator_value)
            scroll_command = (
                f"new UiScrollable(new UiSelector().scrollable(true)).scrollIntoView({self._build_uiautomator_selector(locator_strategy, locator_value)})"
            )
            self.driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, scroll_command)
        if self.wait is not None and EC is not None:
            self.wait.until(EC.visibility_of_element_located(self._build_locator(locator_strategy, locator_value)))

    def _create_driver(self, desired_caps: Dict[str, Any], server_url: str) -> Any:
        """Create the Appium driver with platform-appropriate options."""
        from appium import webdriver
        
        platform = desired_caps.get("platformName", "Android")
        
        if platform.lower() == "ios":
            from appium.options.ios import XCUITestOptions
            options = XCUITestOptions().load_capabilities(desired_caps)
        else:  # Android
            from appium.options.android import UiAutomator2Options
            options = UiAutomator2Options().load_capabilities(desired_caps)

        return webdriver.Remote(server_url, options=options)

    def _build_locator(self, locator_strategy: str, locator_value: str) -> Tuple[str, str]:
        """Convert a logical locator into an Appium locator tuple."""

        if locator_strategy == "resource_id":
            return (AppiumBy.ID, locator_value)

        if locator_strategy == "accessibility_id":
            return (AppiumBy.ACCESSIBILITY_ID, locator_value)

        # Fallback for Android
        if self.platform.lower() == "android":
            return (
                AppiumBy.ANDROID_UIAUTOMATOR,
                self._build_uiautomator_selector(locator_strategy, locator_value),
            )
        else:
            # iOS fallback to name or accessibility_id
            return (AppiumBy.NAME, locator_value)

    def _build_uiautomator_selector(self, locator_strategy: str, locator_value: str) -> str:
        """Create a UiAutomator2 selector string without using fragile XPath (Android only)."""
        strategy = (locator_strategy or "text").strip().lower()
        if strategy == "accessibility_id":
            return f'new UiSelector().description("{locator_value}")'
        if strategy == "resource_id":
            return f'new UiSelector().resourceId("{locator_value}")'
        return f'new UiSelector().text("{locator_value}")'

    def _dismiss_android_popups(self) -> None:
        """Dismiss common Android system popups (16KB compatibility warning, permissions, etc.)."""
        import time
        time.sleep(2)  # Wait for popup to appear
        
        # List of button texts to try clicking (in order of preference)
        dismiss_buttons = [
            "Don't Show Again",  # Suppress future warnings
            "OK",                # Standard dismiss
            "Allow",             # Permissions
            "Accept",            # Generic accept
            "Continue",          # Generic continue
            "Got it",            # Tutorial/help screens
        ]
        
        for button_text in dismiss_buttons:
            try:
                # Try to find and click button using text
                button_locator = (
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    f'new UiSelector().text("{button_text}")'
                )
                button = self.driver.find_element(*button_locator)
                if button.is_displayed():
                    button.click()
                    print(f"✓ Dismissed popup by clicking '{button_text}'")
                    time.sleep(1)  # Wait for popup to close
                    return
            except Exception:
                # Button not found, try next one
                continue
        
        # No popup found or already dismissed
        print("✓ No Android system popups detected")

    def _is_login_form_visible(self) -> bool:
        """Return True when the login form is already visible on screen."""
        candidates = [
            (AppiumBy.ACCESSIBILITY_ID, "test-Username"),
            (AppiumBy.ACCESSIBILITY_ID, "Username input field"),
            (AppiumBy.XPATH, '//android.widget.EditText[@content-desc="test-Username"]'),
        ]

        for by, value in candidates:
            try:
                elements = self.driver.find_elements(by, value)
                if elements:
                    return True
            except Exception:
                continue
        return False

    def test_login(self) -> None:
        """Exercise the screen actions discovered by the locator agent."""
        import time
        
        # Step 1: Open navigation drawer only if login form is not already visible.
        time.sleep(3)  # Wait for app to fully load
        if not self._is_login_form_visible():
            print("Opening hamburger menu...")
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
                    menu_button = self.driver.find_element(by, value)
                    menu_button.click()
                    print(f"Menu opened using {by}: {value}")
                    menu_opened = True
                    break
                except Exception:
                    continue

            if not menu_opened:
                self.driver.save_screenshot("android_menu_not_found.png")
                raise Exception("Could not find hamburger menu using fallback locators")

            time.sleep(1)
            print("Finding Login menu item...")

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
                    login_item = self.driver.find_element(by, value)
                    login_item.click()
                    print(f"Login menu item tapped using {by}: {value}")
                    login_menu_opened = True
                    break
                except Exception:
                    continue

            if not login_menu_opened and not self._is_login_form_visible():
                self.driver.save_screenshot("android_login_menu_not_found.png")
                raise Exception("Could not find Login menu item using fallback locators")
        else:
            print("Login form is already visible; skipping menu navigation")
        
        # Step 3: Type Username
        time.sleep(2)  # Wait for login screen to fully load
        print("Looking for Username field...")
        
        # Try multiple strategies to find username field
        username_strategies = [
            ('accessibility_id', 'Username input field'),
            ('accessibility_id', 'test-Username'),
            ('xpath', '//android.widget.EditText[@content-desc="test-Username"]'),
            ('xpath', '//android.widget.EditText[1]'),  # First EditText
            ('class_name', 'android.widget.EditText'),  # Any EditText
        ]
        
        username_entered = False
        for strategy_type, strategy_value in username_strategies:
            try:
                print(f"  Trying {strategy_type}: {strategy_value}")
                if strategy_type == 'accessibility_id':
                    username_field = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                elif strategy_type == 'xpath':
                    username_field = self.driver.find_element(AppiumBy.XPATH, strategy_value)
                elif strategy_type == 'class_name':
                    username_field = self.driver.find_elements(AppiumBy.CLASS_NAME, strategy_value)[0]
                
                username_field.click()
                username_field.send_keys('bob@example.com')
                print(f"✓ Username entered using {strategy_type}")
                username_entered = True
                break
            except Exception as e:
                print(f"  ✗ Failed: {str(e)[:80]}")
                continue
        
        if not username_entered:
            raise Exception("Could not find username field with any strategy")
        
        # Step 4: Type Password
        print("Looking for Password field...")
        
        password_strategies = [
            ('accessibility_id', 'Password input field'),
            ('accessibility_id', 'test-Password'),
            ('xpath', '//android.widget.EditText[@content-desc="test-Password"]'),
            ('xpath', '//android.widget.EditText[2]'),  # Second EditText
        ]
        
        password_entered = False
        for strategy_type, strategy_value in password_strategies:
            try:
                print(f"  Trying {strategy_type}: {strategy_value}")
                if strategy_type == 'accessibility_id':
                    password_field = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                elif strategy_type == 'xpath':
                    password_field = self.driver.find_element(AppiumBy.XPATH, strategy_value)
                
                password_field.click()
                password_field.send_keys('10203040')
                print(f"✓ Password entered using {strategy_type}")
                password_entered = True
                break
            except Exception as e:
                print(f"  ✗ Failed: {str(e)[:80]}")
                continue
        
        if not password_entered:
            raise Exception("Could not find password field with any strategy")
        
        # Step 5: Tap Login Button
        print("Looking for Login button...")
        
        login_button_strategies = [
            ('accessibility_id', 'Login button'),
            ('accessibility_id', 'test-LOGIN'),
            ('xpath', '//android.view.ViewGroup[@content-desc="test-LOGIN"]'),
            ('xpath', '//*[contains(@text, "Login")]'),
        ]
        
        login_tapped = False
        for strategy_type, strategy_value in login_button_strategies:
            try:
                print(f"  Trying {strategy_type}: {strategy_value}")
                if strategy_type == 'accessibility_id':
                    login_button = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, strategy_value)
                elif strategy_type == 'xpath':
                    login_button = self.driver.find_element(AppiumBy.XPATH, strategy_value)
                
                login_button.click()
                print(f"✓ Login button tapped using {strategy_type}")
                login_tapped = True
                break
            except Exception as e:
                print(f"  ✗ Failed: {str(e)[:80]}")
                continue
        
        if not login_tapped:
            raise Exception("Could not find login button with any strategy")
        
        # Wait a bit to see if login succeeds
        time.sleep(2)
        print("✓ Login test completed")

