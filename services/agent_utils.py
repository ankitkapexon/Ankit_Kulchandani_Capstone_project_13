"""Shared utilities for agent behavior that must remain consistent."""

from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_SCREEN_ELEMENTS: List[Dict[str, Any]] = [
    {
        "id": "screen_root",
        "type": "container",
        "text": "",
        "bounds": [0, 0, 1080, 2400],
        "attributes": {"description": "Main screen container"},
    },
    {
        "id": "primary_action",
        "type": "button",
        "text": "Continue",
        "bounds": [390, 2100, 690, 2200],
        "attributes": {"clickable": True},
    },
]


def infer_screen_name(image_path: str) -> str:
    """Infer a stable screen name from file path keywords."""
    lower = image_path.lower()
    if "login" in lower:
        return "Login"
    if "product_listing" in lower or "product listing" in lower:
        return "Product Listing"
    if "product_details" in lower or "product details" in lower:
        return "Product Details"
    if "cart" in lower:
        return "Cart"
    return "Unknown Screen"


def ensure_non_empty_elements(elements: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    """Guarantee that downstream stages receive at least baseline elements."""
    if elements:
        return elements
    return list(DEFAULT_SCREEN_ELEMENTS)
