# -*- coding: utf-8 -*-
"""
Lightweight golden dataset — structural evaluation with mock fixtures

Since GitHub data is dynamic (star counts change), we test:
1. Schema correctness (all required fields present and valid)
2. Field coverage (trend_score range, last_commit_days, tags)
3. Analyst output structure (architecture_pattern, risk_flags, score_breakdown)
4. End-to-end pipeline with mocked GitHub API
5. Report generation quality (structure, completeness)

Uses mocked API responses as the "golden" input, validates output contracts.
"""

import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ============================================================
# Golden Dataset: Mock GitHub API Responses
# ============================================================

GOLDEN_REPOS = [
    {
        "full_name": "langchain-ai/langchain",
        "html_url": "https://github.com/langchain-ai/langchain",
        "stargazers_count": 90000,
        "forks_count": 15000,
        "watchers_count": 3000,
        "open_issues_count": 500,
        "language": "Python",
        "description": "Building applications with LLMs through composability",
        "topics": ["python", "llm", "ai", "langchain", "framework"],
        "updated_at": "2026-04-29T00:00:00Z",
        "owner": {"login": "langchain-ai"},
        "fork": False,
        "archived": False,
        "readme": """# LangChain

⚣ Building applications with LLMs through composability ⚣

## Features
- **Prompt Management**: Templates, formatting, and versioning
- **Chains**: Composable sequences of processing steps
- **Agents**: LLMs that can take actions
- **Memory**: State persistence across conversations

## Installation
```bash
pip install langchain
```

## Quick Start
```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
```

## Architecture
LangChain uses a modular architecture with:
- Components: Core building blocks
- Integrations: Connectors to external services
- Chains: Workflow definitions
- Agents: Autonomous decision-making

## Security
- No hardcoded credentials
- Token-based authentication
- Rate limiting built-in
""",
    },
    {
        "full_name": "facebook/react",
        "html_url": "https://github.com/facebook/react",
        "stargazers_count": 220000,
        "forks_count": 44000,
        "watchers_count": 7000,
        "open_issues_count": 800,
        "language": "JavaScript",
        "description": "A JavaScript library for building user interfaces",
        "topics": ["javascript", "ui", "frontend", "react", "web"],
        "updated_at": "2026-04-28T00:00:00Z",
        "owner": {"login": "facebook"},
        "fork": False,
        "archived": False,
        "readme": """# React

A JavaScript library for building user interfaces.

## Features
- Declarative views
- Component-based architecture
- Virtual DOM for performance
- Cross-platform support

## Install
```bash
npm install react react-dom
```

## Example
```jsx
function App() {
  return <h1>Hello World</h1>;
}
```

## Contributing
See CONTRIBUTING.md for guidelines.
""",
    },
    {
        "full_name": "owner/small-project",
        "html_url": "https://github.com/owner/small-project",
        "stargazers_count": 5,
        "forks_count": 1,
        "watchers_count": 1,
        "open_issues_count": 0,
        "language": "Rust",
        "description": "A tiny utility",
        "topics": [],
        "updated_at": "2025-01-01T00:00:00Z",
        "owner": {"login": "owner"},
        "fork": False,
        "archived": True,
        "readme": "# Small Project\n\nA tiny utility.\n\nNo features yet.",
    },
]


# ============================================================
# 1. Schema Correctness Tests
# ============================================================

