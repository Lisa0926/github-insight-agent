# -*- coding: utf-8 -*-
"""
Tests for Phase 5 deployment improvements:
- Prompt version management (prompt_version.py)
- Trace sampling strategies (trace_sampling.py)
- Prompt A/B testing (prompt_ab_test.py)
- Summary quality validation (summary_quality.py)
"""

import json
import os
import tempfile
import time
from unittest.mock import patch

import pytest

from src.core.prompt_version import PromptVersion, PromptVersionManager
from src.core.trace_sampling import SamplingMode, TraceSampler, sample_span, _matches_pattern
from src.core.prompt_ab_test import (
    PromptABTester,
    ExperimentStatus,
    Winner,
    ExperimentReport,
)
from src.core.summary_quality import (
    _extract_keywords,
    _extract_entities,
    validate_summary,
    validate_prompt_injection,
)


# ============================================================
# Prompt Version Management Tests
# ============================================================


class TestPromptVersionDataclass:
    def test_to_dict_and_from_dict(self):
        v = PromptVersion(
            agent_key="researcher",
            prompt_key="system_prompt",
            version=1,
            prompt_hash="abc123",
            prompt_content="Hello prompt",
            change_reason="Initial",
            timestamp="2026-05-07T00:00:00",
            feedback_scores=[1.0, 0.5],
        )
        d = v.to_dict()
        assert d["agent_key"] == "researcher"
        assert d["version"] == 1
        v2 = PromptVersion.from_dict(d)
        assert v2.prompt_hash == "abc123"
        assert v2.feedback_scores == [1.0, 0.5]


class TestPromptVersionManager:
    @pytest.fixture
    def manager(self, tmp_path):
        storage = str(tmp_path / "prompt_versions.json")
        return PromptVersionManager(storage_path=storage)

    def test_record_first_version(self, manager):
        v = manager.record_prompt("researcher", "Hello prompt", change_reason="Initial")
        assert v.version == 1
        assert len(v.prompt_hash) == 12

    def test_skip_unchanged(self, manager):
        manager.record_prompt("researcher", "Same prompt", change_reason="Initial")
        v2 = manager.record_prompt("researcher", "Same prompt", change_reason="No change")
        assert v2.version == 1  # No new version

    def test_new_version_on_change(self, manager):
        manager.record_prompt("researcher", "Version 1", change_reason="v1")
        v2 = manager.record_prompt("researcher", "Version 2 changed", change_reason="v2")
        assert v2.version == 2

    def test_different_agents_separate_history(self, manager):
        v1 = manager.record_prompt("researcher", "Researcher prompt")
        v2 = manager.record_prompt("analyst", "Analyst prompt")
        assert v1.version == 1
        assert v2.version == 1

    def test_get_latest(self, manager):
        manager.record_prompt("researcher", "v1")
        manager.record_prompt("researcher", "v2")
        latest = manager.get_latest("researcher")
        assert latest.version == 2

    def test_get_latest_empty(self, manager):
        assert manager.get_latest("unknown") is None

    def test_get_history(self, manager):
        manager.record_prompt("researcher", "v1")
        manager.record_prompt("researcher", "v2")
        manager.record_prompt("researcher", "v3")
        history = manager.get_history("researcher")
        assert len(history) == 3

    def test_compare_versions_same(self, manager):
        manager.record_prompt("researcher", "Same content")
        result = manager.compare_versions("researcher", v1=1, v2=1)
        assert result["changed"] is False

    def test_compare_versions_different(self, manager):
        manager.record_prompt("researcher", "Content A")
        manager.record_prompt("researcher", "Content B")
        result = manager.compare_versions("researcher", v1=1, v2=2)
        assert result["changed"] is True
        assert "Added" in result["diff_summary"]

    def test_compare_missing_version(self, manager):
        manager.record_prompt("researcher", "Only one")
        result = manager.compare_versions("researcher", v1=1, v2=99)
        assert "error" in result

    def test_record_feedback_correlation(self, manager):
        manager.record_prompt("researcher", "Prompt text")
        manager.record_feedback("researcher", "system_prompt", score=1.0)
        stats = manager.get_version_stats("researcher")
        assert stats["feedback_count"] == 1
        assert stats["avg_feedback_score"] == 1.0

    def test_record_feedback_no_version(self, manager):
        manager.record_feedback("researcher", "system_prompt", score=1.0)
        stats = manager.get_version_stats("researcher")
        assert stats["total_versions"] == 0

    def test_get_version_stats_empty(self, manager):
        stats = manager.get_version_stats("unknown")
        assert stats["total_versions"] == 0

    def test_get_version_stats_with_data(self, manager):
        manager.record_prompt("researcher", "Prompt", change_reason="test")
        manager.record_feedback("researcher", "system_prompt", score=1.0)
        manager.record_feedback("researcher", "system_prompt", score=0.5)
        stats = manager.get_version_stats("researcher")
        assert stats["total_versions"] == 1
        assert stats["feedback_count"] == 2
        assert stats["avg_feedback_score"] == 0.75

    def test_get_recent_changes_across_agents(self, manager):
        manager.record_prompt("researcher", "R prompt")
        manager.record_prompt("analyst", "A prompt")
        changes = manager.get_recent_changes(count=10)
        assert len(changes) == 2

    def test_get_recent_changes_filter_by_agent(self, manager):
        manager.record_prompt("researcher", "R prompt")
        manager.record_prompt("analyst", "A prompt")
        changes = manager.get_recent_changes(agent_key="researcher")
        assert len(changes) == 1
        assert changes[0].agent_key == "researcher"

    def test_persistence_roundtrip(self, tmp_path):
        storage = str(tmp_path / "pv.json")
        m1 = PromptVersionManager(storage_path=storage)
        m1.record_prompt("researcher", "Persisted prompt")
        m2 = PromptVersionManager(storage_path=storage)
        latest = m2.get_latest("researcher")
        assert latest is not None
        assert latest.version == 1


