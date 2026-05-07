# -*- coding: utf-8 -*-
"""Tests for S3-P2: Tool→Tool Orchestration."""

from unittest.mock import MagicMock, patch

from src.core.tool_orchestrator import (
    ToolOrchestrator,
    get_builtin_pipelines,
    describe_pipeline,
    PIPELINES,
)


# ============================================================
# ToolOrchestrator Tests
# ============================================================

class TestToolOrchestrator:
    """Test Tool→Tool chaining and pipeline execution."""

    def _make_orchestrator(self):
        """Create an orchestrator with mocked github_tool."""
        mock_github = MagicMock()
        orchestrator = ToolOrchestrator(github_tool=mock_github)
        return orchestrator, mock_github

    def test_register_pipeline(self):
        """Test registering a custom pipeline."""
        orchestrator, _ = self._make_orchestrator()

        orchestrator.register_pipeline(
            "my_pipeline",
            [
                {"tool": "search_repositories", "params": {"query": "{query}"}, "output_key": "search"},
            ],
        )
        assert "my_pipeline" in orchestrator.get_available_pipelines()

    def test_execute_single_step(self):
        """Test executing a single step pipeline."""
        orchestrator, mock_github = self._make_orchestrator()

        mock_github.search_repositories.return_value = []

        steps = [
            {"tool": "search_repositories", "params": {"query": "test"}, "output_key": "results"},
        ]
        result = orchestrator.execute_tool_chain(steps, {"query": "test"})

        assert result["success"] is True
        assert len(result["steps"]) == 1
        assert result["steps"][0]["tool"] == "search_repositories"
        assert result["steps"][0]["success"] is True
        mock_github.search_repositories.assert_called_once_with(query="test")

    def test_execute_multi_step_chain(self):
        """Test executing a multi-step chain where context flows between steps."""
        orchestrator, mock_github = self._make_orchestrator()

        mock_repo_info = MagicMock()
        mock_repo_info.full_name = "owner/repo"
        mock_repo_info.stargazers_count = 5000
        mock_github.get_repo_info.return_value = mock_repo_info

        mock_readme = "# Test README\n\nThis is a test project."
        mock_github.get_readme.return_value = mock_readme

        steps = [
            {"tool": "get_repo_info", "params": {"owner": "{owner}", "repo": "{repo}"}, "output_key": "info"},
            {"tool": "get_readme", "params": {"owner": "{owner}", "repo": "{repo}"}, "output_key": "readme"},
        ]
        result = orchestrator.execute_tool_chain(
            steps, {"owner": "owner", "repo": "repo"}
        )

        assert result["success"] is True
        assert len(result["steps"]) == 2
        # Results are stored as formatted strings in context
        assert "info" in result["context"]
        assert "readme" in result["context"]
        assert result["context"]["readme"] == mock_readme
        mock_github.get_repo_info.assert_called_once()
        mock_github.get_readme.assert_called_once()

    def test_context_placeholder_resolution(self):
        """Test that {key} placeholders are resolved from context."""
        orchestrator, _ = self._make_orchestrator()

        # Test string resolution directly
        context = {"owner": "django", "repo": "django", "limit": 10}
        params = {"owner": "{owner}", "repo": "{repo}", "limit": "{limit}"}
        resolved = orchestrator._resolve_params(params, context)

        assert resolved["owner"] == "django"
        assert resolved["repo"] == "django"
        assert resolved["limit"] == "10"

    def test_placeholder_with_default(self):
        """Test {key|default} syntax."""
        orchestrator, _ = self._make_orchestrator()

        context = {"owner": "test"}
        text = orchestrator._resolve_string("{per_page|5}", context)
        assert text == "5"

        text = orchestrator._resolve_string("{owner|missing}", context)
        assert text == "test"

    def test_missing_placeholder_resolves_to_empty(self):
        """Test that missing keys resolve to empty string."""
        orchestrator, _ = self._make_orchestrator()

        context = {"owner": "test"}
        text = orchestrator._resolve_string("{missing_key}", context)
        assert text == ""

    def test_condition_skip(self):
        """Test that steps with unmet conditions are skipped."""
        orchestrator, mock_github = self._make_orchestrator()

        steps = [
            {"tool": "search_repositories", "params": {"query": "test"}, "output_key": "search_results"},
            {"tool": "get_repo_info", "params": {"owner": "x", "repo": "y"}, "output_key": "repo_info",
             "condition": "search_results.exists"},
        ]

        # First step: returns non-empty result
        mock_repo = MagicMock()
        mock_repo.full_name = "test/repo"
        mock_repo.stargazers_count = 100
        mock_repo.language = "Python"
        mock_repo.description = "Test"
        mock_repo.html_url = "https://github.com/test/repo"
        mock_github.search_repositories.return_value = [mock_repo]
        mock_github.get_repo_info.return_value = mock_repo

        result = orchestrator.execute_tool_chain(
            steps, {"query": "test"}
        )
        # Both steps should execute (condition met)
        assert result["steps"][0].get("success") is True
        assert result["steps"][1].get("success") is True

    def test_condition_not_met_skips_step(self):
        """Test that steps with unmet conditions are skipped."""
        orchestrator, mock_github = self._make_orchestrator()

        steps = [
            {"tool": "get_readme", "params": {"owner": "o", "repo": "r"}, "output_key": "readme"},
            {"tool": "get_repo_info", "params": {"owner": "x", "repo": "y"}, "output_key": "repo_info",
             "condition": "nonexistent_key.exists"},
        ]

        mock_github.get_readme.return_value = "# README"

        result = orchestrator.execute_tool_chain(
            steps, {"owner": "o", "repo": "r"}
        )
        assert result["steps"][0].get("success") is True
        assert result["steps"][1].get("skipped") is True
        # get_repo_info should NOT have been called (step skipped)
        mock_github.get_repo_info.assert_not_called()

    def test_step_failure_continues_chain(self):
        """Test that a failed step doesn't abort the chain."""
        from src.core.tool_orchestrator import ToolOrchestrator

        # Use a real object (not MagicMock) so hasattr returns False
        class DummyTool:
            pass

        orchestrator = ToolOrchestrator(github_tool=DummyTool())

        steps = [
            {"tool": "nonexistent_step", "params": {}, "output_key": "step1"},
            {"tool": "get_readme", "params": {"owner": "o", "repo": "r"}, "output_key": "readme"},
        ]

        result = orchestrator.execute_tool_chain(steps, {"owner": "o", "repo": "r"})
        assert result["steps"][0]["success"] is False
        assert result["steps"][1]["success"] is False  # Also fails (tool not found)

    def test_execute_builtin_pipeline_repo_analysis(self):
        """Test executing the built-in repo_analysis pipeline."""
        orchestrator, mock_github = self._make_orchestrator()

        mock_repo_info = MagicMock()
        mock_repo_info.full_name = "owner/repo"
        mock_github.get_repo_info.return_value = mock_repo_info
        mock_github.get_readme.return_value = "# Test"
        mock_github.evaluate_code_quality.return_value = "Quality: 8/10"

        result = orchestrator.execute_pipeline(
            "repo_analysis",
            {"owner": "owner", "repo": "repo"},
        )

        assert result["success"] is True
        assert len(result["steps"]) == 3
        assert "repo_info" in result["context"]
        assert "readme" in result["context"]
        assert "quality_report" in result["context"]
        mock_github.get_repo_info.assert_called_once_with(owner="owner", repo="repo")
        mock_github.get_readme.assert_called_once_with(owner="owner", repo="repo")

    def test_execute_unknown_pipeline(self):
        """Test executing a non-existent pipeline."""
        orchestrator, _ = self._make_orchestrator()

        result = orchestrator.execute_pipeline("nonexistent", {})
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_get_available_pipelines(self):
        """Test listing available pipelines."""
        orchestrator, _ = self._make_orchestrator()

        pipelines = orchestrator.get_available_pipelines()
        assert "repo_analysis" in pipelines
        assert "security_scan" in pipelines

    def test_format_tool_result_dict(self):
        """Test _format_tool_result converts dict to JSON string."""
        orchestrator, _ = self._make_orchestrator()

        result = orchestrator._format_tool_result({"key": "value", "num": 42})
        assert '"key"' in result
        assert '"value"' in result
        assert "42" in result

    def test_format_tool_result_string_passthrough(self):
        """Test _format_tool_result passes strings through."""
        orchestrator, _ = self._make_orchestrator()

        result = orchestrator._format_tool_result("plain text")
        assert result == "plain text"


# ============================================================
# Convenience Function Tests
# ============================================================

class TestPipelineConvenience:
    """Test pipeline convenience functions."""

    def test_get_builtin_pipelines(self):
        """Test get_builtin_pipelines returns all built-in pipelines."""
        pipelines = get_builtin_pipelines()
        assert "repo_analysis" in pipelines
        assert "security_scan" in pipelines
        assert "pr_review" in pipelines

    def test_describe_existing_pipeline(self):
        """Test describe_pipeline returns step details."""
        description = describe_pipeline("repo_analysis")
        assert description is not None
        assert description["name"] == "repo_analysis"
        assert len(description["steps"]) == 3
        assert description["steps"][0]["tool"] == "get_repo_info"

    def test_describe_nonexistent_pipeline(self):
        """Test describe_pipeline returns None for unknown pipeline."""
        description = describe_pipeline("does_not_exist")
        assert description is None
