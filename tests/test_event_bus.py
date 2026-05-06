# -*- coding: utf-8 -*-
"""Tests for EventBus (P2-8: pipeline communication)."""

from src.core.event_bus import (
    EventBus,
    EventEnvelope,
    get_event_bus,
    reset_event_bus,
    get_tti_segments,
    reset_tti_tracker,
)


class TestEventEnvelope:
    def test_envelope_creation(self):
        env = EventEnvelope("search_complete", {"count": 5})
        assert env.event == "search_complete"
        assert env.data == {"count": 5}
        assert env.event_id is not None
        assert isinstance(env.timestamp, float)

    def test_envelope_repr(self):
        env = EventEnvelope("test", data=None)
        assert "EventEnvelope" in repr(env)


class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []

        def handler(envelope):
            received.append(envelope)

        bus.subscribe("search_complete", handler)
        bus.emit("search_complete", {"count": 3})

        assert len(received) == 1
        assert received[0].event == "search_complete"
        assert received[0].data == {"count": 3}

    def test_multiple_listeners(self):
        bus = EventBus()
        calls = []

        def handler_a(_):
            calls.append("a")

        def handler_b(_):
            calls.append("b")

        bus.subscribe("analysis_complete", handler_a)
        bus.subscribe("analysis_complete", handler_b)
        bus.emit("analysis_complete")

        assert len(calls) == 2

    def test_emit_unknown_event_no_crash(self):
        bus = EventBus()
        # Should not raise even if no listeners
        bus.emit("nonexistent_event")

    def test_wildcard_subscription(self):
        bus = EventBus()
        received = []

        def wildcard_handler(envelope):
            received.append(envelope)

        bus.subscribe("*", wildcard_handler)
        bus.emit("search_complete", data=1)
        bus.emit("report_complete", data=2)

        assert len(received) == 2

    def test_handler_error_does_not_crash(self):
        bus = EventBus()

        def bad_handler(_):
            raise RuntimeError("handler error")

        bus.subscribe("test_event", bad_handler)
        # Should not raise
        bus.emit("test_event")

    def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(_):
            received.append(1)

        bus.subscribe("test", handler)
        bus.emit("test")
        bus.unsubscribe("test", handler)
        bus.emit("test")

        assert len(received) == 1

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("a", lambda _: None)
        bus.subscribe("b", lambda _: None)
        bus.clear()
        assert bus.event_count == 0

    def test_event_count(self):
        bus = EventBus()
        bus.subscribe("a", lambda _: None)
        bus.subscribe("a", lambda _: None)
        bus.subscribe("b", lambda _: None)
        assert bus.event_count == 3


class TestGlobalEventBus:
    def teardown_method(self):
        reset_event_bus()

    def test_singleton(self):
        reset_event_bus()
        b1 = get_event_bus()
        b2 = get_event_bus()
        assert b1 is b2

    def test_default_handlers(self):
        reset_event_bus()
        bus = get_event_bus()
        # Should have default wildcard subscribers (logging + tti)
        assert bus.event_count >= 2

    def test_reset(self):
        bus = get_event_bus()
        bus.subscribe("custom", lambda _: None)
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus2 is not bus


class TestTTIHandler:
    def teardown_method(self):
        from src.core.event_bus import reset_tti_tracker
        reset_tti_tracker()

    def test_tti_records_timestamps(self):
        from src.core.event_bus import _tti_handler, EventEnvelope
        reset_tti_tracker()

        _tti_handler(EventEnvelope("search_complete"))
        _tti_handler(EventEnvelope("report_complete"))

        segments = get_tti_segments()
        assert "search_complete_to_report_complete" in segments

    def test_tti_empty_before_any_events(self):
        from src.core.event_bus import reset_tti_tracker
        reset_tti_tracker()
        segments = get_tti_segments()
        assert segments == {}
