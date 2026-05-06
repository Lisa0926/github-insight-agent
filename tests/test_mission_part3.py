# -*- coding: utf-8 -*-
"""
Mission Part 3: Supplemental tests for uncommitted working tree changes.

Covers:
- feedback_trend.py: FeedbackTrendAnalyzer (new module)
- llm_cache.py: LLMCache + singleton (new module)
- agent_pipeline.py: New delegation methods (get_north_star_metric, etc.)
- report_generator.py: LLM caching in strategy/sufficiency decisions
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.feedback_trend import FeedbackTrendAnalyzer
from src.core.llm_cache import LLMCache, _cache_key, get_llm_cache, reset_llm_cache


# ============================================================
# New Module: feedback_trend.py
# ============================================================

@pytest.fixture
def feedback_db():
    """Create a temporary feedback database with test data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            run_id TEXT DEFAULT '',
            agent TEXT DEFAULT '',
            user_input TEXT DEFAULT '',
            assistant_output TEXT DEFAULT '',
            rating TEXT NOT NULL CHECK(rating IN ('good', 'bad', 'neutral')),
            reason TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'
        )
    """)
    now = datetime.now()
    test_data = [
        (
            now.strftime("%Y-%m-%dT%H:%M:%S"), "run1", "pipeline", "good query",
            "report1", "good", "Great", '{"project_count": 3, "tti_total": 45.0}',
        ),
        (
            now.strftime("%Y-%m-%dT%H:%M:%S"), "run2", "pipeline", "bad query",
            "report2", "bad", "Missing data", '{"project_count": 1, "tti_total": 30.0}',
        ),
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run3", "researcher", "neutral q", "report3", "neutral", "OK", '{}'),
        (
            (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            "run4", "pipeline", "old good", "report4", "good", "Helpful",
            '{"project_count": 5, "tti_total": 60.0}',
        ),
        (
            (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S"),
            "run5", "pipeline", "old bad", "report5", "bad", "Bad",
            '{"project_count": 2, "tti_total": 25.0}',
        ),
    ]
    conn.executemany(
        (
            "INSERT INTO feedback "
            "(timestamp, run_id, agent, user_input, assistant_output, rating, reason, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        test_data,
    )
    conn.commit()
    conn.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


class TestFeedbackTrendAnalyzer:
    """Test FeedbackTrendAnalyzer methods."""

    def test_get_daily_trends(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        trends = analyzer.get_daily_trends(days=7)
        assert len(trends) == 3  # today, yesterday, 5 days ago
        # trends are sorted ASC by date, so first entry is oldest (5 days ago)
        oldest = trends[0]
        assert oldest["total"] == 1
        assert oldest["good"] == 0
        assert oldest["bad"] == 1
        # Last entry is today (3 entries: good, bad, neutral)
        today = trends[-1]
        assert today["total"] == 3
        assert today["good"] == 1
        assert today["bad"] == 1
        assert today["neutral"] == 1
        assert today["positive_rate"] == pytest.approx(33.3, abs=0.2)

    def test_get_daily_trends_empty_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                user_input TEXT DEFAULT '',
                assistant_output TEXT DEFAULT '',
                rating TEXT NOT NULL,
                reason TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()
        try:
            analyzer = FeedbackTrendAnalyzer(db_path=tmp.name)
            assert analyzer.get_daily_trends() == []
        finally:
            os.unlink(tmp.name)

    def test_get_north_star_metric(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        metric = analyzer.get_north_star_metric()
        overall = metric["overall"]
        assert overall["total"] == 5
        assert overall["good"] == 2
        assert overall["bad"] == 2
        assert overall["positive_rate"] == 40.0
        assert "avg_tti" in overall
        assert metric["recent_7d"]["total"] == 5
        assert metric["recent_30d"]["total"] == 5
        assert len(metric["by_agent"]) >= 1

    def test_north_star_empty_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("""
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                user_input TEXT DEFAULT '',
                assistant_output TEXT DEFAULT '',
                rating TEXT NOT NULL,
                reason TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.commit()
        conn.close()
        try:
            analyzer = FeedbackTrendAnalyzer(db_path=tmp.name)
            metric = analyzer.get_north_star_metric()
            assert metric["overall"]["total"] == 0
            assert metric["overall"]["positive_rate"] == 0.0
            assert metric["by_agent"] == []
        finally:
            os.unlink(tmp.name)

    def test_get_report_stats(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        stats = analyzer.get_report_stats(limit=3)
        assert len(stats) == 3
        for s in stats:
            assert "id" in s
            assert "rating" in s
            assert "project_count" in s
            assert "tti_total" in s
            assert "agent" in s

    def test_get_report_stats_limit(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        assert len(analyzer.get_report_stats(limit=1)) == 1
        assert len(analyzer.get_report_stats(limit=10)) == 5

    def test_get_trend_summary(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        summary = analyzer.get_trend_summary()
        assert "Feedback Trend Summary" in summary
        assert "Total feedback" in summary
        assert "Positive rate" in summary

    def test_trend_summary_with_daily_breakdown(self, feedback_db):
        analyzer = FeedbackTrendAnalyzer(db_path=feedback_db)
        summary = analyzer.get_trend_summary()
        assert "|" in summary  # table formatting
        assert "##" in summary

    def test_nonexistent_db_path(self):
        analyzer = FeedbackTrendAnalyzer(db_path="/tmp/nonexistent_feedback_trend.db")
        # Should return empty results, not crash
        assert analyzer.get_daily_trends() == []
        metric = analyzer.get_north_star_metric()
        assert metric["overall"] == {}
        assert analyzer.get_report_stats() == []


# ============================================================
# New Module: llm_cache.py
# ============================================================

class TestLLMCacheNewModule:
    """Additional tests for LLMCache beyond existing test_llm_cache.py."""

    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.tmp.close()
        self.cache = LLMCache(ttl=10, cache_file=Path(self.tmp.name))

    def teardown_method(self):
        reset_llm_cache()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_cache_key_empty_projects(self):
        key = _cache_key("test query", [])
        assert isinstance(key, str)
        assert len(key) == 32  # MD5 hex length

    def test_put_overwrite_same_key(self):
        """JSONL cache appends; get() returns first match. Verify both entries exist."""
        self.cache.put("q", ["p"], {"v": 1})
        self.cache.put("q", ["p"], {"v": 2})
        # get() returns first match (v=1) since it's append-only
        result = self.cache.get("q", ["p"])
        assert result["v"] == 1
        # But both entries are in the file
        with open(self.tmp.name, "r") as f:
            lines = [ln for ln in f if ln.strip()]
        assert len(lines) == 2

    def test_cache_file_creation(self):
        assert not Path(self.tmp.name).exists() or os.path.getsize(self.tmp.name) == 0
        self.cache.put("q", ["p"], {"data": "test"})
        assert Path(self.tmp.name).exists()
        assert os.path.getsize(self.tmp.name) > 0

    def test_cache_persistence_format(self):
        self.cache.put("strategy", ["projA", "projB"], {"type": "strategy", "plan": {"strategy": "deep"}})
        with open(self.tmp.name, "r") as f:
            line = f.readline().strip()
            entry = json.loads(line)
        assert entry["key"] == _cache_key("strategy", ["projA", "projB"])
        assert entry["query"] == "strategy"
        assert entry["projects"] == ["projA", "projB"]
        assert "timestamp" in entry

    def test_singleton_cache_file_default(self):
        reset_llm_cache()
        cache = get_llm_cache()
        assert cache.cache_file == Path.home() / ".hermes" / "llm_cache.jsonl"

    def test_clear_expired_on_missing_file(self):
        missing_cache = LLMCache(ttl=10, cache_file=Path("/tmp/nonexistent_llm_cache.jsonl"))
        assert missing_cache.clear_expired() == 0

    def test_get_on_missing_file(self):
        missing_cache = LLMCache(ttl=10, cache_file=Path("/tmp/nonexistent_llm_cache_2.jsonl"))
        assert missing_cache.get("q", ["p"]) is None


# ============================================================
# Modified Module: agent_pipeline.py — new delegation methods
# ============================================================

class TestAgentPipelineNewMethods:
    """Verify new methods added to AgentPipeline delegate to ReportGenerator."""

    def test_get_north_star_metric_delegates(self):
        from src.workflows.agent_pipeline import AgentPipeline
        with patch.object(AgentPipeline, "__init__", return_value=None):
            pipeline = AgentPipeline.__new__(AgentPipeline)
            mock_gen = MagicMock()
            mock_gen.get_north_star_metric.return_value = {"overall": {"positive_rate": 75.0}}
            pipeline._report_gen = mock_gen
            result = pipeline.get_north_star_metric()
            mock_gen.get_north_star_metric.assert_called_once()
            assert result["overall"]["positive_rate"] == 75.0

    def test_get_feedback_trends_delegates(self):
        from src.workflows.agent_pipeline import AgentPipeline
        with patch.object(AgentPipeline, "__init__", return_value=None):
            pipeline = AgentPipeline.__new__(AgentPipeline)
            mock_gen = MagicMock()
            mock_gen.get_feedback_trends.return_value = [{"date": "2026-05-01", "total": 10}]
            pipeline._report_gen = mock_gen
            result = pipeline.get_feedback_trends(days=7)
            mock_gen.get_feedback_trends.assert_called_once_with(days=7)
            assert result[0]["date"] == "2026-05-01"

    def test_get_trend_summary_delegates(self):
        from src.workflows.agent_pipeline import AgentPipeline
        with patch.object(AgentPipeline, "__init__", return_value=None):
            pipeline = AgentPipeline.__new__(AgentPipeline)
            mock_gen = MagicMock()
            mock_gen.get_trend_summary.return_value = "## Feedback Trend Summary\n- Total: 100"
            pipeline._report_gen = mock_gen
            result = pipeline.get_trend_summary()
            mock_gen.get_trend_summary.assert_called_once()
            assert "Total: 100" in result

    def test_get_report_stats_delegates(self):
        from src.workflows.agent_pipeline import AgentPipeline
        with patch.object(AgentPipeline, "__init__", return_value=None):
            pipeline = AgentPipeline.__new__(AgentPipeline)
            mock_gen = MagicMock()
            mock_gen.get_report_stats.return_value = [{"id": 1, "rating": "good"}]
            pipeline._report_gen = mock_gen
            result = pipeline.get_report_stats(limit=10)
            mock_gen.get_report_stats.assert_called_once_with(limit=10)
            assert result[0]["rating"] == "good"


# ============================================================
# Modified Module: report_generator.py — LLM caching
# ============================================================

class TestReportGeneratorLLMCaching:
    """Verify LLM strategy/sufficiency caching works in report_generator."""

    def test_strategy_cache_hit_avoids_llm_call(self):
        """When cache has a strategy entry, LLM should not be called."""
        from src.workflows.report_generator import ReportGenerator
        reset_llm_cache()

        with patch.object(ReportGenerator, "__init__", return_value=None):
            rg = ReportGenerator.__new__(ReportGenerator)
            rg.analyst = MagicMock()

            # Pre-populate cache
            cache_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
            cache_file.close()
            cache = LLMCache(ttl=60, cache_file=Path(cache_file.name))
            cache.put("test query", ["projA"], {
                "type": "strategy",
                "plan": {"strategy": "deep", "confidence": 0.9, "num_projects": 1},
            })

            with patch("src.workflows.report_generator.get_llm_cache", return_value=cache):
                search_results = [{"full_name": "projA"}]
                result = rg._llm_decide_strategy("test query", search_results)

            assert result is not None
            assert result["strategy"] == "deep"
            assert result["confidence"] == 0.9
            # Verify LLM was NOT called
            rg.analyst._get_model_wrapper.assert_not_called()

            try:
                os.unlink(cache_file.name)
            except OSError:
                pass

    def test_sufficiency_cache_hit_avoids_llm_call(self):
        """When cache has a sufficiency entry, LLM should not be called."""
        from src.workflows.report_generator import ReportGenerator
        reset_llm_cache()

        with patch.object(ReportGenerator, "__init__", return_value=None):
            rg = ReportGenerator.__new__(ReportGenerator)
            rg.analyst = MagicMock()

            cache_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
            cache_file.close()
            cache = LLMCache(ttl=60, cache_file=Path(cache_file.name))
            cache.put("sufficiency|deep", ["projA"], {
                "type": "sufficiency",
                "decision": {"needs_more_analysis": False, "reason": "Sufficient", "decision_method": "llm_cached"},
            })

            with patch("src.workflows.report_generator.get_llm_cache", return_value=cache):
                analysis_results = [{"project": "projA"}]
                plan = {"strategy": "deep"}
                result = rg._llm_decide_sufficiency(analysis_results, plan)

            assert result is not None
            assert result["decision_method"] == "llm_cached"
            rg.analyst._get_model_wrapper.assert_not_called()

            try:
                os.unlink(cache_file.name)
            except OSError:
                pass

    def test_strategy_cache_miss_calls_llm(self):
        """When cache misses, LLM should be called and result cached."""
        from src.workflows.report_generator import ReportGenerator
        reset_llm_cache()

        cache_file = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        cache_file.close()
        cache = LLMCache(ttl=60, cache_file=Path(cache_file.name))

        with patch.object(ReportGenerator, "__init__", return_value=None):
            rg = ReportGenerator.__new__(ReportGenerator)
            mock_model = MagicMock()
            mock_model.return_value = '{"strategy": "quick", "confidence": 0.7, "focus_areas": ["readme"]}'
            rg.analyst = MagicMock()
            rg.analyst._get_model_wrapper.return_value = mock_model
            rg.analyst._extract_response_text.return_value = (
                '{"strategy": "quick", "confidence": 0.7, "focus_areas": ["readme"]}'
            )

            with patch("src.workflows.report_generator.get_llm_cache", return_value=cache):
                search_results = [{"full_name": "projA"}]
                result = rg._llm_decide_strategy("new query", search_results)

            assert result is not None
            assert result["strategy"] == "quick"
            # Verify result was cached
            cached = cache.get("new query", ["projA"])
            assert cached is not None
            assert cached["type"] == "strategy"

            try:
                os.unlink(cache_file.name)
            except OSError:
                pass
