# -*- coding: utf-8 -*-
"""
PR automated review tool

Features:
- Analyze Pull Request code changes
- Detect potential issues (code quality, security, performance)
- Provide improvement suggestions
- Generate structured review reports

Reference CodeRabbit core capabilities:
- Intelligent code change analysis
- Automated issue detection
- Line-level comment suggestions
- Review summary generation
"""

import re
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from src.core.logger import get_logger
from src.core.config_manager import ConfigManager
from src.llm.provider_factory import get_provider
from src.types.schemas import ToolResponse
from src.tools.owasp_security_rules import OWASPRuleEngine, IssueSeverity as OWASPIssueSeverity

logger = get_logger(__name__)


class IssueSeverity(Enum):
    """Issue severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(Enum):
    """Issue categories"""
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUG_RISK = "bug_risk"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TEST = "test"


@dataclass
class CodeChange:
    """Code change"""
    file_path: str
    hunk_start_line: int
    changes: List[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0


@dataclass
class ReviewComment:
    """Review comment"""
    file_path: str
    line_number: int
    category: IssueCategory
    severity: IssueSeverity
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None


class PRReviewer:
    """
    PR automated reviewer

    Analyzes code changes, detects issues, and generates review comments.
    """

    # OWASP security rule engine (50+ rules)
    _owasp_engine: Optional[OWASPRuleEngine] = None

    # Code issue detection rules (non-security)
    PATTERNS = {
        # Performance issues
        "inefficient_loop": {
            "pattern": r"for\s+\w+\s+in\s+\w+.*:\s*\n\s+for\s+\w+\s+in\s+\w+",
            "category": IssueCategory.PERFORMANCE,
            "severity": IssueSeverity.MEDIUM,
            "message": "嵌套循环可能导致性能问题",
            "suggestion": "考虑使用列表推导式、字典或算法优化"
        },
        # Code quality
        "long_function": {
            "pattern": r"def\s+\w+\s*\([^)]*\)\s*:",
            "category": IssueCategory.CODE_QUALITY,
            "severity": IssueSeverity.LOW,
            "message": "函数可能过长（建议检查）",
            "suggestion": "将长函数拆分为多个小函数，每个函数单一职责"
        },
        "bare_except": {
            "pattern": r"except\s*:",
            "category": IssueCategory.CODE_QUALITY,
            "severity": IssueSeverity.MEDIUM,
            "message": "使用裸 except 会捕获所有异常",
            "suggestion": "明确指定要捕获的异常类型，如 except ValueError:"
        },
        "print_in_code": {
            "pattern": r"\bprint\s*\(",
            "category": IssueCategory.STYLE,
            "severity": IssueSeverity.LOW,
            "message": "代码中包含 print() 语句",
            "suggestion": "使用 logging 模块替代 print()，生产代码应移除调试输出"
        },
        # Test issues
        "missing_assert": {
            "pattern": r"def\s+test_\w+\s*\(",
            "category": IssueCategory.TEST,
            "severity": IssueSeverity.LOW,
            "message": "测试函数可能缺少断言（建议检查）",
            "suggestion": "确保测试包含 assert 语句验证预期结果"
        },
        # Documentation issues
        "missing_docstring": {
            "pattern": r"(def|class)\s+\w+\s*[^:]*:\s*\n\s+[^\"']",
            "category": IssueCategory.DOCUMENTATION,
            "severity": IssueSeverity.LOW,
            "message": "公共函数/类缺少文档字符串",
            "suggestion": "添加 docstring 说明功能、参数和返回值"
        },
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the PR reviewer

        Args:
            config: Config manager instance
        """
        self._config = config or ConfigManager()

        # Initialize OWASP security rule engine
        PRReviewer._owasp_engine = OWASPRuleEngine(config=self._config)

        # Initialize LLM Provider
        provider_name = self._config.llm_provider.lower() if hasattr(self._config, 'llm_provider') else 'dashscope'
        api_key = self._config.dashscope_api_key if provider_name == 'dashscope' else None
        model = self._config.dashscope_model_name if provider_name == 'dashscope' else None

        try:
            self._llm_provider = get_provider(provider_name, api_key=api_key, model=model)
        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider: {e}")
            self._llm_provider = None

        rules_count = len(PRReviewer._owasp_engine.SECURITY_RULES)
        logger.info("PRReviewer initialized with OWASP security rules (%d rules)", rules_count)

    def _detect_issues_by_rules(self, changes: List[CodeChange]) -> List[ReviewComment]:  # noqa: C901
        """
        Detect code issues based on rules (including OWASP security rules)

        Args:
            changes: List of code changes

        Returns:
            List of review comments
        """
        issues: List[ReviewComment] = []

        for change in changes:
            code_content = "\n".join(change.changes)

            # 1. OWASP security rule detection (50+ rules)
            if PRReviewer._owasp_engine:
                owasp_issues = PRReviewer._owasp_engine.detect_issues(change.file_path, code_content, change.hunk_start_line)
                for owasp_issue in owasp_issues:
                    # Map OWASP severity to PR reviewer severity
                    severity_map = {
                        OWASPIssueSeverity.CRITICAL: IssueSeverity.CRITICAL,
                        OWASPIssueSeverity.HIGH: IssueSeverity.HIGH,
                        OWASPIssueSeverity.MEDIUM: IssueSeverity.MEDIUM,
                        OWASPIssueSeverity.LOW: IssueSeverity.LOW,
                    }
                    # Map OWASP category to PR reviewer category
                    category_str = owasp_issue.category.value
                    if "A03" in owasp_issue.owasp_id or "Injection" in category_str:
                        pr_category = IssueCategory.SECURITY
                    elif "A01" in owasp_issue.owasp_id or "Access" in category_str:
                        pr_category = IssueCategory.SECURITY
                    elif "A02" in owasp_issue.owasp_id or "Crypto" in category_str:
                        pr_category = IssueCategory.SECURITY
                    elif "A07" in owasp_issue.owasp_id or "Auth" in category_str:
                        pr_category = IssueCategory.SECURITY
                    elif "A08" in owasp_issue.owasp_id or "Integrity" in category_str:
                        pr_category = IssueCategory.SECURITY
                    elif "A10" in owasp_issue.owasp_id or "SSRF" in category_str:
                        pr_category = IssueCategory.SECURITY
                    else:
                        pr_category = IssueCategory.SECURITY

                    comment = ReviewComment(
                        file_path=owasp_issue.file_path,
                        line_number=owasp_issue.line_number,
                        category=pr_category,
                        severity=severity_map.get(owasp_issue.severity, IssueSeverity.MEDIUM),
                        message=f"[{owasp_issue.owasp_id}] {owasp_issue.message}",
                        suggestion=owasp_issue.suggestion,
                    )
                    issues.append(comment)

            # 2. General code quality detection rules
            for rule_name, rule_config in self.PATTERNS.items():
                matches = re.finditer(rule_config["pattern"], code_content, re.IGNORECASE | re.MULTILINE)

                for match in matches:
                    # Calculate line number
                    line_number = change.hunk_start_line + code_content[:match.start()].count('\n')

                    # Create review comment
                    comment = ReviewComment(
                        file_path=change.file_path,
                        line_number=line_number,
                        category=rule_config["category"],
                        severity=rule_config["severity"],
                        message=f"[{rule_name}] {rule_config['message']}",
                        suggestion=rule_config.get("suggestion"),
                    )
                    issues.append(comment)

        # Deduplicate (same location may trigger multiple rules)
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue.file_path, issue.line_number, issue.message)
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

    async def _llm_review(
        self,
        pr_title: str,
        pr_description: str,
        changes: List[CodeChange],
    ) -> Dict[str, Any]:
        """
        Use LLM for in-depth review

        Args:
            pr_title: PR title
            pr_description: PR description
            changes: Code changes

        Returns:
            LLM review result
        """
        if self._llm_provider is None:
            logger.warning("LLM provider not available")
            return {
                "summary": "基于规则的自动审查（LLM 不可用）",
                "strengths": [],
                "concerns": [],
                "suggestions": [],
            }

        # Build change summary
        changes_summary = []
        for change in changes[:20]:  # Limit file count to avoid token overflow
            additions = change.additions
            deletions = change.deletions
            changes_summary.append(f"- {change.file_path}: +{additions} -{deletions}")

        # Extract partial code changes (first 100 lines)
        code_snippets = []
        total_lines = 0
        for change in changes:
            if total_lines >= 100:
                break
            snippet = "\n".join(change.changes[:20])  # Max 20 lines per file
            code_snippets.append(f"### {change.file_path}\n```diff\n{snippet}\n```")
            total_lines += len(change.changes)

        prompt = f"""你是一个资深的代码审查专家。请审查以下 Pull Request 的代码变更。

## PR 信息
- 标题：{pr_title}
- 描述：{pr_description[:500] if pr_description else '无描述'}

## 文件变更摘要
{chr(10).join(changes_summary)}

## 代码变更详情（部分）
{chr(10).join(code_snippets[:5])}

请以 JSON 格式输出审查结果：
```json
{{
    "summary": "一句话总结本次 PR 的主要变更和质量",
    "score": 7,
    "strengths": ["代码结构清晰", "有注释说明"],
    "concerns": ["发现 1 个潜在安全问题", "测试覆盖不足"],
    "suggestions": [
        {{
            "file": "path/to/file.py",
            "line": 42,
            "issue": "硬编码的 API 密钥",
            "suggestion": "使用环境变量存储密钥"
        }}
    ],
    "approval_recommendation": "request_changes"
}}
```

approval_recommendation 可选值:
- "approve": 代码质量良好，可以合并
- "comment": 有一些建议但不影响合并
- "request_changes": 需要修改后再审查

只返回 JSON，不要其他解释。"""

        try:
            response = await self._llm_provider.chat([
                {"role": "system", "content": "你是一个专业的代码审查专家，擅长发现代码问题并提供建设性意见。"},
                {"role": "user", "content": prompt},
            ])

            # Parse JSON response
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                result = json.loads(response)

            return {
                "summary": result.get("summary", ""),
                "score": result.get("score", 5),
                "strengths": result.get("strengths", []),
                "concerns": result.get("concerns", []),
                "suggestions": result.get("suggestions", []),
                "approval_recommendation": result.get("approval_recommendation", "comment"),
            }

        except Exception as e:
            logger.error(f"LLM 审查失败：{e}")
            return {
                "summary": "基于规则的自动审查（LLM 解析失败）",
                "score": 5,
                "strengths": [],
                "concerns": [f"LLM 审查失败：{str(e)}"],
                "suggestions": [],
                "approval_recommendation": "comment",
            }

    async def review(
        self,
        pr_title: str,
        pr_description: str,
        changes: List[CodeChange],
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute PR review

        Args:
            pr_title: PR title
            pr_description: PR description
            changes: List of code changes
            use_llm: Whether to use LLM enhancement

        Returns:
            Review report
        """
        logger.info(f"Reviewing PR: {pr_title}")

        # Step 1: Rule-based issue detection
        rule_issues = self._detect_issues_by_rules(changes)

        # Step 2: LLM deep review
        llm_result = {}
        if use_llm:
            llm_result = await self._llm_review(pr_title, pr_description, changes)

        # Step 3: Compile report
        stats = {
            "total_files": len(set(c.file_path for c in changes)),
            "total_additions": sum(c.additions for c in changes),
            "total_deletions": sum(c.deletions for c in changes),
            "issues_found": len(rule_issues),
        }

        # Stats already computed above; rule_issues available directly in report

        report = {
            "pr_title": pr_title,
            "stats": stats,
            "rule_based_issues": [
                {
                    "file": i.file_path,
                    "line": i.line_number,
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in rule_issues
            ],
            "llm_review": llm_result,
            "summary": self._generate_summary(stats, rule_issues, llm_result),
        }

        return report

    def _generate_summary(
        self,
        stats: Dict[str, Any],
        issues: List[ReviewComment],
        llm_result: Dict[str, Any],
    ) -> str:
        """Generate review summary"""
        critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == IssueSeverity.HIGH)

        summary_parts = [
            f"审查完成。共 {stats['total_files']} 个文件变更，"
            f"+{stats['total_additions']} -{stats['total_deletions']} 行代码。"
        ]

        if critical_count > 0:
            summary_parts.append(f"⚠️ 发现 {critical_count} 个严重问题")
        if high_count > 0:
            summary_parts.append(f"⚠️ 发现 {high_count} 个高优先级问题")

        if llm_result.get("score", 5) >= 8:
            summary_parts.append("✅ 代码质量良好")
        elif llm_result.get("score", 5) >= 6:
            summary_parts.append("📝 代码质量中等")
        else:
            summary_parts.append("🔧 建议改进后重新审查")

        return " ".join(summary_parts)


async def review_pull_request(
    pr_title: str,
    pr_description: str,
    diff_content: str,
    use_llm: bool = True,
    config: Optional[ConfigManager] = None,
) -> ToolResponse:
    """
    Review a Pull Request (tool function)

    Args:
        pr_title: PR title
        pr_description: PR description
        diff_content: git diff content
        use_llm: Whether to use LLM enhancement
        config: Config manager

    Returns:
        Review report wrapped in ToolResponse
    """
    try:
        # Parse diff content
        changes = _parse_diff(diff_content)

        # Execute review
        reviewer = PRReviewer(config=config)
        report = await reviewer.review(pr_title, pr_description, changes, use_llm=use_llm)

        # Format as human-readable report
        report_text = _format_report(report)

        return ToolResponse.ok(
            data=report,
            message=report_text,
        )

    except Exception as e:
        logger.error(f"PR 审查失败：{e}")
        return ToolResponse.fail(error_message=str(e))


def _parse_diff(diff_content: str) -> List[CodeChange]:  # noqa: C901
    """
    Parse git diff content into a list of CodeChange objects

    Args:
        diff_content: git diff output

    Returns:
        List of CodeChange objects
    """
    changes: List[CodeChange] = []
    current_file: Optional[CodeChange] = None
    current_hunk_start = 0

    lines = diff_content.split('\n')

    for line in lines:
        # Detect new file
        if line.startswith('+++ b/') or line.startswith('+++ /dev/null'):
            if current_file is not None:
                changes.append(current_file)

            file_path = line[6:] if line.startswith('+++ b/') else 'new_file'
            current_file = CodeChange(file_path=file_path, hunk_start_line=0, changes=[])

        # Detect hunk header
        elif line.startswith('@@'):
            match = re.search(r'\+(\d+)', line)
            if match and current_file is not None:
                current_hunk_start = int(match.group(1))
                current_file.hunk_start_line = current_hunk_start

        # Addition line
        elif line.startswith('+') and not line.startswith('+++'):
            if current_file is not None:
                current_file.changes.append(line[1:])  # Remove + prefix
                current_file.additions += 1

        # Deletion line
        elif line.startswith('-') and not line.startswith('---'):
            if current_file is not None:
                current_file.changes.append(line[1:])  # Remove - prefix
                current_file.deletions += 1

        # Context line
        elif line.startswith(' '):
            if current_file is not None:
                current_file.changes.append(line[1:])

    # Add the last file
    if current_file is not None:
        changes.append(current_file)

    return changes


def _format_report(report: Dict[str, Any]) -> str:  # noqa: C901
    """Format review report as human-readable text"""
    lines = [
        "=" * 60,
        "PR 自动审查报告",
        "=" * 60,
        f"\nPR 标题：{report['pr_title']}",
        "",
        "## 变更统计",
        f"- 文件数：{report['stats']['total_files']}",
        f"- 新增行数：+{report['stats']['total_additions']}",
        f"- 删除行数：-{report['stats']['total_deletions']}",
        f"- 发现问题：{report['stats']['issues_found']}",
        "",
        "## 审查摘要",
        report['summary'],
        "",
    ]

    # LLM review results
    if report.get('llm_review'):
        llm = report['llm_review']
        lines.extend([
            "## AI 审查意见",
            f"综合评分：{llm.get('score', 'N/A')}/10",
            f"审查摘要：{llm.get('summary', 'N/A')}",
            "",
        ])

        if llm.get('strengths'):
            lines.append("### ✅ 优点")
            for s in llm['strengths']:
                lines.append(f"- {s}")
            lines.append("")

        if llm.get('concerns'):
            lines.append("### ⚠️ 关注点")
            for c in llm['concerns']:
                lines.append(f"- {c}")
            lines.append("")

        if llm.get('suggestions'):
            lines.append("### 💡 改进建议")
            for s in llm['suggestions']:
                lines.append(f"- {s.get('file', '')}:{s.get('line', '')} - {s.get('issue', '')}")
                if s.get('suggestion'):
                    lines.append(f"  → {s['suggestion']}")
            lines.append("")

        lines.append(f"**建议操作**: {llm.get('approval_recommendation', 'comment')}")
        lines.append("")

    # Rule-detected issues
    if report.get('rule_based_issues'):
        issues = report['rule_based_issues']
        if issues:
            lines.extend([
                "## 🔍 规则检测问题",
                "",
            ])
            for issue in issues[:10]:  # Show at most 10
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                    issue['severity'], "⚪"
                )
                lines.append(
                    f"{severity_icon} [{issue['severity'].upper()}] "
                    f"{issue['file']}:{issue['line']}"
                )
                lines.append(f"   {issue['message']}")
                if issue.get('suggestion'):
                    lines.append(f"   💡 {issue['suggestion']}")
                lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