class TestSchemaCorrectness:
    """Verify all data models pass Pydantic validation"""

    def test_github_repo_schema(self):
        """GitHubRepo should parse all golden repos correctly"""
        from src.types.schemas import GitHubRepo

        for repo_data in GOLDEN_REPOS:
            repo = GitHubRepo.from_api_response(repo_data)
            assert repo.full_name == repo_data["full_name"]
            assert repo.html_url == repo_data["html_url"]
            assert isinstance(repo.stargazers_count, int)
            assert isinstance(repo.language, str)
            assert isinstance(repo.topics, list)

    def test_github_search_result_schema(self):
        """GitHubSearchResult should wrap multiple repos"""
        from src.types.schemas import GitHubSearchResult, GitHubRepo

        items = [GitHubRepo.from_api_response(r) for r in GOLDEN_REPOS]
        result = GitHubSearchResult(
            total_count=len(items),
            items=items,
            incomplete_results=False,
        )
        assert result.total_count == 3
        assert len(result.items) == 3
        assert result.incomplete_results is False

    def test_project_fact_schema(self):
        """ProjectFact should validate trend_score range"""
        from src.types.schemas import ProjectFact

        fact = ProjectFact(
            owner="test",
            repo="repo",
            stars=100,
            lang="Python",
            readme_snippet="Test readme",
            trend_score=0.5,
            last_commit_days=7,
            tags=["test"],
        )
        assert fact.trend_score == 0.5
        assert fact.full_name == "test/repo"

    def test_project_fact_trend_score_boundary(self):
        """ProjectFact should reject trend_score outside 0.0-1.0"""
        from pydantic import ValidationError
        from src.types.schemas import ProjectFact

        with pytest.raises(ValidationError):
            ProjectFact(owner="t", repo="r", trend_score=1.5)

        with pytest.raises(ValidationError):
            ProjectFact(owner="t", repo="r", trend_score=-0.1)

    def test_score_breakdown_schema(self):
        """ScoreBreakdown should validate all scores 0.0-1.0"""
        from pydantic import ValidationError
        from src.types.schemas import ScoreBreakdown

        scores = ScoreBreakdown(
            functionality=0.8,
            code_quality=0.7,
            security=0.9,
            maintainability=0.6,
            community=0.8,
        )
        assert all(0.0 <= v <= 1.0 for v in scores.model_dump().values())

    def test_score_breakdown_invalid(self):
        """ScoreBreakdown should reject out-of-range scores"""
        from pydantic import ValidationError
        from src.types.schemas import ScoreBreakdown

        with pytest.raises(ValidationError):
            ScoreBreakdown(functionality=1.5)


# ============================================================
# 2. Field Coverage Tests
# ============================================================

class TestFieldCoverage:
    """Verify all required fields are populated"""

    def test_trend_score_range(self):
        """Trend score should be in 0.0-1.0 for all repos"""
        from unittest.mock import MagicMock

        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()

            for repo_data in GOLDEN_REPOS:
                mock_repo = MagicMock()
                mock_repo.stargazers_count = repo_data["stargazers_count"]
                mock_repo.forks_count = repo_data["forks_count"]
                mock_repo.topics = repo_data["topics"]
                mock_repo.language = repo_data["language"]
                mock_repo.watchers_count = repo_data.get("watchers_count", 0)

                score = agent._calculate_trend_score(mock_repo)
                assert 0.0 <= score <= 1.0, (
                    f"Trend score {score} out of range for {repo_data['full_name']}"
                )

    def test_trend_score_ranking(self):
        """Higher-star repos should generally have higher trend scores"""
        from unittest.mock import MagicMock

        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()

            def make_mock(data):
                m = MagicMock()
                m.stargazers_count = data["stargazers_count"]
                m.forks_count = data["forks_count"]
                m.topics = data["topics"]
                m.language = data["language"]
                m.watchers_count = data.get("watchers_count", 0)
                return m

            big = agent._calculate_trend_score(make_mock(GOLDEN_REPOS[0]))
            small = agent._calculate_trend_score(make_mock(GOLDEN_REPOS[2]))

            assert big > small, (
                f"Big repo ({big}) should score higher than small repo ({small})"
            )

    def test_last_commit_days_calculation(self):
        """Last commit days should be reasonable"""
        from unittest.mock import MagicMock
        from datetime import datetime

        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()

            for repo_data in GOLDEN_REPOS:
                mock_repo = MagicMock()
                mock_repo.updated_at = repo_data["updated_at"]

                days = agent._calculate_last_commit_days(mock_repo)
                expected_days = (
                    datetime.now().astimezone() - datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00"))
                ).days
                assert abs(days - expected_days) <= 1, (
                    f"Last commit days mismatch: {days} vs {expected_days}"
                )

    def test_search_result_fields(self):
        """Search results should include all golden dataset fields"""
        from src.types.schemas import GitHubRepo

        for repo_data in GOLDEN_REPOS:
            repo = GitHubRepo.from_api_response(repo_data)
            # Verify all required fields are present
            assert hasattr(repo, "full_name")
            assert hasattr(repo, "stargazers_count")
            assert hasattr(repo, "language")
            assert hasattr(repo, "topics")
            assert hasattr(repo, "is_archived")
            assert hasattr(repo, "is_fork")

            # Verify field values
            assert repo.full_name == repo_data["full_name"]
            assert repo.stargazers_count == repo_data["stargazers_count"]
            assert repo.language == repo_data["language"]
            assert repo.topics == repo_data["topics"]
            assert repo.is_archived == repo_data.get("archived", False)
            assert repo.is_fork == repo_data.get("fork", False)


