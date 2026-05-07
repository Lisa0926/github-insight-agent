# -*- coding: utf-8 -*-
"""Tests for P2 improvements: MCP robustness, half-open circuit breaker,
cross-session memory, feedback→prompt injection."""

from unittest.mock import patch, MagicMock
import time

from src.core.resilient_http import ResilientHTTPClient, CircuitBreakerError
from src.core.guardrails import AgentCircuitBreaker
from src.core.feedback import FeedbackCollector, reset_feedback_collector
from src.core.prompt_builder import get_system_prompt


# ============================================================
# P2-1: MCP Connection Robustness
# ============================================================

class TestGitHubMCPClientRobustness:
    """Test MCP client connection retry and caching."""

    def test_get_available_tools_from_cache(self):
        """Test get_available_tools() returns cached tools after list_tools()."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        mock_tool = MagicMock()
        mock_tool.name = "github_search"
        mock_tool.title = "GitHub Search"
        mock_tool.description = "Search GitHub repos"
        mock_tool.inputSchema = {"type": "object"}

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        client._cached_tools = [mock_tool]

        tools = client.get_available_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "github_search"
        assert tools[0]["description"] == "Search GitHub repos"

    def test_get_available_tools_returns_empty_when_not_connected(self):
        """Test get_available_tools() returns [] when not cached/connected."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        if '_cached_tools' in client.__dict__:
            del client.__dict__['_cached_tools']

        tools = client.get_available_tools()
        assert tools == []

    def test_is_connected_returns_false_when_not_connected(self):
        """Test connected property returns False when not connected."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        assert client.connected is False

    def test_is_connected_returns_true_when_connected(self):
        """Test connected property returns True when connected with session."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        client.__dict__['is_connected'] = True
        client.session = MagicMock()
        assert client.connected is True

    def test_is_connected_false_with_no_session(self):
        """Test connected property returns False if session is None."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        client.__dict__['is_connected'] = True
        client.session = None
        assert client.connected is False

    def test_connect_with_retry_success_first_attempt(self):
        """Test connect_with_retry succeeds on first attempt."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        client._max_reconnect_attempts = 3
        client._base_reconnect_delay = 0.001

        async def mock_connect():
            client.__dict__['is_connected'] = True
            client.session = MagicMock()

        async def mock_list_tools():
            client._cached_tools = []

        with patch.object(client, 'connect', mock_connect), \
             patch.object(client, 'list_tools', mock_list_tools):
            result = client.connect_with_retry()
            assert result is True

    def test_connect_with_retry_exhausts_attempts(self):
        """Test connect_with_retry returns False after exhausting attempts."""
        from src.github_mcp.github_mcp_client import GitHubMCPClient

        client = GitHubMCPClient.__new__(GitHubMCPClient)
        client._max_reconnect_attempts = 2
        client._base_reconnect_delay = 0.001

        async def mock_connect():
            raise ConnectionError("No MCP server")

        with patch.object(client, 'connect', mock_connect):
            result = client.connect_with_retry()
            assert result is False


# ============================================================
# P2-2: Half-Open Circuit Breaker
# ============================================================

class TestHalfOpenHTTPCircuitBreaker:
    """Test HTTP circuit breaker half-open state."""

    def test_half_open_allows_probe_request(self):
        """After timeout, circuit allows request (half-open)."""
        client = ResilientHTTPClient(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=0.01,
        )

        client._failure_count = 2
        client._circuit_open = True
        client._circuit_open_time = time.time() - 0.1

        # Timeout passed — should allow probe
        client._check_circuit_breaker()  # Should not raise

    def test_circuit_stays_open_before_timeout(self):
        """Circuit stays open when timeout hasn't passed."""
        client = ResilientHTTPClient(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=60,
        )

        client._failure_count = 2
        client._circuit_open = True
        client._circuit_open_time = time.time()

        try:
            client._check_circuit_breaker()
            assert False, "Should have raised CircuitBreakerError"
        except CircuitBreakerError:
            pass

    def test_half_open_probe_success_resets(self):
        """Successful request in half-open state resets circuit breaker."""
        client = ResilientHTTPClient(
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=0.01,
        )

        client._failure_count = 2
        client._circuit_open = True
        client._circuit_open_time = time.time() - 0.1

        time.sleep(0.02)
        # Enters half-open state
        client._check_circuit_breaker()
        assert client._half_open is True
        # Simulate successful probe — _record_success should close circuit
        client._record_success()
        assert client._circuit_open is False
        assert client._failure_count == 0
        assert client._half_open is False


