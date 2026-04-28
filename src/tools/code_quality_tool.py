# -*- coding: utf-8 -*-
"""
Code quality/security scoring tool

Features:
- LLM-based analysis of GitHub repository code quality and security best practices
- Generates quality score (1-5) and security score (1-5)
- Outputs structured evaluation reports

Evaluation dimensions:
1. Code quality
   - Documentation completeness (README, docs site)
   - Test coverage (test file existence)
   - Code standards (linting configuration)
   - CI/CD maturity
   - Community activity

2. Security best practices
   - Security policy file (SECURITY.md)
   - Dependency management (requirements.txt, package.json)
   - License clarity
   - Vulnerability response mechanism
   - Sensitive information leak risk
"""

import json
from typing import Any, Dict, Optional

from src.core.logger import get_logger
from src.core.config_manager import ConfigManager
from src.llm.provider_factory import get_provider
from src.types.schemas import ToolResponse

logger = get_logger(__name__)


class CodeQualityScorer:
    """
    Code quality/security scorer

    Uses LLM-based intelligent evaluation based on project metadata and README content.
    """

    # Evaluation dimension weights
    QUALITY_DIMENSIONS = {
        "documentation": 0.20,      # Documentation completeness
        "testing": 0.20,            # Test coverage
        "code_standards": 0.15,     # Code standards
        "ci_cd": 0.15,              # CI/CD maturity
        "community": 0.15,          # Community activity
        "maintenance": 0.15,        # Maintenance activity
    }

    SECURITY_DIMENSIONS = {
        "security_policy": 0.25,    # Security policy file
        "dependency_management": 0.20,  # Dependency management
        "license_clarity": 0.15,    # License clarity
        "vulnerability_response": 0.20,  # Vulnerability response
        "secret_exposure": 0.20,    # Sensitive information leak
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        Initialize the scorer

        Args:
            config: Config manager instance
        """
        self._config = config or ConfigManager()

        # Get LLM Provider (using default config)
        provider_name = self._config.llm_provider.lower() if hasattr(self._config, 'llm_provider') else 'dashscope'
        api_key = self._config.dashscope_api_key if provider_name == 'dashscope' else None
        model = self._config.dashscope_model_name if provider_name == 'dashscope' else None

        try:
            self._llm_provider = get_provider(provider_name, api_key=api_key, model=model)
        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider: {e}. Using rule-based scoring only.")
            self._llm_provider = None

        logger.info("CodeQualityScorer initialized")

    def _detect_quality_signals(self, readme_content: str, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect quality signals from README and repository info

        Args:
            readme_content: README content
            repo_info: Repository metadata

        Returns:
            Dictionary of detected signals
        """
        signals = {
            # Documentation signals
            "has_readme": True,
            "has_badges": any(badge in readme_content.lower() for badge in [
                "[!", "![", "shield", "badge", "travis", "circleci", "codecov"
            ]),
            "has_installation_guide": any(keyword in readme_content.lower() for keyword in [
                "installation", "install", "setup", "quick start", "getting started"
            ]),
            "has_api_docs": any(keyword in readme_content.lower() for keyword in [
                "api", "reference", "documentation", "docs", "methods", "classes"
            ]),
            "has_examples": any(keyword in readme_content.lower() for keyword in [
                "example", "usage", "demo", "sample", "tutorial"
            ]),

            # Test signals
            "has_tests": any(keyword in readme_content.lower() for keyword in [
                "test", "spec", "coverage", "pytest", "unittest", "jest", "mocha"
            ]),
            "has_ci_badge": any(ci in readme_content.lower() for ci in [
                "github actions", "travis", "circleci", "jenkins", "gitlab ci"
            ]),
            "has_codecov": "codecov" in readme_content.lower() or "coveralls" in readme_content.lower(),

            # Code standards signals
            "has_linting": any(lint in readme_content.lower() for lint in [
                "ruff", "flake8", "pylint", "eslint", "black", "prettier"
            ]),
            "has_type_hints": "typing" in readme_content.lower() or "type hints" in readme_content.lower(),

            # CI/CD signals
            "has_github_actions": ".github" in readme_content.lower() or "github actions" in readme_content.lower(),
            "has_deploy_guide": any(keyword in readme_content.lower() for keyword in [
                "deploy", "deployment", "production", "release"
            ]),

            # Community signals
            "has_contributing": "contributing" in readme_content.lower() or "contribute" in readme_content.lower(),
            "has_code_of_conduct": "code of conduct" in readme_content.lower(),
            "has_issue_template": "issue template" in readme_content.lower(),
            "stars": repo_info.get("stars", 0),
            "forks": repo_info.get("forks", 0),
            "open_issues": repo_info.get("open_issues", 0),

            # Security signals
            "has_security_policy": "security" in readme_content.lower() or "security.md" in readme_content.lower(),
            "has_license": bool(repo_info.get("license")),
            "license_type": repo_info.get("license", "Unknown"),
            "has_dependencies": any(dep in readme_content.lower() for dep in [
                "requirements", "dependencies", "package.json", "pip", "npm", "yarn"
            ]),
        }

        # Compute derived metrics
        signals["fork_rate"] = signals["forks"] / max(signals["stars"], 1)
        signals["issue_attention"] = signals["open_issues"] / max(signals["stars"], 1) * 100

        return signals

    def _calculate_rule_based_score(self, signals: Dict[str, Any]) -> Dict[str, float]:  # noqa: C901
        """
        Rule-based preliminary scoring

        Args:
            signals: Detected signals

        Returns:
            Dictionary of per-dimension scores
        """
        # Quality score (0-5)
        quality_score = 0.0

        # Documentation (1 point)
        if signals["has_readme"]:
            quality_score += 0.2
        if signals["has_badges"]:
            quality_score += 0.2
        if signals["has_installation_guide"]:
            quality_score += 0.2
        if signals["has_api_docs"]:
            quality_score += 0.2
        if signals["has_examples"]:
            quality_score += 0.2

        # Testing (1 point)
        if signals["has_tests"]:
            quality_score += 0.4
        if signals["has_ci_badge"]:
            quality_score += 0.3
        if signals["has_codecov"]:
            quality_score += 0.3

        # Code standards (1 point)
        if signals["has_linting"]:
            quality_score += 0.5
        if signals["has_type_hints"]:
            quality_score += 0.5

        # CI/CD (1 point)
        if signals["has_github_actions"]:
            quality_score += 0.5
        if signals["has_deploy_guide"]:
            quality_score += 0.5

        # Community (1 point)
        if signals["has_contributing"]:
            quality_score += 0.34
        if signals["has_code_of_conduct"]:
            quality_score += 0.33
        if signals["has_issue_template"]:
            quality_score += 0.33

        # Security score (0-5)
        security_score = 0.0

        # Security policy (1.25 points)
        if signals["has_security_policy"]:
            security_score += 1.25

        # Dependency management (1 point)
        if signals["has_dependencies"]:
            security_score += 0.5
        if signals["has_license"]:
            security_score += 0.5

        # License clarity (0.75 points)
        if signals["license_type"] not in ["Unknown", "Other"]:
            security_score += 0.75

        # Community health (1 point) - indirectly reflects security attention
        if 0.05 <= signals["fork_rate"] <= 0.5:
            security_score += 0.5
        if signals["issue_attention"] < 5:
            security_score += 0.5

        # Deductions: suspicious signals
        if signals["issue_attention"] > 20:
            security_score -= 0.5  # Too many open issues may indicate poor maintenance

        return {
            "quality_rule_based": min(5.0, max(0.0, quality_score)),
            "security_rule_based": min(5.0, max(0.0, security_score)),
        }

    async def _llm_enhanced_score(
        self,
        readme_content: str,
        repo_info: Dict[str, Any],
        rule_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Use LLM for enhanced evaluation

        Args:
            readme_content: README content
            repo_info: Repository info
            rule_scores: Rule-based scores

        Returns:
            LLM-enhanced evaluation result
        """
        if self._llm_provider is None:
            logger.warning("LLM provider not available, using rule-based scoring")
            return {
                "quality_llm": rule_scores.get("quality_rule_based", 2.5),
                "security_llm": rule_scores.get("security_rule_based", 2.5),
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "assessment": "基于规则的自动评分（LLM 不可用）",
                "raw_llm_response": "",
            }

        prompt = f"""你是一个资深的代码质量评估专家。请分析以下 GitHub 项目的 README 和元数据，进行代码质量和安全评分。

## 项目信息
- 名称：{repo_info.get('full_name', 'Unknown')}
- Stars: {repo_info.get('stars', 0):,}
- Forks: {repo_info.get('forks', 0):,}
- 语言：{repo_info.get('language', 'Unknown')}
- 许可证：{repo_info.get('license', 'Unknown')}
- 主题：{', '.join(repo_info.get('topics', []))}

## README 内容 (前 3000 字符)
{readme_content[:3000] if len(readme_content) > 3000 else readme_content}

## 基于规则的初步评分
- 质量评分：{rule_scores.get('quality_rule_based', 0):.1f}/5
- 安全评分：{rule_scores.get('security_rule_based', 0):.1f}/5

请以 JSON 格式输出你的评估结果：
```json
{{
    "quality_score": 3.5,
    "security_score": 4.0,
    "quality_strengths": ["文档完整", "有测试示例"],
    "quality_weaknesses": ["缺少 CI 徽章", "无类型注解"],
    "security_strengths": ["有 MIT 许可证", "社区活跃"],
    "security_weaknesses": ["无 SECURITY.md"],
    "recommendations": ["添加 GitHub Actions CI", "创建安全策略文件"],
    "overall_assessment": "这是一个质量良好的项目，适合生产使用"
}}
```

只返回 JSON，不要其他解释。"""

        try:
            response = await self._llm_provider.chat([
                {"role": "system", "content": "你是一个专业的代码质量评估专家，擅长分析开源项目的质量和安全性。"},
                {"role": "user", "content": prompt},
            ])

            # Parse JSON response
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try direct parsing
                result = json.loads(response)

            return {
                "quality_llm": result.get("quality_score", rule_scores.get("quality_rule_based", 2.5)),
                "security_llm": result.get("security_score", rule_scores.get("security_rule_based", 2.5)),
                "strengths": result.get("quality_strengths", []) + result.get("security_strengths", []),
                "weaknesses": result.get("quality_weaknesses", []) + result.get("security_weaknesses", []),
                "recommendations": result.get("recommendations", []),
                "assessment": result.get("overall_assessment", ""),
                "raw_llm_response": response,
            }

        except Exception as e:
            logger.warning(f"LLM evaluation failed, using rule-based scoring: {e}")
            return {
                "quality_llm": rule_scores.get("quality_rule_based", 2.5),
                "security_llm": rule_scores.get("security_rule_based", 2.5),
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "assessment": "基于规则的自动评分（LLM 评估失败）",
                "raw_llm_response": "",
            }

    async def evaluate(
        self,
        readme_content: str,
        repo_info: Dict[str, Any],
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Comprehensive project quality and security evaluation

        Args:
            readme_content: README content
            repo_info: Repository info
            use_llm: Whether to use LLM-enhanced evaluation

        Returns:
            Comprehensive evaluation result
        """
        logger.info(f"Evaluating code quality: {repo_info.get('full_name', 'Unknown')}")

        # Step 1: Detect quality signals
        signals = self._detect_quality_signals(readme_content, repo_info)

        # Step 2: Rule-based scoring
        rule_scores = self._calculate_rule_based_score(signals)

        # Step 3: LLM-enhanced evaluation (optional)
        if use_llm:
            llm_result = await self._llm_enhanced_score(readme_content, repo_info, rule_scores)
            final_quality = (rule_scores["quality_rule_based"] + llm_result["quality_llm"]) / 2
            final_security = (rule_scores["security_rule_based"] + llm_result["security_llm"]) / 2
        else:
            final_quality = rule_scores["quality_rule_based"]
            final_security = rule_scores["security_rule_based"]
            llm_result = {
                "strengths": [],
                "weaknesses": [],
                "recommendations": [],
                "assessment": "基于规则的自动评分",
            }

        # Build final report
        report = {
            "quality_score": round(final_quality, 2),
            "security_score": round(final_security, 2),
            "overall_score": round((final_quality + final_security) / 2, 2),
            "quality_breakdown": {
                "documentation": "detected" if signals["has_readme"] and signals["has_installation_guide"] else "missing",
                "testing": "detected" if signals["has_tests"] else "unknown",
                "ci_cd": "detected" if signals["has_github_actions"] else "unknown",
                "community": "active" if signals["stars"] > 100 else "growing",
            },
            "security_breakdown": {
                "policy": "present" if signals["has_security_policy"] else "missing",
                "license": signals["license_type"],
                "dependencies": "managed" if signals["has_dependencies"] else "unknown",
            },
            "signals_detected": signals,
            "strengths": llm_result.get("strengths", []),
            "weaknesses": llm_result.get("weaknesses", []),
            "recommendations": llm_result.get("recommendations", []),
            "assessment": llm_result.get("assessment", ""),
        }

        logger.info(
            f"Quality: {report['quality_score']}/5, Security: {report['security_score']}/5"
        )

        return report


async def evaluate_code_quality(
    readme_content: str,
    repo_info: Dict[str, Any],
    use_llm: bool = True,
    config: Optional[ConfigManager] = None,
) -> ToolResponse:
    """
    Evaluate code quality and security (tool function)

    Args:
        readme_content: README content
        repo_info: Repository info
        use_llm: Whether to use LLM enhancement
        config: Config manager

    Returns:
        Evaluation result wrapped in ToolResponse
    """
    try:
        scorer = CodeQualityScorer(config=config)
        result = await scorer.evaluate(readme_content, repo_info, use_llm=use_llm)

        # Format as human-readable report
        report_text = f"""## 代码质量评估报告

**项目**: {repo_info.get('full_name', 'Unknown')}

### 综合评分
| 维度 | 得分 |
|------|------|
| 📊 代码质量 | {result['quality_score']}/5.0 |
| 🔒 安全最佳实践 | {result['security_score']}/5.0 |
| 🎯 总体评分 | {result['overall_score']}/5.0 |

### 优势
{chr(10).join(f"- ✅ {s}" for s in result['strengths']) if result['strengths'] else '- 暂无明显优势'}

### 待改进
{chr(10).join(f"- ⚠️ {w}" for w in result['weaknesses']) if result['weaknesses'] else '- 无明显短板'}

### 建议
{chr(10).join(f"- 📌 {r}" for r in result['recommendations']) if result['recommendations'] else '- 保持现状'}

### 评估摘要
{result['assessment']}
"""

        return ToolResponse.ok(
            data=result,
            message=report_text,
        )

    except Exception as e:
        logger.error(f"代码质量评估失败：{e}")
        return ToolResponse.fail(error_message=str(e))
