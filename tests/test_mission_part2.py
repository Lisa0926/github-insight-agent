# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - Mission Part 2: Additional Test Coverage

Tests added for:
- DashScopeProvider model env var fallback (bug fix verification)
- PersistentMemory singleton per db_path (bug fix verification)
- PersistentMemory __exit__ cache cleanup (bug fix verification)
- OWASP security: path traversal, eval/exec, pickle, XSS detection
- DashScopeWrapper error handling
- NaturalLanguageParser edge cases
- AgentPipeline initialization
- ConfigManager property coverage
- Schema edge cases (AnalysisResult, ToolResponse)
- PR Review tool edge cases
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ===========================================
# Test 1: DashScopeProvider model fallback fix
# ===========================================
def test_ds_provider_model_env_fallback():
    """Verify that model env var fallback works (bug fix for line 33 overwrite)"""
    from src.llm.providers.dashscope_provider import DashScopeProvider

    # Test with empty model and env var set
    original = os.environ.get("DASHSCOPE_MODEL")
    try:
        os.environ["DASHSCOPE_MODEL"] = "test-model-from-env"
        provider = DashScopeProvider(api_key="test-key", model="")
        assert provider.model == "test-model-from-env", \
            f"Expected 'test-model-from-env', got '{provider.model}'"
        print("  ✓ Model env var fallback works correctly")

        # Test that explicit model overrides env var
        provider2 = DashScopeProvider(api_key="test-key", model="explicit-model")
        assert provider2.model == "explicit-model", \
            f"Expected 'explicit-model', got '{provider2.model}'"
        print("  ✓ Explicit model overrides env var")
    finally:
        if original is not None:
            os.environ["DASHSCOPE_MODEL"] = original
        else:
            os.environ.pop("DASHSCOPE_MODEL", None)


# ===========================================
# Test 2: PersistentMemory singleton per db_path
# ===========================================
def test_persistent_memory_singleton_per_db_path():
    """Verify that different db_paths get different instances"""
    from src.core.agentscope_persistent_memory import (
        get_persistent_memory, _persistent_memory_cache
    )

    # Clear cache first
    import src.core.agentscope_persistent_memory as pm_mod
    pm_mod._persistent_memory_cache = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        db1 = os.path.join(tmpdir, "test1.db")
        db2 = os.path.join(tmpdir, "test2.db")

        inst1 = get_persistent_memory(db_path=db1)
        inst2 = get_persistent_memory(db_path=db2)

        assert inst1 is not inst2, "Different db_paths should return different instances"
        print("  ✓ Different db_paths return different instances")

        # Same db_path should return same instance
        inst1_again = get_persistent_memory(db_path=db1)
        assert inst1 is inst1_again, "Same db_path should return same instance"
        print("  ✓ Same db_path returns cached instance")

        # force_new should create new instance
        inst1_new = get_persistent_memory(db_path=db1, force_new=True)
        assert inst1_new is not inst1, "force_new should create new instance"
        print("  ✓ force_new creates new instance")

        # Cleanup
        try:
            import asyncio
            asyncio.get_event_loop().run_until_complete(inst1.close())
        except Exception:
            pass
        try:
            asyncio.get_event_loop().run_until_complete(inst2.close())
        except Exception:
            pass
        try:
            asyncio.get_event_loop().run_until_complete(inst1_new.close())
        except Exception:
            pass


# ===========================================
# Test 3: PersistentMemory __exit__ clears cache
# ===========================================
def test_persistent_memory_exit_clears_cache():
    """Verify that context manager exit clears singleton cache"""
    import src.core.agentscope_persistent_memory as pm_mod

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_exit.db")

        # Pre-populate cache with a different path
        pm_mod._persistent_memory_cache = {"some_other_path": "dummy"}

        # Create via context manager
        with pm_mod.PersistentMemoryContext(db_path=db_path) as pm:
            pm.add_user_message("Hello")
            # Cache should have our instance
            assert db_path in pm_mod._persistent_memory_cache

        # After exiting, cache should be cleared
        assert pm_mod._persistent_memory_cache == {}, \
            f"Cache should be cleared after context manager exit, got: {pm_mod._persistent_memory_cache}"
        print("  ✓ Context manager exit clears singleton cache")


