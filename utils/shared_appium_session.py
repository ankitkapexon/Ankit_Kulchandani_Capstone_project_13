"""Shared Appium driver session helpers.

This module allows generated tests to reuse one Appium session for an entire
pytest run, so the app is launched once and steps execute in a single flow.
"""

from __future__ import annotations

import atexit
import os
from typing import Any, Callable, Optional


_shared_driver: Optional[Any] = None
_atexit_registered = False


def _single_session_enabled() -> bool:
    value = os.getenv("SINGLE_APP_SESSION", "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def get_or_create_driver(factory: Callable[[], Any]) -> Any:
    """Return a shared Appium driver when single-session mode is enabled."""
    driver, _is_new = get_or_create_driver_with_state(factory)
    return driver


def get_or_create_driver_with_state(factory: Callable[[], Any]) -> tuple[Any, bool]:
    """Return shared Appium driver and whether it was created in this call."""
    global _shared_driver
    global _atexit_registered

    if not _single_session_enabled():
        return factory(), True

    if _shared_driver is not None and getattr(_shared_driver, "session_id", None):
        return _shared_driver, False

    _shared_driver = factory()

    if not _atexit_registered:
        atexit.register(close_shared_driver)
        _atexit_registered = True

    return _shared_driver, True


def should_quit_driver() -> bool:
    """Whether generated teardown should quit the active driver."""
    return not _single_session_enabled()


def close_shared_driver() -> None:
    """Best-effort shutdown of the shared driver at process exit."""
    global _shared_driver

    if _shared_driver is None:
        return

    try:
        _shared_driver.quit()
    except Exception:
        pass
    finally:
        _shared_driver = None
