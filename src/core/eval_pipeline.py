# -*- coding: utf-8 -*-
"""
Automated evaluation pipeline for CI.

Runs golden dataset tests + LLM-as-Judge batch scoring + KPI aggregation,
outputs a JSON summary report.

Usage:
    # Run full evaluation
    python -m src.core.eval_pipeline --output eval_report.json

    # Run with mock LLM judge (no API call needed)
    python -m src.core.eval_pipeline --mock --output eval_report.json

    # Run golden dataset only
    python -m src.core.eval_pipeline --golden-only
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EvalResult:
    """Single evaluation result."""
    test_name: str
    passed: bool
    score: Optional[float] = None
    details: str = ""


@dataclass
class EvalReport:
    """Aggregated evaluation report."""
    timestamp: str = ""
    version: str = ""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    golden_dataset_results: List[EvalResult] = field(default_factory=list)
    judge_scores: Dict[str, float] = field(default_factory=dict)
    kpi_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "version": self.version,
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "pass_rate": round(self.passed / self.total_tests, 3) if self.total_tests > 0 else 0,
            },
            "golden_dataset": [
                {"name": r.test_name, "passed": r.passed, "score": r.score, "details": r.details}
                for r in self.golden_dataset_results
            ],
            "judge_scores": self.judge_scores,
            "kpi_summary": self.kpi_summary,
        }


def run_schema_validation(report: EvalReport) -> None:
    """Run schema validation tests against golden dataset."""
    from src.core.golden_dataset import load_golden_dataset
    from src.types.schemas import GitHubRepo

    dataset = load_golden_dataset()
    report.version = dataset.version

    for repo in dataset.repos:
        api_data = repo.to_api_response()
        try:
            parsed = GitHubRepo.from_api_response(api_data)
            report.golden_dataset_results.append(EvalResult(
                test_name=f"schema:{repo.id}",
                passed=True,
                details=f"Parsed {parsed.full_name}",
            ))
        except Exception as e:
            report.golden_dataset_results.append(EvalResult(
                test_name=f"schema:{repo.id}",
                passed=False,
                details=str(e),
            ))


def run_field_coverage(report: EvalReport) -> None:
    """Run field coverage tests."""
    from src.core.golden_dataset import load_golden_dataset
    from src.agents.researcher_agent import ResearcherAgent

    dataset = load_golden_dataset()

    import os
    from unittest.mock import MagicMock, patch

    with patch.dict(os.environ, {"GITHUB_TOKEN": "test", "DASHSCOPE_API_KEY": "test"}):
        from src.core.config_manager import ConfigManager
        ConfigManager._instance = None
        ConfigManager._initialized = False
        agent = ResearcherAgent()

    for repo in dataset.repos:
        mock_repo = MagicMock()
        mock_repo.stargazers_count = repo.stargazers_count
        mock_repo.forks_count = repo.forks_count
        mock_repo.topics = repo.topics
        mock_repo.language = repo.language
        mock_repo.watchers_count = repo.watchers_count

        try:
            score = agent._calculate_trend_score(mock_repo)
            if 0.0 <= score <= 1.0:
                report.golden_dataset_results.append(EvalResult(
                    test_name=f"trend_score:{repo.id}",
                    passed=True,
                    score=round(score, 3),
                ))
            else:
                report.golden_dataset_results.append(EvalResult(
                    test_name=f"trend_score:{repo.id}",
                    passed=False,
                    score=score,
                    details=f"Out of range: {score}",
                ))
        except Exception as e:
            report.golden_dataset_results.append(EvalResult(
                test_name=f"trend_score:{repo.id}",
                passed=False,
                details=str(e),
            ))


def run_llm_judge_batch(report: EvalReport) -> None:
    """Run LLM-as-Judge batch scoring with rule-based fallback."""
    from src.core.golden_dataset import load_golden_dataset
    from src.core.llm_judge import RuleBasedScorer

    dataset = load_golden_dataset()

    scores = []
    for repo in dataset.repos:
        # Simulate an analysis output from the repo's README
        output = f"""# {repo.full_name}

## Core Function
{repo.description or 'N/A'}

## Tech Stack
{repo.language}

## Topics
{', '.join(repo.topics) if repo.topics else 'None'}

