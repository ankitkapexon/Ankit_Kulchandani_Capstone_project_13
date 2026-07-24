"""Shared OpenAI client and completion helpers used by agents."""

from __future__ import annotations

from typing import Any

from openai import OpenAI


def build_openai_client(api_key: str | None, api_base: str | None = None) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=api_base or None)


def create_chat_completion(
    client: OpenAI,
    *,
    model: str,
    prompt: str,
    max_tokens: int = 1024,
) -> Any:
    request_kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if str(model).lower().startswith("gpt-5"):
        request_kwargs["temperature"] = 1
    else:
        request_kwargs["temperature"] = 0

    try:
        return client.chat.completions.create(**request_kwargs)
    except Exception as exc:
        message = str(exc)
        if "temperature" in message and "UnsupportedParamsError" in message:
            request_kwargs.pop("temperature", None)
            return client.chat.completions.create(**request_kwargs)
        raise
