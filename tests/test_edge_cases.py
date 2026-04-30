# -*- coding: utf-8 -*-
"""
Edge case and resilience tests

Tests scenarios that occur in production but are hard to reproduce:
1. Network failures (ConnectionError, Timeout, 5xx)
2. API rate limits (429 with Retry-After, exhausted retries)
3. Empty/missing search results
4. Archived and private repository handling
5. Input boundary conditions (max length, special characters)
6. Circuit breaker integration
7. Output filtering edge cases (chained patterns, encoding)
"""

import os
import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import requests


# ============================================================
# 1. Network Failure Scenarios
# ============================================================

class TestNetworkFailures:
    """Test network-level failures"""

    def test_connection_error_propagated(self):
        """ConnectionError should propagate after retries exhausted"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            tool.RETRY_DELAY = 0

            with patch.object(tool._http_client._session, 'request',
                              side_effect=requests.exceptions.ConnectionError("Connection refused")):
                with pytest.raises(RuntimeError):
                    tool.get_repo_info("owner", "repo")

    def test_timeout_propagated(self):
        """Timeout should propagate after retries exhausted"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            tool.RETRY_DELAY = 0

            with patch.object(tool._http_client._session, 'request',
                              side_effect=requests.exceptions.Timeout("Read timeout")):
                with pytest.raises(RuntimeError):
                    tool.get_repo_info("owner", "repo")

    def test_502_bad_gateway(self):
        """502 should be retried via tenacity, then raise RuntimeError"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            tool.RETRY_DELAY = 0

            call_count = 0

            def mock_request(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                resp = MagicMock()
                resp.status_code = 502
                return resp

            with patch.object(tool._http_client._session, 'request', side_effect=mock_request):
                with pytest.raises(RuntimeError):
                    tool.get_repo_info("owner", "repo")

    def test_503_unavailable(self):
        """503 should be retried, then raise RuntimeError"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            tool.RETRY_DELAY = 0

            resp = MagicMock()
            resp.status_code = 503

            with patch.object(tool._http_client._session, 'request', return_value=resp):
                with pytest.raises(RuntimeError):
                    tool.get_repo_info("owner", "repo")

    def test_504_gateway_timeout(self):
        """504 should be retried"""
        from src.tools.github_tool import GitHubTool

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            tool = GitHubTool()
            tool.RETRY_DELAY = 0

            resp = MagicMock()
            resp.status_code = 504

            with patch.object(tool._http_client._session, 'request', return_value=resp):
                with pytest.raises(RuntimeError):
                    tool.search_repositories("test")


# ============================================================
# 2. API Rate Limit Scenarios
# ============================================================

class TestRateLimitScenarios:
    """Test rate limiting behavior"""

    def test_429_with_retry_after_header(self):
        """429 with Retry-After should raise RateLimitError"""
        from src.core.resilient_http import ResilientHTTPClient, RateLimitError

        client = ResilientHTTPClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "60"}

        with pytest.raises(RateLimitError) as excinfo:
            client._handle_rate_limit(mock_resp)

        assert excinfo.value.retry_after == 60
        assert "60" in str(excinfo.value)

    def test_429_without_retry_after_header(self):
        """429 without Retry-After should still raise RateLimitError"""
        from src.core.resilient_http import ResilientHTTPClient, RateLimitError

        client = ResilientHTTPClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}

        with pytest.raises(RateLimitError):
            client._handle_rate_limit(mock_resp)


# ============================================================
# 3. Empty/Missing Data Scenarios
# ============================================================

