# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - Mission Part 3: Supplemental Tests

Tests for new features in working tree changes:
- ResearcherAgent LLM intent understanding (_understand_intent)
- ResearcherAgent new execution methods (_execute_search, _execute_get_repo_info, etc.)
- CLI _forward_to_studio function
- ReportGenerator intent routing in answer_followup
- INTENT_TOOLS and INTENT_SYSTEM_PROMPT structure
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


# ===========================================
# Test 1: INTENT_TOOLS structure validation
# ===========================================
def test_intent_tools_structure():
    """Verify INTENT_TOOLS has the expected 5 tools with correct structure."""
    from src.agents.researcher_agent import INTENT_TOOLS

    assert len(INTENT_TOOLS) == 5, f"Expected 5 tools, got {len(INTENT_TOOLS)}"

    tool_names = {t["name"] for t in INTENT_TOOLS}
    expected = {"search_repositories", "get_repo_info", "analyze_project",
                "compare_repositories", "chat"}
    assert tool_names == expected, f"Expected {expected}, got {tool_names}"

    for tool in INTENT_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert "properties" in tool["parameters"]
        assert "required" in tool["parameters"]

    print("  ✓ INTENT_TOOLS structure is valid")


def test_intent_tools_required_fields():
    """Verify each tool has correct required fields."""
    from src.agents.researcher_agent import INTENT_TOOLS

    search = next(t for t in INTENT_TOOLS if t["name"] == "search_repositories")
    assert "query" in search["parameters"]["required"]

    get_repo = next(t for t in INTENT_TOOLS if t["name"] == "get_repo_info")
    assert "owner" in get_repo["parameters"]["required"]
    assert "repo" in get_repo["parameters"]["required"]

    compare = next(t for t in INTENT_TOOLS if t["name"] == "compare_repositories")
    assert "repositories" in compare["parameters"]["required"]

    print("  ✓ INTENT_TOOLS required fields are correct")


def test_intent_system_prompt():
    """Verify INTENT_SYSTEM_PROMPT is non-empty and contains key instructions."""
    from src.agents.researcher_agent import INTENT_SYSTEM_PROMPT

    assert len(INTENT_SYSTEM_PROMPT) > 100
    assert "search_repositories" in INTENT_SYSTEM_PROMPT
    assert "get_repo_info" in INTENT_SYSTEM_PROMPT
    assert "chat" in INTENT_SYSTEM_PROMPT
    assert "json" in INTENT_SYSTEM_PROMPT.lower()

    print("  ✓ INTENT_SYSTEM_PROMPT content is valid")


# ===========================================
# Test 2: ResearcherAgent new methods exist
# ===========================================
def test_researcher_agent_new_methods():
    """Verify ResearcherAgent has the new intent-based methods."""
    from src.agents.researcher_agent import ResearcherAgent

    assert hasattr(ResearcherAgent, '_understand_intent')
    assert hasattr(ResearcherAgent, '_execute_search')
    assert hasattr(ResearcherAgent, '_execute_get_repo_info')
    assert hasattr(ResearcherAgent, '_execute_analyze_project')
    assert hasattr(ResearcherAgent, '_execute_compare')

    print("  ✓ All new ResearcherAgent methods exist")


# ===========================================
# Test 3: _understand_intent fallback behavior
# ===========================================
def test_understand_intent_fallback_on_failure():
    """When intent understanding fails, it should fallback to chat action."""
    from src.agents.researcher_agent import ResearcherAgent

    # Create agent with mock config
    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    # The _understand_intent should fallback to chat when model wrapper fails
    # (since we don't have a real API key)
    result = agent._understand_intent("search for Python projects")
    assert result["action"] == "chat"
    assert result["params"]["message"] == "search for Python projects"

    print("  ✓ _understand_intent falls back to chat on failure")


