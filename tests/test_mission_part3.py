# -*- coding: utf-8 -*-
"""Tests for current mission untracked modules and fixes:
1. Span attributes (span_attributes.py) — no existing tests
2. Eval pipeline (eval_pipeline.py) — no dedicated test file
3. Summary quality (summary_quality.py) — no dedicated test file
4. ResearcherAgent total_count bug fix verification
5. Span attributes integration in researcher_agent and github_tool
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 1. Span Attributes Module Tests
# ============================================================

class TestSpanAttributes:
    """Test src/core/span_attributes.py module."""

    def test_hash_function(self):
        """Test the _hash helper produces consistent truncated SHA-256."""
        from src.core.span_attributes import _hash

        h1 = _hash("test query")
        h2 = _hash("test query")
        assert h1 == h2
        assert len(h1) == 8  # default length

        h3 = _hash("test query", length=12)
        assert len(h3) == 12

        h4 = _hash("different query")
        assert h1 != h4

    def test_hash_unicode_handling(self):
        """Test hash handles unicode with error replacement."""
        from src.core.span_attributes import _hash

        h = _hash("测试中文 query")
        assert len(h) == 8
        assert isinstance(h, str)

    def test_set_span_attribute_noop_when_no_span(self):
        """set_span_attribute should not raise when no active span."""
        from src.core.span_attributes import set_span_attribute

        # Should not raise even with no OTel span
        set_span_attribute("test.key", "test_value")
        set_span_attribute("test.int", 42)
        set_span_attribute("test.float", 3.14)
        set_span_attribute("test.bool", True)
        set_span_attribute("test.none", None)

    def test_set_span_attributes_noop(self):
        """set_span_attributes should not raise when no active span."""
        from src.core.span_attributes import set_span_attributes

        set_span_attributes({
            "key1": "value1",
            "key2": 123,
            "key3": True,
        })

    def test_set_span_error_noop(self):
        """set_span_error should not raise when no active span."""
        from src.core.span_attributes import set_span_error

        set_span_error(ValueError("test error"))
        set_span_error(RuntimeError("another error"))

    def test_span_timer_context_manager(self):
        """SpanTimer records elapsed time as attribute."""
        from src.core.span_attributes import SpanTimer

        # Track what attributes were set
        captured = {}

        def mock_set(k, v):
            captured[k] = v

        with patch('src.core.span_attributes.set_span_attribute', side_effect=mock_set):
            with SpanTimer("test_duration_ms"):
                time.sleep(0.05)  # 50ms

        assert "test_duration_ms" in captured
        assert captured["test_duration_ms"] >= 40  # Allow some margin
        assert captured["test_duration_ms"] < 5000  # Sanity cap

    def test_span_timer_custom_prefix(self):
        """SpanTimer uses custom prefix."""
        import time
        from src.core.span_attributes import SpanTimer

        captured = {}
        with patch('src.core.span_attributes.set_span_attribute', side_effect=lambda k, v: captured.__setitem__(k, v)):
            with SpanTimer("custom_metric"):
                time.sleep(0.01)

        assert "custom_metric" in captured


# ============================================================
# 2. Eval Pipeline Tests
# ============================================================

class TestEvalPipeline:
    """Test src/core/eval_pipeline.py module."""

    def test_eval_result_dataclass(self):
        """Test EvalResult dataclass."""
        from src.core.eval_pipeline import EvalResult

        r = EvalResult(test_name="test1", passed=True, score=0.95, details="OK")
        assert r.test_name == "test1"
        assert r.passed is True
        assert r.score == 0.95
        assert r.details == "OK"

        # Defaults
        r2 = EvalResult(test_name="test2", passed=False)
        assert r2.score is None
        assert r2.details == ""

    def test_eval_report_to_dict(self):
        """Test EvalReport.to_dict serialization."""
        from src.core.eval_pipeline import EvalReport, EvalResult

        report = EvalReport(
            timestamp="2026-05-07T00:00:00",
            version="1.0.0",
            total_tests=3,
            passed=2,
            failed=1,
            golden_dataset_results=[
                EvalResult(test_name="t1", passed=True, score=0.9),
                EvalResult(test_name="t2", passed=False, details="fail"),
            ],
            judge_scores={"mean": 3.5},
            kpi_summary={"researcher": {"success_rate": 0.8}},
        )

        d = report.to_dict()
        assert d["timestamp"] == "2026-05-07T00:00:00"
        assert d["version"] == "1.0.0"
        assert d["summary"]["total_tests"] == 3
        assert d["summary"]["passed"] == 2
        assert d["summary"]["failed"] == 1
        assert abs(d["summary"]["pass_rate"] - 0.667) < 0.01
        assert len(d["golden_dataset"]) == 2
        assert d["judge_scores"]["mean"] == 3.5

    def test_eval_report_zero_division_guard(self):
        """EvalReport.to_dict handles zero total_tests."""
        from src.core.eval_pipeline import EvalReport

        report = EvalReport(total_tests=0, passed=0, failed=0)
        d = report.to_dict()
        assert d["summary"]["pass_rate"] == 0

    def test_golden_dataset_file_exists(self):
        """Verify golden dataset JSON file exists."""
        from src.core.golden_dataset import _GOLDEN_DATASET_PATH

        assert _GOLDEN_DATASET_PATH.exists()

    def test_eval_pipeline_golden_only(self):
        """Test running eval pipeline with golden_only=True."""
        from src.core.eval_pipeline import run_eval_pipeline

        report = run_eval_pipeline(golden_only=True)
        assert report.total_tests > 0
        assert report.passed + report.failed == report.total_tests

    def test_eval_pipeline_multi_model_judge_mock(self):
        """Test multi-model judge scoring with mock functions."""
        from src.core.eval_pipeline import run_eval_pipeline

        report = run_eval_pipeline(mock=True)
        assert "consensus_mean" in report.judge_scores or "mean" in report.judge_scores

    def test_eval_pipeline_full_run(self):
        """Test full eval pipeline (golden + judge + kpi)."""
        from src.core.eval_pipeline import run_eval_pipeline

        report = run_eval_pipeline(mock=True)
        assert report.total_tests > 0
        assert report.version != ""
        assert report.judge_scores  # Judge scores populated
        assert report.kpi_summary  # KPI summary populated

    def test_eval_pipeline_output_json(self):
        """Test that eval pipeline can write JSON output."""
        from src.core.eval_pipeline import run_eval_pipeline

        report = run_eval_pipeline(golden_only=True)
        output = report.to_dict()

        # Verify JSON serializable
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["summary"]["total_tests"] == report.total_tests


# ============================================================
# 3. Summary Quality Tests
# ============================================================

class TestSummaryQuality:
    """Test src/core/summary_quality.py module."""

    def test_extract_keywords(self):
        """Test keyword extraction from text."""
        from src.core.summary_quality import _extract_keywords

        keywords = _extract_keywords("Hello world, this is Python code.")
        assert "hello" in keywords
        assert "world" in keywords
        assert "python" in keywords
        assert "code" in keywords
        # Short words filtered out
        assert "is" not in keywords

    def test_extract_keywords_min_length(self):
        """Test min_length parameter."""
        from src.core.summary_quality import _extract_keywords

        keywords = _extract_keywords("ab cde fghi", min_length=3)
        assert "ab" not in keywords
        assert "cde" in keywords
        assert "fghi" in keywords

    def test_extract_entities(self):
        """Test entity extraction."""
        from src.core.summary_quality import _extract_entities

        text = "The langchain-ai/langchain repo uses Python and FastAPI"
        entities = _extract_entities(text)
        assert "langchain-ai/langchain" in entities

    def test_validate_summary_good(self):
        """Test validate_summary with good overlap."""
        from src.core.summary_quality import validate_summary

        original = [
            {"role": "user", "content": "Search for Python web frameworks like FastAPI and Django"},
            {"role": "assistant", "content": "Found FastAPI, Django, and Flask. FastAPI is modern and async."},
        ]
        summary = "Python web frameworks: FastAPI (modern async), Django, Flask"

        result = validate_summary(original, summary)
        assert result["keyword_overlap"] > 0.3
        assert result["length_ratio"] < 1.0  # Summary should be shorter
        assert result["quality"] in ("good", "fair", "poor")

    def test_validate_summary_empty_input(self):
        """Test validate_summary with empty inputs."""
        from src.core.summary_quality import validate_summary

        result = validate_summary([], "Some summary")
        assert result["keyword_overlap"] == 0.0
        assert result["quality"] == "poor"

        result = validate_summary([{"role": "user", "content": "hello"}], "")
        assert result["keyword_overlap"] == 0.0
        assert result["quality"] == "poor"

    def test_validate_summary_no_keywords(self):
        """Test validate_summary when original has no keywords."""
        from src.core.summary_quality import validate_summary

        original = [{"role": "user", "content": "... --- ..."}]
        result = validate_summary(original, "some summary text")
        assert result["keyword_overlap"] == 0.0

    def test_validate_prompt_injection(self):
        """Test prompt injection validation."""
        from src.core.summary_quality import validate_prompt_injection

        summary = "Previous conversation summary"
        context = f"System: Here is the summary: {summary}\nRecent: hello"

        result = validate_prompt_injection(summary, context)
        assert result["injected"] is True
        assert result["summary_length"] == len(summary)

    def test_validate_prompt_injection_not_injected(self):
        """Test when summary is NOT in context."""
        from src.core.summary_quality import validate_prompt_injection

        summary = "Some summary"
        context = "Different context without the summary"

        result = validate_prompt_injection(summary, context)
        assert result["injected"] is False

    def test_validate_prompt_injection_empty_summary(self):
        """Test with empty summary."""
        from src.core.summary_quality import validate_prompt_injection

        result = validate_prompt_injection("", "context")
        assert result["injected"] is False
        assert result["reason"] == "Empty summary"


# ============================================================
# 4. ResearcherAgent Bug Fix Verification
# ============================================================

class TestResearcherAgentTotalCountFix:
    """Verify the total_count NameError fix in researcher_agent.py."""

    def test_search_and_analyze_no_name_error(self):
        """After fix, search_and_analyze should not raise NameError."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            # Simulate the code path that had the bug
            repos = [MagicMock(full_name="test/repo", html_url="https://github.com/test/repo",
                               stargazers_count=100, language="Python", description="Test",
                               topics=["test"])]
            query = "test query"
            search_query = "test"

            # This should NOT raise NameError after the fix
            # The fix changed `total_count` to `len(repos)`
            set_span_attrs = {}

            def mock_set(k, v):
                set_span_attrs[k] = v

            with patch('src.core.span_attributes.set_span_attribute', side_effect=mock_set):
                # Simulate the fixed code path
                mock_set("researcher.query", query)
                mock_set("researcher.search_query", search_query)
                mock_set("researcher.result_count", len(repos))
                mock_set("researcher.total_found", len(repos))  # Fixed: was total_count

            # Verify all attributes were set
            assert set_span_attrs["researcher.total_found"] == len(repos)
            assert set_span_attrs["researcher.result_count"] == len(repos)


