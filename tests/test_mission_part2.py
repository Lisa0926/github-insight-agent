# -*- coding: utf-8 -*-
"""Mission Part 2 supplemental tests — May 8, 2026.

Covers the latest uncommitted changes:
- researcher_agent._extract_search_keywords (keyword extraction from Chinese queries)
- researcher_agent._call_llm (general chat)
- researcher_agent._execute_compare (repo comparison)
- dashscope_wrapper output.text fallback when choices is None/empty
"""

from unittest.mock import MagicMock, patch


# ============================================================
# 1. _extract_search_keywords — keyword extraction
# ============================================================

class TestExtractSearchKeywords:
    """Test researcher_agent._extract_search_keywords for Chinese-to-English conversion."""

    def _make_agent(self):
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        return agent

    def test_english_query_passthrough(self):
        """English queries should be returned as-is."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("python web framework")
        assert "python" in result.lower()
        assert "web" in result.lower()
        assert "framework" in result.lower()

    def test_mixed_chinese_english(self):
        """Mixed queries should extract only English terms."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("找一个 Python web 框架")
        assert "Python" in result
        assert "web" in result

    def test_pure_chinese_ai_query(self):
        """Pure Chinese AI query should default to AI-related keywords."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("人工智能框架推荐")
        assert "AI" in result
        assert "framework" in result

    def test_pure_chinese_chatbot_query(self):
        """Pure Chinese chatbot query should map to chatbot keyword."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("做一个聊天机器人")
        assert "chatbot" in result

    def test_pure_chinese_web_query(self):
        """Pure Chinese web query should map to web keyword."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("网页开发工具")
        assert "web" in result

    def test_pure_chinese_game_query(self):
        """Pure Chinese game query should map to game keyword."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("游戏引擎")
        assert "game" in result

    def test_pure_chinese_database_query(self):
        """Pure Chinese database query should map to database keyword."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("数据库管理系统")
        assert "database" in result

    def test_empty_string(self):
        """Empty string should return default 'AI framework'."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("")
        assert result == "AI framework"

    def test_only_numbers(self):
        """Query with only numbers should return default."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("123456")
        assert result == "AI framework"

    def test_single_english_word(self):
        """Single English word should be returned."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("react")
        assert result == "react"

    def test_technical_terms_with_hyphens(self):
        """Technical terms with hyphens should be captured."""
        agent = self._make_agent()
        result = agent._extract_search_keywords("machine-learning framework")
        assert "machine-learning" in result

    def test_domain_hints_multiple_matches(self):
        """Query matching multiple domains should return all matched keywords."""
        agent = self._make_agent()
        # Pure Chinese query with multiple domain hints
        result = agent._extract_search_keywords("人工智能数据库管理系统")
        # Both AI and database domain hints should match
        assert "AI" in result
        assert "database" in result


# ============================================================
# 2. _call_llm — general chat method
# ============================================================

class TestCallLLM:
    """Test researcher_agent._call_llm for general Q&A."""

    def test_call_llm_success(self):
        """Successful LLM call should return content."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        mock_wrapper = MagicMock(return_value={
            "content": "Hello, this is a test response.",
            "metadata": {},
        })
        agent._get_model_wrapper = MagicMock(return_value=mock_wrapper)
        agent._build_messages = MagicMock(return_value=[{"role": "user", "content": "hi"}])
        agent._add_to_memory = MagicMock()  # Use MagicMock directly instead of patch.object

        with patch('src.agents.researcher_agent.filter_sensitive_output', side_effect=lambda x: x):
            result = agent._call_llm("hello")

        assert "test response" in result.lower()

    def test_call_llm_error_fallback(self):
        """Failed LLM call should return Chinese error message."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        agent._get_model_wrapper = MagicMock(side_effect=ConnectionError("Network error"))

        result = agent._call_llm("hello")
        assert "抱歉" in result
        assert "失败" in result


# ============================================================
# 3. _execute_compare — repository comparison
# ============================================================

