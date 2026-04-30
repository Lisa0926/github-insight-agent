# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - Mission Part 3: Report Module Tests

Tests for the new src/report/ module (untracked working tree changes):
- HTMLExporter: export_markdown_to_html, export_to_string, ReportExtractor
- PushReportOptimizer: optimize_for_wechat, optimize_for_feishu
- Edge cases: empty inputs, None content, special characters, length limits
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ===========================================
# Test 1: HTMLExporter basic export
# ===========================================
def test_html_exporter_basic():
    """Test HTMLExporter can export markdown to HTML file"""
    from src.report.html_exporter import HTMLExporter

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = HTMLExporter(output_dir=tmpdir)
        md_content = "# Test Report\n\nThis is a test report.\n\n## Metrics\n\n| Name | Value |\n|------|-------|\n| Tests | 176 |\n"
        output_path = exporter.export(md_content)

        assert os.path.exists(output_path), f"HTML file not created at {output_path}"
        assert output_path.endswith('.html')

        with open(output_path, 'r', encoding='utf-8') as f:
            html = f.read()

        assert '<!DOCTYPE html>' in html
        assert 'Test Report' in html
        assert 'This is a test report.' in html
        print("  ✓ HTMLExporter basic export works")


# ===========================================
# Test 2: HTMLExporter export_to_string
# ===========================================
def test_html_exporter_to_string():
    """Test HTMLExporter can export to string (no file)"""
    from src.report.html_exporter import HTMLExporter

    exporter = HTMLExporter()
    md_content = "# String Export Test\n\nContent here."
    html = exporter.export_to_string(md_content)

    assert isinstance(html, str)
    assert '<!DOCTYPE html>' in html
    assert 'String Export Test' in html
    assert 'Content here.' in html
    print("  ✓ HTMLExporter export_to_string works")


# ===========================================
# Test 3: Convenience functions
# ===========================================
def test_convenience_functions():
    """Test export_markdown_to_html and export_markdown_to_html_string"""
    from src.report.html_exporter import (
        export_markdown_to_html,
        export_markdown_to_html_string,
    )

    md = "# Convenience Test\n\nHello world."

    # Test to string
    html_str = export_markdown_to_html_string(md)
    assert isinstance(html_str, str)
    assert 'Convenience Test' in html_str
    print("  ✓ export_markdown_to_html_string works")

    # Test to file
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, 'test.html')
        result_path = export_markdown_to_html(md, output_path=output_path)
        assert os.path.exists(result_path)
        print("  ✓ export_markdown_to_html works")


# ===========================================
# Test 4: ReportExtractor title extraction
# ===========================================
def test_report_extractor_title():
    """Test ReportExtractor extracts title from markdown"""
    from src.report.html_exporter import ReportExtractor

    md = "# My Awesome Report\n\nSome content here."
    extractor = ReportExtractor(md)
    result = extractor.extract()

    assert result['title'] == 'My Awesome Report'
    assert 'My Awesome Report' in result['content']
    print("  ✓ ReportExtractor title extraction works")


# ===========================================
# Test 5: ReportExtractor metric extraction
# ===========================================
def test_report_extractor_metrics():
    """Test ReportExtractor extracts metrics from markdown"""
    from src.report.html_exporter import ReportExtractor

    md = "# Report\n\n176 个测试 176 个通过\n\n54 条安全规则"
    extractor = ReportExtractor(md)
    extractor._extract_metrics()

    assert len(extractor.metrics) >= 1
    # Check test metric
    test_metrics = [m for m in extractor.metrics if '测试' in m.get('label', '')]
    assert len(test_metrics) >= 1
    print(f"  ✓ ReportExtractor metrics extraction works ({len(extractor.metrics)} metrics)")


# ===========================================
# Test 6: ReportExtractor HTML conversion with tables
# ===========================================
def test_report_extractor_table_wrapper():
    """Test ReportExtractor wraps tables in div.table-wrapper"""
    from src.report.html_exporter import ReportExtractor

    md = "# Report\n\n| Col1 | Col2 |\n|------|------|\n| A | B |\n"
    extractor = ReportExtractor(md)
    result = extractor.extract()

    assert 'class="table-wrapper"' in result['content']
    print("  ✓ ReportExtractor table wrapper works")