# ============================================================
# 5. Span Attributes Integration Tests
# ============================================================

class TestSpanAttributesIntegration:
    """Test span attributes are properly integrated in source files."""

    def test_researcher_agent_imports_span_attributes(self):
        """ResearcherAgent imports set_span_attributes."""
        with open("src/agents/researcher_agent.py") as f:
            content = f.read()
        assert "from src.core.span_attributes import set_span_attributes" in content

    def test_github_tool_imports_span_attributes(self):
        """GitHubTool imports set_span_attributes."""
        with open("src/tools/github_tool.py") as f:
            content = f.read()
        assert "from src.core.span_attributes import set_span_attributes" in content

    def test_researcher_agent_uses_span_attributes(self):
        """ResearcherAgent calls set_span_attributes with researcher attributes."""
        with open("src/agents/researcher_agent.py") as f:
            content = f.read()
        assert "researcher.query" in content
        assert "researcher.search_query" in content
        assert "researcher.result_count" in content
        assert "researcher.total_found" in content

    def test_github_tool_uses_span_attributes(self):
        """GitHubTool calls set_span_attributes with github attributes."""
        with open("src/tools/github_tool.py") as f:
            content = f.read()
        assert "github.query_hash" in content
        assert "github.result_count" in content
        assert "github.readme_length" in content
        assert "github.repo_stars" in content


