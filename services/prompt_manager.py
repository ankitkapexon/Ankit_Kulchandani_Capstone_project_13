"""Prompt loading utilities with alias resolution and caching."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class PromptManager:
    """Loads prompts from the prompts directory using stable logical keys."""

    _ALIASES = {
        "vision": ("vision_analysis.txt",),
        "testcase": ("test_generation.txt",),
        "locator": ("locator_prompt.txt", "LocatorAgent_Prompt.txt"),
        "review": ("review_prompt.txt", "Reviewer_Prompt.txt"),
        "appium": ("AppiumScrip_prompt.txt",),
    }

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.prompts_dir = self.project_root / "prompts"

    @lru_cache(maxsize=32)
    def load(self, key: str) -> str | None:
        key = key.strip().lower()
        candidates = self._ALIASES.get(key)
        if not candidates:
            candidates = (f"{key}.txt",)

        for filename in candidates:
            path = self.prompts_dir / filename
            if path.exists():
                return path.read_text(encoding="utf-8")
        return None
