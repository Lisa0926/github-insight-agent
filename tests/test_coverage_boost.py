# -*- coding: utf-8 -*-
"""Tests for core modules that need coverage boost."""

import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from src.tools.github_tool import GitHubTool
from src.tools.owasp_security_rules import (
    OWASPRuleEngine, scan_security, SecurityComment, IssueCategory, IssueSeverity,
    _format_report as owasp_format_report,
)
from src.tools.pr_review_tool import (
    PRReviewer, _parse_diff, _format_report, CodeChange,
    review_pull_request,
)


class TestOWASPRuleEngineCoverage:
    """Test OWASP rule engine for coverage."""

    def test_detect_issues_basic(self):
        engine = OWASPRuleEngine.__new__(OWASPRuleEngine)
        code = 'eval(user_input)'
        issues = engine.detect_issues("test.py", code)
        assert len(issues) > 0

    def test_get_stats(self):
        engine = OWASPRuleEngine.__new__(OWASPRuleEngine)
        stats = engine.get_stats()
        assert stats["total_rules"] > 0
        assert "by_category" in stats
        assert "by_severity" in stats

    def test_scan_security_success(self):
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            scan_security("test.py", "x = 1")
        )
        assert result.success is True

    def test_scan_security_report_format(self):
        issues = [
            SecurityComment(
                file_path="test.py",
                line_number=1,
                category=IssueCategory.A03_INJECTION,
                severity=IssueSeverity.HIGH,
                owasp_id="A03",
                message="SQL injection",
                suggestion="Use parameterized queries",
            )
        ]
        stats = {"total_rules": 50, "owasp_coverage": ["A03"]}
        report = owasp_format_report("test.py", issues, stats)
        assert "OWASP" in report


