import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI
from pydantic import ValidationError

from models.ssm import ScreenSemanticModel
from services.agent_utils import ensure_non_empty_elements
from services.llm_client import build_openai_client, create_chat_completion

logger = logging.getLogger(__name__)


class VisionAgent(ABC):
    """Abstract base class for all vision/screenshot understanding agents."""

    def __init__(self, model_name: str | None = None, **kwargs):
        self.model_name = model_name

    @abstractmethod
    def analyze_image(self, image_path: str, **kwargs) -> Dict[str, Any]:
        """Analyse a screenshot and return a structured result."""
        raise NotImplementedError

    def validate_configuration(self) -> None:
        """Ensure agent configuration is valid before runtime."""
        return None


class OpenAIVisionAgent(VisionAgent):
    """Adapter for OpenAI-style multimodal models."""

    def __init__(self, prompt_template: str | None = None, model_name: str | None = None):
        super().__init__(model_name=model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("OPENAI_API_BASE")
        self.prompt_template = prompt_template
        self._client = None

    def validate_configuration(self) -> None:
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY is required for OpenAIVisionAgent.")

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = build_openai_client(api_key=self.api_key, api_base=self.api_base)
        return self._client

    def _create_chat_completion(self, client: OpenAI, prompt: str):
        return create_chat_completion(client, model=self.model_name, prompt=prompt, max_tokens=1024)

    def _infer_screen_name(self, raw_name: str | None, image_path: str | None = None, screen_purpose: str | None = None) -> str | None:
        if raw_name:
            normalized = str(raw_name).strip()
            if normalized.lower() not in {"unknown", "unspecified", "n/a", "none", "screen", ""}:
                return normalized

        stem = Path(image_path).stem if image_path else ""
        normalized_stem = stem.lower().replace(" ", "_").replace("-", "_")

        if "login" in normalized_stem:
            return "Login"
        if "cart" in normalized_stem:
            return "Cart"
        if "detail" in normalized_stem or "product_detail" in normalized_stem or "productdetails" in normalized_stem:
            return "Product Details"
        if "listing" in normalized_stem or "product_listing" in normalized_stem or "productlist" in normalized_stem or "products" in normalized_stem or "search" in normalized_stem:
            return "Product Listing"
        if "checkout" in normalized_stem:
            return "Checkout"
        if "home" in normalized_stem:
            return "Home"
        if "profile" in normalized_stem:
            return "Profile"
        if "settings" in normalized_stem:
            return "Settings"

        if screen_purpose:
            purpose = screen_purpose.lower()
            if "login" in purpose or "authenticate" in purpose:
                return "Login"
            if "cart" in purpose or "checkout" in purpose:
                return "Cart"
            if "detail" in purpose:
                return "Product Details"
            if "listing" in purpose or "search" in purpose or "product" in purpose:
                return "Product Listing"

        return raw_name or None

    def _default_elements_for_screen(self, screen_name: str | None) -> list[dict[str, Any]]:
        """Return minimal fallback elements for known screen types."""
        name = (screen_name or "").lower()

        if "login" in name:
            return [
                {"label": "Username", "type": "textfield", "actions": ["enter_text"], "confidence": 0.5},
                {"label": "Password", "type": "textfield", "actions": ["enter_text"], "confidence": 0.5},
                {"label": "Login", "type": "button", "actions": ["tap"], "confidence": 0.5},
            ]
        if "cart" in name:
            return [
                {"label": "Cart Item", "type": "label", "actions": ["verify"], "confidence": 0.45},
                {"label": "Checkout", "type": "button", "actions": ["tap"], "confidence": 0.5},
            ]
        if "product listing" in name or "listing" in name:
            return [
                {"label": "Product Item", "type": "card", "actions": ["tap", "scroll"], "confidence": 0.45},
                {"label": "Search", "type": "textfield", "actions": ["enter_text"], "confidence": 0.45},
            ]
        if "product details" in name or "detail" in name:
            return [
                {"label": "Product Title", "type": "label", "actions": ["verify"], "confidence": 0.45},
                {"label": "Add To Cart", "type": "button", "actions": ["tap"], "confidence": 0.5},
            ]

        return [
            {"label": "Primary Action", "type": "button", "actions": ["tap"], "confidence": 0.4}
        ]

    def _fallback_elements_for_screen(self, screen_name: str | None) -> list[dict[str, Any]]:
        """Preserve existing screen-specific fallback behavior with shared final guard."""
        custom = self._default_elements_for_screen(screen_name)
        return ensure_non_empty_elements(custom)

    def _build_prompt(self, image_b64: str, filename: str | None = None) -> str:
        if self.prompt_template:
            prompt = self.prompt_template
            name_hint = filename or "image"

            prompt = prompt.replace("{{filename}}", name_hint).replace("{filename}", name_hint)

            if "{{image_b64}}" in prompt or "{image_b64}" in prompt:
                return prompt.replace("{{image_b64}}", image_b64).replace("{image_b64}", image_b64)

            # Some custom prompts are instruction-only and do not provide an
            # explicit image placeholder. Append the image payload so analysis
            # remains multimodal instead of degrading to text-only inference.
            return f"{prompt}\n\nIMAGE_BASE64:\n{image_b64}"
    
        return f"""
                You are an expert Mobile UI Understanding Assistant.

                Analyze the mobile app screenshot and return ONLY valid JSON matching the ScreenSemanticModel schema.

                Rules:

                1. Detect every visible UI element.

                2. IMPORTANT:
                If a label is immediately followed by an editable text box, treat them as TWO separate elements.

                Example:

                Username
                [ empty input box ]

                Generate:

                {
                "label": "Username",
                "type": "label"
                }

                {
                "label": "Username Input",
                "type": "textfield"
                }

                Similarly:

                Password
                [ empty input box ]

                Generate:

                {
                "label": "Password",
                "type": "label"
                }

                {
                "label": "Password Input",
                "type": "password_field"
                }

                Buttons remain buttons.

                Never classify a label as a text field.

                Respond ONLY with valid JSON.

                IMAGE_BASE64:
                {image_b64}
                """

    def analyze_image(self, image_path: str, **kwargs) -> Dict[str, Any]:
        self.validate_configuration()
        logger.info("[VisionAgent] Analyzing screenshot: %s", os.path.basename(image_path))
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        image_b64 = base64.b64encode(img_bytes).decode("utf-8")

        prompt = self._build_prompt(image_b64, filename=os.path.basename(image_path))

        try:
            client = self._get_client()
            resp = self._create_chat_completion(client, prompt)
            text = resp.choices[0].message.content.strip()
        except Exception as exc:
            raise RuntimeError(f"Vision model call failed: {exc}")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                raise ValueError("Model response did not contain valid JSON")
            parsed = json.loads(match.group(0))

        try:
            ssm = ScreenSemanticModel.model_validate(parsed)
        except ValidationError as ve:
            raise ValueError(f"Response validation failed: {ve}")

        inferred_name = self._infer_screen_name(ssm.screen_name, image_path=image_path, screen_purpose=ssm.screen_purpose)
        if inferred_name:
            ssm.screen_name = inferred_name

        ssm_payload = ssm.model_dump()
        if not ssm_payload.get("elements"):
            ssm_payload["elements"] = self._fallback_elements_for_screen(ssm_payload.get("screen_name"))
            metadata = dict(ssm_payload.get("metadata") or {})
            metadata["auto_filled_elements"] = True
            metadata["auto_fill_reason"] = "vision_model_returned_empty_elements"
            ssm_payload["metadata"] = metadata
            ssm = ScreenSemanticModel.model_validate(ssm_payload)

        logger.info("[VisionAgent] SSM generated for screen: '%s' (%d elements)", ssm.screen_name, len(ssm.elements))
        return ssm.model_dump()


class MockVisionAgent(VisionAgent):
    """Mock agent for local pipeline testing without a real model provider."""

    def analyze_image(self, image_path: str, **kwargs) -> Dict[str, Any]:
        logger.info("[VisionAgent][Mock] Generating mock SSM for: %s", os.path.basename(image_path))
        stem = Path(image_path).stem
        return {
            "screen_name": stem.replace("_", " ").title(),
            "screen_purpose": "Understand the primary action for this screen.",
            "source": image_path,
            "elements": [
                {
                    "id": "action_1",
                    "label": "Primary button",
                    "type": "button",
                    "actions": ["tap"],
                    "confidence": 0.75,
                },
                {
                    "id": "field_1",
                    "label": "Input field",
                    "type": "textfield",
                    "actions": ["enter_text"],
                    "confidence": 0.65,
                },
            ],
            "metadata": {
                "note": "Mock output; replace with real vision provider for production.",
            },
        }


def create_vision_agent(provider: str = "openai", prompt_template: str = None) -> VisionAgent:
    provider = provider.lower().strip()
    if provider == "openai":
        return OpenAIVisionAgent(prompt_template=prompt_template)
    if provider == "mock":
        return MockVisionAgent()
    raise ValueError(f"Unsupported vision provider: {provider}")