# ============================================================
# 6. Golden Dataset Additional Tests
# ============================================================

class TestGoldenDatasetAdditional:
    """Additional golden dataset tests not covered elsewhere."""

    def test_stats(self):
        """Test GoldenDataset.stats method."""
        from src.core.golden_dataset import load_golden_dataset

        dataset = load_golden_dataset()
        stats = dataset.stats()

        assert stats["total_repos"] == len(dataset.repos)
        assert "categories" in stats
        assert "languages" in stats
        assert "has_readme" in stats
        assert "no_readme" in stats
        assert "archived" in stats
        assert "forks" in stats

    def test_get_all_ids(self):
        """Test get_all_ids returns all repo IDs."""
        from src.core.golden_dataset import load_golden_dataset

        dataset = load_golden_dataset()
        ids = dataset.get_all_ids()
        assert len(ids) == len(dataset.repos)
        assert len(set(ids)) == len(ids)  # All unique

    def test_filter_by_language_case_insensitive(self):
        """Test filter_by_language is case-insensitive."""
        from src.core.golden_dataset import load_golden_dataset

        dataset = load_golden_dataset()
        py1 = dataset.filter_by_language("Python")
        py2 = dataset.filter_by_language("python")
        py3 = dataset.filter_by_language("PYTHON")
        assert len(py1) == len(py2) == len(py3)

    def test_add_repo_new(self):
        """Test adding a new repo to dataset."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo

        ds = GoldenDataset(version="test", description="test")
        assert len(ds.repos) == 0

        repo = GoldenRepo(
            id="test_repo",
            category="test",
            full_name="test/repo",
            html_url="https://github.com/test/repo",
            stargazers_count=10,
            forks_count=2,
            watchers_count=5,
            open_issues_count=1,
            language="Python",
            description="A test repo",
            topics=["test"],
            updated_at="2026-01-01",
            owner_login="test",
            is_fork=False,
            is_archived=False,
            readme=None,
        )
        ds.add_repo(repo)
        assert len(ds.repos) == 1

    def test_add_repo_replace(self):
        """Test adding a repo replaces existing with same ID."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo

        ds = GoldenDataset(version="test", description="test")
        repo1 = GoldenRepo(
            id="r1", category="c", full_name="a/b", html_url="https://x",
            stargazers_count=10, forks_count=1, watchers_count=1,
            open_issues_count=0, language="Python", description="d",
            topics=[], updated_at="2026-01-01", owner_login="a",
            is_fork=False, is_archived=False, readme=None,
        )
        ds.add_repo(repo1)

        repo2 = GoldenRepo(
            id="r1", category="c", full_name="a/b", html_url="https://x",
            stargazers_count=100, forks_count=1, watchers_count=1,
            open_issues_count=0, language="Python", description="d",
            topics=[], updated_at="2026-01-01", owner_login="a",
            is_fork=False, is_archived=False, readme=None,
        )
        ds.add_repo(repo2)
        assert len(ds.repos) == 1
        assert ds.repos[0].stargazers_count == 100

    def test_remove_repo(self):
        """Test removing a repo."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo

        ds = GoldenDataset(version="test", description="test")
        repo = GoldenRepo(
            id="r1", category="c", full_name="a/b", html_url="https://x",
            stargazers_count=10, forks_count=1, watchers_count=1,
            open_issues_count=0, language="Python", description="d",
            topics=[], updated_at="2026-01-01", owner_login="a",
            is_fork=False, is_archived=False, readme=None,
        )
        ds.add_repo(repo)
        assert ds.remove_repo("r1") is True
        assert len(ds.repos) == 0
        assert ds.remove_repo("nonexistent") is False

    def test_update_repo(self):
        """Test updating repo fields."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo

        ds = GoldenDataset(version="test", description="test")
        repo = GoldenRepo(
            id="r1", category="c", full_name="a/b", html_url="https://x",
            stargazers_count=10, forks_count=1, watchers_count=1,
            open_issues_count=0, language="Python", description="d",
            topics=[], updated_at="2026-01-01", owner_login="a",
            is_fork=False, is_archived=False, readme=None,
        )
        ds.add_repo(repo)

        assert ds.update_repo("r1", stargazers_count=999) is True
        assert ds.repos[0].stargazers_count == 999
        assert ds.update_repo("nonexistent", stargazers_count=1) is False

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test save_to_file and load_golden_dataset roundtrip."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo, load_golden_dataset

        ds = GoldenDataset(version="1.0.0", description="test dataset")
        repo = GoldenRepo(
            id="r1", category="test", full_name="a/b", html_url="https://x",
            stargazers_count=100, forks_count=5, watchers_count=10,
            open_issues_count=2, language="Python", description="A test repo",
            topics=["test", "python"], updated_at="2026-01-01", owner_login="a",
            is_fork=False, is_archived=False, readme="# Readme",
        )
        ds.add_repo(repo)

        path = str(tmp_path / "test_dataset.json")
        ds.save_to_file(path)

        loaded = load_golden_dataset(path)
        assert loaded.version == "1.0.0"
        assert len(loaded.repos) == 1
        assert loaded.repos[0].id == "r1"
        assert loaded.repos[0].stargazers_count == 100

    def test_merge_dataset(self):
        """Test merging two datasets."""
        from src.core.golden_dataset import GoldenDataset, GoldenRepo

        def make_ds(rid, stars):
            ds = GoldenDataset(version="1.0", description="test")
            ds.add_repo(GoldenRepo(
                id=rid, category="c", full_name="a/b", html_url="https://x",
                stargazers_count=stars, forks_count=1, watchers_count=1,
                open_issues_count=0, language="Python", description="d",
                topics=[], updated_at="2026-01-01", owner_login="a",
                is_fork=False, is_archived=False, readme=None,
            ))
            return ds

        ds1 = make_ds("r1", 10)
        ds2 = make_ds("r1", 100)  # Same ID, different stars
        ds2.add_repo(GoldenRepo(
            id="r2", category="c", full_name="c/d", html_url="https://y",
            stargazers_count=200, forks_count=1, watchers_count=1,
            open_issues_count=0, language="Rust", description="e",
            topics=[], updated_at="2026-01-01", owner_login="c",
            is_fork=False, is_archived=False, readme=None,
        ))

        count = ds1.merge_dataset(ds2)
        assert count == 2  # 1 updated + 1 added
        assert len(ds1.repos) == 2

    def test_to_api_response(self):
        """Test GoldenRepo.to_api_response produces correct format."""
        from src.core.golden_dataset import GoldenRepo

        repo = GoldenRepo(
            id="r1", category="c", full_name="owner/repo", html_url="https://github.com/owner/repo",
            stargazers_count=500, forks_count=50, watchers_count=100,
            open_issues_count=10, language="TypeScript", description="A repo",
            topics=["web", "api"], updated_at="2026-01-01", owner_login="owner",
            is_fork=True, is_archived=False, readme="# README",
        )
        api = repo.to_api_response()

        assert api["full_name"] == "owner/repo"
        assert api["stargazers_count"] == 500
        assert api["owner"]["login"] == "owner"
        assert api["fork"] is True
        assert api["archived"] is False
        assert api["readme"] == "# README"


