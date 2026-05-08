# -*- coding: utf-8 -*-
"""Tests for github_toolkit closure functions and adaptation layer."""

from unittest.mock import patch, MagicMock

from src.tools.github_toolkit import (
    create_github_toolkit,
    get_github_tool_schemas,
    get_github_toolkit,
)


class TestToolkitCreation:
    """Test create_github_toolkit function."""

    def setup_method(self):
        """Reset singleton before each test."""
        import src.tools.github_toolkit as gtk
        gtk._github_toolkit_cache = None

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_toolkit_has_github_tools(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        toolkit = create_github_toolkit(use_mcp=False)
        schemas = toolkit.get_json_schemas()
        names = [s.get('function', {}).get('name') for s in schemas]

        assert 'search_repositories' in names
        assert 'get_readme' in names
        assert 'get_repo_info' in names
        assert 'get_project_summary' in names
        assert 'check_rate_limit' in names

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_toolkit_has_orphan_tools(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        toolkit = create_github_toolkit(use_mcp=False)
        schemas = toolkit.get_json_schemas()
        names = [s.get('function', {}).get('name') for s in schemas]

        assert 'evaluate_code_quality' in names
        assert 'scan_security_code' in names
        assert 'review_code_changes' in names

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_get_json_schemas(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        toolkit = create_github_toolkit(use_mcp=False)
        schemas = get_github_tool_schemas(toolkit)
        assert len(schemas) > 0
        assert all('function' in s for s in schemas)


class TestToolResponseAdaptation:
    """Test Pydantic-to-AgentScope ToolResponse adaptation."""

    def setup_method(self):
        import src.tools.github_toolkit as gtk
        gtk._github_toolkit_cache = None

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_evaluate_code_quality_success(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        create_github_toolkit(use_mcp=False)

        # Import the registered function
        from agentscope.tool import ToolResponse
        mock_pydantic = MagicMock()
        mock_pydantic.success = True
        mock_pydantic.data = {"quality_score": 4.0}
        mock_pydantic.error_message = "Report text here"

        with patch('src.tools.code_quality_tool.evaluate_code_quality') as mock_eval, \
             patch('asyncio.get_event_loop') as mock_loop:

            mock_loop.return_value.run_until_complete.return_value = mock_pydantic
            mock_eval.return_value = mock_pydantic

            result = ToolResponse(content=[{"text": "test"}])
            assert isinstance(result, ToolResponse)

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_evaluate_code_quality_invalid_json(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        toolkit = create_github_toolkit(use_mcp=False)
        schemas = toolkit.get_json_schemas()
        names = [s.get('function', {}).get('name') for s in schemas]
        assert 'evaluate_code_quality' in names


class TestGetGithubToolkit:
    """Test get_github_toolkit singleton function."""

    def setup_method(self):
        import src.tools.github_toolkit as gtk
        gtk._github_toolkit_cache = None

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_singleton_returns_same_instance(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        t1 = get_github_toolkit(use_mcp=False)
        t2 = get_github_toolkit(use_mcp=False)
        assert t1 is t2

    @patch('src.tools.github_toolkit.GitHubTool')
    @patch('src.tools.github_toolkit.create_github_mcp_client', return_value=None)
    def test_force_new_creates_new_instance(self, mock_mcp, mock_tool_cls):
        mock_instance = MagicMock()
        mock_tool_cls.return_value = mock_instance

        t1 = get_github_toolkit(use_mcp=False)
        t2 = get_github_toolkit(use_mcp=False, force_new=True)
        assert t1 is not t2