class TestDataBoundaries:
    """Test empty and boundary data scenarios"""

    def test_search_result_no_language(self):
        """Repo with null language should default to empty string"""
        from src.types.schemas import GitHubRepo

        repo = GitHubRepo.from_api_response({
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
            "language": None,
        })
        assert repo.language == ""

    def test_search_result_no_topics(self):
        """Repo with null topics should default to empty list"""
        from src.types.schemas import GitHubRepo

        repo = GitHubRepo.from_api_response({
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
            "topics": None,
        })
        assert repo.topics == []

    def test_search_result_no_description(self):
        """Repo with null description should default to empty string"""
        from src.types.schemas import GitHubRepo

        repo = GitHubRepo.from_api_response({
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
            "description": None,
        })
        assert repo.description == ""

    def test_search_result_is_fork(self):
        """Repo marked as fork"""
        from src.types.schemas import GitHubRepo

        repo = GitHubRepo.from_api_response({
            "full_name": "fork-owner/repo",
            "html_url": "https://github.com/fork-owner/repo",
            "fork": True,
        })
        assert repo.is_fork is True

    def test_search_result_is_archived(self):
        """Repo marked as archived"""
        from src.types.schemas import GitHubRepo

        repo = GitHubRepo.from_api_response({
            "full_name": "owner/old-repo",
            "html_url": "https://github.com/owner/old-repo",
            "archived": True,
        })
        assert repo.is_archived is True

    def test_search_result_empty_items_markdown(self):
        """Empty items should show 'No results found' in markdown"""
        from src.types.schemas import GitHubSearchResult

        result = GitHubSearchResult(total_count=0, items=[])
        md = result.to_markdown_table()
        assert "No results found" in md

    def test_search_result_markdown_truncation(self):
        """Long descriptions should be truncated in markdown table"""
        from src.types.schemas import GitHubSearchResult, GitHubRepo

        result = GitHubSearchResult(
            total_count=1,
            items=[
                GitHubRepo(
                    full_name="owner/repo",
                    html_url="https://github.com/owner/repo",
                    stargazers_count=100,
                    language="Python",
                    description="A" * 100,
                )
            ],
        )
        md = result.to_markdown_table()
        assert "..." in md
        assert len(md) < 500  # Should not be excessively long


# ============================================================
# 4. Input Boundary Conditions
# ============================================================

class TestInputBoundaries:
    """Test input boundary conditions"""

    def test_empty_input_sanitization(self):
        """Empty input should return empty string"""
        from src.core.guardrails import sanitize_user_input

        assert sanitize_user_input("") == ""
        assert sanitize_user_input(None) == ""

    def test_max_length_input(self):
        """Input exceeding max_length should be truncated"""
        from src.core.guardrails import sanitize_user_input

        long_input = "x" * 10000
        result = sanitize_user_input(long_input)
        assert len(result) == 4000  # default MAX_USER_INPUT_LENGTH

    def test_control_characters_removed(self):
        """Control characters (null, bell, etc.) should be removed"""
        from src.core.guardrails import sanitize_user_input

        result = sanitize_user_input("Hello\x00\x01\x02World\x7f")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x7f" not in result

    def test_special_char_threshold(self):
        """Excessive special chars should be blocked"""
        from src.core.guardrails import sanitize_user_input

        # 10+ consecutive special chars
        with pytest.raises(ValueError):
            sanitize_user_input("!!@@##$$%%^^&&**")

    def test_whitespace_only_input(self):
        """Whitespace-only input should pass through"""
        from src.core.guardrails import sanitize_user_input

        result = sanitize_user_input("   \t\n  ")
        assert result.strip() == "" or result == "   \t\n  "


# ============================================================
# 5. Circuit Breaker Integration Tests
# ============================================================