class TestHalfOpenAgentCircuitBreaker:
    """Test Agent circuit breaker half-open state."""

    def test_agent_cb_start_session_resets(self):
        """start_session() resets the agent circuit breaker."""
        cb = AgentCircuitBreaker(max_steps=5, max_time_seconds=10)
        cb.start_session()

        cb._open = True
        cb._reason = "test"
        cb.start_session()

        assert cb._open is False
        assert cb._reason == ""
        assert cb._step_count == 0

    def test_agent_cb_check_raises_when_open(self):
        """check() raises RuntimeError when circuit is open."""
        cb = AgentCircuitBreaker()
        cb.start_session()
        cb._open = True
        cb._reason = "test reason"

        try:
            cb.check()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "test reason" in str(e)

    def test_agent_cb_probe_after_timeout(self):
        """Test that starting a new session after being tripped acts as a probe."""
        cb = AgentCircuitBreaker(max_steps=3, max_time_seconds=10)
        cb.start_session()

        # Trip the breaker
        for _ in range(3):
            cb.record_step()
        try:
            cb.check()
        except RuntimeError:
            pass
        assert cb._open is True

        # Start new session — the "half-open" probe
        cb.start_session()
        assert cb._open is False
        cb.check()  # Should pass


# ============================================================
# P2-3: Cross-Session Memory
# ============================================================

class TestCrossSessionMemory:
    """Test cross-session memory loading."""

    def test_persistent_memory_get_recent_summary(self):
        """Test PersistentMemory can retrieve recent conversation summary."""
        from src.core.agentscope_persistent_memory import PersistentMemory
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            pm = PersistentMemory(db_path=db_path)
            pm.add_user_message("Hello from last session")
            pm.add_assistant_message("Hello! How can I help?")

            summary = pm.get_messages_summary()
            assert "Hello" in summary
        finally:
            os.unlink(db_path)

    def test_persistent_memory_size(self):
        """Test PersistentMemory size tracking."""
        from src.core.agentscope_persistent_memory import PersistentMemory
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            pm = PersistentMemory(db_path=db_path)
            assert pm.size() == 0
            pm.add_user_message("test")
            assert pm.size() >= 1
        finally:
            os.unlink(db_path)


# ============================================================
# P2-4: Feedback→Prompt Injection
# ============================================================

class TestFeedbackPatternExtraction:
    """Test extracting positive feedback patterns from FeedbackCollector."""

    def setup_method(self):
        reset_feedback_collector()

    def test_get_positive_feedback_patterns_empty(self):
        """Test get_positive_feedback_patterns with no feedback."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            collector = FeedbackCollector(db_path=db_path)
            patterns = collector.get_positive_feedback_patterns()
            assert patterns == []
        finally:
            os.unlink(db_path)

    def test_get_positive_feedback_patterns_with_data(self):
        """Test get_positive_feedback_patterns returns patterns from good feedback."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            collector = FeedbackCollector(db_path=db_path)
            collector.record(rating="good", reason="detailed analysis")
            collector.record(rating="good", reason="structured output")
            collector.record(rating="bad", reason="too slow")
            collector.record(rating="good", reason="clear explanations")

            patterns = collector.get_positive_feedback_patterns(limit=10)
            assert len(patterns) == 3
            assert "detailed analysis" in patterns
            assert "structured output" in patterns
            assert "too slow" not in patterns
        finally:
            os.unlink(db_path)

    def test_get_feedback_stats(self):
        """Test get_stats returns correct counts."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            collector = FeedbackCollector(db_path=db_path)
            collector.record(rating="good", reason="test")
            collector.record(rating="good", reason="test")
            collector.record(rating="bad", reason="test")

            stats = collector.get_stats()
            assert stats["total"] == 3
            assert stats["good"] == 2
            assert stats["bad"] == 1
            assert stats["positive_rate"] > 60
        finally:
            os.unlink(db_path)

    def test_prompt_builder_with_feedback_patterns(self):
        """Test get_system_prompt with feedback patterns injected."""
        prompt = get_system_prompt("researcher", feedback_patterns=[
            "structured data output",
            "clear summary",
        ])

        assert "structured data output" in prompt
        assert "clear summary" in prompt

    def test_prompt_builder_without_feedback(self):
        """Test get_system_prompt works without feedback patterns."""
        prompt = get_system_prompt("researcher")
        # Should contain the default researcher prompt content
        assert len(prompt) > 0