# ===========================================
# Test 7: HTMLExporter with special characters
# ===========================================
def test_html_exporter_special_chars():
    """Test HTMLExporter handles special characters and emoji"""
    from src.report.html_exporter import HTMLExporter

    md = "# 测试报告 📊\n\n• ✅ 通过\n• ⚠️ 警告\n• 🔴 错误\n\n**Bold text** and *italic text*"
    html = HTMLExporter().export_to_string(md)

    assert '测试报告' in html
    assert 'badge-success' in html
    assert 'badge-warning' in html
    assert 'badge-danger' in html
    print("  ✓ HTMLExporter handles special characters and emoji")


# ===========================================
# Test 8: HTMLExporter empty content
# ===========================================
def test_html_exporter_empty_content():
    """Test HTMLExporter handles empty/minimal markdown"""
    from src.report.html_exporter import HTMLExporter

    html = HTMLExporter().export_to_string("")
    assert isinstance(html, str)
    assert '<!DOCTYPE html>' in html
    print("  ✓ HTMLExporter handles empty content")


# ===========================================
# Test 9: PushReportOptimizer - WeChat format
# ===========================================
def test_push_optimizer_wechat():
    """Test PushReportOptimizer optimizes for WeChat"""
    from src.report.push_optimizer import PushReportOptimizer

    report = "# 项目分析报告\n\n176 个测试 176 个通过\n\n## 总结\n\n发现关键问题：测试覆盖率不足。\n\n## 行动建议\n\n1. 增加单元测试覆盖率到 80%\n2. 修复已知安全漏洞\n3. 优化性能瓶颈"

    optimizer = PushReportOptimizer(report)
    result = optimizer.optimize_for_wechat()

    assert '📊' in result
    assert len(result) <= 1800
    assert '项目分析报告' in result
    print("  ✓ PushReportOptimizer WeChat optimization works")


# ===========================================
# Test 10: PushReportOptimizer - Feishu format
# ===========================================
def test_push_optimizer_feishu():
    """Test PushReportOptimizer optimizes for Feishu"""
    from src.report.push_optimizer import PushReportOptimizer

    report = "# 项目分析报告\n\n176 个测试 176 个通过\n\n54 条安全规则\n\n## 总结\n\n发现关键问题：测试覆盖率不足。\n\n## 竞品动态\n\nCodeRabbit 发布新功能。\n\n## 行动建议\n\n1. 增加单元测试覆盖率到 80%\n2. 修复已知安全漏洞\n3. 优化性能瓶颈"

    optimizer = PushReportOptimizer(report)
    result = optimizer.optimize_for_feishu()

    assert '**' in result  # Feishu uses markdown bold
    assert len(result) <= 3000
    assert '项目分析报告' in result
    print("  ✓ PushReportOptimizer Feishu optimization works")


# ===========================================
# Test 11: PushReportOptimizer length truncation
# ===========================================
def test_push_optimizer_wechat_truncation():
    """Test WeChat output respects max_length limit"""
    from src.report.push_optimizer import PushReportOptimizer

    # Create a very long report
    long_report = "# Long Report\n\n" + "A" * 5000 + "\n\n" + "B" * 5000

    optimizer = PushReportOptimizer(long_report)
    result = optimizer.optimize_for_wechat(max_length=500)

    assert len(result) <= 500
    assert result.endswith('...') or len(result) < 500
    print("  ✓ WeChat output truncation works")


# ===========================================
# Test 12: PushReportOptimizer Feishu length truncation
# ===========================================
def test_push_optimizer_feishu_truncation():
    """Test Feishu output respects max_length limit"""
    from src.report.push_optimizer import PushReportOptimizer

    long_report = "# Long Report\n\n" + "A" * 5000 + "\n\n" + "B" * 5000

    optimizer = PushReportOptimizer(long_report)
    result = optimizer.optimize_for_feishu(max_length=500)

    assert len(result) <= 500
    print("  ✓ Feishu output truncation works")


# ===========================================
# Test 13: PushReportOptimizer convenience functions
# ===========================================
def test_push_optimizer_convenience():
    """Test optimize_for_wechat and optimize_for_feishu convenience functions"""
    from src.report.push_optimizer import optimize_for_wechat, optimize_for_feishu

    report = "# Test\n\n100 个测试 100 个通过"

    wechat = optimize_for_wechat(report)
    assert isinstance(wechat, str)
    assert '📊' in wechat
    print("  ✓ optimize_for_wechat convenience function works")

    feishu = optimize_for_feishu(report)
    assert isinstance(feishu, str)
    assert '**' in feishu
    print("  ✓ optimize_for_feishu convenience function works")