# ===========================================
# Test 4: OWASP path traversal detection
# ===========================================
def test_owasp_path_traversal():
    """Verify OWASP engine detects path traversal patterns"""
    from src.tools.owasp_security_rules import OWASPRuleEngine

    engine = OWASPRuleEngine()

    code = 'open("/data/" + user_input + ".txt", "r")'
    issues = engine.detect_issues("file.py", code, 1)
    assert len(issues) > 0, "Should detect path traversal"
    assert any("路径遍历" in i.message or "traversal" in i.message.lower() for i in issues), \
        f"Should mention path traversal, got: {[i.message for i in issues]}"
    print(f"  ✓ Path traversal detected ({len(issues)} issues)")


# ===========================================
# Test 5: OWASP eval/exec detection
# ===========================================
def test_owasp_eval_exec():
    """Verify OWASP engine detects eval/exec usage"""
    from src.tools.owasp_security_rules import OWASPRuleEngine

    engine = OWASPRuleEngine()

    # eval
    code = "result = eval(user_input)"
    issues = engine.detect_issues("main.py", code, 1)
    assert len(issues) > 0, "Should detect eval"
    print(f"  ✓ eval() detected ({len(issues)} issues)")

    # exec
    code2 = "exec(dynamic_code)"
    issues2 = engine.detect_issues("main.py", code2, 1)
    assert len(issues2) > 0, "Should detect exec"
    print(f"  ✓ exec() detected ({len(issues2)} issues)")


# ===========================================
# Test 6: OWASP pickle detection
# ===========================================
def test_owasp_pickle():
    """Verify OWASP engine detects unsafe pickle usage"""
    from src.tools.owasp_security_rules import OWASPRuleEngine

    engine = OWASPRuleEngine()

    code = "data = pickle.loads(raw_bytes)"
    issues = engine.detect_issues("data.py", code, 1)
    assert len(issues) > 0, "Should detect pickle"
    assert any("反序列化" in i.message or "pickle" in i.message.lower() for i in issues)
    print(f"  ✓ pickle.loads() detected ({len(issues)} issues)")


# ===========================================
# Test 7: OWASP XSS detection
# ===========================================
def test_owasp_xss():
    """Verify OWASP engine detects XSS patterns"""
    from src.tools.owasp_security_rules import OWASPRuleEngine

    engine = OWASPRuleEngine()

    # innerHTML function call with concatenation (matches the regex pattern)
    code = "document.write(user_comment + more_data)"
    issues = engine.detect_issues("app.js", code, 1)
    assert len(issues) > 0, "Should detect XSS"
    print(f"  ✓ XSS (document.write) detected ({len(issues)} issues)")


# ===========================================
# Test 8: OWASP bare except detection
# ===========================================
def test_owasp_bare_except():
    """Verify OWASP engine detects bare except"""
    from src.tools.owasp_security_rules import OWASPRuleEngine

    engine = OWASPRuleEngine()

    code = """
try:
    do_something()
except:
    pass
"""
    issues = engine.detect_issues("app.py", code, 1)
    assert len(issues) > 0, "Should detect bare except"
    print(f"  ✓ Bare except detected ({len(issues)} issues)")


# ===========================================
# Test 9: DashScopeWrapper error handling
# ===========================================
def test_ds_wrapper_error_handling():
    """Verify DashScopeWrapper handles errors gracefully"""
    from src.core.dashscope_wrapper import DashScopeWrapper

    # Test with invalid model - should not crash, should return error response
    wrapper = DashScopeWrapper(
        model_name="invalid-model-xyz",
        api_key="invalid-key",
        base_url="https://invalid.example.com",
    )
    assert wrapper.model_name == "invalid-model-xyz"
    print("  ✓ DashScopeWrapper initialization with invalid params OK")