class TestCircuitBreakerIntegration:
    """Test circuit breaker in workflow context"""

    def test_circuit_breaker_starts_fresh(self):
        """Each start_session should reset counters"""
        from src.core.guardrails import AgentCircuitBreaker

        cb = AgentCircuitBreaker(max_steps=1, max_time_seconds=100, max_tokens=1000)
        cb.start_session()
        cb.record_step()
        cb._open = True

        cb.start_session()
        assert cb._open is False
        assert cb._step_count == 0

    def test_circuit_breaker_token_tracking(self):
        """Token counting should work independently of steps"""
        from src.core.guardrails import AgentCircuitBreaker

        cb = AgentCircuitBreaker(max_steps=100, max_time_seconds=100, max_tokens=100)
        cb.start_session()
        cb.record_tokens(50)
        cb.record_tokens(49)
        assert cb._token_count == 99

        cb.record_tokens(5)
        assert cb._token_count == 104  # Just tracking, doesn't trip on its own

    def test_circuit_breaker_elapsed_time(self):
        """Elapsed time should be measurable"""
        import time
        from src.core.guardrails import AgentCircuitBreaker

        cb = AgentCircuitBreaker(max_steps=100, max_time_seconds=100, max_tokens=1000)
        cb.start_session()
        time.sleep(0.05)
        assert cb.elapsed_time >= 0.05

    def test_circuit_breaker_state_dict(self):
        """get_state should return all required fields"""
        from src.core.guardrails import get_circuit_breaker

        cb = get_circuit_breaker(max_steps=10, max_time_seconds=60, max_tokens=2000)
        cb.start_session()

        state = cb.get_state()
        assert "steps" in state
        assert "max_steps" in state
        assert "elapsed" in state
        assert "max_time" in state
        assert "tokens" in state
        assert "max_tokens" in state
        assert "open" in state
        assert "reason" in state


# ============================================================
# 6. Output Filtering Edge Cases
# ============================================================

class TestOutputFilteringEdgeCases:
    """Test output filtering with complex scenarios"""

    def test_multiple_sensitive_patterns_in_one_string(self):
        """Multiple sensitive items should all be redacted"""
        from src.core.guardrails import filter_sensitive_output

        text = (
            "api_key = 'sk_test1234567890abcdef1234567890abcdef' "
            "token = 'ghp_" + "a" * 25 + "' "
            "AWS: AKIA1234567890ABCDEF"
        )
        result = filter_sensitive_output(text)
        assert "AKIA1234" not in result
        assert "[REDACTED_AWS_KEY]" in result

    def test_empty_output(self):
        """Empty output should return empty string"""
        from src.core.guardrails import filter_sensitive_output

        assert filter_sensitive_output("") == ""
        assert filter_sensitive_output(None) == ""

    def test_no_sensitive_data_passes_through(self):
        """Normal text should be unchanged"""
        from src.core.guardrails import filter_sensitive_output

        text = "The project has 100 stars and uses Python."
        result = filter_sensitive_output(text)
        assert result == text

    def test_path_filtering(self):
        """Internal paths should be redacted"""
        from src.core.guardrails import filter_sensitive_output

        text = "Deployed to /home/testuser/app/config"
        result = filter_sensitive_output(text)
        assert "/home/" not in result
        assert "INTERNAL_PATH" in result

    def test_private_ip_filtering(self):
        """Private IP addresses should be redacted"""
        from src.core.guardrails import filter_sensitive_output

        text = "Server at 192.168.1.100:8080 is running"
        result = filter_sensitive_output(text)
        assert "192.168.1.100" not in result
        assert "INTERNAL_URL" in result


# ============================================================
# 7. HITL Integration Tests
# ============================================================