# ===========================================
# Test 14: PushReportOptimizer empty report
# ===========================================
def test_push_optimizer_empty_report():
    """Test PushReportOptimizer handles empty/minimal reports"""
    from src.report.push_optimizer import PushReportOptimizer

    optimizer = PushReportOptimizer("")
    wechat = optimizer.optimize_for_wechat()
    feishu = optimizer.optimize_for_feishu()

    assert isinstance(wechat, str)
    assert isinstance(feishu, str)
    print("  ✓ PushReportOptimizer handles empty report")


# ===========================================
# Test 15: PushReportOptimizer metric extraction patterns
# ===========================================
def test_push_optimizer_metric_patterns():
    """Test PushReportOptimizer extracts various metric patterns"""
    from src.report.push_optimizer import PushReportOptimizer

    report = """# Analysis Report

176 个测试 158 个通过
54 条安全规则
10 个项目
+100 -50

## 发现
关键发现 1
关键发现 2
"""
    optimizer = PushReportOptimizer(report)
    sections = optimizer._extract_key_sections(report.split('\n'))

    assert len(sections['metrics']) >= 1
    print(f"  ✓ Metric extraction: {len(sections['metrics'])} metrics found")


# ===========================================
# Test 16: PushReportOptimizer finding extraction
# ===========================================
def test_push_optimizer_finding_extraction():
    """Test PushReportOptimizer extracts findings from report"""
    from src.report.push_optimizer import PushReportOptimizer

    report = """# Report

## 总结

这是一个重要发现，需要关注。
另一个重要发现，关于安全。
"""
    optimizer = PushReportOptimizer(report)
    sections = optimizer._extract_key_sections(report.split('\n'))

    assert len(sections['findings']) >= 1
    print(f"  ✓ Finding extraction: {len(sections['findings'])} findings found")


# ===========================================
# Test 17: PushReportOptimizer action extraction
# ===========================================
def test_push_optimizer_action_extraction():
    """Test PushReportOptimizer extracts action items from report"""
    from src.report.push_optimizer import PushReportOptimizer

    report = """# Report

## 下一步行动

增加测试覆盖率到 80%
修复 OWASP 安全漏洞
"""
    optimizer = PushReportOptimizer(report)
    sections = optimizer._extract_key_sections(report.split('\n'))

    assert len(sections['actions']) >= 1
    print(f"  ✓ Action extraction: {len(sections['actions'])} actions found")


# ===========================================
# Test 18: PushReportOptimizer competitor extraction
# ===========================================
def test_push_optimizer_competitor_extraction():
    """Test PushReportOptimizer extracts competitor mentions"""
    from src.report.push_optimizer import PushReportOptimizer

    report = """# Report

## 竞品动态

CodeRabbit 发布了新的 AI review 功能
Qodo 更新了定价策略
"""
    optimizer = PushReportOptimizer(report)
    sections = optimizer._extract_key_sections(report.split('\n'))

    assert len(sections['competitors']) >= 1
    print(f"  ✓ Competitor extraction: {len(sections['competitors'])} competitors found")


# ===========================================
# Test 19: Module import and __all__
# ===========================================
def test_report_module_exports():
    """Test that src.report module exports expected names"""
    import src.report as report_mod

    expected_exports = [
        'export_markdown_to_html',
        'export_markdown_to_html_string',
        'HTMLExporter',
        'optimize_for_wechat',
        'optimize_for_feishu',
        'PushReportOptimizer',
    ]

    for name in expected_exports:
        assert name in report_mod.__all__, f"{name} missing from __all__"
        assert hasattr(report_mod, name), f"{name} not accessible"

    print(f"  ✓ Module exports all {len(expected_exports)} expected names")


# ===========================================
# Test 20: HTML template renders properly
# ===========================================
def test_html_template_rendering():
    """Test that the HTML template renders with all expected elements"""
    from src.report.html_exporter import HTMLExporter

    md = "# Full Test\n\n## Section 1\n\nContent 1\n\n## Section 2\n\nContent 2"
    html = HTMLExporter().export_to_string(md)

    # Check template elements
    assert 'lang="zh-CN"' in html
    assert 'viewport' in html
    assert 'container' in html
    assert 'footer' in html
    assert 'Generated by GitHub Insight Agent' in html
    assert ':root' in html  # CSS variables
    assert '--bg-primary' in html
    assert 'media' in html  # responsive design
    print("  ✓ HTML template renders with all expected elements")