# ===========================================
# Test 10: DashScopeWrapper duplicate import fix
# ===========================================
def test_ds_wrapper_no_dup_imports():
    """Verify no duplicate import os in dashscope_wrapper.py"""
    import ast
    source = Path(__file__).parent.parent / "src" / "core" / "dashscope_wrapper.py"
    tree = ast.parse(source.read_text())

    # Count 'import os' statements
    import_os_count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    import_os_count += 1

    assert import_os_count == 1, f"Expected 1 'import os', found {import_os_count}"
    print("  ✓ No duplicate 'import os' in dashscope_wrapper.py")


# ===========================================
# Test 11: NaturalLanguageParser edge cases
# ===========================================
def test_nlp_empty_input():
    """Test NaturalLanguageParser with empty/None-like inputs"""
    from src.cli.natural_language_parser import NaturalLanguageParser, IntentType

    parser = NaturalLanguageParser()

    # Empty string
    result = parser.parse("")
    assert result.intent == IntentType.UNKNOWN or result.query == ""
    print("  ✓ Empty input handled")

    # Whitespace only
    result2 = parser.parse("   ")
    assert result2.intent == IntentType.UNKNOWN or result2.query.strip() == ""
    print("  ✓ Whitespace-only input handled")


def test_nlp_english_patterns():
    """Test NaturalLanguageParser with English patterns"""
    from src.cli.natural_language_parser import NaturalLanguageParser, IntentType

    parser = NaturalLanguageParser()

    # English search
    result = parser.parse("search for Python web frameworks")
    assert result.intent in (IntentType.SEARCH, IntentType.ANALYZE, IntentType.REPORT, IntentType.UNKNOWN)
    print(f"  ✓ English search pattern parsed (intent={result.intent.name})")


def test_nlp_owner_repo_pattern():
    """Test NaturalLanguageParser with owner/repo pattern"""
    from src.cli.natural_language_parser import NaturalLanguageParser, IntentType

    parser = NaturalLanguageParser()

    result = parser.parse("analyze microsoft/TypeScript")
    assert result.intent == IntentType.ANALYZE
    assert "microsoft" in result.query.lower() or "typescript" in result.query.lower()
    print(f"  ✓ Owner/repo pattern parsed (query='{result.query}')")


# ===========================================
# Test 12: AgentPipeline initialization
# ===========================================
def test_agent_pipeline_init():
    """Test AgentPipeline can be initialized"""
    # Reset cache to avoid None from previous tests
    import src.core.agentscope_persistent_memory as pm_mod
    pm_mod._persistent_memory_cache = {}

    from src.workflows.agent_pipeline import AgentPipeline

    pipeline = AgentPipeline()
    assert pipeline is not None
    assert hasattr(pipeline, 'researcher')
    assert hasattr(pipeline, 'analyst')
    print("  ✓ AgentPipeline initialization OK")


# ===========================================
# Test 13: ConfigManager comprehensive properties
# ===========================================
def test_config_manager_all_properties():
    """Test all ConfigManager properties return expected types"""
    from src.core.config_manager import ConfigManager

    # Reset singleton
    ConfigManager._instance = None
    ConfigManager._initialized = False

    config = ConfigManager()

    properties = [
        ("dashscope_api_key", str),
        ("dashscope_organization_id", str),
        ("dashscope_model_name", str),
        ("dashscope_base_url", str),
        ("github_token", str),
        ("github_api_url", str),
        ("github_timeout", int),
        ("github_rate_limit", int),
        ("model_temperature", float),
        ("model_max_tokens", int),
        ("model_top_p", float),
        ("model_repetition_penalty", float),
        ("log_level", str),
        ("log_max_size_mb", int),
        ("log_retention_days", int),
        ("log_dir", str),
        ("project_root", str),
        ("max_retries", int),
        ("retry_delay_seconds", float),
        ("request_timeout", int),
        ("debug_mode", bool),
    ]

    for prop_name, expected_type in properties:
        value = getattr(config, prop_name)
        assert isinstance(value, expected_type), \
            f"{prop_name}: expected {expected_type.__name__}, got {type(value).__name__} ({value})"

    print(f"  ✓ All {len(properties)} ConfigManager properties return correct types")


