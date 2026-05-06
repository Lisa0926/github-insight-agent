# -*- coding: utf-8 -*-
"""
Tests for feedback collection system

Tests:
1. FeedbackCollector — SQLite CRUD
2. FeedbackSession — context tracking
3. Rating validation
4. Stats aggregation
5. CLI command integration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def collector(db_path):
    from src.core.feedback import FeedbackCollector, reset_feedback_collector
    c = FeedbackCollector(db_path=db_path)
    yield c
    reset_feedback_collector()


@pytest.fixture
def session():
    from src.core.feedback import FeedbackSession
    return FeedbackSession(run_id="test_run", current_agent="researcher")


# ============================================================
# 1. FeedbackCollector CRUD
# ============================================================

class TestFeedbackCollectorCRUD:
    """Test basic create/record operations"""

    def test_record_good_feedback(self, collector):
        row_id = collector.record(rating="good", reason="Accurate analysis")
        assert row_id == 1

    def test_record_bad_feedback(self, collector):
        row_id = collector.record(rating="bad", reason="Missed key details")
        assert row_id == 1

    def test_record_neutral_feedback(self, collector):
        row_id = collector.record(rating="neutral", reason="Decent but incomplete")
        assert row_id == 1

    def test_record_with_full_metadata(self, collector):
        row_id = collector.record(
            rating="good",
            reason="Great",
            user_input="Search Python frameworks",
            assistant_output="Here are 3 frameworks...",
            agent="researcher",
            run_id="run_001",
            metadata={"model": "qwen-max"},
        )
        assert row_id == 1

    def test_record_multiple_entries(self, collector):
        collector.record(rating="good", reason="A")
        collector.record(rating="bad", reason="B")
        collector.record(rating="neutral", reason="C")
        recent = collector.get_recent(limit=10)
        assert len(recent) == 3

    def test_invalid_rating_rejected(self, collector):
        with pytest.raises(ValueError, match="Invalid rating"):
            collector.record(rating="excellent", reason="N/A")

    def test_record_creates_table(self, tmp_path):
        """Table should be created automatically on init"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector
        db = str(tmp_path / "new.db")
        c = FeedbackCollector(db_path=db)
        conn = c._get_connection()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        assert any(t[0] == "feedback" for t in tables)
        reset_feedback_collector()


# ============================================================
# 2. FeedbackSession
# ============================================================

class TestFeedbackSession:
    """Test session context tracking"""

    def test_session_init(self, session):
        assert session.run_id == "test_run"
        assert session.current_agent == "researcher"
        assert session.last_user_input == ""
        assert session.last_assistant_output == ""

    def test_set_last_interaction(self, session):
        session.set_last_interaction("search python", "Found 3 repos")
        assert session.last_user_input == "search python"
        assert session.last_assistant_output == "Found 3 repos"

    def test_set_agent(self, session):
        session.set_agent("analyst")
        assert session.current_agent == "analyst"

    def test_record_quick_with_session(self, collector, session):
        session.set_last_interaction("hello", "hi there")
        row_id = collector.record_quick(
            rating="good", reason="Nice", session_state=session
        )
        assert row_id == 1
        recent = collector.get_recent(limit=1)
        assert recent[0]["user_input"] == "hello"
        assert recent[0]["assistant_output"] == "hi there"
        assert recent[0]["agent"] == "researcher"
        assert recent[0]["run_id"] == "test_run"

    def test_record_quick_without_session(self, collector):
        row_id = collector.record_quick(rating="good", reason="No session")
        assert row_id == 1
        recent = collector.get_recent(limit=1)
        assert recent[0]["user_input"] == ""
        assert recent[0]["assistant_output"] == ""


# ============================================================
# 3. Stats Aggregation
# ============================================================

class TestFeedbackStats:
    """Test stats aggregation"""

    def test_empty_stats(self, collector):
        stats = collector.get_stats()
        assert stats["total"] == 0
        assert stats["good"] == 0
        assert stats["bad"] == 0
        assert stats["neutral"] == 0
        assert stats["positive_rate"] == 0.0

    def test_stats_with_mixed_feedback(self, collector):
        collector.record(rating="good", reason="1")
        collector.record(rating="good", reason="2")
        collector.record(rating="bad", reason="3")
        collector.record(rating="neutral", reason="4")
        collector.record(rating="good", reason="5")

        stats = collector.get_stats()
        assert stats["total"] == 5
        assert stats["good"] == 3
        assert stats["bad"] == 1
        assert stats["neutral"] == 1
        assert stats["positive_rate"] == 60.0

    def test_stats_rounding(self, collector):
        collector.record(rating="good", reason="1")
        collector.record(rating="bad", reason="2")
        collector.record(rating="bad", reason="3")

        stats = collector.get_stats()
        assert stats["positive_rate"] == 33.3


# ============================================================
# 4. Get Recent
# ============================================================

