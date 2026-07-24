"""Test case agent — abstract base, concrete OpenAI/Mock implementations, and factory.

Structure mirrors agents/vision_agent.py for consistency.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from openai import OpenAI
from services.llm_client import build_openai_client, create_chat_completion

logger = logging.getLogger(__name__)


# ── Abstract base ─────────────────────────────────────────────────────────────

class TestCaseAgent(ABC):
    """Abstract base class for agents that generate manual test cases from SSM JSON."""

    @abstractmethod
    def generate_from_ssm(self, ssm_data: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError()


# ── OpenAI implementation ─────────────────────────────────────────────────────

class OpenAITestCaseAgent(TestCaseAgent):
    """Generates manual test cases from SSM JSON using an OpenAI-compatible model."""

    def __init__(self, prompt_template: str = None):
        self.prompt_template = prompt_template
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("OPENAI_API_BASE")
        self._client = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = build_openai_client(api_key=self.api_key, api_base=self.api_base)
        return self._client

    def _create_chat_completion(self, client: OpenAI, prompt: str):
        return create_chat_completion(client, model=self.model, prompt=prompt, max_tokens=1024)

    def _build_prompt(self, ssm_json: str, filename: str = None) -> str:
        if self.prompt_template:
            return (
                self.prompt_template
                .replace("{{ssm_json}}", ssm_json)
                .replace("{{filename}}", filename or "ssm")
            )
        return (
            "You are a test case generation assistant. Given the Screen Semantic Model JSON, "
            "generate a plain-text manual test case specification. "
            "Do not output JSON, code, or Appium locators. Use numbered test cases and numbered steps.\n\n"
            "SSM_JSON:\n" + ssm_json
        )

    def generate_from_ssm(self, ssm_data: Dict[str, Any], **kwargs) -> str:
        try:
            client = self._get_client()
        except Exception as exc:
            raise RuntimeError("openai package is required for OpenAITestCaseAgent") from exc

        screen = ssm_data.get("screen_name", "unknown")
        logger.info("[TestCaseAgent] Generating test cases for screen: '%s'", screen)
        ssm_json = json.dumps(ssm_data, indent=2)
        prompt = self._build_prompt(ssm_json, filename=kwargs.get("filename"))
        try:
            resp = self._create_chat_completion(client, prompt)
            result = resp.choices[0].message.content.strip()
            logger.info("[TestCaseAgent] Test cases generated for screen: '%s'", screen)
            return result
        except Exception as exc:
            raise RuntimeError(f"Test case generation failed: {exc}")


# ── Mock implementation ───────────────────────────────────────────────────────

class MockTestCaseAgent(TestCaseAgent):
    """Offline mock agent — generates test cases from SSM data without calling any LLM."""

    def _element_label(self, element: Dict[str, Any]) -> str:
        return element.get("label") or element.get("id") or "UI element"

    def _build_cases_from_elements(
        self, screen_name: str, screen_purpose: str, elements: List[Dict[str, Any]]
    ) -> List[str]:
        lines: List[str] = []
        text_fields = [el for el in elements if str(el.get("type") or "").lower() in {"textfield", "searchbar", "input"}]
        buttons     = [el for el in elements if str(el.get("type") or "").lower() in {"button", "link", "icon_button"}]
        selectable  = [el for el in elements if str(el.get("type") or "").lower() in {"product_card", "list_item", "checkbox", "switch"}]

        if text_fields:
            first_field = text_fields[0]
            lines += [
                f"Test Case 1: Validate input handling on {screen_name}",
                "Test ID: TC-001", "Priority: High", "Type: Functional",
                f"Description: Verify the user can enter data into the {self._element_label(first_field)} field.",
                "Preconditions:", f"  - The {screen_name} screen is available.",
                "Steps:", f"  1. Open the {screen_name} screen.",
                f"  2. Enter sample text into the {self._element_label(first_field)} field.",
            ]
            if buttons:
                lines.append(f"  3. Tap the {self._element_label(buttons[0])} control.")
            lines += ["Expected Result:", "  - The entered data is accepted.", ""]

        if buttons:
            primary = buttons[0]
            lines += [
                f"Test Case 2: Verify primary action on {screen_name}",
                "Test ID: TC-002", "Priority: High", "Type: Functional",
                f"Description: Validate the main action for the {self._element_label(primary)} control.",
                "Preconditions:", f"  - The {screen_name} screen is displayed.",
                "Steps:", f"  1. Open the {screen_name} screen.",
                f"  2. Tap the {self._element_label(primary)} control.",
                "Expected Result:", "  - The expected action is triggered.", "",
            ]

        if selectable:
            item = selectable[0]
            lines += [
                f"Test Case 3: Verify selection interaction on {screen_name}",
                "Test ID: TC-003", "Priority: Medium", "Type: Functional",
                f"Description: Ensure the user can select the {self._element_label(item)} item.",
                "Preconditions:", f"  - The {screen_name} screen contains at least one selectable item.",
                "Steps:", f"  1. Open the {screen_name} screen.",
                f"  2. Tap the {self._element_label(item)} item.",
                "Expected Result:", "  - The item opens or transitions correctly.", "",
            ]

        if not lines:
            lines += [
                f"Test Case 1: Validate main screen experience for {screen_name}",
                "Test ID: TC-001", "Priority: Medium", "Type: Functional",
                f"Description: Confirm the {screen_name} screen loads correctly.",
                "Steps:", f"  1. Open the {screen_name} screen.",
                "  2. Verify the screen loads without errors.",
                "Expected Result:", "  - The screen appears correctly.",
            ]
        return lines

    def _build_flow_cases(self, screens: List[Dict[str, Any]]) -> List[str]:
        if len(screens) < 2:
            return []
        lines = [
            "End-to-End Flow 1: User journey across the main screens",
            "Test ID: E2E-001", "Priority: High", "Type: End-to-End",
            "Description: Verify the user can move through the primary application flow.",
            "Steps:",
        ]
        for i, screen in enumerate(screens, start=1):
            name = screen.get("screen_name") or f"Screen {i}"
            lines.append(f"  {i}. Open the {name} screen.")
        lines += ["Expected Result:", "  - The user navigates all screens successfully.", ""]
        return lines

    def generate_from_ssm(self, ssm_data: Dict[str, Any], **kwargs) -> str:
        if isinstance(ssm_data, dict) and isinstance(ssm_data.get("screens"), list):
            screens = ssm_data["screens"]
            logger.info("[TestCaseAgent][Mock] Generating test cases for %d screens", len(screens))
            lines = ["Manual test cases generated from SSM JSON:", ""]
            for screen in screens:
                screen_name    = screen.get("screen_name") or "Unnamed Screen"
                screen_purpose = screen.get("screen_purpose", "")
                elements       = screen.get("elements", [])
                lines += [f"Screen: {screen_name}", ""]
                lines.extend(self._build_cases_from_elements(screen_name, screen_purpose, elements))
                lines.append("")
            lines.extend(self._build_flow_cases(screens))
            return "\n".join(lines)

        screen_name    = ssm_data.get("screen_name") or "Unnamed Screen"
        screen_purpose = ssm_data.get("screen_purpose", "")
        elements       = ssm_data.get("elements", [])
        lines = [f"Manual test cases for {screen_name} screen:", ""]
        lines.extend(self._build_cases_from_elements(screen_name, screen_purpose, elements))
        return "\n".join(lines)


# ── Factory ───────────────────────────────────────────────────────────────────

def create_testcase_agent(provider: str = None, prompt_template: str = None) -> TestCaseAgent:
    """Return the correct TestCaseAgent implementation for the given provider."""
    resolved = (provider or os.getenv("TESTCASE_AGENT_PROVIDER") or "").lower().strip()
    if not resolved:
        resolved = "openai" if os.getenv("OPENAI_API_KEY") else "mock"
    if resolved == "openai":
        return OpenAITestCaseAgent(prompt_template=prompt_template)
    if resolved == "mock":
        return MockTestCaseAgent()
    raise ValueError(f"Unsupported testcase provider: {resolved}")
