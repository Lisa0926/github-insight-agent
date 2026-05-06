# -*- coding: utf-8 -*-
"""Tests for FeedbackTrendAnalyzer (feedback_trend.py)."""

import sqlite3
import tempfile
from datetime import datetime

import pytest

from src.core.feedback_trend import FeedbackTrendAnalyzer


@pytest.fixture
def db_path():
    """Create a temporary database with feedback data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT    NOT NULL,
            run_id           TEXT    DEFAULT '',
            agent            TEXT    DEFAULT '',
            user_input       TEXT    DEFAULT '',
            assistant_output TEXT    DEFAULT '',
            rating           TEXT    NOT NULL CHECK(rating IN ('good', 'bad', 'neutral')),
            reason           TEXT    DEFAULT '',
            metadata         TEXT    DEFAULT '{}'
        )
    """)

    # Insert test data
    now = datetime.now()
    test_data = [
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run1", "pipeline", "query1",
         "report1", "good", "Great analysis",
         '{"project_count": 3, "tti_total": 45.0}'),
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run2", "pipeline", "query2",
         "report2", "good", "Very helpful",
         '{"project_count": 5, "tti_total": 60.0}'),
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run3", "pipeline", "query3",
         "report3", "bad", "Missing key data",
         '{"project_count": 2, "tti_total": 30.0}'),
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run4", "researcher", "query4",
         "report4", "neutral", "Okay",
         '{"project_count": 1, "tti_total": 20.0}'),
        (now.strftime("%Y-%m-%dT%H:%M:%S"), "run5", "pipeline", "query5",
         "report5", "good", "Comprehensive",
         '{"project_count": 4, "tti_total": 55.0}'),
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
    yield db_path

    import os
    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestFeedbackTrendAnalyzer:
    """Test FeedbackTrendAnalyzer methods."""

    def test_get_daily_trends(self, db_path):
        analyzer = FeedbackTrendAnalyzer(db_path=db_path)
        trends = analyzer.get_daily_trends(days=7)
        assert len(trends) >= 1
        today_entry = trends[0]
        assert "date" in today_entry
        assert today_entry["total"] == 5
        assert today_entry["good"] == 3
        assert today_entry["bad"] == 1
        assert today_entry["neutral"] == 1
        assert today_entry["positive_rate"] == 60.0

    def test_get_north_star_metric(self, db_path):
        analyzer = FeedbackTrendAnalyzer(db_path=db_path)
        metric = analyzer.get_north_star_metric()
        assert metric["overall"]["total"] == 5
        assert metric["overall"]["good"] == 3
        assert metric["overall"]["bad"] == 1
        assert metric["overall"]["positive_rate"] == 60.0
        assert metric["recent_7d"]["total"] == 5
        assert metric["recent_30d"]["total"] == 5
        assert len(metric["by_agent"]) >= 1

    def test_get_north_star_metric_empty_db(self):
        """Test with empty database."""
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
        conn.commit()
        conn.close()

        analyzer = FeedbackTrendAnalyzer(db_path=tmp.name)
        metric = analyzer.get_north_star_metric()
        assert metric["overall"]["total"] == 0
        assert metric["overall"]["positive_rate"] == 0.0

        import os
        os.unlink(tmp.name)

    def test_get_report_stats(self, db_path):
        analyzer = FeedbackTrendAnalyzer(db_path=db_path)
        stats = analyzer.get_report_stats(limit=3)
        assert len(stats) == 3
        assert stats[0]["rating"] in ("good", "bad", "neutral")
        assert "project_count" in stats[0]
        assert "tti_total" in stats[0]

    def test_get_trend_summary(self, db_path):
        analyzer = FeedbackTrendAnalyzer(db_path=db_path)
        summary = analyzer.get_trend_summary()
        assert "Feedback Trend Summary" in summary
        assert "positive rate" in summary.lower() or "Positive rate" in summary

    def test_trend_summary_format(self, db_path):
        analyzer = FeedbackTrendAnalyzer(db_path=db_path)
        summary = analyzer.get_trend_summary()
        assert "##" in summary
        assert "|" in summary  # Table formatting

    def test_daily_trends_no_data(self):
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
        conn.commit()
        conn.close()

        analyzer = FeedbackTrendAnalyzer(db_path=tmp.name)
        trends = analyzer.get_daily_trends()
        assert trends == []

        import os
        os.unlink(tmp.name)
