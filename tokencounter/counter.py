"""Token counting via the Anthropic count_tokens endpoint."""

import os
from typing import Any

import anthropic


def count_tokens(
    prompt: str,
    system: str | None = None,
    model: str = "claude-opus-4-7",
    api_key: str | None = None,
) -> dict[str, int]:
    """Count tokens in a prompt without consuming API credits for generation.

    Returns dict with input_token_count.
    """
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    result = client.messages.count_tokens(**kwargs)
    return {"input_token_count": result.input_tokens}


def count_tokens_multi_turn(
    messages: list[dict],
    system: str | None = None,
    model: str = "claude-opus-4-7",
    api_key: str | None = None,
) -> dict[str, int]:
    """Count tokens for a multi-turn conversation."""
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    result = client.messages.count_tokens(**kwargs)
    return {"input_token_count": result.input_tokens}


# Approximate per-model context window limits (tokens)
CONTEXT_LIMITS = {
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-haiku": 200_000,
}

DEFAULT_CONTEXT_LIMIT = 200_000


def get_context_limit(model: str) -> int:
    for key, limit in CONTEXT_LIMITS.items():
        if model.startswith(key):
            return limit
    return DEFAULT_CONTEXT_LIMIT


def context_usage_pct(used_tokens: int, model: str) -> float:
    return used_tokens / get_context_limit(model) * 100
