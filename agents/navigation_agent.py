from typing import List, Tuple

from config.app_config import get_config


class NavigationAgent:
    """
    Returns navigation steps required to reach a screen.
    """

    def get_navigation_steps(self, screen_name: str) -> List[Tuple[str, str, str]]:
        screen = screen_name.lower().strip()

        config = get_config()
        app_package = config.app_package
        app_specific_navigation_enabled = config.app_specific_navigation_enabled

        if not app_specific_navigation_enabled or not app_package:
            return []

        preset = config.app_profile_preset
        if preset == "banking":
            return {
                "login": [
                    ("tap", "text", "Sign In"),
                ],
                "accounts": [
                    ("tap", "text", "Accounts"),
                ],
                "payments": [
                    ("tap", "text", "Payments"),
                ],
            }.get(screen, [])

        if preset == "social":
            return {
                "login": [
                    ("tap", "text", "Log In"),
                ],
                "feed": [
                    ("tap", "text", "Home"),
                ],
                "profile": [
                    ("tap", "text", "Profile"),
                ],
            }.get(screen, [])

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