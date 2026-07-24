import unittest

from models.ssm import ScreenSemanticModel


class SSMModelTests(unittest.TestCase):
    def test_accepts_varied_element_types_and_actions(self) -> None:
        payload = {
            "screen_name": "Product Listing",
            "screen_purpose": "Browse available products",
            "elements": [
                {"label": "Search", "type": "search_field", "actions": ["view_items"]},
                {"label": "Product card", "type": "list", "actions": ["view"]},
                {"label": "Stepper", "type": "stepper", "actions": ["increase", "decrease"]},
            ],
        }

        model = ScreenSemanticModel.model_validate(payload)

        self.assertEqual(model.screen_name, "Product Listing")
        self.assertEqual(model.elements[0].type, "search_field")
        self.assertEqual(model.elements[2].actions, ["increase", "decrease"])


if __name__ == "__main__":
    unittest.main()