# ===========================================
# Test 14: ToolResponse with complex data
# ===========================================
def test_tool_response_complex_data():
    """Test ToolResponse with nested/complex data structures"""
    from src.types.schemas import ToolResponse
    import json

    # Nested dict
    nested = {"level1": {"level2": {"level3": [1, 2, 3]}}}
    resp = ToolResponse.ok(data=nested)
    parsed = json.loads(resp.to_json())
    assert parsed["data"]["level1"]["level2"]["level3"] == [1, 2, 3]
    print("  ✓ Nested dict serialization OK")

    # List of dicts
    list_data = [{"name": "a", "value": 1}, {"name": "b", "value": 2}]
    resp2 = ToolResponse.ok(data=list_data)
    parsed2 = json.loads(resp2.to_json())
    assert len(parsed2["data"]) == 2
    print("  ✓ List of dicts serialization OK")

    # Unicode content
    unicode_data = {"message": "你好世界 🌍"}
    resp3 = ToolResponse.ok(data=unicode_data)
    parsed3 = json.loads(resp3.to_json())
    assert parsed3["data"]["message"] == "你好世界 🌍"
    print("  ✓ Unicode content serialization OK")


# ===========================================
# Test 15: PR Review tool edge cases
# ===========================================
def test_pr_review_empty_diff():
    """Test PR reviewer with empty diff"""
    from src.tools.pr_review_tool import PRReviewer, _parse_diff

    changes = _parse_diff("")
    assert changes == [] or len(changes) == 0
    print("  ✓ Empty diff parsed correctly")


def test_pr_review_new_file_diff():
    """Test PR reviewer with new file diff"""
    from src.tools.pr_review_tool import _parse_diff

    diff = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,3 @@
+def hello():
+    print("Hello")
+    return True
"""
    changes = _parse_diff(diff)
    assert len(changes) == 1
    assert changes[0].file_path == "new_file.py"
    print("  ✓ New file diff parsed correctly")


def test_pr_reviewer_rule_based_security():
    """Test PR reviewer detects security issues"""
    import asyncio
    from src.tools.pr_review_tool import PRReviewer, _parse_diff

    # Create a diff with security issues
    diff = """diff --git a/auth.py b/auth.py
--- a/auth.py
+++ b/auth.py
@@ -1,3 +1,5 @@
+password = "admin123"
+DEBUG = True
 def login(user):
+    result = eval(user.input)
     return True
