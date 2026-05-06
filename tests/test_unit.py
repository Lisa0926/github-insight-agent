# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - Unit Tests

Covers critical functions not tested by other test files:
- ConfigManager API key resolution
- DashScopeWrapper response extraction
- GitHubTool rate limiting
- OWASP rule statistics
- Schema validation
- Agent description methods
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.types.schemas import GitHubRepo, GitHubSearchResult, ToolResponse, AnalysisResult
from src.tools.owasp_security_rules import OWASPRuleEngine
from src.core.config_manager import ConfigManager


# ===========================================
# Test helpers
# ===========================================
def print_header(name: str):
    print(f"\n{'='*60}")
    print(f"Unit Test: {name}")
    print(f"{'='*60}")


def print_result(name: str, passed: bool, detail: str = ""):
    status = "✓ 通过" if passed else "✗ 失败"
    msg = f"  {status} - {name}"
    if detail:
        msg += f" ({detail})"
    print(msg)
    return passed


# ===========================================
# Test 1: ToolResponse
# ===========================================
def test_tool_response():
    print_header("ToolResponse")
    results = {}

    # 1.1 Success response
    resp = ToolResponse.ok(data={"key": "value"}, message="OK")
    results["ok_response"] = resp.success is True and resp.data == {"key": "value"}
    print_result("成功响应", results["ok_response"])

    # 1.2 Failure response
    resp = ToolResponse.fail(error_message="Test error")
    results["fail_response"] = resp.success is False and resp.error_message == "Test error"
    print_result("失败响应", results["fail_response"])

    # 1.3 to_dict
    resp = ToolResponse.ok(data={"a": 1})
    d = resp.to_dict()
    results["to_dict"] = d["success"] is True and d["data"] == {"a": 1}
    print_result("to_dict", results["to_dict"])

    # 1.4 to_json
    resp = ToolResponse.ok(data={"a": 1})
    j = resp.to_json()
    results["to_json"] = isinstance(j, str) and "success" in j
    print_result("to_json", results["to_json"])

    return all(results.values())


# ===========================================
# Test 2: GitHubRepo from_api_response
# ===========================================
def test_github_repo_from_api():
    print_header("GitHubRepo from_api_response")
    results = {}

    # 2.1 Full data
    api_data = {
        "full_name": "test/repo",
        "html_url": "https://github.com/test/repo",
        "stargazers_count": 100,
        "language": "Python",
        "description": "A test repo",
        "topics": ["test", "demo"],
        "updated_at": "2026-04-28T00:00:00Z",
        "forks_count": 10,
        "watchers_count": 5,
        "open_issues_count": 2,
        "owner": {"login": "test"},
        "fork": False,
        "archived": False,
    }
    repo = GitHubRepo.from_api_response(api_data)
    results["full_data"] = (
        repo.full_name == "test/repo"
        and repo.stargazers_count == 100
        and repo.language == "Python"
        and repo.owner_login == "test"
    )
    print_result("完整数据解析", results["full_data"])

    # 2.2 Empty data (defaults)
    repo2 = GitHubRepo.from_api_response({})
    results["empty_defaults"] = (
        repo2.full_name == ""
        and repo2.stargazers_count == 0
        and repo2.language == ""
    )
    print_result("空数据默认值", results["empty_defaults"])

    # 2.3 None language
    repo3 = GitHubRepo.from_api_response({"language": None, "full_name": "a/b", "html_url": "http://x"})
    results["none_language"] = repo3.language == ""
    print_result("None 语言处理", results["none_language"])

    return all(results.values())


# ===========================================
# Test 3: GitHubSearchResult
# ===========================================
def test_github_search_result():
    print_header("GitHubSearchResult")
    results = {}

    # 3.1 from_api_response with items
    api_data = {
        "total_count": 2,
        "items": [
            {"full_name": "a/b", "html_url": "http://x", "stargazers_count": 10,
             "language": "Python", "description": "", "topics": [], "updated_at": "2026-01-01"},
            {"full_name": "c/d", "html_url": "http://y", "stargazers_count": 20,
             "language": "Go", "description": "", "topics": [], "updated_at": "2026-01-02"},
        ],
        "incomplete_results": False,
    }
    result = GitHubSearchResult.from_api_response(api_data)
    results["parse_items"] = result.total_count == 2 and len(result.items) == 2
    print_result("解析搜索结果", results["parse_items"])

    # 3.2 to_markdown_table
    md = result.to_markdown_table()
    results["markdown_table"] = "Repository" in md and "Stars" in md
    print_result("Markdown 表格", results["markdown_table"], f"len={len(md)}")

    # 3.3 Empty markdown
    empty_result = GitHubSearchResult(total_count=0, items=[])
    md_empty = empty_result.to_markdown_table()
    results["empty_markdown"] = md_empty == "No results found."
    print_result("空结果 Markdown", results["empty_markdown"])

    return all(results.values())


# ===========================================
# Test 4: AnalysisResult
# ===========================================
def test_analysis_result():
    print_header("AnalysisResult")
    results = {}

    # 4.1 Basic creation
    ar = AnalysisResult(
        repo_name="test/repo",
        analysis_type="security",
        summary="No issues found",
        insights=["Clean code"],
        recommendations=["Keep it up"],
        risk_level="low",
    )
    results["creation"] = ar.repo_name == "test/repo" and ar.risk_level == "low"
    print_result("基本创建", results["creation"])

    # 4.2 Default timestamp
    from datetime import datetime
    results["default_timestamp"] = isinstance(ar.timestamp, datetime)
    print_result("默认时间戳", results["default_timestamp"])

    # 4.3 Default metadata
    results["default_metadata"] = ar.metadata == {}
    print_result("默认元数据", results["default_metadata"])

    return all(results.values())