# ============================================================
# 3. Analyst Output Structure Tests
# ============================================================

class TestAnalystOutputStructure:
    """Verify analyst output matches expected schema"""

    def test_analysis_result_required_fields(self):
        """AnalysisResult should have all required fields"""
        from src.types.schemas import AnalysisResult

        result = AnalysisResult(
            repo_name="test/repo",
            analysis_type="technical",
            summary="Test analysis",
            insights=["insight1", "insight2"],
            recommendations=["rec1"],
            risk_level="low",
        )
        assert result.repo_name == "test/repo"
        assert len(result.insights) == 2
        assert len(result.recommendations) == 1
        assert result.risk_level == "low"

    def test_project_fact_from_researcher_output(self):
        """ProjectFact should be constructible from researcher output"""
        from src.types.schemas import ProjectFact

        # Simulate researcher output
        researcher_output = {
            "full_name": "langchain-ai/langchain",
            "stars": 90000,
            "language": "Python",
            "readme_snippet": "Building applications with LLMs",
            "trend_score": 0.9,
            "last_commit_days": 1,
            "tags": ["python", "llm", "ai"],
        }

        owner, repo = researcher_output["full_name"].split("/")
        fact = ProjectFact(
            owner=owner,
            repo=repo,
            stars=researcher_output["stars"],
            lang=researcher_output["language"],
            readme_snippet=researcher_output["readme_snippet"],
            trend_score=researcher_output["trend_score"],
            last_commit_days=researcher_output["last_commit_days"],
            tags=researcher_output["tags"],
        )

        assert fact.owner == "langchain-ai"
        assert fact.repo == "langchain"
        assert fact.trend_score == 0.9
        assert fact.last_commit_days == 1
        assert len(fact.tags) == 3

    def test_project_analysis_report_schema(self):
        """ProjectAnalysisReport should validate full analyst output"""
        from src.types.schemas import ProjectAnalysisReport, ScoreBreakdown

        report = ProjectAnalysisReport(
            core_function="LLM application framework",
            tech_stack=["Python", "OpenAI API"],
            architecture_pattern="Library",
            pain_points=["LLM integration complexity", "Prompt management"],
            suitability="LLM-powered applications",
            risk_flags=[],
            score_breakdown=ScoreBreakdown(
                functionality=0.9,
                code_quality=0.8,
                security=0.7,
                maintainability=0.8,
                community=0.9,
            ),
            suitability_score=0.85,
        )

        assert report.core_function == "LLM application framework"
        assert report.score_breakdown.functionality == 0.9
        assert report.suitability_score == 0.85
        assert len(report.tech_stack) == 2


# ============================================================
# 4. End-to-End Pipeline Tests (Mocked)
# ============================================================

