# -*- coding: utf-8 -*-
"""
Phase 4 P2/P3 improvement tests:
- Golden dataset loader (P3 persistence)
- Multi-model LLM-as-Judge (P3)
- Automated evaluation pipeline (P3)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ============================================================
# 1. Golden Dataset Loader Tests
# ============================================================

class TestGoldenDatasetLoader:
    """Test persistent golden dataset loading and filtering."""

    @pytest.fixture
    def dataset(self):
        from src.core.golden_dataset import load_golden_dataset
        return load_golden_dataset()

    def test_load_dataset(self, dataset):
        assert dataset.version == "1.0.0"
        assert len(dataset.repos) == 10

    def test_get_by_id(self, dataset):
        langchain = dataset.get_by_id("standard_large_python")
        assert langchain is not None
        assert langchain.full_name == "langchain-ai/langchain"
        assert langchain.stargazers_count == 90000

    def test_get_by_id_not_found(self, dataset):
        assert dataset.get_by_id("nonexistent") is None

    def test_get_by_category(self, dataset):
        standard = dataset.get_by_category("standard")
        edge = dataset.get_by_category("edge")
        assert len(standard) == 4
        assert len(edge) == 6

    def test_filter_by_language(self, dataset):
        python_repos = dataset.filter_by_language("Python")
        assert len(python_repos) == 3
        assert all(r.language == "Python" for r in python_repos)

    def test_get_all_ids(self, dataset):
        ids = dataset.get_all_ids()
        assert len(ids) == 10
        assert "standard_large_python" in ids
        assert "edge_zero_star" in ids

    def test_stats(self, dataset):
        stats = dataset.stats()
        assert stats["version"] == "1.0.0"
        assert stats["total_repos"] == 10
        assert stats["categories"]["standard"] == 4
        assert stats["categories"]["edge"] == 6
        assert "Python" in stats["languages"]

    def test_to_api_response(self, dataset):
        repo = dataset.get_by_id("standard_large_python")
        api_data = repo.to_api_response()
        assert api_data["full_name"] == "langchain-ai/langchain"
        assert api_data["stargazers_count"] == 90000
        assert api_data["owner"]["login"] == "langchain-ai"
        assert api_data["fork"] is False
        assert api_data["archived"] is False

    def test_get_repo_by_id_convenience(self):
        from src.core.golden_dataset import get_repo_by_id
        repo = get_repo_by_id("edge_zero_star")
        assert repo is not None
        assert repo.stargazers_count == 0

    def test_edge_case_zero_star(self, dataset):
        repo = dataset.get_by_id("edge_zero_star")
        assert repo.stargazers_count == 0
        assert repo.description == ""
        assert repo.topics == []

    def test_edge_case_no_readme(self, dataset):
        repo = dataset.get_by_id("edge_no_readme")
        assert repo.readme is None

    def test_edge_case_archived(self, dataset):
        repo = dataset.get_by_id("edge_archived_go")
        assert repo.is_archived is True

    def test_edge_case_fork(self, dataset):
        repo = dataset.get_by_id("edge_fork_repo")
        assert repo.is_fork is True


# ============================================================
# 2. Multi-Model LLM-as-Judge Tests
# ============================================================

class TestJudgeModelConfig:
    """Test judge model configuration."""

    def test_judge_models_defined(self):
        from src.core.llm_judge import JUDGE_MODELS
        assert "gpt-4o" in JUDGE_MODELS
        assert "claude" in JUDGE_MODELS
        assert "qwen" in JUDGE_MODELS

    def test_model_config_attributes(self):
        from src.core.llm_judge import JUDGE_MODELS
        config = JUDGE_MODELS["gpt-4o"]
        assert config.model_id == "gpt-4o"
        assert config.temperature == 0.0
        assert config.max_tokens == 1024

    def test_model_config_defaults(self):
        from src.core.llm_judge import JudgeModelConfig
        config = JudgeModelConfig(name="test", description="test", model_id="test-model")
        assert config.temperature == 0.0
        assert config.max_tokens == 1024
        assert config.score_min == 1.0
        assert config.score_max == 5.0


class TestModelScoreNormalizer:
    """Test cross-model score normalization."""

    def test_normalize_gpt4o_identity(self):
        from src.core.llm_judge import ModelScoreNormalizer
        # GPT-4o is baseline: slope=1.0, intercept=0.0
        assert ModelScoreNormalizer.normalize(3.0, "gpt-4o") == 3.0
        assert ModelScoreNormalizer.normalize(5.0, "gpt-4o") == 5.0

    def test_normalize_claude_expansion(self):
        from src.core.llm_judge import ModelScoreNormalizer
        # Claude: slope=1.1, intercept=0.2
        normalized = ModelScoreNormalizer.normalize(3.0, "claude")
        assert normalized == 3.5  # 3.0 * 1.1 + 0.2 = 3.5

    def test_normalize_qwen_shrink(self):
        from src.core.llm_judge import ModelScoreNormalizer
        # Qwen: slope=1.0, intercept=-0.1
        normalized = ModelScoreNormalizer.normalize(3.0, "qwen")
        assert normalized == 2.9  # 3.0 * 1.0 - 0.1 = 2.9

    def test_normalize_clamped_to_range(self):
        from src.core.llm_judge import ModelScoreNormalizer
        assert ModelScoreNormalizer.normalize(5.0, "claude") == 5.0  # would be 5.7, clamped
        assert ModelScoreNormalizer.normalize(1.0, "qwen") == 1.0  # would be 0.9, clamped

    def test_normalize_unknown_model_defaults(self):
        from src.core.llm_judge import ModelScoreNormalizer
        # Unknown model uses slope=1.0, intercept=0.0
        assert ModelScoreNormalizer.normalize(3.5, "unknown") == 3.5

    def test_normalize_scores_dict(self):
        from src.core.llm_judge import ModelScoreNormalizer
        scores = {"relevance": 4.0, "accuracy": 3.0}
        normalized = ModelScoreNormalizer.normalize_scores(scores, "gpt-4o")
        assert normalized["relevance"] == 4.0
        assert normalized["accuracy"] == 3.0

    def test_get_model_keys(self):
        from src.core.llm_judge import ModelScoreNormalizer
        keys = ModelScoreNormalizer.get_model_keys()
        assert set(keys) == {"gpt-4o", "claude", "qwen"}


class TestMultiModelJudge:
    """Test multi-model judge orchestration."""

    def test_multi_model_judge_init(self):
        from src.core.llm_judge import MultiModelJudge
        judge = MultiModelJudge()
        assert judge.model_fns == {}
        assert judge.rubric is not None

    def test_score_with_no_models(self):
        from src.core.llm_judge import MultiModelJudge
        judge = MultiModelJudge()
        result = judge.score_all("test input", "test output")
        assert "consensus" not in result

    def test_score_with_model_returns_none_for_missing(self):
        from src.core.llm_judge import MultiModelJudge
        judge = MultiModelJudge()
        result = judge.score_with_model("gpt-4o", "input", "output")
        assert result is None

    def test_score_with_unavailable_model(self):
        from src.core.llm_judge import MultiModelJudge
        judge = MultiModelJudge(model_fns={})
        result = judge.score_with_model("claude", "input", "output")
        assert result is None

    def test_score_with_mock_model(self):
        from src.core.llm_judge import MultiModelJudge, DEFAULT_RUBRIC

        mock_response = {
            "content": json.dumps({
                "scores": {"relevance": 4.0, "accuracy": 5.0, "completeness": 3.0, "actionability": 4.0},
                "reasoning": "Good response",
            })
        }

        def mock_model_fn(messages):
            return mock_response

        judge = MultiModelJudge(model_fns={"gpt-4o": mock_model_fn}, rubric=DEFAULT_RUBRIC)
        result = judge.score_with_model("gpt-4o", "Search Python repos", "Found FastAPI, Django...")
        assert result is not None
        assert result["model"] == "gpt-4o"
        assert "normalized_weighted" in result


# ============================================================
# 3. Evaluation Pipeline Tests
# ============================================================

class TestEvalPipeline:
    """Test automated evaluation pipeline."""

    def test_eval_result_dataclass(self):
        from src.core.eval_pipeline import EvalResult
        r = EvalResult(test_name="test", passed=True, score=0.95, details="OK")
        assert r.test_name == "test"
        assert r.passed is True
        assert r.score == 0.95

    def test_eval_report_to_dict(self):
        from src.core.eval_pipeline import EvalReport, EvalResult
        report = EvalReport(
            timestamp="2026-05-07T00:00:00",
            version="1.0.0",
            total_tests=10,
            passed=8,
            failed=2,
            golden_dataset_results=[
                EvalResult(test_name="test1", passed=True, score=0.9),
                EvalResult(test_name="test2", passed=False, details="error"),
            ],
            judge_scores={"mean": 4.2, "min": 3.5, "max": 5.0, "count": 10},
        )
        d = report.to_dict()
        assert d["summary"]["total_tests"] == 10
        assert d["summary"]["passed"] == 8
        assert d["summary"]["failed"] == 2
        assert d["summary"]["pass_rate"] == 0.8
        assert len(d["golden_dataset"]) == 2
        assert d["judge_scores"]["mean"] == 4.2

    def test_eval_report_pass_rate_zero_tests(self):
        from src.core.eval_pipeline import EvalReport
        report = EvalReport(total_tests=0)
        assert report.to_dict()["summary"]["pass_rate"] == 0

    def test_run_schema_validation(self):
        from src.core.eval_pipeline import run_schema_validation, EvalReport
        report = EvalReport()
        run_schema_validation(report)
        assert len(report.golden_dataset_results) == 10
        assert all(r.passed for r in report.golden_dataset_results)

    def test_run_field_coverage(self):
        from src.core.eval_pipeline import run_field_coverage, EvalReport
        report = EvalReport()
        run_field_coverage(report)
        assert len(report.golden_dataset_results) == 10
        passed = [r for r in report.golden_dataset_results if r.passed]
        assert len(passed) == 10
        for r in passed:
            assert r.score is not None
            assert 0.0 <= r.score <= 1.0

    def test_run_llm_judge_batch(self):
        from src.core.eval_pipeline import run_llm_judge_batch, EvalReport
        report = EvalReport()
        run_llm_judge_batch(report)
        assert "mean" in report.judge_scores
        assert "min" in report.judge_scores
        assert "max" in report.judge_scores
        assert report.judge_scores["count"] == 10

    def test_run_kpi_aggregation(self):
        from src.core.eval_pipeline import run_kpi_aggregation, EvalReport
        report = EvalReport()
        run_kpi_aggregation(report)
        assert "researcher" in report.kpi_summary
        assert "analyst" in report.kpi_summary
        assert "pipeline" in report.kpi_summary

    def test_run_eval_pipeline_full(self):
        from src.core.eval_pipeline import run_eval_pipeline
        report = run_eval_pipeline(mock=True)
        assert report.total_tests == 20
        assert report.passed == 20
        assert report.failed == 0
        assert report.judge_scores  # not empty
        assert report.kpi_summary  # not empty

    def test_run_eval_pipeline_golden_only(self):
        from src.core.eval_pipeline import run_eval_pipeline
        report = run_eval_pipeline(golden_only=True)
        assert report.total_tests == 20
        assert report.passed == 20
        assert not report.judge_scores  # empty in golden-only mode
        assert not report.kpi_summary  # empty in golden-only mode

    def test_eval_pipeline_json_output(self, tmp_path):
        from src.core.eval_pipeline import run_eval_pipeline
        report = run_eval_pipeline()
        output_file = str(tmp_path / "report.json")
        with open(output_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        with open(output_file, "r") as f:
            loaded = json.load(f)
        assert loaded["summary"]["total_tests"] == 20
        assert loaded["version"] == "1.0.0"


# ============================================================
# 4. Integration: Golden Dataset + Judge + Pipeline
# ============================================================

class TestPhase4Integration:
    """Integration tests for Phase 4 P2/P3 improvements."""

    def test_dataset_judge_pipeline_flow(self):
        """Golden dataset → judge scoring → pipeline report."""
        from src.core.golden_dataset import load_golden_dataset
        from src.core.llm_judge import RuleBasedScorer

        dataset = load_golden_dataset()
        assert len(dataset.repos) >= 10

        for repo in dataset.repos:
            output = f"# {repo.full_name}\n{repo.description}\nLanguage: {repo.language}"
            scores = RuleBasedScorer.score_total(
                output,
                keywords=[repo.language.lower()],
                required_sections=["core function"],
                expected_fields=[repo.language],
            )
            assert all(1.0 <= v <= 5.0 for v in scores.values())

    def test_full_pipeline_output_serializable(self):
        """Pipeline report should be fully JSON-serializable."""
        from src.core.eval_pipeline import run_eval_pipeline
        report = run_eval_pipeline()
        d = report.to_dict()
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        assert deserialized["summary"]["total_tests"] == 20

    def test_all_languages_covered(self):
        """Golden dataset should cover multiple languages."""
        from src.core.golden_dataset import load_golden_dataset
        dataset = load_golden_dataset()
        languages = set(r.language for r in dataset.repos)
        assert len(languages) >= 5
        assert "Python" in languages
        assert "JavaScript" in languages

    def test_edge_cases_in_dataset(self):
        """Golden dataset should include edge cases."""
        from src.core.golden_dataset import load_golden_dataset
        dataset = load_golden_dataset()
        edge_repos = dataset.get_by_category("edge")
        assert len(edge_repos) >= 4
        edge_ids = [r.id for r in edge_repos]
        assert "edge_zero_star" in edge_ids
        assert "edge_archived_go" in edge_ids


# ============================================================
# 5. End-to-End LLM Judge Mock Tests
# ============================================================

class TestLLMJudgeEndToEnd:
    """End-to-end tests mocking LLM judge calls."""

    def test_llm_judge_metric_normal_flow(self):
        """Full flow: input → mock LLM → JSON parse → weighted score."""
        from src.core.llm_judge import LLMJudgeMetric, DEFAULT_RUBRIC

        def mock_model_fn(messages):
            return {
                "content": json.dumps({
                    "scores": {
                        "relevance": 4.5,
                        "accuracy": 4.0,
                        "completeness": 3.5,
                        "actionability": 4.0,
                    },
                    "reasoning": "Good overall quality",
                })
            }

        metric = LLMJudgeMetric(model_fn=mock_model_fn, rubric=DEFAULT_RUBRIC)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(
            success=True, output="Found FastAPI, Django, Flask for Python web frameworks.",
            trajectory=[], meta={"task_id": "e2e_test"},
        )

        async def run():
            return await metric(solution, task_input="Search Python web frameworks")

        result = asyncio.get_event_loop().run_until_complete(run())
        assert 3.0 <= result.result <= 5.0
        assert "dimensions" in result.message
        assert "reasoning" in result.message

    def test_llm_judge_metric_markdown_wrapped_json(self):
        """Handle JSON wrapped in markdown code blocks."""
        from src.core.llm_judge import LLMJudgeMetric, DEFAULT_RUBRIC

        def mock_model_fn(messages):
            return {
                "content": "```json\n" + json.dumps({
                    "scores": {"relevance": 5.0, "accuracy": 5.0, "completeness": 5.0, "actionability": 5.0},
                    "reasoning": "Perfect",
                }) + "\n```"
            }

        metric = LLMJudgeMetric(model_fn=mock_model_fn, rubric=DEFAULT_RUBRIC)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(success=True, output="Perfect response", trajectory=[], meta={})

        async def run():
            return await metric(solution, task_input="test")

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.result == 5.0

    def test_llm_judge_metric_invalid_json_fallback(self):
        """Fallback to 3.0 when LLM returns invalid JSON."""
        from src.core.llm_judge import LLMJudgeMetric, DEFAULT_RUBRIC

        def mock_model_fn(messages):
            return {"content": "This is not valid JSON at all"}

        metric = LLMJudgeMetric(model_fn=mock_model_fn, rubric=DEFAULT_RUBRIC)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(success=True, output="test", trajectory=[], meta={})

        async def run():
            return await metric(solution, task_input="test")

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result.result == 3.0
        assert "error" in result.message

    def test_llm_judge_metric_missing_dimensions(self):
        """Default to 3.0 for missing dimensions."""
        from src.core.llm_judge import LLMJudgeMetric, DEFAULT_RUBRIC

        def mock_model_fn(messages):
            return {
                "content": json.dumps({
                    "scores": {"relevance": 5.0},  # Only relevance provided
                    "reasoning": "Partial response",
                })
            }

        metric = LLMJudgeMetric(model_fn=mock_model_fn, rubric=DEFAULT_RUBRIC)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(success=True, output="test", trajectory=[], meta={})

        async def run():
            return await metric(solution, task_input="test")

        result = asyncio.get_event_loop().run_until_complete(run())
        # Relevance=5.0, others default to 3.0 → weighted average
        assert 3.0 < result.result < 5.0

    def test_llm_judge_metric_score_clamping(self):
        """Clamp out-of-range scores to 1.0-5.0."""
        from src.core.llm_judge import LLMJudgeMetric, DEFAULT_RUBRIC

        def mock_model_fn(messages):
            return {
                "content": json.dumps({
                    "scores": {
                        "relevance": 6.0,   # Above max → clamp to 5.0
                        "accuracy": -1.0,   # Below min → clamp to 1.0
                        "completeness": 3.0,
                        "actionability": 4.0,
                    },
                    "reasoning": "Out of range scores",
                })
            }

        metric = LLMJudgeMetric(model_fn=mock_model_fn, rubric=DEFAULT_RUBRIC)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(success=True, output="test", trajectory=[], meta={})

        async def run():
            return await metric(solution, task_input="test")

        result = asyncio.get_event_loop().run_until_complete(run())
        # Clamped: relevance=5.0, accuracy=1.0, completeness=3.0, actionability=4.0
        assert 1.0 <= result.result <= 5.0

    def test_multi_model_consensus_scoring(self):
        """Multi-model judge produces consensus score."""
        from src.core.llm_judge import MultiModelJudge, DEFAULT_RUBRIC
        import json

        def make_mock(base):
            def mock_fn(messages):
                return {
                    "content": json.dumps({
                        "scores": {
                            "relevance": round(base, 1),
                            "accuracy": round(base - 0.3, 1),
                            "completeness": round(base + 0.2, 1),
                            "actionability": round(base - 0.1, 1),
                        },
                        "reasoning": f"Mock score base={base}",
                    })
                }
            return mock_fn

        judge = MultiModelJudge(model_fns={
            "gpt-4o": make_mock(4.0),
            "claude": make_mock(3.5),
            "qwen": make_mock(4.2),
        }, rubric=DEFAULT_RUBRIC)

        result = judge.score_all("Search repos", "Found React, Vue, Angular")
        assert "consensus" in result
        assert "normalized_weighted" in result["consensus"]
        assert "model_count" in result["consensus"]
        assert result["consensus"]["model_count"] == 3

    def test_multi_model_model_specific_scores(self):
        """Each model produces its own score in multi-model judge."""
        from src.core.llm_judge import MultiModelJudge, DEFAULT_RUBRIC
        import json

        def make_mock(score):
            def mock_fn(messages):
                return {
                    "content": json.dumps({
                        "scores": {
                            "relevance": score, "accuracy": score,
                            "completeness": score, "actionability": score,
                        },
                        "reasoning": "uniform",
                    })
                }
            return mock_fn

        judge = MultiModelJudge(model_fns={
            "gpt-4o": make_mock(4.5),
            "claude": make_mock(3.0),
        }, rubric=DEFAULT_RUBRIC)

        result = judge.score_all("input", "output")
        assert "gpt-4o" in result
        assert "claude" in result
        assert "consensus" in result


# ============================================================
# 6. Golden Dataset Dynamic Update Tests
# ============================================================

class TestGoldenDatasetDynamicUpdate:
    """Test golden dataset add/update/remove/save/merge."""

    @pytest.fixture
    def dataset(self):
        from src.core.golden_dataset import load_golden_dataset, GoldenRepo
        return load_golden_dataset(), GoldenRepo

    def test_add_repo(self, dataset):
        ds, GoldenRepo = dataset
        initial_count = len(ds.repos)
        new_repo = GoldenRepo(
            id="dynamic_test_repo", category="edge", full_name="test/dynamic",
            html_url="https://github.com/test/dynamic", stargazers_count=500,
            forks_count=50, watchers_count=20, open_issues_count=5,
            language="Kotlin", description="Dynamic test repo", topics=["kotlin"],
            updated_at="2026-05-01T00:00:00Z", owner_login="test",
            is_fork=False, is_archived=False, readme="# Dynamic"
        )
        ds.add_repo(new_repo)
        assert len(ds.repos) == initial_count + 1
        assert ds.get_by_id("dynamic_test_repo") is not None

    def test_add_repo_replaces_existing(self, dataset):
        ds, GoldenRepo = dataset
        initial_count = len(ds.repos)
        updated = GoldenRepo(
            id="standard_large_python", category="standard",
            full_name="langchain-ai/langchain-updated",
            html_url="https://github.com/langchain-ai/langchain",
            stargazers_count=100000, forks_count=16000, watchers_count=3100,
            open_issues_count=510, language="Python",
            description="Updated description", topics=["python"],
            updated_at="2026-05-01T00:00:00Z", owner_login="langchain-ai",
            is_fork=False, is_archived=False, readme=None
        )
        ds.add_repo(updated)
        # Should replace, not add
        assert len(ds.repos) == initial_count
        assert ds.get_by_id("standard_large_python").full_name == "langchain-ai/langchain-updated"

    def test_update_repo(self, dataset):
        ds, _ = dataset
        result = ds.update_repo("edge_zero_star", stargazers_count=100)
        assert result is True
        repo = ds.get_by_id("edge_zero_star")
        assert repo.stargazers_count == 100

    def test_update_repo_nonexistent(self, dataset):
        ds, _ = dataset
        result = ds.update_repo("nonexistent_id", stargazers_count=999)
        assert result is False

    def test_update_repo_multiple_fields(self, dataset):
        ds, _ = dataset
        ds.update_repo("edge_zero_star", stargazers_count=50, description="Updated desc")
        repo = ds.get_by_id("edge_zero_star")
        assert repo.stargazers_count == 50
        assert repo.description == "Updated desc"

    def test_remove_repo(self, dataset):
        ds, GoldenRepo = dataset
        ds.add_repo(GoldenRepo(
            id="to_remove", category="edge", full_name="test/remove",
            html_url="https://github.com/test/remove", stargazers_count=1,
            forks_count=0, watchers_count=0, open_issues_count=0,
            language="Python", description="Remove me", topics=[],
            updated_at="2026-05-01T00:00:00Z", owner_login="test",
            is_fork=False, is_archived=False, readme=None
        ))
        assert ds.get_by_id("to_remove") is not None
        result = ds.remove_repo("to_remove")
        assert result is True
        assert ds.get_by_id("to_remove") is None

    def test_remove_repo_nonexistent(self, dataset):
        ds, _ = dataset
        result = ds.remove_repo("does_not_exist")
        assert result is False

    def test_save_and_reload(self, dataset, tmp_path):
        ds, GoldenRepo = dataset
        ds.add_repo(GoldenRepo(
            id="save_test", category="standard", full_name="save/test",
            html_url="https://github.com/save/test", stargazers_count=10,
            forks_count=1, watchers_count=0, open_issues_count=0,
            language="Python", description="Save test", topics=[],
            updated_at="2026-05-01T00:00:00Z", owner_login="save",
            is_fork=False, is_archived=False, readme=None
        ))
        output_path = str(tmp_path / "test_dataset.json")
        ds.save_to_file(output_path)

        from src.core.golden_dataset import load_golden_dataset
        reloaded = load_golden_dataset(output_path)
        assert reloaded.get_by_id("save_test") is not None
        assert len(reloaded.repos) == len(ds.repos)

    def test_merge_dataset(self, dataset):
        ds1, GoldenRepo = dataset
        from src.core.golden_dataset import load_golden_dataset
        ds2 = load_golden_dataset()

        # Add unique repo to ds1
        ds1.add_repo(GoldenRepo(
            id="unique_ds1", category="edge", full_name="unique/ds1",
            html_url="https://github.com/unique/ds1", stargazers_count=1,
            forks_count=0, watchers_count=0, open_issues_count=0,
            language="Scala", description="Unique to ds1", topics=[],
            updated_at="2026-05-01T00:00:00Z", owner_login="unique",
            is_fork=False, is_archived=False, readme=None
        ))

        merged = ds2.merge_dataset(ds1)
        assert ds2.get_by_id("unique_ds1") is not None
        assert merged > 0  # At least the unique repo was added

    def test_merge_no_overwrite(self, dataset):
        ds, GoldenRepo = dataset
        from src.core.golden_dataset import load_golden_dataset
        other_ds = load_golden_dataset()

        # Update a repo in ds to have different data
        ds.update_repo("standard_large_python", stargazers_count=999999)

        # Merge with overwrite=False: original data should be preserved
        other_ds.merge_dataset(ds, overwrite=False)
        # Original should keep its value (90000)
        assert other_ds.get_by_id("standard_large_python").stargazers_count == 90000
