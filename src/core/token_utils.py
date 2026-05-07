# -*- coding: utf-8 -*-
"""
Token counting utilities using tiktoken.

Provides token estimation for prompt building, context window budget management,
and safe truncation to prevent model context overflow.
"""

from typing import Optional

from src.core.logger import get_logger

logger = get_logger(__name__)

# tiktoken encoding for qwen models (uses cl100k_base)
_ENCODING_NAME = "cl100k_base"


def _get_encoding() -> object:
    """Lazy-load tiktoken encoding."""
    import tiktoken
    return tiktoken.get_encoding(_ENCODING_NAME)


def count_tokens(text: str, encoding: Optional[object] = None) -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Input text
        encoding: Optional pre-loaded tiktoken encoding (avoids re-loading)

    Returns:
        Token count
    """
    if not text:
        return 0
    if encoding is None:
        encoding = _get_encoding()
    return len(encoding.encode(text))


def truncate_to_tokens(
    text: str,
    max_tokens: int,
    encoding: Optional[object] = None,
) -> str:
    """
    Truncate text to fit within max_tokens.

    Uses binary search for efficient truncation.

    Args:
        text: Input text
        max_tokens: Maximum token count
        encoding: Optional pre-loaded tiktoken encoding

    Returns:
        Truncated text (char-accurate approximation)
    """
    if not text or max_tokens <= 0:
        return ""

    if encoding is None:
        encoding = _get_encoding()

    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # Approximate: each token is ~4 chars on average
    approx_chars = int(max_tokens * 3.5)
    truncated = text[:approx_chars]

    # Verify and adjust
    actual_tokens = len(encoding.encode(truncated))
    if actual_tokens > max_tokens:
        # Binary search for exact boundary
        lo, hi = 0, len(truncated)
        while lo < hi:
            mid = (lo + hi) // 2
            if len(encoding.encode(text[:mid])) <= max_tokens:
                lo = mid + 1
            else:
                hi = mid
        truncated = text[:lo]

    logger.debug(f"Truncated text from {len(tokens)} to {len(encoding.encode(truncated))} tokens")
    return truncated


def estimate_messages_tokens(messages: list, encoding: Optional[object] = None) -> int:
    """
    Estimate total tokens for a list of message dicts.

    Args:
        messages: List of {"role": ..., "content": ...} dicts
        encoding: Optional pre-loaded tiktoken encoding

    Returns:
        Total token count
    """
    if encoding is None:
        encoding = _get_encoding()

    total = 0
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "")
        # Each message has overhead for role + formatting (~4 tokens)
        total += count_tokens(f"{role}: {content}", encoding) + 4
    return total
