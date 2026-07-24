from typing import List, Tuple


class NavigationAgent:
    """
    Returns navigation steps required to reach a screen.
    """

    def get_navigation_steps(self, screen_name: str) -> List[Tuple[str, str, str]]:
        screen = screen_name.lower().strip()

        navigation = {

            # App launches here
            "product listing": [],

            # Login Screen
            "login": [
                (
                    "tap",
                    "resource_id",
                    "com.saucelabs.mydemoapp.android:id/menuIV",
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
                    "com.saucelabs.mydemoapp.android:id/cartIV",
                )
            ],

            # Product Details
            "product details": [
                (
                    "tap",
                    "resource_id",
                    "com.saucelabs.mydemoapp.android:id/productIV",
                )
            ],
        }

        return navigation.get(screen, [])