class TestEndToEndPipeline:
    """Test full pipeline with mocked GitHub API"""

    def _mock_github_client(self, repo_data, readme_content=""):
        """Create a mock HTTP client that returns golden data"""
        import base64

        client = MagicMock()

        def mock_request(method, url, *args, **kwargs):
            resp = MagicMock()
            if "readme" in url.lower():
                resp.status_code = 200
                resp.json.return_value = {
                    "content": base64.b64encode(readme_content.encode()).decode(),
                    "encoding": "base64",
                }
            else:
                resp.status_code = 200
                resp.json.return_value = repo_data
            return resp

        return mock_request

    def test_github_tool_search_pipeline(self):
        """Search pipeline should return golden repos with correct schema"""
        from src.tools.github_tool import GitHubTool
        from src.types.schemas import GitHubRepo

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()

            # Mock search response
            search_response = MagicMock()
            search_response.status_code = 200
            search_response.json.return_value = {
                "total_count": len(GOLDEN_REPOS),
                "items": GOLDEN_REPOS,
                "incomplete_results": False,
            }

            with patch.object(tool._http_client._session, 'request', return_value=search_response):
                repos = tool.search_repositories("test", per_page=3)

                assert len(repos) == 3
                for repo in repos:
                    assert isinstance(repo, GitHubRepo)
                    assert repo.full_name is not None
                    assert isinstance(repo.stargazers_count, int)

    def test_github_tool_repo_info_pipeline(self):
        """Repo info pipeline should return validated schema"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            golden = GOLDEN_REPOS[0]  # langchain

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            # Remove owner login from nested dict for API format
            api_data = {k: v for k, v in golden.items() if k != "owner"}
            api_data["owner"] = golden["owner"]
            mock_resp.json.return_value = api_data

            with patch.object(tool._http_client._session, 'request', return_value=mock_resp):
                repo = tool.get_repo_info("langchain-ai", "langchain")
                assert repo.full_name == "langchain-ai/langchain"
                assert repo.stargazers_count == 90000
                assert repo.language == "Python"

    def test_readme_cleaning_preserves_content(self):
        """README cleaning should preserve meaningful content"""
        from src.tools.github_tool import GitHubTool

        readme = GOLDEN_REPOS[0]["readme"]
        cleaned = GitHubTool.clean_readme_text(readme)

        # Should preserve meaningful text
        assert "LangChain" in cleaned
        assert "LLM" in cleaned or "llm" in cleaned.lower()
        # Should remove code blocks
        assert "```" not in cleaned


# ============================================================
# 5. Report Generation Quality Tests
# ============================================================

class TestReportQuality:
    """Test report structure and completeness"""

    def test_report_has_all_sections(self):
        """Report should have executive summary, comparison, details, assessment"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()

        search_results = [
            {"full_name": "a/b", "html_url": "https://example.com", "stars": 100,
             "language": "Python", "description": "Test repo",
             "owner": "a", "repo": "b"},
        ]

        analysis_results = [
            {
                "project": "a/b",
                "url": "https://example.com",
                "stars": 100,
                "language": "Python",
                "analysis": {
                    "core_function": "Test function",
                    "tech_stack": {"language": "Python", "frameworks": ["FastAPI"]},
                    "pain_points_solved": ["API complexity"],
                    "unique_value": "Simple API design",
                    "maturity_assessment": "stable",
                    "recommendation": "recommend",
                    "competitive_analysis": "Better than Flask",
                },
            },
        ]

        report = gen._generate_report("test query", search_results, analysis_results)

        assert "# GitHub Project Analysis Report" in report
        assert "Executive Summary" in report
        assert "Project Comparison" in report
        assert "a/b" in report
        assert "Test function" in report

    def test_comparison_table_format(self):
        """Comparison table should have correct markdown format"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()

        analysis_results = [
            {
                "project": "owner/repo",
                "stars": 1000,
                "language": "Python",
                "analysis": {
                    "maturity_assessment": "stable",
                    "recommendation": "recommend",
                },
            },
        ]

        table = gen._generate_comparison_table(analysis_results)
        assert "| 1 |" in table
        assert "owner/repo" in table
        assert "1,000" in table or "1000" in table

    def test_executive_summary_with_multiple_projects(self):
        """Executive summary should aggregate multiple projects"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()

        search_results = [
            {"full_name": "a/b", "stars": 100, "language": "Python", "description": "Repo 1"},
            {"full_name": "c/d", "stars": 200, "language": "JavaScript", "description": "Repo 2"},
        ]

        analysis_results = [
            {"project": "a/b", "stars": 100, "language": "Python", "analysis": {}},
            {"project": "c/d", "stars": 200, "language": "JavaScript", "analysis": {}},
        ]

        summary = gen._generate_executive_summary(search_results, analysis_results)

        assert "2" in summary
        assert "300" in summary  # Total stars
        assert "Python" in summary
        assert "JavaScript" in summary

    def test_empty_analysis_handling(self):
        """Empty analysis should not crash report generation"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()

        details = gen._generate_project_details([
            {"project": "test/repo", "stars": 0, "language": "", "analysis": {}},
        ])
        assert "test/repo" in details

    def test_insufficient_data_flag(self):
        """INSUFFICIENT_DATA should be detectable"""
        from src.types.schemas import INSUFFICIENT_DATA, is_insufficient_data

        assert is_insufficient_data(INSUFFICIENT_DATA) is True
        assert is_insufficient_data("INSUFFICIENT_DATA") is True
        assert is_insufficient_data("valid data") is False
        assert is_insufficient_data(None) is False
        assert is_insufficient_data(0) is False


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
