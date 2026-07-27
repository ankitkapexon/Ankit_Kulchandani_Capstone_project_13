"""Reusable retry and wait helpers for runtime reliability."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Configurable retry/backoff policy."""

    attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0


def with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Run operation with bounded retries and exponential backoff."""
    delay = max(0.0, float(policy.initial_delay_seconds))
    last_error: BaseException | None = None

    for attempt in range(1, max(1, policy.attempts) + 1):
        try:
            return operation()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= policy.attempts:
                break
            if delay > 0:
                time.sleep(delay)
            delay = min(max(0.0, float(policy.max_delay_seconds)), delay * float(policy.backoff_multiplier or 1.0))

    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry operation failed without captured exception")


def wait_until(
    predicate: Callable[[], bool],
    *,
    policy: RetryPolicy,
) -> bool:
    """Poll predicate until it becomes true or retries are exhausted."""

    def _probe() -> bool:
        if predicate():
            return True
        raise RuntimeError("Condition not ready")

    try:
        with_retry(_probe, policy=policy, retry_exceptions=(Exception,))
        return True
    except Exception:
        return False
