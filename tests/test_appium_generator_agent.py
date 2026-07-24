import json
import tempfile
import unittest
from pathlib import Path

from agents.appium_generator_agent import AppiumGeneratorAgent


class AppiumGeneratorAgentTests(unittest.TestCase):
    def test_generate_script_contains_ui_automator_helpers(self) -> None:
        agent = AppiumGeneratorAgent()
        locator_payload = {
            "screen": "Login",
            "elements": [
                {"element": "Username", "action": "tap", "locator_strategy": "text", "locator_value": "Username"},
                {"element": "Password", "action": "enter_text", "locator_strategy": "text", "locator_value": "Password"},
            ],
        }

        script = agent.generate_script_for_locator(locator_payload)

        self.assertIn("from appium.webdriver.common.appiumby import AppiumBy", script)
        self.assertIn("def tap(", script)
        self.assertIn("def type(", script)
        self.assertIn("def scroll(", script)
        self.assertIn("AppiumBy.ANDROID_UIAUTOMATOR", script)
        self.assertIn("EC.element_to_be_clickable", script)

    def test_generate_scripts_from_directory_writes_one_script_per_locator_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            output_dir = temp_path / "output"
            input_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            locator_payloads = [
                {"screen": "Login", "elements": [{"element": "Login", "action": "tap", "locator_strategy": "text", "locator_value": "Login"}]},
                {"screen": "Cart", "elements": [{"element": "Checkout", "action": "tap", "locator_strategy": "text", "locator_value": "Checkout"}]},
            ]

            for index, payload in enumerate(locator_payloads, start=1):
                input_path = input_dir / f"locator_{index}.json"
                with input_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle)

            agent = AppiumGeneratorAgent(project_root=temp_path)
            output_files = agent.generate_scripts_from_directory(input_dir=input_dir, output_dir=output_dir)

            self.assertEqual(len(output_files), 2)
            self.assertTrue((output_dir / "test_login_screen.py").exists())
            self.assertTrue((output_dir / "test_cart_screen.py").exists())


if __name__ == "__main__":
    unittest.main()