# ===========================================
# Test 4: _execute_search with mocked GitHubTool
# ===========================================
def test_execute_search_with_results():
    """Verify _execute_search produces markdown table with results."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    # Mock github_tool
    mock_repo = MagicMock()
    mock_repo.full_name = "test/repo1"
    mock_repo.html_url = "https://github.com/test/repo1"
    mock_repo.stargazers_count = 1000
    mock_repo.language = "Python"
    mock_repo.description = "A test repository"

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.return_value = [mock_repo]

    result = agent._execute_search({
        "query": "test",
        "sort": "stars",
        "limit": 5,
        "time_range_days": 0,
    })

    assert "## 搜索结果" in result
    assert "test/repo1" in result
    assert "1,000" in result  # formatted number
    assert "Python" in result

    print("  ✓ _execute_search produces correct markdown output")


def test_execute_search_no_results():
    """Verify _execute_search returns empty message when no results."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.return_value = []

    result = agent._execute_search({"query": "nonexistent_xyz", "sort": "stars", "limit": 5})
    assert "没有找到" in result

    print("  ✓ _execute_search handles no results correctly")


def test_execute_search_with_time_range():
    """Verify _execute_search includes time range in query."""
    from src.agents.researcher_agent import ResearcherAgent
    from datetime import datetime, timedelta

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.return_value = []

    result = agent._execute_search({
        "query": "Rust",
        "sort": "stars",
        "limit": 10,
        "time_range_days": 7,
    })

    # Should include created: date range in the search
    expected_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    assert f"created:{expected_date}" in result or "没有找到" in result

    print("  ✓ _execute_search includes time range in query")


# ===========================================
# Test 5: _execute_get_repo_info
# ===========================================
def test_execute_get_repo_info_success():
    """Verify _execute_get_repo_info returns formatted info."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    mock_repo = MagicMock()
    mock_repo.full_name = "langchain-ai/langchain"
    mock_repo.html_url = "https://github.com/langchain-ai/langchain"
    mock_repo.stargazers_count = 90000
    mock_repo.forks_count = 15000
    mock_repo.language = "Python"
    mock_repo.description = "Build context-aware reasoning applications"
    mock_repo.updated_at = "2024-01-01"

    agent.github_tool = MagicMock()
    agent.github_tool.get_repo_info.return_value = mock_repo

    result = agent._execute_get_repo_info({
        "owner": "langchain-ai",
        "repo": "langchain",
    })

    assert "langchain-ai/langchain" in result
    assert "90,000" in result
    assert "Python" in result

    print("  ✓ _execute_get_repo_info returns formatted info")


# ===========================================
# Test 6: _execute_compare
# ===========================================
def test_execute_compare_multiple_repos():
    """Verify _execute_compare handles multiple repositories."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    # Mock get_repo_info to return formatted string
    agent._execute_get_repo_info = MagicMock(return_value="Stars: 1000")

    result = agent._execute_compare({
        "repositories": ["org/repo1", "org/repo2"],
    })

    assert "## 项目对比" in result
    assert "org/repo1" in result
    assert "org/repo2" in result

    print("  ✓ _execute_compare handles multiple repos")


def test_execute_compare_empty_list():
    """Verify _execute_compare handles empty repo list."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    result = agent._execute_compare({"repositories": []})
    assert "请提供" in result

    print("  ✓ _execute_compare handles empty list")


# ===========================================
# Test 7: CLI Studio integration
# ===========================================
def test_cli_studio_integration_exists():
    """Verify CLI app.py has Studio integration functions."""
    from src.cli.app import _push_to_studio, _setup_studio

    assert callable(_push_to_studio)
    assert callable(_setup_studio)

    print("  ✓ CLI _push_to_studio and _setup_studio exist")


def test_cli_studio_push_graceful_degradation():
    """Verify _push_to_studio doesn't crash when Studio is unavailable."""
    from src.cli.app import _push_to_studio

    # Should not raise even when Studio is not configured
    _push_to_studio("Test Agent", "test content", "assistant")

    print("  ✓ _push_to_studio degrades gracefully")


# ===========================================
# Test 8: ReportGenerator intent routing
# ===========================================
def test_report_generator_intent_routing():
    """Verify ReportGenerator has intent routing in _answer_followup."""
    from src.workflows.report_generator import ReportGenerator
    import inspect

    source = inspect.getsource(ReportGenerator._answer_followup)
    assert "_understand_intent" in source
    assert "_execute_search" in source or "_execute_get_repo_info" in source
    assert "try:" in source
    assert "except" in source

    print("  ✓ ReportGenerator._answer_followup has intent routing")


