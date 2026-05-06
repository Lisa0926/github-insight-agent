# -*- coding: utf-8 -*-
"""
Tests for natural language understanding improvements:
1. Direct repo lookup routing (_is_repo_lookup_query, _resolve_repo_by_name)
2. Tool-augmented followup handler (_resolve_repo_query)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ============================================================
# 1. Direct Repo Lookup Detection
# ============================================================

class TestRepoLookupDetection:
    """Test _is_repo_lookup_query pattern detection"""

    def test_owner_repo_format(self):
        """owner/repo patterns should be detected"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "langchain/langchain")
        assert result == "langchain/langchain"

    def test_owner_repo_with_prefix(self):
        """'请分析 langchain/langchain' should detect owner/repo"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "请分析 langchain/langchain")
        assert result == "langchain/langchain"

    def test_project_name_with_star_question(self):
        """'langchain的star数是多少' should detect 'langchain'"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "langchain的star数是多少")
        assert result is not None
        assert "langchain" in result.lower()

    def test_project_name_with_fork_question(self):
        """'django fork 多少' should detect 'django'"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "django fork 多少")
        assert result is not None
        assert "django" in result.lower()

    def test_project_name_with_language_question(self):
        """'react语言' should detect 'react'"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "react语言")
        assert result is not None
        assert "react" in result.lower()

    def test_search_query_not_detected_as_repo(self):
        """General search queries should NOT be detected as repo lookups"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        # "搜索" is a general search instruction
        result = ResearcherAgent._is_repo_lookup_query(agent, "搜索最火的AI框架")
        assert result is None

    def test_chat_query_not_detected_as_repo(self):
        """Pure chat should not trigger repo lookup"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        result = ResearcherAgent._is_repo_lookup_query(agent, "你好，帮我介绍一下GitHub")
        assert result is None

    def test_common_words_filtered(self):
        """Common English words should not be treated as project names"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        # "what" is a common word
        result = ResearcherAgent._is_repo_lookup_query(agent, "what is the star count")
        assert result is None


# ============================================================
# 2. Repo Resolution
# ============================================================

class TestRepoResolution:
    """Test _resolve_repo_by_name"""

    def test_exact_owner_repo_match(self):
        """owner/repo format should try exact match first"""
        from src.agents.researcher_agent import ResearcherAgent

        mock_info = MagicMock()
        mock_info.full_name = "langchain-ai/langchain"
        mock_info.stargazers_count = 90000
        mock_info.forks_count = 20000
        mock_info.language = "Python"
        mock_info.description = "A framework for LLM apps"
        mock_info.html_url = "https://github.com/langchain-ai/langchain"

        agent = MagicMock()
        agent.github_tool.get_repo_info.return_value = mock_info

        result = ResearcherAgent._resolve_repo_by_name(agent, "langchain-ai/langchain")
        assert result is not None
        assert "langchain-ai/langchain" in result
        assert "90,000" in result
        agent.github_tool.get_repo_info.assert_called_once_with("langchain-ai", "langchain")

    def test_fuzzy_search_fallback(self):
        """When exact match fails, should fall back to fuzzy search"""
        from src.agents.researcher_agent import ResearcherAgent

        mock_repo = MagicMock()
        mock_repo.full_name = "langchain-ai/langchain"
        mock_repo.stargazers_count = 90000
        mock_repo.language = "Python"
        mock_repo.description = "LLM framework"
        mock_repo.html_url = "https://github.com/langchain-ai/langchain"

        agent = MagicMock()
        agent.github_tool.get_repo_info.side_effect = RuntimeError("Not found")
        agent.github_tool.search_repositories.return_value = [mock_repo]

        result = ResearcherAgent._resolve_repo_by_name(agent, "langchain")
        assert result is not None
        assert "langchain-ai/langchain" in result
        assert "匹配" in result  # Should indicate fuzzy match

    def test_no_results_returns_none(self):
        """When both exact and fuzzy fail, return None"""
        from src.agents.researcher_agent import ResearcherAgent

        agent = MagicMock()
        agent.github_tool.get_repo_info.side_effect = RuntimeError("Not found")
        agent.github_tool.search_repositories.return_value = []

        result = ResearcherAgent._resolve_repo_by_name(agent, "nonexistentproject12345")
        assert result is None


# ============================================================
# 3. Tool-Augmented Followup Handler
# ============================================================

class TestToolAugmentedFollowup:
    """Test _resolve_repo_query in ReportGenerator"""

    def test_resolve_owner_repo_in_followup(self):
        """'langchain/langchain的star数' should resolve to repo data"""
        from src.workflows.report_generator import ReportGenerator

        mock_repo_info = MagicMock()
        mock_repo_info.full_name = "langchain-ai/langchain"
        mock_repo_info.stargazers_count = 90000
        mock_repo_info.forks_count = 20000
        mock_repo_info.language = "Python"
        mock_repo_info.description = "LLM framework"
        mock_repo_info.html_url = "https://github.com/langchain-ai/langchain"

        gen = MagicMock()
        gen.analyst.github_tool.get_repo_info.return_value = mock_repo_info

        result = ReportGenerator._resolve_repo_query(gen, "langchain/langchain的star数是多少")
        assert result is not None
        assert "langchain-ai/langchain" in result
        assert "90,000" in result
        gen.analyst.github_tool.get_repo_info.assert_called_once()

    def test_resolve_project_name_in_followup(self):
        """'django的star多少' should search by name"""
        from src.workflows.report_generator import ReportGenerator

        mock_repo = MagicMock()
        mock_repo.full_name = "django/django"
        mock_repo.stargazers_count = 75000
        mock_repo.forks_count = 25000
        mock_repo.language = "Python"
        mock_repo.description = "Web framework"
        mock_repo.html_url = "https://github.com/django/django"

        gen = MagicMock()
        # Exact match fails
        gen.analyst.github_tool.get_repo_info.side_effect = RuntimeError("Not found")
        gen.researcher.github_tool.search_repositories.return_value = [mock_repo]

        result = ReportGenerator._resolve_repo_query(gen, "django的star是多少")
        assert result is not None
        assert "django/django" in result
        assert "matched" in result
        gen.researcher.github_tool.search_repositories.assert_called_once()

    def test_non_repo_followup_returns_none(self):
        """General questions without repo mentions should return None"""
        from src.workflows.report_generator import ReportGenerator

        gen = MagicMock()

        result = ReportGenerator._resolve_repo_query(gen, "总结一下这些项目的共同特点")
        assert result is None

    def test_empty_query_returns_none(self):
        """Empty query should return None"""
        from src.workflows.report_generator import ReportGenerator

        gen = MagicMock()

        result = ReportGenerator._resolve_repo_query(gen, "")
        assert result is None


# ============================================================
# 4. Integration: reply_to_message routing
# ============================================================

class TestReplyToMessageRouting:
    """Test that reply_to_message correctly routes repo lookups"""

    def test_repo_name_bypasses_intent_understanding(self):
        """Repo lookup should resolve before calling _understand_intent"""
        from src.agents.researcher_agent import ResearcherAgent

        mock_repo_info = MagicMock()
        mock_repo_info.full_name = "django/django"
        mock_repo_info.stargazers_count = 75000
        mock_repo_info.forks_count = 25000
        mock_repo_info.language = "Python"
        mock_repo_info.description = "Web framework for perfectionists"
        mock_repo_info.html_url = "https://github.com/django/django"

        with patch.object(ResearcherAgent, '__init__', lambda self, **kw: None):
            agent = ResearcherAgent.__new__(ResearcherAgent)
            agent.github_tool = MagicMock()
            agent.github_tool.get_repo_info.return_value = mock_repo_info
            agent.github_tool.search_repositories.return_value = [mock_repo_info]

        # _is_repo_lookup_query should detect "django" from the query
        # _resolve_repo_by_name should return the repo info
        result = agent.reply_to_message("django的star数是多少")
        assert "django/django" in result
        assert "75,000" in result
        # get_repo_info should have been called (fuzzy search path)
        agent.github_tool.search_repositories.assert_called()

    def test_search_query_still_uses_intent(self):
        """General search should go through intent understanding"""
        from src.agents.researcher_agent import ResearcherAgent

        with patch.object(ResearcherAgent, '__init__', lambda self, **kw: None):
            agent = ResearcherAgent.__new__(ResearcherAgent)
            agent.github_tool = MagicMock()

        # This should NOT match repo lookup patterns
        detected = agent._is_repo_lookup_query("搜索最火的AI框架")
        assert detected is None


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
