# -*- coding: utf-8 -*-
"""Tests for Pydantic agent data contracts."""

import pytest
from pydantic import ValidationError

from src.core.contracts import ProjectFact, ProjectAnalysisReport


class TestProjectFact:
    """Tests for ProjectFact contract (ResearcherAgent output)."""

    def test_valid_minimal(self):
        fact = ProjectFact(owner="langchain-ai", repo="langchain", stars=90000)
        assert fact.owner == "langchain-ai"
        assert fact.repo == "langchain"
        assert fact.stars == 90000
        assert fact.lang == ""
        assert fact.tags == []

    def test_valid_full(self):
        fact = ProjectFact(
            owner="django",
            repo="django",
            stars=75000,
            lang="Python",
            readme_snippet="The Web framework for perfectionists...",
            trend_score=0.85,
            last_commit_days=1,
            tags=["python", "web", "framework"],
        )
        assert fact.full_name == "django/django"
        assert fact.lang == "Python"
        assert fact.trend_score == 0.85
        assert fact.last_commit_days == 1
        assert len(fact.tags) == 3

    def test_trend_score_clamping(self):
        # Above 1.0 → clamped to 1.0
        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=1.5)
        assert fact.trend_score == 1.0

        # Below 0.0 → clamped to 0.0
        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=-0.5)
        assert fact.trend_score == 0.0

    def test_trend_score_none_allowed(self):
        fact = ProjectFact(owner="test", repo="test", stars=100, trend_score=None)
        assert fact.trend_score is None

    def test_lang_default_empty_string(self):
        fact = ProjectFact(owner="test", repo="test", stars=100, lang=None)
        assert fact.lang == ""

    def test_stars_ge_zero(self):
        with pytest.raises(ValidationError):
            ProjectFact(owner="test", repo="test", stars=-1)

    def test_extra_fields_ignored(self):
        fact = ProjectFact(
            owner="test", repo="test", stars=100,
            lang="Python", extra_field="should_be_ignored",
        )
        assert fact.owner == "test"
        assert not hasattr(fact, "extra_field")

    def test_full_name_property(self):
        fact = ProjectFact(owner="microsoft", repo="vscode", stars=100)
        assert fact.full_name == "microsoft/vscode"

    def test_model_validate_from_dict(self):
        data = {
            "owner": "facebook",
            "repo": "react",
            "stars": 220000,
            "lang": "JavaScript",
            "tags": ["javascript", "ui", "frontend"],
        }
        fact = ProjectFact.model_validate(data)
        assert fact.lang == "JavaScript"


class TestProjectAnalysisReport:
    """Tests for ProjectAnalysisReport contract (AnalystAgent output)."""

    def test_valid_minimal(self):
        report = ProjectAnalysisReport(
            core_function="Full-featured web framework",
        )
        assert report.core_function == "Full-featured web framework"
        assert report.tech_stack == []
        assert report.suitability_score == 0.5

    def test_valid_full(self):
        report = ProjectAnalysisReport(
            core_function="Async web framework",
            tech_stack=["Python", "FastAPI", "SQLAlchemy"],
            architecture_pattern="Microservices",
            pain_points=["High memory usage", "Complex config"],
            suitability="Good for async services",
            risk_flags=["Low maintainer count"],
            score_breakdown={"performance": 0.8, "docs": 0.9},
            suitability_score=0.85,
        )
        assert len(report.tech_stack) == 3
        assert report.score("performance") == 0.8
        assert report.suitability_score == 0.85

    def test_suitability_score_clamping(self):
        # Above 1.0 → clamped
        report = ProjectAnalysisReport(
            core_function="Test", suitability_score=1.5
        )
        assert report.suitability_score == 1.0

        # Below 0.0 → clamped
        report = ProjectAnalysisReport(
            core_function="Test", suitability_score=-0.5
        )
        assert report.suitability_score == 0.0

    def test_suitability_score_invalid_default(self):
        report = ProjectAnalysisReport(
            core_function="Test", suitability_score="not_a_number"
        )
        assert report.suitability_score == 0.5

    def test_score_helper(self):
        report = ProjectAnalysisReport(
            core_function="Test",
            score_breakdown={"security": 0.7, "performance": 0.9},
        )
        assert report.score("security") == 0.7
        assert report.score("nonexistent") == 0.0

    def test_extra_fields_ignored(self):
        report = ProjectAnalysisReport(
            core_function="Test", extra_field="ignored",
        )
        assert report.core_function == "Test"
        assert not hasattr(report, "extra_field")

    def test_model_validate_from_dict(self):
        data = {
            "core_function": "ORM library",
            "tech_stack": ["Python", "SQLAlchemy"],
            "architecture_pattern": "ActiveRecord",
            "pain_points": ["Complex migrations"],
            "suitability": "Data-heavy apps",
            "risk_flags": [],
            "score_breakdown": {"quality": 0.85},
            "suitability_score": 0.8,
        }
        report = ProjectAnalysisReport.model_validate(data)
        assert report.suitability_score == 0.8
