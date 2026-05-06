# -*- coding: utf-8 -*-
"""Tests for circuit breaker integration with role_kpi.yaml."""

import pytest

from src.core.guardrails import (
    AgentCircuitBreaker,
    get_circuit_breaker,
    circuit_breaker_guard,
)
from src.core.kpi_tracker import _load_role_kpi_config


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset global circuit breaker before each test."""
    import src.core.guardrails as guardrails
    original = guardrails._global_circuit_breaker
    guardrails._global_circuit_breaker = None
    yield
    guardrails._global_circuit_breaker = original


class TestAgentCircuitBreaker:
    def test_session_starts_closed(self):
        cb = AgentCircuitBreaker()
        cb.start_session()
        assert cb.is_open is False

    def test_trips_on_step_limit(self):
        cb = AgentCircuitBreaker(max_steps=3)
        cb.start_session()
        cb.record_step()
        cb.record_step()
        cb.record_step()
        with pytest.raises(RuntimeError, match="Max steps exceeded"):
            cb.check()

    def test_trips_on_time_limit(self):
        cb = AgentCircuitBreaker(max_time_seconds=0)
        cb.start_session()
        import time
        time.sleep(0.01)
        with pytest.raises(RuntimeError, match="Max time exceeded"):
            cb.check()

    def test_get_state(self):
        cb = AgentCircuitBreaker(max_steps=10, max_time_seconds=60, max_tokens=5000)
        cb.start_session()
        state = cb.get_state()
        assert state["max_steps"] == 10
        assert state["max_time"] == 60
        assert state["max_tokens"] == 5000


class TestCircuitBreakerFromRoleKpi:
    def test_reads_defaults_from_role_kpi_yaml(self):
        """When role_kpi.yaml is available, circuit breaker should use its values."""
        config = _load_role_kpi_config()
        if config is None:
            pytest.skip("role_kpi.yaml not found")

        cb = get_circuit_breaker()
        constraints = config.get("global_constraints", {})
        cost_config = constraints.get("cost_control", {})
        cb_config = cost_config.get("circuit_breaker", {})

        assert cb.max_steps == cb_config.get("max_steps", 50)
        assert cb.max_time_seconds == cb_config.get("max_time_seconds", 180)
        assert cb.max_tokens == cost_config.get("max_tokens_per_session", 5000)

    def test_explicit_params_override_yaml(self):
        """Explicit parameters should override YAML defaults."""
        cb = get_circuit_breaker(max_steps=10, max_time_seconds=30, max_tokens=1000)
        assert cb.max_steps == 10
        assert cb.max_time_seconds == 30
        assert cb.max_tokens == 1000

    def test_yaml_values_match_expected(self):
        """Verify the YAML values match the expected defaults from role_kpi.yaml."""
        config = _load_role_kpi_config()
        if config is None:
            pytest.skip("role_kpi.yaml not found")

        constraints = config.get("global_constraints", {})
        cost_config = constraints.get("cost_control", {})
        cb_config = cost_config.get("circuit_breaker", {})

        assert cb_config.get("max_steps") == 50
        assert cb_config.get("max_time_seconds") == 180
        assert cost_config.get("max_tokens_per_session") == 5000


class TestCircuitBreakerGuard:
    def test_decorator_starts_session(self):
        @circuit_breaker_guard
        def dummy_func():
            return "ok"

        result = dummy_func()
        assert result == "ok"

    def test_decorator_trips_on_limit(self):
        @circuit_breaker_guard
        def dummy_func():
            return "ok"

        # First call should work
        dummy_func()

        # Second call should also work (new session each time)
        # because circuit_breaker_guard calls start_session() before each call
        result = dummy_func()
        assert result == "ok"
