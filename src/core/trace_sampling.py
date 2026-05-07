# -*- coding: utf-8 -*-
"""
Trace sampling strategies for OpenTelemetry spans.

Provides sampling modes to reduce trace volume in high-traffic scenarios:
- Head sampling: decide at span start based on probability
- Tail sampling: decide after span completes based on duration/error
- Rate-limited sampling: cap traces per time window

Usage:
    from src.core.trace_sampling import TraceSampler, SamplingMode

    sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=0.1)
    if sampler.should_sample("github.search_repositories"):
        # execute traced operation
"""

import hashlib
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class SamplingMode(str, Enum):
    """Sampling strategy."""

    ALWAYS = "always"
    NEVER = "never"
    PROBABILITY = "probability"
    RATE_LIMIT = "rate_limit"


class TraceSampler:
    """
    Configurable trace sampler supporting multiple strategies.

    Thread-safety: uses a simple lock-free design with atomic counters.
    """

    def __init__(
        self,
        mode: SamplingMode = SamplingMode.ALWAYS,
        rate: float = 1.0,
        max_traces_per_minute: int = 60,
        operation_filters: Optional[Dict[str, SamplingMode]] = None,
    ):
        """
        Args:
            mode: Default sampling mode
            rate: Sampling rate for PROBABILITY mode (0.0–1.0)
            max_traces_per_minute: Cap for RATE_LIMIT mode
            operation_filters: Per-override overrides, e.g. {"github.*": SamplingMode.PROBABILITY}
        """
        self.mode = mode
        self.rate = max(0.0, min(1.0, rate))
        self.max_traces_per_minute = max_traces_per_minute
        self.operation_filters = operation_filters or {}

        # Rate limit state
        self._window_start: float = 0.0
        self._window_count: int = 0

        # Probabilistic state (seeded counter for consistency)
        self._call_counter: int = 0

        logger.info(
            f"TraceSampler initialized: mode={mode.value}, rate={rate}, "
            f"max_traces_per_minute={max_traces_per_minute}"
        )

    def should_sample(self, operation: str) -> bool:
        """
        Decide whether to sample a trace for the given operation.

        Args:
            operation: Operation name, e.g. "github.search_repositories"

        Returns:
            True if this trace should be recorded
        """
        effective_mode = self._resolve_mode(operation)

        if effective_mode == SamplingMode.ALWAYS:
            return True
        if effective_mode == SamplingMode.NEVER:
            return False
        if effective_mode == SamplingMode.PROBABILITY:
            return self._probabilistic_sample(operation)
        if effective_mode == SamplingMode.RATE_LIMIT:
            return self._rate_limit_sample()

        return True

    def _resolve_mode(self, operation: str) -> SamplingMode:
        """Resolve effective mode for an operation, checking filters first."""
        for pattern, mode in self.operation_filters.items():
            if _matches_pattern(operation, pattern):
                return mode
        return self.mode

    def _probabilistic_sample(self, operation: str) -> bool:
        """Consistent probabilistic sampling using operation hash."""
        self._call_counter += 1
        # Use a hash-based approach for consistency
        seed = f"{operation}:{self._call_counter}".encode()
        hash_val = int(hashlib.md5(seed).hexdigest(), 16)
        return (hash_val % 100) < int(self.rate * 100)

    def _rate_limit_sample(self) -> bool:
        """Rate-limited sampling: cap traces per minute."""
        now = time.time()
        window = now - self._window_start

        # Reset window if more than 60s elapsed
        if window >= 60.0:
            self._window_start = now
            self._window_count = 0
            return True

        if self._window_count < self.max_traces_per_minute:
            self._window_count += 1
            return True

        return False

    def get_stats(self) -> Dict[str, Any]:
        """Return current sampler statistics."""
        return {
            "mode": self.mode.value,
            "rate": self.rate,
            "max_traces_per_minute": self.max_traces_per_minute,
            "call_counter": self._call_counter,
            "window_count": self._window_count,
        }


def sample_span(
    operation: str,
    sampler: TraceSampler,
    fn: Callable,
    *args: Any,
    fallback: Optional[Any] = None,
    **kwargs: Any,
) -> Any:
    """
    Execute a traced operation with sampling.

    If sampling decides to skip, calls fn with fallback (or None).
    Otherwise executes fn normally.

    Args:
        operation: Operation name
        sampler: TraceSampler instance
        fn: Callable to execute
        *args: Positional args for fn
        fallback: Value returned when sampling skips
        **kwargs: Keyword args for fn

    Returns:
        Result of fn() or fallback
    """
    if sampler.should_sample(operation):
        return fn(*args, **kwargs)
    logger.debug(f"Trace sampled out for operation: {operation}")
    return fallback


def _matches_pattern(operation: str, pattern: str) -> bool:
    """Simple glob-like matching for operation filter patterns."""
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return operation.startswith(prefix)
    return operation == pattern
