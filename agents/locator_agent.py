import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.app_config import AppConfig, get_config
from services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class LocatorAgent:
    """Convert SSM JSON and manual test steps into structured locator metadata."""

    def __init__(
        self,
        project_root: Optional[Path | str] = None,
        config: Optional[AppConfig] = None,
        prompt_manager: Optional[PromptManager] = None,
    ) -> None:
        self.config = config or get_config()
        self.project_root = Path(project_root) if project_root else self.config.project_root
        self.prompt_manager = prompt_manager or PromptManager(self.project_root)
        self.prompt_template = self.prompt_manager.load("locator")

        self._action_keywords = {
            "scroll": ["scroll", "swipe"],
            "type": ["enter", "type", "input", "fill", "set", "write"],
            "tap": ["tap", "click", "press", "select", "toggle", "choose", "open"],
            "verify": ["verify", "displayed", "visible", "check", "seen", "exists", "present"],
        }

    def run(self) -> List[Path]:
        """Generate locator files for all matching SSM/manual testcase pairs."""
        results = self.process_artifact_files()
        return [Path(item["output_file"]) for item in results]

    def generate_locators(self, ssm_data: Any, test_case_text: Any) -> Dict[str, Any]:
        ssm_payload = self._load_ssm_payload(ssm_data)
        elements = ssm_payload.get("elements") or []
        if not elements:
            raise ValueError("SSM data does not contain any elements.")

        steps = self._load_test_case_steps(test_case_text)
        if not steps:
            raise ValueError("Test case text is empty.")

        screen = ssm_payload.get("screen_name", "unknown")
        logger.info("[LocatorAgent] Extracting locators for screen: '%s' (%d elements)", screen, len(elements))

        generated_elements: List[Dict[str, Any]] = []
        element_lookup: Dict[str, Dict[str, Any]] = {}

        for step in steps:
            normalized_step = self._normalize_text(step)
            if not normalized_step:
                continue

            matched_element = self._find_best_element_match(normalized_step, elements)
            if matched_element is None:
                continue

            action = self._infer_action(normalized_step, matched_element)
            locator_entry = self._build_locator_entry(matched_element, action, normalized_step)
            element_key = locator_entry["element"].lower()

            if element_key in element_lookup:
                existing_entry = element_lookup[element_key]
                existing_entry["action"] = self._resolve_action(existing_entry["action"], locator_entry["action"])
                if existing_entry.get("confidence") is None and locator_entry.get("confidence") is not None:
                    existing_entry["confidence"] = locator_entry["confidence"]
                continue

            generated_elements.append(locator_entry)
            element_lookup[element_key] = locator_entry

        return {
            "screen": ssm_payload.get("screen_name") or ssm_payload.get("screen") or "Unknown",
            "elements": generated_elements,
        }

    def process_artifact_files(self) -> List[Dict[str, Any]]:
        ssm_dir = self.config.ssm_output_dir
        manual_dir = self.config.manual_testcases_dir
        output_dir = self.config.locator_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        ssm_files = sorted(ssm_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if ssm_dir.exists() else []
        manual_files = sorted(manual_dir.glob("*.txt")) if manual_dir.exists() else []

        if not ssm_files:
            raise FileNotFoundError(f"No SSM JSON files were found in {ssm_dir}")
        if not manual_files:
            raise FileNotFoundError(f"No manual test case files were found in {manual_dir}")

        processed_results: List[Dict[str, Any]] = []
        for ssm_path in ssm_files:
            ssm_metadata = self._parse_artifact_name(ssm_path.name)
            if not ssm_metadata:
                continue

            matching_manual = self._find_matching_manual_file(manual_files, ssm_metadata)
            if matching_manual is None:
                continue

            with open(ssm_path, "r", encoding="utf-8") as handle:
                ssm_payload = json.load(handle)

            with open(matching_manual, "r", encoding="utf-8") as handle:
                test_case_text = handle.read()

            locator_payload = self.generate_locators(ssm_payload, test_case_text)
            screen_name = locator_payload.get("screen") or ssm_metadata["screen_name"]
            output_filename = f"locator_{self._slugify(screen_name)}.json"
            output_path = output_dir / output_filename

            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(locator_payload, handle, indent=2)
                handle.write("\n")

            processed_results.append(
                {
                    "screen": screen_name,
                    "ssm_file": str(ssm_path),
                    "manual_file": str(matching_manual),
                    "output_file": str(output_path),
                }
            )

        return processed_results

    def _load_ssm_payload(self, ssm_data: Any) -> Dict[str, Any]:
        if isinstance(ssm_data, dict):
            return ssm_data

        if isinstance(ssm_data, str):
            candidate = ssm_data.strip()
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as handle:
                    return self._parse_json(handle.read(), "SSM")

            return self._parse_json(candidate, "SSM")

        raise TypeError("SSM input must be a dictionary, JSON string, or file path.")

    def _load_test_case_steps(self, test_case_text: Any) -> List[str]:
        if isinstance(test_case_text, str):
            candidate = test_case_text.strip()
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as handle:
                    return [line.strip() for line in handle.readlines() if line.strip()]

            return [line.strip() for line in candidate.splitlines() if line.strip()]

        raise TypeError("Test case input must be text or a file path.")

    def _parse_json(self, raw_text: str, payload_name: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid {payload_name} JSON.") from exc

        if not isinstance(parsed, dict):
            raise ValueError(f"{payload_name} JSON must be an object.")
        return parsed

    def _normalize_text(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"\s+", " ", value.strip().lower())

    def _find_best_element_match(self, step_text: str, elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best_element: Optional[Dict[str, Any]] = None
        best_score = -1

        for element in elements:
            label = self._normalize_text(element.get("label") or element.get("element"))
            if not label:
                continue

            score = self._score_element_match(label, step_text)
            if score > best_score:
                best_score = score
                best_element = element

        if best_score <= 0:
            return None
        return best_element

    def _score_element_match(self, label: str, step_text: str) -> int:
        if label in step_text:
            return len(label.split()) + 3

        label_tokens = set(re.findall(r"[a-z0-9]+", label))
        step_tokens = set(re.findall(r"[a-z0-9]+", step_text))
        return len(label_tokens & step_tokens)

    def _infer_action(self, step_text: str, element: Dict[str, Any]) -> str:
        element_type = self._classify_element_type(element)
        step_action = self._infer_step_action(step_text)

        if element_type in {"text_field", "password_field", "email_field", "search_field"}:
            if step_action == "verify":
                return "verify"
            return "type"

        if element_type in {"button", "checkbox", "radio_button", "toggle_switch", "dropdown"}:
            if step_action == "verify":
                return "verify"
            return "tap"

        if element_type == "list":
            return "scroll"

        if element_type in {"image", "label", "static_text"}:
            return "verify"

        if step_action in {"scroll", "type", "tap", "verify"}:
            return step_action

        element_actions = [str(action).lower() for action in (element.get("actions") or [])]
        if "tap" in element_actions:
            return "tap"
        if "scroll" in element_actions:
            return "scroll"
        if "verify" in element_actions:
            return "verify"
        return "verify"

    def _build_locator_entry(self, element: Dict[str, Any], action: str, step_text: str) -> Dict[str, Any]:
        label = element.get("label") or element.get("element") or "Unknown"
        element_type = self._classify_element_type(element)
        locator_strategy, locator_value = self._select_locator_strategy(element)
        entry: Dict[str, Any] = {
            "element": label,
            "element_type": element_type,
            "action": action,
            "locator_strategy": locator_strategy,
            "locator_value": self._suggest_locator_value(element, action, step_text, locator_value),
            "confidence": element.get("confidence"),
        }

        if action == "type" and self._is_input_element_type(element_type):
            entry["input_value"] = self._suggest_input_value(element, label)
        return entry

    def _resolve_action(self, existing_action: str, new_action: str) -> str:
        if existing_action == new_action:
            return existing_action

        priority = {"type": 0, "tap": 1, "scroll": 2, "verify": 3}
        if existing_action in priority and new_action in priority:
            return existing_action if priority[existing_action] <= priority[new_action] else new_action
        return existing_action or new_action

    def _select_locator_strategy(self, element: Dict[str, Any]) -> tuple[str, str]:
        value = self._extract_locator_value(element, ("resource_id", "resource-id", "resourceId"))
        if value:
            return "resource_id", str(value)

        value = self._extract_locator_value(
            element,
            ("accessibility_id", "content_desc", "content-desc", "contentDescription", "accessibilityId"),
        )
        if value:
            return "accessibility_id", str(value)

        value = self._extract_locator_value(element, ("id", "android_id", "view_id"))
        if value:
            return "id", str(value)

        text_value = self._extract_locator_value(element, ("text",))
        if text_value:
            return "text", str(text_value)

        value = element.get("android_uiautomator") or element.get("uiautomator")
        if value:
            return "android_uiautomator", str(value)

        override = self._guess_app_specific_locator(element)
        if override:
            return override

        label = str(element.get("label") or element.get("element") or "").lower()
        if "username" in label:
            return "android_uiautomator", 'new UiSelector().className("android.widget.EditText").instance(0)'
        if "password" in label:
            return "android_uiautomator", 'new UiSelector().className("android.widget.EditText").instance(1)'
        if label:
            return "text", label

        return "text", "unknown"

    def _extract_locator_value(self, element: Dict[str, Any], field_names: tuple[str, ...]) -> Optional[str]:
        for field_name in field_names:
            value = element.get(field_name)
            if value:
                return str(value)

        metadata = element.get("metadata")
        if isinstance(metadata, dict):
            for field_name in field_names:
                value = metadata.get(field_name)
                if value:
                    return str(value)

        return None

    def _guess_app_specific_locator(self, element: Dict[str, Any]) -> Optional[tuple[str, str]]:
        if not self.config.app_specific_locator_hints_enabled:
            return None

        app_package = (self.config.app_package or "").strip()
        if not app_package:
            return None

        label = str(element.get("element") or element.get("label") or "").strip().lower()
        normalized_label = re.sub(r"[^a-z0-9]+", "_", label).strip("_")

        preset = self.config.app_profile_preset

        preset_locators: dict[str, tuple[str, str]] = {}
        if preset == "banking":
            preset_locators = {
                "login": ("text", "Sign In"),
                "username": ("resource_id", f"{app_package}:id/username"),
                "password": ("resource_id", f"{app_package}:id/password"),
                "accounts": ("text", "Accounts"),
                "payments": ("text", "Payments"),
                "transfer": ("text", "Transfer"),
            }
        elif preset == "social":
            preset_locators = {
                "login": ("text", "Log In"),
                "feed": ("text", "Home"),
                "profile": ("text", "Profile"),
                "search": ("text", "Search"),
                "messages": ("text", "Messages"),
            }

        app_specific_locators = {
            "login": ("resource_id", f"{app_package}:id/loginBtn"),
            "username": ("resource_id", f"{app_package}:id/nameET"),
            "password": ("resource_id", f"{app_package}:id/passwordET"),
            "menu": ("resource_id", f"{app_package}:id/menuIV"),
            "product_image": ("resource_id", f"{app_package}:id/productIV"),
            "product": ("resource_id", f"{app_package}:id/productIV"),
            "product_title": ("resource_id", f"{app_package}:id/productTV"),
            "title": ("resource_id", f"{app_package}:id/productTV"),
            "price": ("resource_id", f"{app_package}:id/priceTV"),
            "add_to_cart": ("resource_id", f"{app_package}:id/cartBt"),
            "cart": ("resource_id", f"{app_package}:id/cartIV"),
            "cart_title": ("resource_id", f"{app_package}:id/titleTV"),
            "checkout": ("resource_id", f"{app_package}:id/cartBt"),
            "quantity_controls": ("resource_id", f"{app_package}:id/plusIV"),
            "subtotal": ("resource_id", f"{app_package}:id/totalPriceTV"),
            "remove_item": ("resource_id", f"{app_package}:id/removeBt"),
        }

        if preset_locators:
            app_specific_locators = {**preset_locators, **app_specific_locators} if preset == "ecommerce" else preset_locators

        for key, locator in app_specific_locators.items():
            normalized_key = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if normalized_key == normalized_label:
                return locator
        return None

    def _infer_step_action(self, step_text: str) -> str:
        for action_name, keywords in self._action_keywords.items():
            if any(keyword in step_text for keyword in keywords):
                return action_name
        return "verify"

    def _classify_element_type(self, element: Dict[str, Any]) -> str:
        raw_type = str(element.get("element_type") or element.get("type") or "").strip().lower()
        if not raw_type:
            return "unknown"

        normalized = raw_type.replace(" ", "_").replace("-", "_")
        mapping = {
            "button": "button",
            "icon_button": "button",
            "link": "button",
            "text_field": "text_field",
            "textfield": "text_field",
            "textinput": "text_field",
            "input": "text_field",
            "edit_text": "text_field",
            "password": "password_field",
            "password_field": "password_field",
            "email": "email_field",
            "email_field": "email_field",
            "search": "search_field",
            "search_field": "search_field",
            "checkbox": "checkbox",
            "radio": "radio_button",
            "radio_button": "radio_button",
            "switch": "toggle_switch",
            "toggle": "toggle_switch",
            "toggle_switch": "toggle_switch",
            "dropdown": "dropdown",
            "select": "dropdown",
            "list": "list",
            "image": "image",
            "label": "label",
            "static_text": "static_text",
            "statictext": "static_text",
            "text": "static_text",
        }
        return mapping.get(normalized, normalized)

    def _is_input_element_type(self, element_type: str) -> bool:
        return element_type in {"text_field", "password_field", "email_field", "search_field"}

    def _suggest_input_value(self, element: Dict[str, Any], label: str) -> str:
        if element.get("input_value"):
            return str(element.get("input_value"))

        lower_label = str(label).lower()
        if "password" in lower_label or "pwd" in lower_label:
            return "10203040"
        if "username" in lower_label or "user" in lower_label:
            return "bod@example.com"
        if "email" in lower_label:
            return "test@example.com"
        if "search" in lower_label:
            return "Test"
        if "phone" in lower_label or "mobile" in lower_label:
            return "9876543210"
        return "test"

    def _suggest_locator_value(self, element: Dict[str, Any], action: str, step_text: str, fallback_value: str) -> str:
        label = str(element.get("label") or "").strip()

        # If an incoming resource id points to a different app package, prefer
        # known app-specific resource ids for this project profile.
        if fallback_value and ":id/" in fallback_value and self.config.app_specific_locator_hints_enabled:
            app_package = (self.config.app_package or "").strip()
            if app_package and not fallback_value.startswith(f"{app_package}:"):
                override = self._guess_app_specific_locator(element)
                if override and override[0] == "resource_id":
                    return override[1]

        if fallback_value and fallback_value != label:
            return str(fallback_value)
        if label:
            return label
        if step_text:
            return step_text
        return "unknown"

    def _parse_artifact_name(self, filename: str) -> Optional[Dict[str, str]]:
        stem = Path(filename).stem
        for prefix in ("manual_testcases_", "ssm_"):
            if stem.startswith(prefix):
                stem = stem[len(prefix) :]

        parts = [part for part in re.split(r"[_\s]+", stem) if part]
        if not parts:
            return None

        screen_name = parts[0]
        identifier = next((part for part in parts[1:] if part.isdigit()), None)
        return {"screen_name": screen_name, "identifier": identifier or ""}

    def _find_matching_manual_file(self, manual_files: List[Path], ssm_metadata: Dict[str, str]) -> Optional[Path]:
        screen_name = self._normalize_text(ssm_metadata.get("screen_name", ""))
        identifier = ssm_metadata.get("identifier", "")

        for manual_path in manual_files:
            manual_metadata = self._parse_artifact_name(manual_path.name)
            if not manual_metadata:
                continue

            if (
                self._normalize_text(manual_metadata.get("screen_name", "")) == screen_name
                and manual_metadata.get("identifier", "") == identifier
            ):
                return manual_path

        return None

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
        return slug.strip("._-") or "screen"


def main() -> None:
    agent = LocatorAgent()
    results = agent.process_artifact_files()
    print(f"Processed {len(results)} locator files.")
    for result in results:
        print(f"- {result['screen']}: {result['output_file']}")


if __name__ == "__main__":
    main()