class TestHitlIntegration:
    """Test Human-in-the-Loop integration"""

    def test_all_dangerous_tools_listed(self):
        """Verify key dangerous tools are in DANGEROUS_TOOLS set"""
        from src.core.guardrails import DANGEROUS_TOOLS

        assert "create_issue" in DANGEROUS_TOOLS
        assert "create_pull_request" in DANGEROUS_TOOLS
        assert "merge_pull_request" in DANGEROUS_TOOLS
        assert "create_repository" in DANGEROUS_TOOLS

    def test_all_safe_tools_not_in_dangerous(self):
        """Verify key safe tools are NOT in DANGEROUS_TOOLS"""
        from src.core.guardrails import DANGEROUS_TOOLS

        assert "search_repositories" not in DANGEROUS_TOOLS
        assert "get_repo_info" not in DANGEROUS_TOOLS
        assert "get_readme" not in DANGEROUS_TOOLS

    def test_approval_manager_denied_tracking(self):
        """Denied operations should be tracked"""
        from src.core.guardrails import HumanApprovalManager

        mgr = HumanApprovalManager(auto_approve=False)
        mgr.request_approval("create_issue", {"title": "test"})
        denied = mgr.get_denied()
        assert len(denied) == 1

    def test_approval_manager_approved_tracking(self):
        """Approved operations should be recorded"""
        from src.core.guardrails import HumanApprovalManager

        mgr = HumanApprovalManager(auto_approve=False)
        mgr.request_approval("search_repositories", {"query": "test"})
        # Safe tools don't get added to denied list
        denied = mgr.get_denied()
        assert len(denied) == 0


# ============================================================
# 8. Trend Score Edge Cases
# ============================================================

class TestTrendScoreEdges:
    """Test trend score calculation edge cases"""

    def test_trend_score_zero_stars(self):
        """Repo with 0 stars should have low trend score"""
        from unittest.mock import MagicMock
        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()
            mock_repo = MagicMock()
            mock_repo.stargazers_count = 0
            mock_repo.forks_count = 0
            mock_repo.topics = []
            mock_repo.language = ""
            mock_repo.watchers_count = 0

            score = agent._calculate_trend_score(mock_repo)
            assert score == 0.0

    def test_trend_score_high_stars(self):
        """Repo with 100k stars should have high trend score"""
        from unittest.mock import MagicMock

        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()
            mock_repo = MagicMock()
            mock_repo.stargazers_count = 100000
            mock_repo.forks_count = 20000
            mock_repo.topics = ["python", "ai", "ml", "framework"]
            mock_repo.language = "Python"
            mock_repo.watchers_count = 5000

            score = agent._calculate_trend_score(mock_repo)
            assert score >= 0.5

    def test_trend_score_exception_handling(self):
        """Invalid repo data should return 0.0, not crash"""
        from src.agents.researcher_agent import ResearcherAgent

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            agent = ResearcherAgent()
            mock_repo = MagicMock()
            mock_repo.stargazers_count = "not_a_number"

            score = agent._calculate_trend_score(mock_repo)
            assert score == 0.0


# ============================================================
# 9. Report Generator Empty Result Handling
# ============================================================

class TestReportEdgeCases:
    """Test report generator edge cases"""

    def test_empty_report_format(self):
        """Empty report should have proper structure"""
        from src.workflows.report_generator import ReportGenerator

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token", "DASHSCOPE_API_KEY": "test"}):
            from src.core.config_manager import ConfigManager
            ConfigManager._instance = None
            ConfigManager._initialized = False

            gen = ReportGenerator()
            report = gen._generate_empty_report("test query")
            assert "test query" in report
            assert "No matching projects found" in report
            assert "#" in report  # Has markdown headers

    def test_star_bar_zero(self):
        """Star bar with 0 stars should show 0%"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()
        bar = gen._generate_star_bar(0, 0)
        assert "0%" in bar

    def test_star_bar_equal(self):
        """Star bar with equal values should show 100%"""
        from src.workflows.report_generator import ReportGenerator

        gen = ReportGenerator()
        bar = gen._generate_star_bar(100, 100)
        assert "100%" in bar

    def test_format_list_empty(self):
        """Empty list should show placeholder"""
        from src.workflows.report_generator import ReportGenerator

        result = ReportGenerator._format_list([])
        assert "暂无相关信息" in result

    def test_format_list_with_items(self):
        """List with items should format each item"""
        from src.workflows.report_generator import ReportGenerator

        result = ReportGenerator._format_list(["item1", "item2"])
        assert "- item1" in result
        assert "- item2" in result


# ============================================================
# Run all tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