class TestGetRecent:
    """Test recent feedback retrieval"""

    def test_get_recent_limit(self, collector):
        for i in range(10):
            collector.record(rating="good", reason=str(i))

        recent = collector.get_recent(limit=3)
        assert len(recent) == 3
        # Most recent first
        assert recent[0]["reason"] == "9"

    def test_get_recent_all_fields(self, collector):
        collector.record(
            rating="good",
            reason="test",
            user_input="input",
            assistant_output="output",
            agent="analyst",
            run_id="r1",
        )
        recent = collector.get_recent(limit=1)
        entry = recent[0]
        assert entry["rating"] == "good"
        assert entry["reason"] == "test"
        assert entry["user_input"] == "input"
        assert entry["assistant_output"] == "output"
        assert entry["agent"] == "analyst"
        assert entry["run_id"] == "r1"


# ============================================================
# 5. Singleton Pattern
# ============================================================

class TestSingleton:
    """Test module-level singleton"""

    def test_get_feedback_collector_singleton(self, tmp_path):
        from src.core.feedback import get_feedback_collector, reset_feedback_collector

        db = str(tmp_path / "singleton.db")
        c1 = get_feedback_collector(db_path=db)
        c2 = get_feedback_collector(db_path=db)
        assert c1 is c2
        reset_feedback_collector()

    def test_reset_feedback_collector(self, tmp_path):
        from src.core.feedback import get_feedback_collector, reset_feedback_collector

        db = str(tmp_path / "reset.db")
        c1 = get_feedback_collector(db_path=db)
        reset_feedback_collector()
        c2 = get_feedback_collector(db_path=db)
        assert c1 is not c2
        reset_feedback_collector()


# ============================================================
# 6. CLI Integration
# ============================================================

class TestCLICommands:
    """Test CLI command parsing without running full REPL"""

    def test_rate_command_good(self, tmp_path):
        """Simulate /rate good processing"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector, FeedbackSession

        db = str(tmp_path / "cli_test.db")
        collector = FeedbackCollector(db_path=db)
        session = FeedbackSession(run_id="run_1", current_agent="researcher")
        session.set_last_interaction("search python", "Found repos")

        # Simulate: /rate good 分析准确
        args = "good 分析准确"
        parts = args.split(maxsplit=1)
        rating = parts[0]
        reason = parts[1] if len(parts) > 1 else ""

        row_id = collector.record_quick(rating=rating, reason=reason, session_state=session)
        assert row_id == 1
        stats = collector.get_stats()
        assert stats["good"] == 1
        reset_feedback_collector()

    def test_rate_command_bad(self, tmp_path):
        """Simulate /rate bad processing"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector

        db = str(tmp_path / "cli_bad.db")
        collector = FeedbackCollector(db_path=db)

        # /rate bad 结果不相关
        args = "bad 结果不相关"
        parts = args.split(maxsplit=1)
        rating = parts[0]
        reason = parts[1] if len(parts) > 1 else ""

        row_id = collector.record(rating=rating, reason=reason)
        assert row_id == 1
        stats = collector.get_stats()
        assert stats["bad"] == 1
        reset_feedback_collector()

    def test_rate_command_short(self, tmp_path):
        """Simulate /rate g (short form)"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector

        db = str(tmp_path / "cli_short.db")
        collector = FeedbackCollector(db_path=db)

        args = "g"
        parts = args.split(maxsplit=1)
        rating = parts[0]
        if rating == "g":
            rating = "good"

        row_id = collector.record(rating=rating)
        assert row_id == 1
        reset_feedback_collector()

    def test_feedback_command(self, tmp_path):
        """Simulate /feedback processing"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector, FeedbackSession

        db = str(tmp_path / "cli_feedback.db")
        collector = FeedbackCollector(db_path=db)
        session = FeedbackSession(run_id="run_2")
        session.set_last_interaction("search react", "Found React")

        # /feedback "希望支持更多分析维度"
        args = "希望支持更多分析维度"
        row_id = collector.record(
            rating="neutral",
            reason=args,
            user_input=session.last_user_input,
            assistant_output=session.last_assistant_output,
        )
        assert row_id == 1
        reset_feedback_collector()

    def test_feedback_stats_command(self, tmp_path):
        """Simulate /feedback-stats display"""
        from src.core.feedback import FeedbackCollector, reset_feedback_collector

        db = str(tmp_path / "cli_stats.db")
        collector = FeedbackCollector(db_path=db)
        collector.record(rating="good", reason="a")
        collector.record(rating="good", reason="b")
        collector.record(rating="bad", reason="c")

        stats = collector.get_stats()
        # Verify the stats match expected format for CLI display
        assert "total" in stats
        assert "good" in stats
        assert "bad" in stats
        assert "neutral" in stats
        assert "positive_rate" in stats
        assert stats["total"] == 3
        reset_feedback_collector()


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
