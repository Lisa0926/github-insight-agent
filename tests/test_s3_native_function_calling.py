# -*- coding: utf-8 -*-
"""Tests for S3-P1: AgentScope native function calling."""

import json
from unittest.mock import patch, MagicMock

from agentscope.message._message_block import ToolUseBlock


# ============================================================
# S3-P1: DashScopeWrapper native function calling
# ============================================================

class TestDashScopeNativeFunctionCalling:
    """Test DashScopeWrapper tool calling support."""

    def test_extract_tool_calls_from_content_list(self):
        """Test extract_tool_calls parses ToolUseBlock list."""
        from src.core.dashscope_wrapper import DashScopeWrapper

        wrapper = DashScopeWrapper(api_key="test", model_name="qwen-turbo")

        response = {
            "content": [
                ToolUseBlock(
                    type="tool_use",
                    id="call_1",
                    name="search_repositories",
                    input={"query": "python", "sort": "stars"},
                    raw_input='{"query": "python"}',
                ),
            ],
        }

        calls = wrapper.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "search_repositories"
        assert calls[0]["input"]["query"] == "python"

    def test_extract_tool_calls_from_dict_blocks(self):
        """Test extract_tool_calls parses dict-style tool_use blocks."""
        from src.core.dashscope_wrapper import DashScopeWrapper

        wrapper = DashScopeWrapper(api_key="test", model_name="qwen-turbo")

        response = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_2",
                    "name": "get_repo_info",
                    "input": {"owner": "django", "repo": "django"},
                },
            ],
        }

        calls = wrapper.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_repo_info"

    def test_extract_tool_calls_empty_for_text_response(self):
        """Test extract_tool_calls returns [] for text-only response."""
        from src.core.dashscope_wrapper import DashScopeWrapper

        wrapper = DashScopeWrapper(api_key="test", model_name="qwen-turbo")

        response = {"content": "Hello, I can help with that."}
        calls = wrapper.extract_tool_calls(response)
        assert calls == []

    def test_has_tool_calls_true(self):
        """Test has_tool_calls returns True when tool calls present."""
        from src.core.dashscope_wrapper import DashScopeWrapper

        wrapper = DashScopeWrapper(api_key="test", model_name="qwen-turbo")

        response = {
            "content": [
                {"type": "tool_use", "id": "1", "name": "test", "input": {}},
            ],
        }
        assert wrapper.has_tool_calls(response) is True

    def test_has_tool_calls_false(self):
        """Test has_tool_calls returns False for text response."""
        from src.core.dashscope_wrapper import DashScopeWrapper

        wrapper = DashScopeWrapper(api_key="test", model_name="qwen-turbo")

        response = {"content": "Just text"}
        assert wrapper.has_tool_calls(response) is False


# ============================================================
# S3-P1: ResearcherAgent native function calling
# ============================================================

