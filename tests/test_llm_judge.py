# -*- coding: utf-8 -*-
"""
LLM-as-Judge evaluation tests

Tests:
1. RuleBasedScorer — structural scoring without LLM
2. LLMJudgeMetric — LLM-powered scoring
3. Scoring dimensions and weighting
4. AgentScope MetricBase compatibility
5. Error handling and fallbacks
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# Module-level mock functions (not bound to test class)


def _good_scores_fn(messages=None):
    return {
        "content": json.dumps({
            "scores": {
                "relevance": 4.5,
                "accuracy": 3.5,
                "completeness": 4.0,
                "actionability": 5.0,
            },
            "reasoning": "Good relevance and actionability, accuracy could be improved."
        })
    }


def _bad_json_fn(messages=None):
    return {"content": "Not valid JSON at all"}


def _out_of_range_fn(messages=None):
    return {
        "content": json.dumps({
            "scores": {
                "relevance": 10.0,
                "accuracy": -5.0,
                "completeness": 4.0,
                "actionability": 3.0,
            },
            "reasoning": "Out of range scores"
        })
    }


def _run_async(coro):
    """Run an async coroutine in the current event loop."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        return loop.run_until_complete(coro)
    else:
        return loop.run_until_complete(coro)


# ============================================================
# 1. RuleBasedScorer
# ============================================================