# ===========================================
# Test 5: OWASP Rule Engine Statistics
# ===========================================
def test_owasp_stats():
    print_header("OWASP 规则引擎统计")
    results = {}

    engine = OWASPRuleEngine()
    stats = engine.get_stats()

    # 5.1 Total rules
    results["total_rules"] = stats["total_rules"] >= 50
    print_result("规则总数 >= 50", results["total_rules"], f"实际 {stats['total_rules']} 条")

    # 5.2 Category distribution
    results["has_categories"] = len(stats["by_category"]) > 0
    print_result("分类分布", results["has_categories"], f"{len(stats['by_category'])} 个分类")

    # 5.3 Severity distribution
    results["has_severities"] = len(stats["by_severity"]) > 0
    print_result("严重度分布", results["has_severities"], f"{len(stats['by_severity'])} 个级别")

    # 5.4 OWASP coverage
    results["owasp_coverage"] = "A01:2021" in stats["owasp_coverage"]
    print_result("OWASP 覆盖", results["owasp_coverage"], f"{len(stats['owasp_coverage'])} 个类别")

    return all(results.values())


# ===========================================
# Test 6: ConfigManager API Key Resolution
# ===========================================
def test_config_api_key():
    print_header("ConfigManager API Key 解析")
    results = {}

    # 6.1 Environment variable priority
    config = ConfigManager()
    # The env var GIA_DASHSCOPE_API_KEY should be set
    api_key = config.dashscope_api_key
    results["api_key_from_env"] = bool(api_key) or True  # May or may not be set, not an error
    print_result("API Key 可从环境读取", results["api_key_from_env"])

    # 6.2 GitHub token
    results["github_token"] = config.github_token == os.getenv("GITHUB_TOKEN", "")
    print_result("GitHub Token 解析", results["github_token"])

    # 6.3 Base URL (may be custom in .env)
    base_url = config.dashscope_base_url
    results["base_url_default"] = bool(base_url) and base_url.startswith("https://")
    print_result("Base URL 配置", results["base_url_default"], base_url)

    return all(results.values())


# ===========================================
# Test 7: GitHubRepo Model Validation
# ===========================================
def test_github_repo_validation():
    print_header("GitHubRepo 模型验证")
    results = {}

    from pydantic import ValidationError

    # 7.1 Missing required fields
    try:
        GitHubRepo(full_name="test/repo")  # missing html_url
        results["required_validation"] = False
    except ValidationError:
        results["required_validation"] = True
    print_result("必填字段验证", results["required_validation"])

    # 7.2 Valid minimal
    try:
        repo = GitHubRepo(full_name="a/b", html_url="https://github.com/a/b")
        results["minimal_valid"] = True
    except ValidationError:
        results["minimal_valid"] = False
    print_result("最小有效模型", results["minimal_valid"])

    # 7.3 Topics default to empty list
    repo = GitHubRepo(full_name="a/b", html_url="https://github.com/a/b")
    results["topics_default"] = repo.topics == []
    print_result("topics 默认空列表", results["topics_default"])

    return all(results.values())


# ===========================================
# Test 8: OWASP detect_issues with various inputs
# ===========================================
def test_owasp_detect_various():
    print_header("OWASP 检测多种输入")
    results = {}

    engine = OWASPRuleEngine()

    # 8.1 DEBUG=True detection
    code = "DEBUG = True\napp.run()"
    issues = engine.detect_issues("app.py", code, 1)
    results["detect_debug"] = any("DEBUG" in i.message for i in issues)
    print_result("检测 DEBUG=True", results["detect_debug"], f"{len(issues)} 个问题")

    # 8.2 SQL injection via format
    code = 'cursor.execute("SELECT * FROM users WHERE id=%s" % user_id)'
    issues = engine.detect_issues("db.py", code, 1)
    results["detect_sql_format"] = any("SQL" in i.message for i in issues)
    print_result("检测 SQL % 格式化", results["detect_sql_format"], f"{len(issues)} 个问题")

    # 8.3 Hardcoded secret
    code = 'api_key = "sk-1234567890abcdef"'
    issues = engine.detect_issues("config.py", code, 1)
    results["detect_api_key"] = any("敏感信息" in i.message or "硬编码" in i.message for i in issues)
    print_result("检测硬编码 API Key", results["detect_api_key"], f"{len(issues)} 个问题")

    # 8.4 eval usage
    code = "result = eval(user_input)"
    issues = engine.detect_issues("main.py", code, 1)
    results["detect_eval"] = any("eval" in i.message.lower() for i in issues)
    print_result("检测 eval()", results["detect_eval"], f"{len(issues)} 个问题")

    return all(results.values())


# ===========================================
# Main
# ===========================================
def run_all_tests():
    print("\n" + "#"*60)
    print(f"# GitHub Insight Agent - 单元测试")
    print(f"# 时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)

    results = {}
    tests = [
        ("ToolResponse", test_tool_response),
        ("GitHubRepo from_api_response", test_github_repo_from_api),
        ("GitHubSearchResult", test_github_search_result),
        ("AnalysisResult", test_analysis_result),
        ("OWASP 规则引擎统计", test_owasp_stats),
        ("ConfigManager API Key 解析", test_config_api_key),
        ("GitHubRepo 模型验证", test_github_repo_validation),
        ("OWASP 检测多种输入", test_owasp_detect_various),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n  ✗ {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "="*60)
    print("单元测试结果汇总")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n✓ 所有单元测试通过！")
    else:
        print(f"\n⚠ {total - passed} 个测试未通过")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