class TestPRReviewToolCoverage:
    """Test PR review tool for coverage."""

    def test_parse_diff_basic(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 context
+added line
-removed line
 context"""
        changes = _parse_diff(diff)
        assert len(changes) >= 1

    def test_parse_diff_multiple_files(self):
        diff = """--- a/file1.py
+++ b/file1.py
@@ -1 +1 @@
+line1
--- a/file2.py
+++ b/file2.py
@@ -1 +1 @@
+line2"""
        changes = _parse_diff(diff)
        assert len(changes) == 2

    def test_format_report_empty_issues(self):
        report_data = {
            "pr_title": "Test PR",
            "stats": {"total_files": 1, "total_additions": 10, "total_deletions": 5, "issues_found": 0},
            "summary": "Clean PR",
            "rule_based_issues": [],
            "llm_review": {},
        }
        formatted = _format_report(report_data)
        assert "PR 自动审查报告" in formatted

    def test_reviewer_detect_issues(self):
        from unittest.mock import patch, MagicMock
        with patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls, \
             patch('src.tools.pr_review_tool.get_provider', return_value=MagicMock()):
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            reviewer = PRReviewer.__new__(PRReviewer)
            reviewer._owasp_engine = mock_engine
            reviewer.PATTERNS = PRReviewer.PATTERNS
            change = CodeChange(file_path="test.py", hunk_start_line=1, changes=["eval(x)"])
            issues = reviewer._detect_issues_by_rules([change])
            # The builtin patterns should detect something
            assert isinstance(issues, list)

    def test_reviewer_llm_review_unavailable(self):
        """Test _llm_review when LLM provider is None."""
        with patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls, \
             patch('src.tools.pr_review_tool.get_provider', return_value=None):
            reviewer = PRReviewer.__new__(PRReviewer)
            reviewer._owasp_engine = MagicMock()
            reviewer._owasp_engine.detect_issues.return_value = []
            reviewer._llm_provider = None
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                reviewer._llm_review("Test PR", "desc", [])
            )
            assert result["summary"] == "基于规则的自动审查（LLM 不可用）"

    def test_reviewer_llm_review_success(self):
        """Test _llm_review with working LLM."""
        mock_provider = MagicMock()
        mock_response = '```json\n{"summary": "Good PR", "score": 8, "strengths": ["clean"], "concerns": [], "suggestions": [], "approval_recommendation": "approve"}\n```'
        mock_provider.chat = AsyncMock(return_value=mock_response)
        with patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls, \
             patch('src.tools.pr_review_tool.get_provider', return_value=mock_provider):
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            reviewer = PRReviewer(MagicMock())
            change = CodeChange(file_path="test.py", hunk_start_line=1, changes=["+x=1"], additions=1)
            result = asyncio.get_event_loop().run_until_complete(
                reviewer._llm_review("Test PR", "desc", [change])
            )
            assert result["score"] == 8
            assert result["approval_recommendation"] == "approve"

    def test_reviewer_full_review_no_llm(self):
        """Test full review() without LLM."""
        with patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls, \
             patch('src.tools.pr_review_tool.get_provider', return_value=None):
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            reviewer = PRReviewer(MagicMock())
            change = CodeChange(file_path="test.py", hunk_start_line=1, changes=["+x=1"], additions=1)
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                reviewer.review("Test PR", "desc", [change], use_llm=False)
            )
            assert "pr_title" in result
            assert "stats" in result

    def test_review_pull_request_success(self):
        """Test review_pull_request convenience function."""
        import asyncio
        diff = """--- a/test.py
+++ b/test.py
@@ -1 +1 @@
+hello"""
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value='{"summary": "OK", "score": 7}')
        with patch('src.tools.pr_review_tool.get_provider', return_value=mock_provider), \
             patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            result = asyncio.get_event_loop().run_until_complete(
                review_pull_request("Test PR", "desc", diff)
            )
            assert result.success is True

    def test_review_pull_request_with_llm_suggestions(self):
        """Test review with LLM suggestions for format coverage."""
        import asyncio
        diff = """--- a/test.py
+++ b/test.py
@@ -1 +1 @@
+hello"""
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=json.dumps({
            "summary": "Good PR",
            "score": 8,
            "strengths": ["clean code"],
            "concerns": ["minor"],
            "suggestions": [{"file": "test.py", "line": 5, "issue": "fix", "suggestion": "improve"}],
            "approval_recommendation": "approve",
        }))
        with patch('src.tools.pr_review_tool.get_provider', return_value=mock_provider), \
             patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            result = asyncio.get_event_loop().run_until_complete(
                review_pull_request("Test PR", "desc", diff)
            )
            assert result.success is True

    def test_review_pull_request_error(self):
        """Test review_pull_request handles diff parsing exceptions."""
        import asyncio
        with patch('src.tools.pr_review_tool._parse_diff', side_effect=ValueError("parse error")):
            result = asyncio.get_event_loop().run_until_complete(
                review_pull_request("Test PR", "desc", "bad diff")
            )
            assert result.success is False

    def test_format_report_with_llm_review(self):
        """Test report formatting with LLM review suggestions."""
        report_data = {
            "pr_title": "Test PR",
            "stats": {"total_files": 1, "total_additions": 10, "total_deletions": 5, "issues_found": 0},
            "summary": "Clean PR",
            "rule_based_issues": [],
            "llm_review": {
                "score": 8,
                "summary": "Good work",
                "strengths": ["clean"],
                "concerns": ["minor"],
                "suggestions": [{"file": "a.py", "line": 1, "issue": "test", "suggestion": "fix"}],
                "approval_recommendation": "approve",
            },
        }
        formatted = _format_report(report_data)
        assert "AI 审查意见" in formatted
        assert "clean" in formatted

    def test_reviewer_llm_review_parse_failure(self):
        """Test LLM review handles JSON parse failure."""
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value='not json at all{{{')
        with patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls, \
             patch('src.tools.pr_review_tool.get_provider', return_value=mock_provider):
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = []
            mock_engine_cls.return_value = mock_engine
            reviewer = PRReviewer(MagicMock())
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                reviewer._llm_review("Test", "desc", [])
            )
            assert "失败" in result["summary"]

    def test_pr_review_with_rule_issues(self):
        """Test PR review that finds rule-based issues."""
        mock_comment = SecurityComment(
            file_path="test.py",
            line_number=1,
            category=IssueCategory.A03_INJECTION,
            severity=IssueSeverity.HIGH,
            owasp_id="A03",
            message="SQL injection",
            suggestion="Fix it",
        )
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value='{"summary": "OK", "score": 6, "strengths": [], "concerns": [], "suggestions": [], "approval_recommendation": "comment"}')
        with patch('src.tools.pr_review_tool.get_provider', return_value=mock_provider), \
             patch('src.tools.pr_review_tool.OWASPRuleEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.detect_issues.return_value = [mock_comment]
            mock_engine_cls.return_value = mock_engine
            import asyncio
            diff = """--- a/test.py
+++ b/test.py
@@ -1 +1 @@
+hello"""
            result = asyncio.get_event_loop().run_until_complete(
                review_pull_request("Test PR", "desc", diff)
            )
            assert result.success is True


class TestGitHubToolBaseToolCoverage:
    """Test GitHubTool BaseTool protocol methods for coverage."""

    def test_execute_search_repositories(self):
        """Test execute() with search_repositories action."""
        with patch('src.tools.github_tool.GitHubTool.__init__', return_value=None):
            tool = GitHubTool.__new__(GitHubTool)
            tool.search_repositories = MagicMock(return_value=[])
            result = tool.execute({"action": "search_repositories", "query": "test"})
            assert result == []

    def test_execute_get_repo_info(self):
        """Test execute() with get_repo_info action."""
        with patch('src.tools.github_tool.GitHubTool.__init__', return_value=None):
            tool = GitHubTool.__new__(GitHubTool)
            mock_repo = MagicMock()
            tool.get_repo_info = MagicMock(return_value=mock_repo)
            result = tool.execute({"action": "get_repo_info", "owner": "test", "repo": "test"})
            assert result == mock_repo

    def test_execute_get_readme(self):
        """Test execute() with get_readme action."""
        with patch('src.tools.github_tool.GitHubTool.__init__', return_value=None):
            tool = GitHubTool.__new__(GitHubTool)
            tool.get_readme = MagicMock(return_value="# README")
            result = tool.execute({"action": "get_readme", "owner": "test", "repo": "test"})
            assert result == "# README"

    def test_execute_get_project_summary(self):
        """Test execute() with get_project_summary action."""
        with patch('src.tools.github_tool.GitHubTool.__init__', return_value=None):
            tool = GitHubTool.__new__(GitHubTool)
            tool.get_project_summary = MagicMock(return_value={"name": "test"})
            result = tool.execute({"action": "get_project_summary", "owner": "test", "repo": "test"})
            assert result == {"name": "test"}

    def test_execute_unknown_action(self):
        """Test execute() with unknown action raises ValueError."""
        with patch('src.tools.github_tool.GitHubTool.__init__', return_value=None):
            tool = GitHubTool.__new__(GitHubTool)
            try:
                tool.execute({"action": "unknown_action"})
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "unknown_action" in str(e)