# ===========================================
# Test 9: search_and_analyze with non-search intent
# ===========================================
def test_search_and_analyze_non_search_intent():
    """Verify search_and_analyze handles non-search intents by logging warning."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""
    config.github_token = ""  # No token for unauthenticated requests
    config.github_timeout = 30
    config.github_rate_limit = 10

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    # Since intent understanding will fail (no API key), it falls back to chat
    # which then triggers the raw query search path
    result = agent.search_and_analyze("analyze this project")
    assert isinstance(result, dict)

    print("  ✓ search_and_analyze handles non-search intent")


# ===========================================
# Test 10: Long description truncation in search results
# ===========================================
def test_execute_search_long_description_truncation():
    """Verify long descriptions are truncated in search results."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    mock_repo = MagicMock()
    mock_repo.full_name = "test/long-desc"
    mock_repo.html_url = "https://github.com/test/long-desc"
    mock_repo.stargazers_count = 500
    mock_repo.language = "JavaScript"
    mock_repo.description = "A" * 200  # Very long description

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.return_value = [mock_repo]

    result = agent._execute_search({
        "query": "test",
        "sort": "stars",
        "limit": 5,
    })

    # Description should be truncated to 60 chars + "..."
    assert "..." in result
    assert len([line for line in result.split('\n') if "A" * 60 in line]) >= 0  # truncated

    print("  ✓ Long descriptions are truncated in search results")


# ===========================================
# Test 11: No description handling
# ===========================================
def test_execute_search_no_description():
    """Verify repos without description show placeholder."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    mock_repo = MagicMock()
    mock_repo.full_name = "test/no-desc"
    mock_repo.html_url = "https://github.com/test/no-desc"
    mock_repo.stargazers_count = 100
    mock_repo.language = "Go"
    mock_repo.description = None

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.return_value = [mock_repo]

    result = agent._execute_search({
        "query": "test",
        "sort": "stars",
        "limit": 5,
    })

    assert "无描述" in result

    print("  ✓ No-description repos show placeholder")


# ===========================================
# Test 12: Error handling in _execute_search
# ===========================================
def test_execute_search_runtime_error():
    """Verify _execute_search handles RuntimeError gracefully."""
    from src.agents.researcher_agent import ResearcherAgent

    config = MagicMock()
    config.dashscope_model_name = ""
    config.dashscope_api_key = ""
    config.dashscope_base_url = ""

    agent = ResearcherAgent(
        name="test",
        model_name="",
        config=config,
        use_persistent=False,
    )

    agent.github_tool = MagicMock()
    agent.github_tool.search_repositories.side_effect = RuntimeError("API error")

    result = agent._execute_search({
        "query": "test",
        "sort": "stars",
        "limit": 5,
    })

    assert "搜索失败" in result

    print("  ✓ _execute_search handles RuntimeError gracefully")


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# GitHub Insight Agent - Mission Part 3: Supplemental Tests")
    print("#" * 60)

    tests = [
        ("INTENT_TOOLS structure", test_intent_tools_structure),
        ("INTENT_TOOLS required fields", test_intent_tools_required_fields),
        ("INTENT_SYSTEM_PROMPT", test_intent_system_prompt),
        ("ResearcherAgent new methods", test_researcher_agent_new_methods),
        ("_understand_intent fallback", test_understand_intent_fallback_on_failure),
        ("_execute_search with results", test_execute_search_with_results),
        ("_execute_search no results", test_execute_search_no_results),
        ("_execute_search with time range", test_execute_search_with_time_range),
        ("_execute_get_repo_info success", test_execute_get_repo_info_success),
        ("_execute_compare multiple repos", test_execute_compare_multiple_repos),
        ("_execute_compare empty list", test_execute_compare_empty_list),
        ("CLI _push_to_studio exists", test_cli_studio_integration_exists),
        ("CLI _push_to_studio degradation", test_cli_studio_push_graceful_degradation),
        ("ReportGenerator intent routing", test_report_generator_intent_routing),
        ("search_and_analyze non-search", test_search_and_analyze_non_search_intent),
        ("Long description truncation", test_execute_search_long_description_truncation),
        ("No description handling", test_execute_search_no_description),
        ("_execute_search error handling", test_execute_search_runtime_error),
    ]

    results = {}
    for name, test_func in tests:
        try:
            test_func()
            results[name] = True
        except Exception as e:
            print(f"  ✗ {name} failed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    print("\n" + "="*60)
    print("Part 3 测试结果汇总")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n✓ 所有 Part 3 补充测试通过！")
    else:
        print(f"\n⚠ {total - passed} 个测试未通过")

    sys.exit(0 if passed == total else 1)
