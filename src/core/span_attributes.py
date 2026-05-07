# -*- coding: utf-8 -*-
"""
Custom span attributes for OpenTelemetry tracing in GIA.

Provides a helper to inject custom attributes into the current span
regardless of whether tracing is enabled (graceful no-op when no active span).

Usage:
    from src.core.span_attributes import set_span_attribute, set_span_attributes

    @trace(name="github.search_repositories")
    def search_repositories(self, query, ...):
        result = self._do_search(query)
        set_span_attributes({
            "search.query_hash": _hash(query),
            "search.result_count": len(result),
            "search.per_page": per_page,
        })
        return result
"""

import hashlib
from typing import Any, Dict


def _hash(value: str, length: int = 8) -> str:
    """Return a truncated SHA-256 hash for privacy-safe query identification."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def set_span_attribute(key: str, value: Any) -> None:
    """Set a single attribute on the current OpenTelemetry span.

    Gracefully no-ops when no active span or OTel is unavailable.
    """
    try:
        from opentelemetry.trace import get_current_span
        span = get_current_span()
        if span and span.is_recording():
            # OTel attributes support str, int, float, bool
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(key, value)
            elif value is None:
                span.set_attribute(key, "None")
            else:
                span.set_attribute(key, str(value))
    except Exception:
        pass


def set_span_attributes(attributes: Dict[str, Any]) -> None:
    """Set multiple attributes on the current OpenTelemetry span.

    Args:
        attributes: Dict mapping attribute keys to values.
    """
    for key, value in attributes.items():
        set_span_attribute(key, value)


def set_span_error(error: Exception) -> None:
    """Record an error on the current span."""
    try:
        from opentelemetry.trace import get_current_span, StatusCode
        span = get_current_span()
        if span and span.is_recording():
            span.set_status(StatusCode.ERROR, str(error))
            span.record_exception(error)
    except Exception:
        pass


class SpanTimer:
    """Context manager that records elapsed time as a span attribute."""

    def __init__(self, prefix: str = "duration_ms"):
        self.prefix = prefix

    def __enter__(self):
        import time
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        import time
        elapsed_ms = (time.monotonic() - self._start) * 1000
        set_span_attribute(self.prefix, round(elapsed_ms, 2))