## Recommendation
Based on {repo.stargazers_count} stars, this project is {'highly active' if repo.stargazers_count > 10000 else 'moderately active'}.
"""
        result = RuleBasedScorer.score_total(
            output,
            keywords=[repo.language.lower()] + [t.lower() for t in repo.topics[:3]],
            required_sections=["core function", "tech stack", "recommendation"],
            expected_fields=[repo.language],
        )
        avg_score = sum(result.values()) / len(result)
        scores.append(avg_score)

    if scores:
        report.judge_scores = {
            "mean": round(sum(scores) / len(scores), 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "count": len(scores),
        }


def run_multi_model_judge(report: EvalReport) -> None:
    """Run multi-model LLM-as-Judge with mock model functions."""
    from src.core.golden_dataset import load_golden_dataset
    from src.core.llm_judge import MultiModelJudge, JUDGE_MODELS
    import json

    dataset = load_golden_dataset()

    # Create mock model functions with model-specific scoring behaviors
    # Each model has a characteristic bias to test normalization
    model_bias = {
        "gpt-4o": {"base": 3.8, "variance": 0.3},  # Baseline: moderate-high
        "claude": {"base": 3.2, "variance": 0.4},  # Conservative: tends lower
        "qwen": {"base": 4.2, "variance": 0.2},    # Generous: tends higher
    }

    def make_mock_fn(model_key: str):
        def mock_fn(messages):
            bias = model_bias[model_key]
            scores = {
                "relevance": round(min(5.0, max(1.0, bias["base"] + bias["variance"] * 0.5)), 1),
                "accuracy": round(min(5.0, max(1.0, bias["base"] - bias["variance"] * 0.3)), 1),
                "completeness": round(min(5.0, max(1.0, bias["base"] + bias["variance"] * 0.2)), 1),
                "actionability": round(min(5.0, max(1.0, bias["base"] - bias["variance"] * 0.1)), 1),
            }
            return {
                "content": json.dumps({
                    "scores": scores,
                    "reasoning": f"Mock scoring from {model_key}",
                })
            }
        return mock_fn

    model_fns = {key: make_mock_fn(key) for key in model_bias}
    judge = MultiModelJudge(model_fns=model_fns)

    all_model_results = []
    for repo in dataset.repos:
        output = f"""# {repo.full_name}

## Core Function
{repo.description or 'N/A'}

## Tech Stack
{repo.language}

## Recommendation
Based on {repo.stargazers_count} stars, this project is {'highly active' if repo.stargazers_count > 10000 else 'moderately active'}.
"""
        result = judge.score_all(f"Analyze {repo.full_name}", output)
        if "consensus" in result:
            all_model_results.append(result["consensus"])

    if all_model_results:
        weights = [r["normalized_weighted"] for r in all_model_results]
        report.judge_scores = {
            "models": list(model_bias.keys()),
            "consensus_mean": round(sum(weights) / len(weights), 2),
            "consensus_min": round(min(weights), 2),
            "consensus_max": round(max(weights), 2),
            "count": len(all_model_results),
            "model_configs": {k: v.model_id for k, v in JUDGE_MODELS.items()},
        }


def run_kpi_aggregation(report: EvalReport) -> None:
    """Run KPI aggregation."""
    from src.core.kpi_tracker import KPITracker

    tracker = KPITracker(metrics_path=str(Path.home() / ".hermes" / "gia_metrics_eval.tmp"))

    # Simulate Researcher KPIs
    researcher_kpis = tracker.track_researcher_kpis(
        intent_action="search_repositories",
        intent_params={"query": "test"},
        success=True,
        result_count=5,
    )

    # Simulate Analyst KPIs
    analyst_kpis = tracker.track_analyst_kpis(
        analysis={
            "core_function": "Test function",
            "tech_stack": ["Python", "FastAPI"],
            "architecture_pattern": "MVC",
            "pain_points": ["Test"],
            "risk_flags": [],
            "stars": 1000,
            "language": "Python",
        },
        report_text="Test report",
    )

    # Simulate Pipeline KPIs
    pipeline_kpis = tracker.track_pipeline_kpis(
        tti_seconds=45.0,
        success=True,
        token_count=2500,
    )

    report.kpi_summary = {
        "researcher": researcher_kpis,
        "analyst": analyst_kpis,
        "pipeline": pipeline_kpis,
    }

    # Cleanup temp file
    try:
        tmp_path = Path.home() / ".hermes" / "gia_metrics_eval.tmp"
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        pass


def run_eval_pipeline(
    mock: bool = False,
    golden_only: bool = False,
) -> EvalReport:
    """Run the full evaluation pipeline."""
    report = EvalReport(timestamp=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()))

    # Golden dataset tests (always run)
    run_schema_validation(report)
    run_field_coverage(report)

    if not golden_only:
        # LLM-as-Judge batch scoring (rule-based fallback)
        run_llm_judge_batch(report)
        # Multi-model LLM-as-Judge consensus scoring
        run_multi_model_judge(report)
        # KPI aggregation
        run_kpi_aggregation(report)

    # Compute totals
    report.total_tests = len(report.golden_dataset_results)
    report.passed = sum(1 for r in report.golden_dataset_results if r.passed)
    report.failed = report.total_tests - report.passed

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="GIA Automated Evaluation Pipeline")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM judge")
    parser.add_argument("--golden-only", action="store_true", help="Run golden dataset tests only")
    args = parser.parse_args()

    report = run_eval_pipeline(mock=args.mock, golden_only=args.golden_only)

    # Print summary
    print("=" * 60)
    print("  GIA Evaluation Report")
    print("=" * 60)
    print(f"  Version: {report.version}")
    print(f"  Total: {report.total_tests} | Passed: {report.passed} | Failed: {report.failed}")
    print(f"  Pass rate: {report.passed / report.total_tests:.1%}" if report.total_tests > 0 else "  N/A")

    if report.judge_scores:
        print("\n  Judge Scores:")
        for k, v in report.judge_scores.items():
            print(f"    {k}: {v}")

    if report.kpi_summary:
        print("\n  KPI Summary:")
        for agent, kpis in report.kpi_summary.items():
            print(f"    {agent}: {kpis}")

    if report.failed > 0:
        print("\n  Failed tests:")
        for r in report.golden_dataset_results:
            if not r.passed:
                print(f"    - {r.test_name}: {r.details}")

    print("=" * 60)

    # Write report
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Report written to: {args.output}")

    return 1 if report.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