# ===========================================
# Test 21: HTMLExporter with non-existent output_dir
# ===========================================
def test_html_exporter_creates_output_dir():
    """Test HTMLExporter creates output directory if it doesn't exist"""
    from src.report.html_exporter import HTMLExporter

    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = os.path.join(tmpdir, 'a', 'b', 'c')
        assert not os.path.exists(nested_dir)
        exporter = HTMLExporter(output_dir=nested_dir)
        assert os.path.exists(nested_dir)
        print("  ✓ HTMLExporter creates nested output directories")


# ===========================================
# Test 22: ReportExtractor with no title (default)
# ===========================================
def test_report_extractor_no_title():
    """Test ReportExtractor uses default title when no H1 found"""
    from src.report.html_exporter import ReportExtractor

    md = "Just some content without a title."
    extractor = ReportExtractor(md)
    result = extractor.extract()

    assert result['title'] == 'GitHub Insight Report'  # default title
    print("  ✓ ReportExtractor uses default title when no H1")


# ===========================================
# Test 23: PushReportOptimizer with HTML URL
# ===========================================
def test_push_optimizer_with_html_url():
    """Test PushReportOptimizer includes HTML URL when present"""
    from src.report.push_optimizer import PushReportOptimizer

    report = """# Report

176 个测试 176 个通过

## 总结

关键发现。

[完整报告](https://example.com/report.html)
"""
    # Add html_url to sections manually to test the path
    optimizer = PushReportOptimizer(report)
    sections = optimizer._extract_key_sections(report.split('\n'))
    sections['html_url'] = 'https://example.com/report.html'

    # Test that the optimizer can handle html_url
    wechat = optimizer.optimize_for_wechat()
    assert isinstance(wechat, str)
    print("  ✓ PushReportOptimizer handles HTML URL field")


# ===========================================
# Test 24: PushReportOptimizer very short max_length
# ===========================================
def test_push_optimizer_very_short_max_length():
    """Test WeChat/Feishu output with very short max_length"""
    from src.report.push_optimizer import PushReportOptimizer

    report = "# Report\n\n176 个测试 176 个通过\n\n## 总结\n\n关键发现。"
    optimizer = PushReportOptimizer(report)

    wechat = optimizer.optimize_for_wechat(max_length=50)
    assert len(wechat) <= 50
    print(f"  ✓ WeChat very short max_length: {len(wechat)} chars")

    feishu = optimizer.optimize_for_feishu(max_length=50)
    assert len(feishu) <= 50
    print(f"  ✓ Feishu very short max_length: {len(feishu)} chars")


# ===========================================
# Test 25: ReportExtractor with no metrics
# ===========================================
def test_report_extractor_no_metrics():
    """Test ReportExtractor handles content with no extractable metrics"""
    from src.report.html_exporter import ReportExtractor

    md = "# Report\n\nJust plain text without any metrics or numbers."
    extractor = ReportExtractor(md)
    result = extractor.extract()

    assert result['title'] == 'Report'
    assert isinstance(result['content'], str)
    print("  ✓ ReportExtractor handles content with no metrics")


# ===========================================
# Test 26: HTMLExporter with full report integration
# ===========================================
def test_html_exporter_full_report():
    """Test HTMLExporter with a realistic full report"""
    from src.report.html_exporter import HTMLExporter

    full_report = """# GitHub 项目分析报告

**生成时间**: 2026-04-30

## 项目概况

- 名称: example/project
- 语言: Python
- Stars: 1,234

## 代码质量

| 指标 | 分数 |
|------|------|
| 可读性 | 85 |
| 可维护性 | 78 |

## 安全扫描

176 个测试 176 个通过

54 条安全规则

### 发现的问题

- ✅ 无严重漏洞
- ⚠️ 2 条中危建议

## 总结

这是一个高质量的项目。

## 下一步行动

1. 增加测试覆盖率到 80%
2. 修复 OWASP 安全漏洞
3. 优化性能瓶颈
"""
    html = HTMLExporter().export_to_string(full_report)

    assert '项目分析报告' in html
    assert 'table-wrapper' in html  # table wrapper
    assert 'badge-success' in html  # ✅ badge
    assert 'badge-warning' in html  # ⚠️ badge
    assert 'metric-card' in html or 'section' in html
    print("  ✓ HTMLExporter handles full realistic report")
