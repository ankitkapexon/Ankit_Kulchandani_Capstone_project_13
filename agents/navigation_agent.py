import os
from typing import List, Tuple


class NavigationAgent:
    """
    Returns navigation steps required to reach a screen.
    """

    def get_navigation_steps(self, screen_name: str) -> List[Tuple[str, str, str]]:
        screen = screen_name.lower().strip()

        app_package = os.getenv("APP_PACKAGE", "").strip()
        enabled_value = os.getenv("ENABLE_APP_SPECIFIC_NAVIGATION")
        if enabled_value is None:
            app_specific_navigation_enabled = "saucelabs" in app_package.lower()
        else:
            app_specific_navigation_enabled = enabled_value.strip().lower() in {"1", "true", "yes", "on"}

        if not app_specific_navigation_enabled or not app_package:
            return []

        navigation = {

            # App launches here
            "product listing": [],

            # Login Screen
            "login": [
                (
                    "tap",
                    "resource_id",
                    f"{app_package}:id/menuIV",
                ),
                (
                    "tap",
                    "text",
                    "Log In",
                ),
            ],

            # Cart
            "cart": [
                (
                    "tap",
                    "resource_id",
                    f"{app_package}:id/cartIV",
                )
            ],

            # Product Details
            "product details": [
                (
                    "tap",
                    "resource_id",
                    f"{app_package}:id/productIV",
                )
            ],
        }

        return navigation.get(screen, [])