class TestResearcherAgentNativeTools:
    """Test ResearcherAgent native function calling methods."""

    def test_get_tool_schemas_returns_schemas(self):
        """Test _get_tool_schemas returns toolkit schemas."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock(spec=ResearcherAgent)
        mock_toolkit = MagicMock()
        mock_toolkit.get_json_schemas.return_value = [
            {"function": {"name": "search_repositories", "description": "Search"}},
            {"function": {"name": "get_repo_info", "description": "Info"}},
        ]
        agent.toolkit = mock_toolkit

        schemas = ResearcherAgent._get_tool_schemas(agent)
        assert len(schemas) == 2
        assert schemas[0]["function"]["name"] == "search_repositories"

    def test_get_tool_schemas_empty_without_toolkit(self):
        """Test _get_tool_schemas returns [] when no toolkit."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock(spec=ResearcherAgent)
        agent.toolkit = None

        schemas = ResearcherAgent._get_tool_schemas(agent)
        assert schemas == []

    def test_execute_tool_call_dispatches_search(self):
        """Test _dispatch_tool routes to search handler."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        agent.github_tool = MagicMock()
        mock_repo = MagicMock()
        mock_repo.full_name = "test/repo"
        mock_repo.stargazers_count = 1000
        mock_repo.forks_count = 200
        mock_repo.language = "Python"
        mock_repo.description = "Test repo"
        mock_repo.html_url = "https://github.com/test/repo"
        agent.github_tool.search_repositories.return_value = [mock_repo]
        # Use real _format_search_results
        agent._format_search_results = lambda repos, query, limit: (
            ResearcherAgent._format_search_results(agent, repos, query, limit)
        )

        tool_call = {
            "id": "call_1",
            "name": "search_repositories",
            "input": {"query": "test", "sort": "stars", "limit": 5},
        }

        result = ResearcherAgent._dispatch_tool(agent, tool_call["name"], tool_call["input"])
        agent.github_tool.search_repositories.assert_called_once()
        assert "test/repo" in result

    def test_dispatch_tool_get_repo_info(self):
        """Test _dispatch_tool routes get_repo_info."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        agent.github_tool = MagicMock()
        mock_info = MagicMock()
        mock_info.full_name = "owner/repo"
        mock_info.stargazers_count = 5000
        mock_info.forks_count = 1000
        mock_info.language = "Python"
        mock_info.description = "Test"
        mock_info.updated_at = "2024-01-01"
        mock_info.html_url = "https://github.com/owner/repo"
        agent.github_tool.get_repo_info.return_value = mock_info

        # _execute_get_repo_info should be called by _dispatch_tool
        # We need to mock the result of _execute_get_repo_info
        agent._execute_get_repo_info.return_value = (
            "**owner/repo**\n- Stars: 5,000\n- Forks: 1,000\n- 语言: Python"
        )

        result = ResearcherAgent._dispatch_tool(
            agent, "get_repo_info", {"owner": "owner", "repo": "repo"}
        )
        agent._execute_get_repo_info.assert_called_once_with(
            {"owner": "owner", "repo": "repo"}
        )
        assert "owner/repo" in result
        assert "5,000" in result

    def test_dispatch_tool_unknown(self):
        """Test _dispatch_tool returns error for unknown tool without matching attr."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        # Use a real object as github_tool so hasattr returns False for missing attrs
        class DummyTool:
            pass
        agent.github_tool = DummyTool()

        result = ResearcherAgent._dispatch_tool(
            agent, "nonexistent_tool", {"foo": "bar"}
        )
        assert "Unknown tool" in result

    def test_format_search_results(self):
        """Test _format_search_results produces markdown table."""
        from src.agents.researcher_agent import ResearcherAgent

        mock_repo = MagicMock()
        mock_repo.full_name = "org/project"
        mock_repo.stargazers_count = 10000
        mock_repo.language = "JavaScript"
        mock_repo.description = "A great project"
        mock_repo.html_url = "https://github.com/org/project"

        agent = MagicMock()
        result = ResearcherAgent._format_search_results(agent, [mock_repo], "project", 5)
        assert "org/project" in result
        assert "10,000" in result
        assert "JavaScript" in result

    def test_format_search_results_empty(self):
        """Test _format_search_results for empty results."""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._format_search_results(agent, [], "nope", 5)
        assert "没有找到" in result

    def test_reply_to_message_falls_back_without_toolkit(self):
        """reply_to_message should use prompt-based intent when no toolkit."""
        from src.agents.researcher_agent import ResearcherAgent

        with patch.object(ResearcherAgent, '__init__', lambda self, **kw: None):
            agent = ResearcherAgent.__new__(ResearcherAgent)
            agent.github_tool = MagicMock()
            agent.toolkit = None

        # Mock _reply_with_prompt_based_intent
        with patch.object(
            ResearcherAgent,
            '_reply_with_prompt_based_intent',
            return_value="fallback response",
        ) as mock_fallback:
            with patch(
                'src.agents.researcher_agent.sanitize_user_input',
                side_effect=lambda x: x,
            ):
                result = agent.reply_to_message("search for python frameworks")
                mock_fallback.assert_called_once()
                assert result == "fallback response"

    def test_reply_to_message_uses_native_with_toolkit(self):
        """reply_to_message should use native tools when toolkit available."""
        from src.agents.researcher_agent import ResearcherAgent

        with patch.object(ResearcherAgent, '__init__', lambda self, **kw: None):
            agent = ResearcherAgent.__new__(ResearcherAgent)
            agent.toolkit = MagicMock()

        with patch.object(
            ResearcherAgent,
            'reply_with_native_tools',
            return_value="native response",
        ) as mock_native:
            with patch(
                'src.agents.researcher_agent.sanitize_user_input',
                side_effect=lambda x: x,
            ):
                result = agent.reply_to_message("search for python")
                mock_native.assert_called_once()
                assert result == "native response"