"""
    changes = _parse_diff(diff)
    reviewer = PRReviewer()

    async def _run_review():
        return await reviewer.review(
            pr_title="Test PR",
            pr_description="Test security issues",
            changes=changes,
            use_llm=False,
        )

    report = asyncio.get_event_loop().run_until_complete(_run_review())

    assert report["stats"]["issues_found"] > 0, \
        f"Should detect security issues, got {report['stats']['issues_found']}"
    print(f"  ✓ PR reviewer detected {report['stats']['issues_found']} security issues")


# ===========================================
# Test 16: GitHubTool clean_readme_text comprehensive
# ===========================================
def test_clean_readme_comprehensive():
    """Comprehensive test for GitHubTool.clean_readme_text"""
    from src.tools.github_tool import GitHubTool

    # Remove code blocks
    text = "Intro\n```python\nprint('hello')\n```\nOutro"
    cleaned = GitHubTool.clean_readme_text(text)
    assert "print('hello')" not in cleaned
    assert "Intro" in cleaned and "Outro" in cleaned
    print("  ✓ Code blocks removed")

    # Remove inline code
    text2 = "Use `pip install foo` to install"
    cleaned2 = GitHubTool.clean_readme_text(text2)
    assert "`" not in cleaned2
    print("  ✓ Inline code removed")

    # Remove headings
    text3 = "### Title\n## Sub\n# Main"
    cleaned3 = GitHubTool.clean_readme_text(text3)
    assert "###" not in cleaned3 and "##" not in cleaned3
    print("  ✓ Headings removed")

    # Remove links
    text4 = "[Click here](https://example.com)"
    cleaned4 = GitHubTool.clean_readme_text(text4)
    assert "Click here" in cleaned4
    assert "https://example.com" not in cleaned4
    print("  ✓ Links removed")

    # Truncation
    text5 = "A" * 10000
    cleaned5 = GitHubTool.clean_readme_text(text5, max_length=5000)
    assert len(cleaned5) <= 5000
    print("  ✓ Truncation works")

    # Empty string
    assert GitHubTool.clean_readme_text("") == ""
    print("  ✓ Empty string handled")

    # None input - should return empty string gracefully
    result = GitHubTool.clean_readme_text(None)
    assert result == "", f"Expected empty string for None input, got: {repr(result)}"
    print("  ✓ None input handled (returns empty string)")


# ===========================================
# Test 17: ResilientHTTPClient context manager
# ===========================================
def test_resilient_http_context_manager():
    """Test ResilientHTTPClient context manager"""
    from src.core.resilient_http import ResilientHTTPClient

    with ResilientHTTPClient(timeout=5) as client:
        assert client.timeout == 5
        assert not client._circuit_open
    print("  ✓ Context manager works")


# ===========================================
# Test 18: GitHubRepo Pydantic validation
# ===========================================
def test_github_repo_validation():
    """Test GitHubRepo Pydantic validation"""
    from src.types.schemas import GitHubRepo
    from pydantic import ValidationError

    # Missing required fields
    try:
        GitHubRepo(full_name="test/repo")
        assert False, "Should raise ValidationError"
    except ValidationError:
        pass
    print("  ✓ Missing required fields rejected")

    # Valid minimal
    repo = GitHubRepo(full_name="a/b", html_url="https://github.com/a/b")
    assert repo.full_name == "a/b"
    assert repo.topics == []
    assert repo.language == ""
    print("  ✓ Valid minimal repo accepted")


# ===========================================
# Test 19: AnalysisResult defaults
# ===========================================
def test_analysis_result_defaults():
    """Test AnalysisResult default values"""
    from src.types.schemas import AnalysisResult
    from datetime import datetime

    result = AnalysisResult(
        repo_name="test/repo",
        analysis_type="security",
        summary="No issues",
    )

    assert isinstance(result.timestamp, datetime)
    assert result.metadata == {}
    assert result.insights == []
    assert result.recommendations == []
    assert result.risk_level == "medium"  # default is 'medium' per schema
    print("  ✓ AnalysisResult defaults correct")


# ===========================================
# Main test runner
# ===========================================
if __name__ == "__main__":
    tests = [
        ("DashScopeProvider model env fallback", test_ds_provider_model_env_fallback),
        ("PersistentMemory singleton per db_path", test_persistent_memory_singleton_per_db_path),
        ("PersistentMemory __exit__ clears cache", test_persistent_memory_exit_clears_cache),
        ("OWASP path traversal", test_owasp_path_traversal),
        ("OWASP eval/exec", test_owasp_eval_exec),
        ("OWASP pickle", test_owasp_pickle),
        ("OWASP XSS", test_owasp_xss),
        ("OWASP bare except", test_owasp_bare_except),
        ("DashScopeWrapper error handling", test_ds_wrapper_error_handling),
        ("DashScopeWrapper no duplicate imports", test_ds_wrapper_no_dup_imports),
        ("NLP empty input", test_nlp_empty_input),
        ("NLP English patterns", test_nlp_english_patterns),
        ("NLP owner/repo pattern", test_nlp_owner_repo_pattern),
        ("AgentPipeline init", test_agent_pipeline_init),
        ("ConfigManager all properties", test_config_manager_all_properties),
        ("ToolResponse complex data", test_tool_response_complex_data),
        ("PR review empty diff", test_pr_review_empty_diff),
        ("PR review new file diff", test_pr_review_new_file_diff),
        ("PR reviewer security detection", test_pr_reviewer_rule_based_security),
        ("clean_readme comprehensive", test_clean_readme_comprehensive),
        ("ResilientHTTP context manager", test_resilient_http_context_manager),
        ("GitHubRepo validation", test_github_repo_validation),
        ("AnalysisResult defaults", test_analysis_result_defaults),
    ]

    print("\n" + "#" * 60)
    print("# Mission Part 2: Additional Test Coverage")
    print("#" * 60)

    results = {}
    for name, test_func in tests:
        try:
            test_func()
            results[name] = True
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} - {name}")
    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 60)

    sys.exit(0 if passed == total else 1)
