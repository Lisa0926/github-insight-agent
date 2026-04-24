# -*- coding: utf-8 -*-
"""
代码质量/安全评分工具

功能:
- 基于 LLM 分析 GitHub 仓库的代码质量和安全最佳实践
- 生成质量评分 (1-5 分) 和安全评分 (1-5 分)
- 输出结构化评估报告

评估维度:
1. 代码质量
   - 文档完整性 (README、文档站点)
   - 测试覆盖 (测试文件存在性)
   - 代码规范 (linting 配置)
   - CI/CD 成熟度
   - 社区活跃度

2. 安全最佳实践
   - 安全策略文件 (SECURITY.md)
   - 依赖管理 (requirements.txt, package.json)
   - 许可证清晰度
   - 漏洞响应机制
   - 敏感信息泄露风险
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
    代码质量/安全评分器

    基于项目元数据和 README 内容，使用 LLM 进行智能评估。
    """

    # 评估维度权重
    QUALITY_DIMENSIONS = {
        "documentation": 0.20,      # 文档完整性
        "testing": 0.20,            # 测试覆盖
        "code_standards": 0.15,     # 代码规范
        "ci_cd": 0.15,              # CI/CD 成熟度
        "community": 0.15,          # 社区活跃度
        "maintenance": 0.15,        # 维护活跃
    }

    SECURITY_DIMENSIONS = {
        "security_policy": 0.25,    # 安全策略文件
        "dependency_management": 0.20,  # 依赖管理
        "license_clarity": 0.15,    # 许可证清晰度
        "vulnerability_response": 0.20,  # 漏洞响应
        "secret_exposure": 0.20,    # 敏感信息泄露
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化评分器

        Args:
            config: 配置管理器实例
        """
        self._config = config or ConfigManager()

        # 获取 LLM Provider（使用默认配置）
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
        从 README 和仓库信息中检测质量信号

        Args:
            readme_content: README 内容
            repo_info: 仓库元数据

        Returns:
            检测到的信号字典
        """
        signals = {
            # 文档信号
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

            # 测试信号
            "has_tests": any(keyword in readme_content.lower() for keyword in [
                "test", "spec", "coverage", "pytest", "unittest", "jest", "mocha"
            ]),
            "has_ci_badge": any(ci in readme_content.lower() for ci in [
                "github actions", "travis", "circleci", "jenkins", "gitlab ci"
            ]),
            "has_codecov": "codecov" in readme_content.lower() or "coveralls" in readme_content.lower(),

            # 代码规范信号
            "has_linting": any(lint in readme_content.lower() for lint in [
                "ruff", "flake8", "pylint", "eslint", "black", "prettier"
            ]),
            "has_type_hints": "typing" in readme_content.lower() or "type hints" in readme_content.lower(),

            # CI/CD 信号
            "has_github_actions": ".github" in readme_content.lower() or "github actions" in readme_content.lower(),
            "has_deploy_guide": any(keyword in readme_content.lower() for keyword in [
                "deploy", "deployment", "production", "release"
            ]),

            # 社区信号
            "has_contributing": "contributing" in readme_content.lower() or "contribute" in readme_content.lower(),
            "has_code_of_conduct": "code of conduct" in readme_content.lower(),
            "has_issue_template": "issue template" in readme_content.lower(),
            "stars": repo_info.get("stars", 0),
            "forks": repo_info.get("forks", 0),
            "open_issues": repo_info.get("open_issues", 0),

            # 安全信号
            "has_security_policy": "security" in readme_content.lower() or "security.md" in readme_content.lower(),
            "has_license": bool(repo_info.get("license")),
            "license_type": repo_info.get("license", "Unknown"),
            "has_dependencies": any(dep in readme_content.lower() for dep in [
                "requirements", "dependencies", "package.json", "pip", "npm", "yarn"
            ]),
        }

        # 计算派生指标
        signals["fork_rate"] = signals["forks"] / max(signals["stars"], 1)
        signals["issue_attention"] = signals["open_issues"] / max(signals["stars"], 1) * 100

        return signals

    def _calculate_rule_based_score(self, signals: Dict[str, Any]) -> Dict[str, float]:  # noqa: C901
        """
        基于规则的初步评分

        Args:
            signals: 检测到的信号

        Returns:
            各维度得分字典
        """
        # 质量评分 (0-5)
        quality_score = 0.0

        # 文档 (1 分)
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

        # 测试 (1 分)
        if signals["has_tests"]:
            quality_score += 0.4
        if signals["has_ci_badge"]:
            quality_score += 0.3
        if signals["has_codecov"]:
            quality_score += 0.3

        # 代码规范 (1 分)
        if signals["has_linting"]:
            quality_score += 0.5
        if signals["has_type_hints"]:
            quality_score += 0.5

        # CI/CD (1 分)
        if signals["has_github_actions"]:
            quality_score += 0.5
        if signals["has_deploy_guide"]:
            quality_score += 0.5

        # 社区 (1 分)
        if signals["has_contributing"]:
            quality_score += 0.34
        if signals["has_code_of_conduct"]:
            quality_score += 0.33
        if signals["has_issue_template"]:
            quality_score += 0.33

        # 安全评分 (0-5)
        security_score = 0.0

        # 安全策略 (1.25 分)
        if signals["has_security_policy"]:
            security_score += 1.25

        # 依赖管理 (1 分)
        if signals["has_dependencies"]:
            security_score += 0.5
        if signals["has_license"]:
            security_score += 0.5

        # 许可证清晰度 (0.75 分)
        if signals["license_type"] not in ["Unknown", "Other"]:
            security_score += 0.75

        # 社区健康 (1 分) - 间接反映安全关注度
        if 0.05 <= signals["fork_rate"] <= 0.5:
            security_score += 0.5
        if signals["issue_attention"] < 5:
            security_score += 0.5

        # 扣分项：可疑信号
        if signals["issue_attention"] > 20:
            security_score -= 0.5  # 太多未解决问题可能表示维护不善

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
        使用 LLM 进行增强评估

        Args:
            readme_content: README 内容
            repo_info: 仓库信息
            rule_scores: 基于规则的评分

        Returns:
            LLM 增强评估结果
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

            # 解析 JSON 响应
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
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
            logger.warning(f"LLM 评估失败，使用规则评分：{e}")
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
        综合评估项目质量和安全

        Args:
            readme_content: README 内容
            repo_info: 仓库信息
            use_llm: 是否使用 LLM 增强评估

        Returns:
            综合评估结果
        """
        logger.info(f"Evaluating code quality: {repo_info.get('full_name', 'Unknown')}")

        # 步骤 1: 检测质量信号
        signals = self._detect_quality_signals(readme_content, repo_info)

        # 步骤 2: 基于规则评分
        rule_scores = self._calculate_rule_based_score(signals)

        # 步骤 3: LLM 增强评估（可选）
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

        # 构建最终报告
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
    评估代码质量和安全（工具函数）

    Args:
        readme_content: README 内容
        repo_info: 仓库信息
        use_llm: 是否使用 LLM 增强
        config: 配置管理器

    Returns:
        ToolResponse 包装的评估结果
    """
    try:
        scorer = CodeQualityScorer(config=config)
        result = await scorer.evaluate(readme_content, repo_info, use_llm=use_llm)

        # 格式化为人类可读的报告
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