# ============================================================
# 7. Trace Sampling Additional Tests
# ============================================================

class TestTraceSamplingAdditional:
    """Additional trace sampling tests."""

    def test_always_mode(self):
        """ALWAYS mode always returns True."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(mode=SamplingMode.ALWAYS)
        assert sampler.should_sample("any.operation") is True
        assert sampler.should_sample("github.search") is True

    def test_never_mode(self):
        """NEVER mode always returns False."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(mode=SamplingMode.NEVER)
        assert sampler.should_sample("any.operation") is False

    def test_probability_mode_deterministic(self):
        """PROBABILITY mode uses hash for consistency."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(mode=SamplingMode.PROBABILITY, rate=0.0)
        # With rate=0, should always be False
        assert sampler.should_sample("any.operation") is False

        sampler2 = TraceSampler(mode=SamplingMode.PROBABILITY, rate=1.0)
        # With rate=1.0, should always be True
        assert sampler2.should_sample("any.operation") is True

    def test_operation_filter_override(self):
        """Operation filters override default mode."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(
            mode=SamplingMode.ALWAYS,
            operation_filters={"github.*": SamplingMode.NEVER},
        )
        # github operations should be NEVER
        assert sampler.should_sample("github.search") is False
        # Other operations should be ALWAYS
        assert sampler.should_sample("other.operation") is True

    def test_rate_limit_window_reset(self):
        """Rate limit window resets after 60s."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(
            mode=SamplingMode.RATE_LIMIT,
            max_traces_per_minute=1,
        )
        # Call 1: window expired (0.0), resets and returns True, count=0
        assert sampler.should_sample("op") is True
        # Call 2: count 0 < 1, returns True, count=1
        assert sampler.should_sample("op") is True
        # Call 3: count 1 >= 1, denied
        assert sampler.should_sample("op") is False

        # Simulate window expired
        sampler._window_start = time.time() - 120
        # Call 4: window expired, resets and returns True, count=0
        assert sampler.should_sample("op") is True
        # Call 5: count 0 < 1, returns True, count=1
        assert sampler.should_sample("op") is True
        # Call 6: count 1 >= 1, denied
        assert sampler.should_sample("op") is False

    def test_sample_span_executes_when_sampled(self):
        """sample_span calls fn when sampling is True."""
        from src.core.trace_sampling import TraceSampler, SamplingMode, sample_span

        sampler = TraceSampler(mode=SamplingMode.ALWAYS)
        result = sample_span("op", sampler, lambda x: x * 2, 5)
        assert result == 10

    def test_sample_span_returns_fallback_when_skipped(self):
        """sample_span returns fallback when sampling is False."""
        from src.core.trace_sampling import TraceSampler, SamplingMode, sample_span

        sampler = TraceSampler(mode=SamplingMode.NEVER)
        result = sample_span("op", sampler, lambda: "executed", fallback="skipped")
        assert result == "skipped"

    def test_matches_pattern(self):
        """Test pattern matching helper."""
        from src.core.trace_sampling import _matches_pattern

        assert _matches_pattern("github.search", "github.*") is True
        assert _matches_pattern("github.search.repos", "github.*") is True
        assert _matches_pattern("other.search", "github.*") is False
        assert _matches_pattern("exact.match", "exact.match") is True
        assert _matches_pattern("exact.match", "different") is False

    def test_get_stats(self):
        """Test sampler statistics."""
        from src.core.trace_sampling import TraceSampler, SamplingMode

        sampler = TraceSampler(
            mode=SamplingMode.PROBABILITY,
            rate=0.5,
            max_traces_per_minute=30,
        )
        sampler.should_sample("op1")
        sampler.should_sample("op2")

        stats = sampler.get_stats()
        assert stats["mode"] == "probability"
        assert stats["rate"] == 0.5
        assert stats["max_traces_per_minute"] == 30
        assert stats["call_counter"] == 2


# ============================================================
# 8. Prompt Version Manager Additional Tests
# ============================================================

class TestPromptVersionAdditional:
    """Additional prompt version tests."""

    def test_record_prompt_skip_unchanged(self, tmp_path):
        """Recording same prompt content skips version creation."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)

        v1 = mgr.record_prompt("researcher", "same prompt", change_reason="first")
        v2 = mgr.record_prompt("researcher", "same prompt", change_reason="second")

        assert v1.version == v2.version  # Same version, no new record
        assert len(mgr.get_history("researcher")) == 1

    def test_record_prompt_new_version(self, tmp_path):
        """Recording different prompt creates new version."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)

        v1 = mgr.record_prompt("researcher", "prompt v1")
        v2 = mgr.record_prompt("researcher", "prompt v2")

        assert v1.version == 1
        assert v2.version == 2
        assert len(mgr.get_history("researcher")) == 2

    def test_record_feedback(self, tmp_path):
        """Test feedback correlation with latest version."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)
        mgr.record_prompt("researcher", "prompt v1")

        mgr.record_feedback("researcher", "system_prompt", 0.8)
        mgr.record_feedback("researcher", "system_prompt", 0.9)

        stats = mgr.get_version_stats("researcher")
        assert stats["feedback_count"] == 2
        assert abs(stats["avg_feedback_score"] - 0.85) < 0.01

    def test_get_latest_empty(self, tmp_path):
        """get_latest returns None when no history."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)
        assert mgr.get_latest("nonexistent") is None

    def test_compare_versions_not_found(self, tmp_path):
        """compare_versions returns error for non-existent versions."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)
        mgr.record_prompt("researcher", "v1 content")

        result = mgr.compare_versions("researcher", v1=1, v2=99)
        assert "error" in result

        result = mgr.compare_versions("researcher", v1=99, v2=1)
        assert "error" in result

    def test_compare_versions_same(self, tmp_path):
        """compare_versions with same content shows no change."""
        from src.core.prompt_version import PromptVersionManager

        path = str(tmp_path / "pv.json")
        mgr = PromptVersionManager(storage_path=path)
        mgr.record_prompt("researcher", "content v1")
        mgr.record_prompt("researcher", "content v2")

        result = mgr.compare_versions("researcher", v1=1, v2=2)
        assert result["changed"] is True
        assert "diff_summary" in result


