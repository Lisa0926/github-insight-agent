# -*- coding: utf-8 -*-
"""Tests for S3-P2: Cross-layer memory data flow."""

import os
import tempfile
from unittest.mock import MagicMock, patch


# ============================================================
# UnifiedMemory Tests
# ============================================================

def _make_temp_db():
    """Create a temporary database path."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    return path


class TestUnifiedMemoryLifecycle:
    """Test UnifiedMemory initialization and lazy creation."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_lazy_creation(self):
        """Test that components are created lazily."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        # Components should be None initially
        assert memory._persistent is None
        assert memory._conversation is None
        assert memory._feedback is None

        # Accessing properties should create them
        assert memory.persistent is not None
        assert memory.conversation is not None
        assert memory.feedback is not None

    def test_injected_components(self):
        """Test that injected components are used directly."""
        from src.core.unified_memory import UnifiedMemory

        mock_persistent = MagicMock()
        mock_conversation = MagicMock()
        mock_feedback = MagicMock()

        memory = UnifiedMemory(
            db_path=self.db_path,
            persistent_memory=mock_persistent,
            conversation_manager=mock_conversation,
            feedback_collector=mock_feedback,
        )

        assert memory.persistent is mock_persistent
        assert memory.conversation is mock_conversation
        assert memory.feedback is mock_feedback


class TestUnifiedMemoryRecordInteraction:
    """Test recording interactions across all layers."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_record_interaction_writes_to_all_layers(self):
        """Test that record_interaction writes to persistent + conversation."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction(
            user_message="Search for React",
            assistant_response="Found 5 React projects",
        )

        # Persistent should have 2 messages
        assert memory.persistent.size() >= 2

        # Conversation should have 1 turn
        assert memory.conversation.get_turn_count() >= 1

    def test_record_interaction_with_tool_results(self):
        """Test that tool results are recorded in conversation."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction(
            user_message="Search for React",
            assistant_response="Found projects",
            tool_results=[
                {"tool_name": "search_repositories", "result": "results..."},
            ],
        )

        history = memory.conversation.get_full_history()
        tool_msgs = [m for m in history if m["role"] == "tool"]
        assert len(tool_msgs) >= 1


class TestUnifiedMemoryContext:
    """Test context aggregation across layers."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_get_context_with_feedback(self):
        """Test get_context aggregates feedback patterns."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        # Record some feedback
        memory.record_feedback("good", "detailed analysis")
        memory.record_feedback("good", "structured output")
        memory.record_feedback("bad", "too slow")

        context = memory.get_context()
        assert "feedback_patterns" in context
        assert "detailed analysis" in context["feedback_patterns"]
        assert "structured output" in context["feedback_patterns"]
        assert "stats" in context
        assert context["stats"]["feedback_stats"]["good"] == 2

    def test_get_context_without_feedback(self):
        """Test get_context excludes feedback when disabled."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_feedback("good", "test pattern")

        context = memory.get_context(include_feedback=False)
        assert "feedback_patterns" not in context

    def test_get_feedback_patterns(self):
        """Test get_feedback_patterns returns positive patterns."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_feedback("good", "pattern A")
        memory.record_feedback("good", "pattern B")

        patterns = memory.get_feedback_patterns(limit=1)
        assert len(patterns) == 1
        # Most recent pattern returned first (ORDER BY id DESC)
        assert "pattern B" in patterns


class TestUnifiedMemoryCrossSession:
    """Test cross-session context aggregation."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_get_cross_session_context_empty(self):
        """Test empty cross-session context when no data."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        result = memory.get_cross_session_context()
        assert result == ""

    def test_get_cross_session_context_with_data(self):
        """Test cross-session context with conversation and feedback."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction("Hello", "Hi! How can I help?")
        memory.record_feedback("good", "friendly tone")

        result = memory.get_cross_session_context()
        assert "会话摘要" in result
        assert "用户偏好" in result
        assert "friendly tone" in result


class TestUnifiedMemorySearch:
    """Test cross-layer search."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_search_relevant_across_layers(self):
        """Test search_relevant returns results from all layers."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)

        # Record data across layers
        memory.record_interaction("Search for Django", "Found Django projects")
        memory.record_feedback("good", "Django analysis was great")

        # Search
        results = memory.search_relevant("Django")

        assert len(results["persistent"]) >= 1
        assert len(results["conversation"]) >= 1
        assert len(results["feedback"]) >= 1
        assert results["persistent"][0]["source"] == "persistent_memory"
        assert results["conversation"][0]["source"] == "conversation_history"
        assert results["feedback"][0]["source"] == "feedback"

    def test_search_relevant_no_matches(self):
        """Test search_relevant returns empty when no matches."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction("Hello", "Hi")

        results = memory.search_relevant("nonexistent_keyword_xyz")
        assert results["persistent"] == []
        assert results["conversation"] == []
        assert results["feedback"] == []


class TestUnifiedMemoryStats:
    """Test unified stats aggregation."""

    def setup_method(self):
        self.db_path = _make_temp_db()

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_get_stats(self):
        """Test get_stats aggregates stats from all layers."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction("test", "response")
        memory.record_feedback("good", "test")

        stats = memory.get_stats()
        assert "persistent_messages" in stats
        assert "conversation_turns" in stats
        assert "feedback" in stats
        assert stats["persistent_messages"] >= 2
        assert stats["feedback"]["good"] == 1

    def test_clear(self):
        """Test clear resets all layers."""
        from src.core.unified_memory import UnifiedMemory

        memory = UnifiedMemory(db_path=self.db_path)
        memory.record_interaction("test", "response")

        memory.clear()
        assert memory.persistent.size() == 0
        assert memory.persistent.compressed_summary == ""
