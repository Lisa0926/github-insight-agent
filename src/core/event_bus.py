# -*- coding: utf-8 -*-
"""
Lightweight event bus (pub/sub) for pipeline communication.

Replaces some synchronous calls with event-driven notifications,
enabling decoupled step tracking and extensibility.

Events:
- search_complete: Emitted after project search finishes
- analysis_start: Emitted before project analysis begins
- analysis_complete: Emitted after each project analysis
- analysis_batch_complete: Emitted after all project analyses
- report_complete: Emitted after report generation
- kpi_violation: Emitted when a KPI threshold is breached
- feedback_submitted: Emitted when user submits feedback
"""

from typing import Any, Callable, Dict, List
from collections import defaultdict
import time
import uuid

from src.core.logger import get_logger

logger = get_logger(__name__)

# Built-in event names
EVENT_SEARCH_COMPLETE = "search_complete"
EVENT_ANALYSIS_START = "analysis_start"
EVENT_ANALYSIS_COMPLETE = "analysis_complete"
EVENT_ANALYSIS_BATCH_COMPLETE = "analysis_batch_complete"
EVENT_REPORT_COMPLETE = "report_complete"
EVENT_KPI_VIOLATION = "kpi_violation"
EVENT_FEEDBACK_SUBMITTED = "feedback_submitted"


class EventEnvelope:
    """Wraps event data with metadata."""

    __slots__ = ("event", "data", "timestamp", "event_id")

    def __init__(self, event: str, data: Any = None):
        self.event = event
        self.data = data
        self.timestamp = time.time()
        self.event_id = uuid.uuid4().hex[:8]

    def __repr__(self) -> str:
        return f"EventEnvelope({self.event}, id={self.event_id})"


class EventBus:
    """Simple pub/sub event bus."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[EventEnvelope], None]]] = defaultdict(list)

    def subscribe(
        self,
        event: str,
        callback: Callable[[EventEnvelope], None],
    ) -> None:
        """Register a callback for an event."""
        self._listeners[event].append(callback)
        logger.debug(f"EventBus: subscribed to '{event}'")

    def emit(self, event: str, data: Any = None) -> EventEnvelope:
        """Publish an event to all subscribers (including wildcard '*' listeners)."""
        envelope = EventEnvelope(event, data)
        for cb in self._listeners.get(event, []):
            try:
                cb(envelope)
            except Exception as e:
                logger.warning(f"EventBus: handler error on '{event}': {e}")
        # Also notify wildcard subscribers
        for cb in self._listeners.get("*", []):
            try:
                cb(envelope)
            except Exception as e:
                logger.warning(f"EventBus: wildcard handler error: {e}")
        return envelope

    def unsubscribe(
        self,
        event: str,
        callback: Callable[[EventEnvelope], None],
    ) -> None:
        """Remove a callback subscription."""
        try:
            self._listeners[event].remove(callback)
        except ValueError:
            pass

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._listeners.clear()

    @property
    def event_count(self) -> int:
        return sum(len(cbs) for cbs in self._listeners.values())


# ---- Built-in handlers ----

def _logging_handler(envelope: EventEnvelope) -> None:
    """Log all pipeline events for observability."""
    logger.info(f"[EventBus] {envelope.event}: {envelope.data}")


def _tti_handler(envelope: EventEnvelope) -> None:
    """Track TTI (Time-to-Insight) by recording event timestamps."""
    if not hasattr(_tti_handler, "_timestamps"):
        _tti_handler._timestamps = {}
    _tti_handler._timestamps[envelope.event] = envelope.timestamp


def get_tti_segments() -> Dict[str, float]:
    """Return TTI segments between consecutive events."""
    ts = getattr(_tti_handler, "_timestamps", {})
    events = sorted(ts.items(), key=lambda x: x[1])
    segments = {}
    for i in range(1, len(events)):
        label = f"{events[i - 1][0]}_to_{events[i][0]}"
        segments[label] = round(events[i][1] - events[i - 1][1], 3)
    return segments


def reset_tti_tracker() -> None:
    if hasattr(_tti_handler, "_timestamps"):
        _tti_handler._timestamps = {}


# ---- Default bus setup ----

_global_bus: EventBus = None


def get_event_bus() -> EventBus:
    """Return the global EventBus singleton with default handlers."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
        _global_bus.subscribe("*", _logging_handler)
        _global_bus.subscribe("*", _tti_handler)
    return _global_bus


def reset_event_bus() -> None:
    """Reset global EventBus (for testing)."""
    global _global_bus
    if _global_bus is not None:
        _global_bus.clear()
    _global_bus = None
    reset_tti_tracker()