# ============================================================
# Trace Sampling Tests
# ============================================================


class TestSamplingModeEnum:
    def test_enum_values(self):
        assert SamplingMode.ALWAYS.value == "always"
        assert SamplingMode.NEVER.value == "never"
        assert SamplingMode.PROBABILITY.value == "probability"
        assert SamplingMode.RATE_LIMIT.value == "rate_limit"


class TestTraceSampler:
    def test_always_sample(self):
        sampler = TraceSampler(mode=SamplingMode.ALWAYS)
        assert sampler.should_sample("github.search") is True
        assert sampler.should_sample("anything") is True

    def test_never_sample(self):
        sampler = TraceSampler(mode=SamplingMode.NEVER)
        assert sampler.should_sample("github.search") is False

    def test_probability_always(self):
        sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=1.0)
        assert sampler.should_sample("op") is True

    def test_probability_never(self):
        sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=0.0)
        assert sampler.should_sample("op") is False

    def test_probability_partial(self):
        """With 0.5 rate, should get mix of True/False over many calls."""
        sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=0.5)
        results = [sampler.should_sample("op") for _ in range(100)]
        assert True in results and False in results

    def test_rate_limit_within_cap(self):
        sampler = TraceSampler(mode=SamplingMode.RATE_LIMIT, max_traces_per_minute=10)
        # Should allow first 10
        for _ in range(10):
            assert sampler.should_sample("op") is True

    def test_rate_limit_exceeds_cap(self):
        sampler = TraceSampler(mode=SamplingMode.RATE_LIMIT, max_traces_per_minute=3)
        # Force window start to now so first calls aren't affected by window reset
        sampler._window_start = time.time()
        sampler._window_count = 0
        for _ in range(3):
            assert sampler.should_sample("op") is True
        # 4th should be rejected
        assert sampler.should_sample("op") is False

    def test_rate_limit_window_reset(self):
        sampler = TraceSampler(mode=SamplingMode.RATE_LIMIT, max_traces_per_minute=2)
        sampler._window_start = time.time()
        sampler._window_count = 0
        sampler.should_sample("op")
        sampler.should_sample("op")
        assert sampler.should_sample("op") is False
        # Simulate window reset
        sampler._window_start = time.time() - 61
        sampler._window_count = 10
        assert sampler.should_sample("op") is True

    def test_operation_filter_override(self):
        sampler = TraceSampler(
            mode=SamplingMode.ALWAYS,
            operation_filters={"github.*": SamplingMode.NEVER},
        )
        assert sampler.should_sample("github.search") is False
        assert sampler.should_sample("other.op") is True

    def test_get_stats(self):
        sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=0.5)
        sampler.should_sample("op")
        stats = sampler.get_stats()
        assert stats["mode"] == "probability"
        assert stats["rate"] == 0.5
        assert stats["call_counter"] >= 1