class TestRuleBasedScorer:
    """Test rule-based scoring without LLM"""

    def test_relevance_full_match(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_relevance(
            "This project uses Python, FastAPI, and React",
            ["python", "fastapi", "react"],
        )
        assert score == 5.0

    def test_relevance_partial_match(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_relevance(
            "This project uses Python and Django",
            ["python", "fastapi", "react"],
        )
        assert 2.0 <= score <= 2.5

    def test_relevance_no_match(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_relevance(
            "This is a Rust project",
            ["python", "django"],
        )
        assert score == 1.0

    def test_relevance_empty_output(self):
        from src.core.llm_judge import RuleBasedScorer

        assert RuleBasedScorer.score_relevance("", ["python"]) == 1.0

    def test_relevance_empty_keywords(self):
        from src.core.llm_judge import RuleBasedScorer

        assert RuleBasedScorer.score_relevance("some output", []) == 1.0

    def test_completeness_all_sections(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_completeness(
            "# Core Function\n# Tech Stack\n# Pain Points\n",
            ["core function", "tech stack", "pain points"],
        )
        assert score == 5.0

    def test_completeness_partial(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_completeness(
            "# Core Function\n",
            ["core function", "tech stack", "pain points"],
        )
        assert 2.0 <= score <= 2.5

    def test_completeness_no_sections(self):
        from src.core.llm_judge import RuleBasedScorer

        # No required sections → default 3.0
        assert RuleBasedScorer.score_completeness("# Title\n", []) == 3.0

    def test_accuracy_full_match(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_accuracy(
            "stars: 50000 language: Python framework: FastAPI",
            ["stars", "language", "framework"],
        )
        assert score == 5.0

    def test_accuracy_no_match(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_accuracy("", ["stars"])
        assert score == 1.0

    def test_accuracy_empty_fields(self):
        from src.core.llm_judge import RuleBasedScorer

        # No expected fields → default 3.0
        assert RuleBasedScorer.score_accuracy("some output", []) == 3.0

    def test_actionability_high(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_actionability(
            "I recommend you should consider implementing this approach first"
        )
        assert score >= 4.0

    def test_actionability_low(self):
        from src.core.llm_judge import RuleBasedScorer

        score = RuleBasedScorer.score_actionability(
            "This is a simple description of the project"
        )
        assert score <= 1.0

    def test_score_total(self):
        from src.core.llm_judge import RuleBasedScorer

        output = "# Core Function\n# Tech Stack\nPython FastAPI stars: 50000"
        result = RuleBasedScorer.score_total(
            output,
            keywords=["python", "fastapi"],
            required_sections=["core function", "tech stack"],
            expected_fields=["stars"],
        )
        assert "relevance" in result
        assert "completeness" in result
        assert "accuracy" in result
        assert "actionability" in result
        assert all(1.0 <= v <= 5.0 for v in result.values())


# ============================================================
# 2. Scoring Dimensions
# ============================================================

class TestScoringDimensions:
    """Test dimension definitions"""

    def test_default_rubric(self):
        from src.core.llm_judge import DEFAULT_RUBRIC

        names = [d.name for d in DEFAULT_RUBRIC]
        assert "relevance" in names
        assert "accuracy" in names
        assert "completeness" in names
        assert "actionability" in names

    def test_dimension_attributes(self):
        from src.core.llm_judge import ScoringDimension

        dim = ScoringDimension(
            name="test",
            description="A test dimension",
            max_score=10.0,
            weight=2.0,
        )
        assert dim.name == "test"
        assert dim.max_score == 10.0
        assert dim.weight == 2.0


# ============================================================
# 3. LLMJudgeMetric — Weighted Score
# ============================================================

class TestWeightedScore:
    """Test weighted score calculation"""

    def test_weighted_score_calculation(self):
        from src.core.llm_judge import LLMJudgeMetric

        metric = LLMJudgeMetric()
        scores = {
            "relevance": 4.0,
            "accuracy": 5.0,
            "completeness": 3.0,
            "actionability": 4.0,
        }
        weighted = metric.compute_weighted_score(scores)
        # Weights: relevance=1.0, accuracy=1.5, completeness=1.0, actionability=1.0
        # = (4+7.5+3+4) / 4.5 = 18.5/4.5 ≈ 4.11
        assert 4.0 < weighted < 4.2

    def test_weighted_score_missing_dimensions(self):
        from src.core.llm_judge import LLMJudgeMetric

        metric = LLMJudgeMetric()
        scores = {"relevance": 5.0}
        weighted = metric.compute_weighted_score(scores)
        # Missing default to 3.0
        assert 3.0 < weighted < 4.0

    def test_weighted_score_all_equal(self):
        from src.core.llm_judge import LLMJudgeMetric

        metric = LLMJudgeMetric()
        scores = {
            "relevance": 4.0,
            "accuracy": 4.0,
            "completeness": 4.0,
            "actionability": 4.0,
        }
        assert metric.compute_weighted_score(scores) == 4.0


# ============================================================
# 4. AgentScope MetricBase Compatibility
# ============================================================

class TestMetricBaseCompatibility:
    """Test that LLMJudgeMetric implements MetricBase interface"""

    def test_metric_inherits_metric_base(self):
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate import MetricBase

        metric = LLMJudgeMetric()
        assert isinstance(metric, MetricBase)

    def test_metric_name_and_type(self):
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate import MetricType

        metric = LLMJudgeMetric()
        assert metric.name == "llm_judge"
        assert metric.metric_type == MetricType.NUMERICAL
        assert metric.description is not None

    def test_metric_no_model_returns_fallback(self):
        """Without model_fn, should return neutral score"""
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate._solution import SolutionOutput
        from agentscope.evaluate import MetricResult

        metric = LLMJudgeMetric()
        solution = SolutionOutput(success=True, output="Test output", trajectory=[])

        import asyncio

        async def run():
            return await metric(solution, task_input="Test input")
        result = asyncio.get_event_loop().run_until_complete(run())
        assert isinstance(result, MetricResult)
        assert result.result == 3.0
        detail = json.loads(result.message)
        assert "Skipped" in detail.get("reasoning", "")


# ============================================================
# 5. Mock LLM Scoring
# ============================================================

class TestMockLLMScore:
    """Test LLM scoring with mock model function"""

    @pytest.fixture
    def event_loop(self):
        import asyncio
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    def test_llm_scoring_good_scores(self, event_loop):
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate._solution import SolutionOutput

        metric = LLMJudgeMetric(model_fn=_good_scores_fn)
        solution = SolutionOutput(
            success=True,
            output="Detailed project analysis with scores and recommendations.",
            trajectory=[],
        )

        async def run():
            return await metric(solution, task_input="Analyze this project")

        result = event_loop.run_until_complete(run())
        assert result.result > 3.0
        detail = json.loads(result.message)
        dims = detail["dimensions"]
        assert dims["relevance"] == 4.5
        assert dims["accuracy"] == 3.5

    def test_llm_scoring_clamps_scores(self, event_loop):
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate._solution import SolutionOutput

        metric = LLMJudgeMetric(model_fn=_out_of_range_fn)
        solution = SolutionOutput(success=True, output="test", trajectory=[])

        async def run():
            return await metric(solution, task_input="test")

        result = event_loop.run_until_complete(run())
        detail = json.loads(result.message)
        dims = detail["dimensions"]
        assert dims["relevance"] == 5.0  # Clamped from 10.0
        assert dims["accuracy"] == 1.0   # Clamped from -5.0

    def test_llm_scoring_invalid_json_fallback(self, event_loop):
        from src.core.llm_judge import LLMJudgeMetric
        from agentscope.evaluate._solution import SolutionOutput

        metric = LLMJudgeMetric(model_fn=_bad_json_fn)
        solution = SolutionOutput(success=True, output="test", trajectory=[])

        async def run():
            return await metric(solution, task_input="test")

        result = event_loop.run_until_complete(run())
        assert result.result == 3.0
        detail = json.loads(result.message)
        assert "error" in detail


# ============================================================
# 6. JudgeTask Convenience
# ============================================================

class TestJudgeTask:
    """Test JudgeTask convenience wrapper"""

    def test_judge_task_creation(self):
        from src.core.llm_judge import create_judge_task

        task = create_judge_task(
            task_id="test_1",
            user_input="Search Python frameworks",
            assistant_output="Found FastAPI, Django, Flask...",
        )
        assert task.id == "test_1"
        assert task.input_text == "Search Python frameworks"
        assert task.output_text == "Found FastAPI, Django, Flask..."

    def test_judge_task_score_sync_no_model(self):
        from src.core.llm_judge import create_judge_task

        task = create_judge_task(
            task_id="test_2",
            user_input="Test",
            assistant_output="Test output",
        )
        # No model_fn → fallback
        result = task.score_sync()
        assert result.result == 3.0


# ============================================================
# 7. Integration: Score Actual Outputs
# ============================================================

class TestOutputScoringIntegration:
    """Test scoring realistic output formats"""

    def test_score_search_results(self):
        """Score a typical search result output"""
        from src.core.llm_judge import RuleBasedScorer

        output = (
            "## Search Results: Python web framework\n"
            "| # | Project | Stars | Language |\n"
            "|---|---------|-------|----------|\n"
            "| 1 | **django** | 75000 | Python |\n"
            "| 2 | **fastapi** | 78000 | Python |\n"
            "| 3 | **flask** | 66000 | Python |\n"
            "Recommendation: Use FastAPI for new projects; Django for full-stack."
        )

        result = RuleBasedScorer.score_total(
            output,
            keywords=["django", "fastapi", "flask", "python"],
            required_sections=["search results"],
            expected_fields=["Stars"],
        )
        assert result["relevance"] >= 4.0
        assert result["completeness"] >= 4.0
        assert result["accuracy"] >= 4.0
        # "Recommend" triggers actionability
        assert result["actionability"] >= 2.0

    def test_score_analysis_report(self):
        """Score a typical analysis report"""
        from src.core.llm_judge import RuleBasedScorer

        output = (
            "# Project Analysis: langchain-ai/langchain\n\n"
            "## Core Function\n"
            "LLM application framework\n\n"
            "## Tech Stack\n"
            "Python, LangChain, Pydantic\n\n"
            "## Pain Points Solved\n"
            "- Unified LLM interface\n"
            "- Chain abstraction\n\n"
            "## Recommendation\n"
            "Suitable for LLM apps. Should be the first choice."
        )

        result = RuleBasedScorer.score_total(
            output,
            keywords=["langchain", "python", "llm"],
            required_sections=["core function", "tech stack", "recommendation"],
            expected_fields=["langchain-ai/langchain"],
        )
        assert result["completeness"] >= 4.0
        assert result["accuracy"] >= 4.0
        assert result["actionability"] >= 3.0

    def test_score_empty_output(self):
        """Score empty output — should give minimum scores where keywords matter"""
        from src.core.llm_judge import RuleBasedScorer

        result = RuleBasedScorer.score_total(
            "",
            keywords=["python"],
            required_sections=["core"],
            expected_fields=["stars"],
        )
        # relevance, accuracy: empty output → 1.0
        assert result["relevance"] == 1.0
        assert result["accuracy"] == 1.0
        # actionability: empty → 1.0
        assert result["actionability"] == 1.0
        # completeness: no required sections match → 1.0
        assert result["completeness"] == 1.0


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
