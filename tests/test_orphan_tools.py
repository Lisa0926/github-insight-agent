# -*- coding: utf-8 -*-
"""Tests for orphan tool registration in github_toolkit.py."""

from unittest.mock import patch, MagicMock

from src.core.tool_base import BaseTool
from src.tools.github_tool import GitHubTool


class TestGitHubToolBaseTool:
    """Test GitHubTool implements BaseTool protocol."""

    def test_github_tool_is_base_tool(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            assert isinstance(tool, BaseTool)

    def test_get_name(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            assert tool.get_name() == "github_tool"

    def test_get_description(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            desc = tool.get_description()
            assert "GitHub" in desc

    def test_get_input_schema(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            schema = tool.get_input_schema()
            assert schema["type"] == "object"
            assert "action" in schema["properties"]

    def test_get_json_schema(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            js = tool.get_json_schema()
            assert js["type"] == "function"
            assert js["function"]["name"] == "github_tool"

    def test_validate_input_valid(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            assert tool.validate_input({"action": "search_repositories"}) is True

    def test_validate_input_missing_action(self):
        with patch.object(GitHubTool, '__init__', lambda self, **kw: None):
            tool = GitHubTool.__new__(GitHubTool)
            assert tool.validate_input({"query": "test"}) is False


class TestOrphanToolRegistration:
    """Test orphan tools are registered in toolkit."""

    def test_create_toolkit_has_orphan_groups(self):
        """Verify orphan tool groups are created in create_github_toolkit."""
        with patch('src.tools.github_toolkit.GitHubTool') as MockGitHubTool, \
             patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None):

            mock_instance = MagicMock()
            MockGitHubTool.return_value = mock_instance

            from src.tools.github_toolkit import create_github_toolkit
            toolkit = create_github_toolkit(use_mcp=False)

            schemas = toolkit.get_json_schemas()
            tool_names = [
                s.get('function', {}).get('name', '')
                for s in schemas
            ]

            # Verify orphan tools are present
            assert "evaluate_code_quality" in tool_names
            assert "scan_security_code" in tool_names
            assert "review_code_changes" in tool_names