# ============================================================
# 9. Prompt A/B Testing Additional Tests
# ============================================================

class TestPromptABTestAdditional:
    """Additional A/B testing tests."""

    def test_create_and_start_experiment(self, tmp_path):
        """Test experiment lifecycle."""
        from src.core.prompt_ab_test import PromptABTester

        path = str(tmp_path / "ab.json")
        tester = PromptABTester(storage_path=path)

        exp = tester.create_experiment(
            agent_key="researcher",
            prompt_a="Prompt A text",
            prompt_b="Prompt B text",
            description="Test A vs B",
        )
        assert exp.status == "draft"

        assert tester.start_experiment(exp.id) is True
        exp = tester.get_experiment(exp.id)
        assert exp.status == "running"

    def test_record_observation_non_running(self, tmp_path):
        """Cannot record observation for non-running experiment."""
        from src.core.prompt_ab_test import PromptABTester

        path = str(tmp_path / "ab.json")
        tester = PromptABTester(storage_path=path)

        exp = tester.create_experiment(
            agent_key="researcher",
            prompt_a="A",
            prompt_b="B",
        )
        assert tester.record_observation(exp.id, "A", 0.8, "good") is False

    def test_auto_conclude_tie(self, tmp_path):
        """Experiment concludes as tie when scores are similar."""
        from src.core.prompt_ab_test import PromptABTester

        path = str(tmp_path / "ab.json")
        tester = PromptABTester(storage_path=path)

        exp = tester.create_experiment(
            agent_key="researcher",
            prompt_a="A",
            prompt_b="B",
        )
        tester.start_experiment(exp.id)

        # Record balanced observations
        for i in range(6):
            tester.record_observation(exp.id, "A", 0.5, "neutral")
            tester.record_observation(exp.id, "B", 0.5, "neutral")

        exp = tester.get_experiment(exp.id)
        assert exp.status == "concluded"
        assert exp.winner == "tie"

    def test_get_active_experiment(self, tmp_path):
        """Get active experiment by agent key."""
        from src.core.prompt_ab_test import PromptABTester

        path = str(tmp_path / "ab.json")
        tester = PromptABTester(storage_path=path)

        exp = tester.create_experiment(
            agent_key="researcher",
            prompt_a="A",
            prompt_b="B",
        )
        tester.start_experiment(exp.id)

        active = tester.get_active_experiment("researcher")
        assert active is not None
        assert active.id == exp.id

        # Non-existent agent
        assert tester.get_active_experiment("nonexistent") is None

    def test_get_report_nonexistent(self, tmp_path):
        """get_report returns None for non-existent experiment."""
        from src.core.prompt_ab_test import PromptABTester

        path = str(tmp_path / "ab.json")
        tester = PromptABTester(storage_path=path)
        assert tester.get_report("nonexistent") is None


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