class TestSampleSpan:
    def test_sample_span_executes_when_sampled(self):
        sampler = TraceSampler(mode=SamplingMode.ALWAYS)
        result = sample_span("op", sampler, lambda: "done")
        assert result == "done"

    def test_sample_span_returns_fallback_when_not_sampled(self):
        sampler = TraceSampler(mode=SamplingMode.NEVER)
        result = sample_span("op", sampler, lambda: "done", fallback="skipped")
        assert result == "skipped"


class TestPatternMatching:
    def test_exact_match(self):
        assert _matches_pattern("github.search", "github.search") is True
        assert _matches_pattern("github.search", "analyst.reply") is False

    def test_wildcard_match(self):
        assert _matches_pattern("github.search", "github.*") is True
        assert _matches_pattern("github.get_readme", "github.*") is True
        assert _matches_pattern("analyst.reply", "github.*") is False


# ============================================================
# Prompt A/B Testing Tests
# ============================================================


class TestPromptABTester:
    @pytest.fixture
    def tester(self, tmp_path):
        storage = str(tmp_path / "ab_tests.json")
        return PromptABTester(storage_path=storage)

    def test_create_experiment(self, tester):
        exp = tester.create_experiment(
            agent_key="researcher",
            prompt_a="Old prompt",
            prompt_b="New prompt",
            description="Test experiment",
        )
        assert exp.status == ExperimentStatus.DRAFT.value
        assert len(exp.id) == 8

    def test_start_experiment(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        assert tester.start_experiment(exp.id) is True
        fresh = tester.get_experiment(exp.id)
        assert fresh.status == ExperimentStatus.RUNNING.value

    def test_start_nonexistent(self, tester):
        assert tester.start_experiment("nonexistent") is False

    def test_record_observation(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        tester.start_experiment(exp.id)
        assert tester.record_observation(exp.id, "A", 1.0, "good") is True
        fresh = tester.get_experiment(exp.id)
        assert len(fresh.observations) == 1

    def test_record_observation_draft_rejected(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        # Experiment is in DRAFT, not RUNNING
        assert tester.record_observation(exp.id, "A", 1.0, "good") is False

    def test_get_active_experiment(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        tester.start_experiment(exp.id)
        active = tester.get_active_experiment("researcher")
        assert active is not None
        assert active.id == exp.id

    def test_report_no_observations(self, tester):
        exp = tester.create_experiment("researcher", "A", "B", description="Test")
        report = tester.get_report(exp.id)
        assert report.variant_a["count"] == 0
        assert report.variant_b["count"] == 0
        assert report.winner is None

    def test_report_with_data(self, tester):
        exp = tester.create_experiment("researcher", "A", "B", description="Test")
        tester.start_experiment(exp.id)
        tester.record_observation(exp.id, "A", 1.0, "good")
        tester.record_observation(exp.id, "B", 0.0, "bad")
        report = tester.get_report(exp.id)
        assert report.variant_a["count"] == 1
        assert report.variant_b["count"] == 1

    def test_auto_conclude_a_wins(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        tester.start_experiment(exp.id)
        # 5 observations for A (all good), 5 for B (all bad)
        for _ in range(5):
            tester.record_observation(exp.id, "A", 1.0, "good")
            tester.record_observation(exp.id, "B", 0.0, "bad")
        assert exp.winner == Winner.A.value
        assert exp.status == ExperimentStatus.CONCLUDED.value

    def test_auto_conclude_b_wins(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        tester.start_experiment(exp.id)
        for _ in range(5):
            tester.record_observation(exp.id, "A", 0.0, "bad")
            tester.record_observation(exp.id, "B", 1.0, "good")
        assert exp.winner == Winner.B.value
        assert exp.status == ExperimentStatus.CONCLUDED.value

    def test_auto_conclude_tie(self, tester):
        exp = tester.create_experiment("researcher", "A", "B")
        tester.start_experiment(exp.id)
        # Both variants get identical scores
        for _ in range(10):
            tester.record_observation(exp.id, "A", 0.7, "good")
            tester.record_observation(exp.id, "B", 0.7, "good")
        assert exp.winner == Winner.TIE.value
        assert exp.status == ExperimentStatus.CONCLUDED.value

    def test_get_all_reports(self, tester):
        e1 = tester.create_experiment("researcher", "A", "B")
        e2 = tester.create_experiment("analyst", "A", "B")
        reports = tester.get_all_reports()
        assert len(reports) == 2

    def test_persistence(self, tmp_path):
        storage = str(tmp_path / "ab.json")
        t1 = PromptABTester(storage_path=storage)
        e = t1.create_experiment("researcher", "A", "B")
        t2 = PromptABTester(storage_path=storage)
        assert t2.get_experiment(e.id) is not None


# ============================================================
# Summary Quality Validation Tests
# ============================================================


class TestKeywordExtraction:
    def test_basic_keywords(self):
        keywords = _extract_keywords("Hello world github repository")
        assert "hello" in keywords
        assert "world" in keywords
        assert "github" in keywords

    def test_min_length_filter(self):
        keywords = _extract_keywords("I am a test with some words")
        assert "i" not in keywords
        assert "am" not in keywords
        assert "a" not in keywords
        assert "test" in keywords

    def test_lowercase(self):
        keywords = _extract_keywords("GitHub Repository Analysis")
        assert "github" in keywords
        assert "GitHub" not in keywords


class TestEntityExtraction:
    def test_repo_refs(self):
        entities = _extract_entities("Check out owner/repo and other/project")
        assert "owner/repo" in entities
        assert "other/project" in entities

    def test_capitalized_words(self):
        entities = _extract_entities("The Python Framework uses Django")
        assert "Python" in entities
        assert "Django" in entities

    def test_no_short_capitalized(self):
        entities = _extract_entities("I am not An entity")
        assert "I" not in entities


class TestValidateSummary:
    def test_good_quality(self):
        original = [
            {"role": "user", "content": "Search for the Python GitHub repository"},
            {"role": "assistant", "content": "Found Python repo with 50000 stars"},
        ]
        summary = "Search for Python GitHub repository with 50000 stars"
        result = validate_summary(original, summary)
        assert result["keyword_overlap"] > 0.5
        assert result["quality"] in ("good", "fair")
        assert result["keyword_overlap"] > 0

    def test_poor_quality(self):
        original = [
            {"role": "user", "content": "Analyze the Kubernetes project architecture"},
        ]
        summary = "This is about something completely different and unrelated"
        result = validate_summary(original, summary)
        assert result["quality"] == "poor"

    def test_empty_original(self):
        result = validate_summary([], "Some summary")
        assert result["quality"] == "poor"
        assert result["reason"] == "Empty input"

    def test_empty_summary(self):
        original = [{"role": "user", "content": "Hello world"}]
        result = validate_summary(original, "")
        assert result["quality"] == "poor"
        assert result["reason"] == "Empty input"

    def test_length_ratio(self):
        original = [{"role": "user", "content": "A" * 1000}]
        summary = "B" * 200
        result = validate_summary(original, summary)
        assert result["length_ratio"] == pytest.approx(0.2, abs=0.01)

    def test_output_fields(self):
        original = [{"role": "user", "content": "Test content here"}]
        summary = "Test content"
        result = validate_summary(original, summary)
        assert "keyword_overlap" in result
        assert "entity_overlap" in result
        assert "length_ratio" in result
        assert "quality" in result
        assert "orig_keyword_count" in result
        assert "summary_keyword_count" in result

    def test_entity_overlap_github_refs(self):
        original = [{"role": "user", "content": "Check out tensorflow/tensorflow on GitHub"}]
        summary = "TensorFlow TensorFlow has many stars"
        result = validate_summary(original, summary)
        assert "entity_overlap" in result


class TestValidatePromptInjection:
    def test_injected_success(self):
        summary = "This is the summary"
        context = "System: You are helpful.\n\nThis is the summary\nRecent history..."
        result = validate_prompt_injection(summary, context)
        assert result["injected"] is True

    def test_not_injected(self):
        summary = "Missing summary"
        context = "Some other context without the summary"
        result = validate_prompt_injection(summary, context)
        assert result["injected"] is False

    def test_empty_summary(self):
        result = validate_prompt_injection("", "Some context")
        assert result["injected"] is False
        assert result["reason"] == "Empty summary"

    def test_context_ratio(self):
        summary = "Short summary"
        context = summary + " " + "Extra context " * 50
        result = validate_prompt_injection(summary, context)
        assert result["context_to_summary_ratio"] > 1.0
        assert result["summary_length"] == len(summary)
        assert result["context_length"] == len(context)