class TestExecuteCompare:
    """Test researcher_agent._execute_compare for repo comparison."""

    def test_compare_empty_list(self):
        """Empty repo list should return Chinese prompt message."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        result = agent._execute_compare({"repositories": []})
        assert "请提供" in result

    def test_compare_no_repos_key(self):
        """Missing 'repositories' key should return Chinese prompt."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        result = agent._execute_compare({})
        assert "请提供" in result

    def test_compare_single_repo(self):
        """Compare a single repo should show its info."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        agent._execute_get_repo_info = MagicMock(
            return_value="- Project: test/repo\n- Stars: 100\n- Language: Python"
        )
        result = agent._execute_compare({"repositories": ["test/repo"]})
        assert "## 项目对比" in result
        assert "### test/repo" in result
        assert "Project" in result

    def test_compare_multiple_repos(self):
        """Compare multiple repos should show all info."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        agent._execute_get_repo_info = MagicMock(
            side_effect=[
                "- Project: a/b\n- Stars: 100",
                "- Project: c/d\n- Stars: 200",
            ]
        )
        result = agent._execute_compare({"repositories": ["a/b", "c/d"]})
        assert "### a/b" in result
        assert "### c/d" in result
        assert agent._execute_get_repo_info.call_count == 2

    def test_compare_invalid_repo_format(self):
        """Invalid repo format (no slash) should be skipped."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        agent._execute_get_repo_info = MagicMock()

        result = agent._execute_compare({"repositories": ["invalid-no-slash"]})
        # Should not crash, just skip invalid entry
        assert "## 项目对比" in result
        agent._execute_get_repo_info.assert_not_called()


# ============================================================
# 4. DashScopeWrapper output.text fallback
# ============================================================

class TestDashScopeTextFallback:
    """Test dashscope_wrapper fallback to output.text when choices is None/empty."""

    def test_fallback_to_output_text(self):
        """When choices is None but output.text has content, use it."""
        from src.core.dashscope_wrapper import DashScopeWrapper
        wrapper = DashScopeWrapper.__new__(DashScopeWrapper)
        wrapper.model_name = "test"
        wrapper.api_key = "key"
        wrapper.base_url = ""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices = None
        mock_resp.output.text = "Direct text response"
        mock_resp.usage = {"input_tokens": 10, "output_tokens": 20}

        with patch('src.core.dashscope_wrapper.Generation') as mock_gen:
            mock_gen.call.return_value = mock_resp
            result = wrapper(messages=[{"role": "user", "content": "hi"}])
            assert result.get("content") == "Direct text response"

    def test_empty_choices_with_output_text(self):
        """When choices is empty list but output.text has content, use it."""
        from src.core.dashscope_wrapper import DashScopeWrapper
        wrapper = DashScopeWrapper.__new__(DashScopeWrapper)
        wrapper.model_name = "test"
        wrapper.api_key = "key"
        wrapper.base_url = ""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices = []
        mock_resp.output.text = "Fallback text"
        mock_resp.usage = {"input_tokens": 5, "output_tokens": 10}

        with patch('src.core.dashscope_wrapper.Generation') as mock_gen:
            mock_gen.call.return_value = mock_resp
            result = wrapper(messages=[{"role": "user", "content": "hi"}])
            assert result.get("content") == "Fallback text"

    def test_normal_choices_takes_precedence(self):
        """When choices has content, output.text should NOT be used."""
        from src.core.dashscope_wrapper import DashScopeWrapper
        wrapper = DashScopeWrapper.__new__(DashScopeWrapper)
        wrapper.model_name = "test"
        wrapper.api_key = "key"
        wrapper.base_url = ""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_msg = {"text": "From choices", "tool_calls": []}
        mock_resp.output.choices = [MagicMock()]
        mock_resp.output.choices[0].message = mock_msg
        mock_resp.output.text = "From output.text (should not be used)"
        mock_resp.usage = {"input_tokens": 5, "output_tokens": 10}

        with patch('src.core.dashscope_wrapper.Generation') as mock_gen:
            mock_gen.call.return_value = mock_resp
            result = wrapper(messages=[{"role": "user", "content": "hi"}])
            assert result.get("content") == "From choices"


# ============================================================
# 5. Intent understanding fallback integration
# ============================================================

class TestIntentFallbackIntegration:
    """Test that _understand_intent properly falls back with keyword extraction."""

    def test_fallback_on_llm_crash_with_chinese_query(self):
        """When LLM crashes on Chinese query, fallback should extract keywords."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        agent._get_model_wrapper = MagicMock(side_effect=RuntimeError("Crash"))

        result = agent._understand_intent("人工智能框架")
        assert result["action"] == "search_repositories"
        # Should extract AI-related keywords, not return raw Chinese
        assert result["params"]["query"] in ("AI", "AI framework")
        assert result["params"]["sort"] == "stars"
        assert result["params"]["limit"] == 5

    def test_fallback_on_json_parse_error(self):
        """When LLM returns non-JSON, should fallback to search."""
        from src.agents.researcher_agent import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        mock_wrapper = MagicMock(return_value={
            "content": "I don't understand what you want",
            "metadata": {},
        })
        agent._get_model_wrapper = MagicMock(return_value=mock_wrapper)

        result = agent._understand_intent("find python repos")
        assert result["action"] == "search_repositories"


# ============================================================
# 6. DashScopeWrapper edge cases
# ============================================================

class TestDashScopeEdgeCases:
    """Additional edge cases for dashscope_wrapper."""

    def test_non_dict_message(self):
        """When message is not a dict, should handle gracefully."""
        from src.core.dashscope_wrapper import DashScopeWrapper
        wrapper = DashScopeWrapper.__new__(DashScopeWrapper)
        wrapper.model_name = "test"
        wrapper.api_key = "key"
        wrapper.base_url = ""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.output.choices = [MagicMock()]
        mock_resp.output.choices[0].message = "not a dict"
        mock_resp.output.text = None
        mock_resp.usage = {"input_tokens": 5, "output_tokens": 10}

        with patch('src.core.dashscope_wrapper.Generation') as mock_gen:
            mock_gen.call.return_value = mock_resp
            result = wrapper(messages=[{"role": "user", "content": "hi"}])
            assert result.get("content") == ""

    def test_usage_extraction_none_usage(self):
        """When resp.usage is None, should default to 0."""
        from src.core.dashscope_wrapper import DashScopeWrapper
        wrapper = DashScopeWrapper.__new__(DashScopeWrapper)
        wrapper.model_name = "test"
        wrapper.api_key = "key"
        wrapper.base_url = ""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_msg = {"text": "hello", "tool_calls": []}
        mock_resp.output.choices = [MagicMock()]
        mock_resp.output.choices[0].message = mock_msg
        mock_resp.usage = None

        with patch('src.core.dashscope_wrapper.Generation') as mock_gen:
            mock_gen.call.return_value = mock_resp
            result = wrapper(messages=[{"role": "user", "content": "hi"}])
            assert result.get("usage").input_tokens == 0
            assert result.get("usage").output_tokens == 0
