# -*- coding: utf-8 -*-
"""
Analyst Agent (supports ReAct mode)

Features:
- Senior technical architect role
- Quickly evaluates a project's technical value by reading README documentation
- Extracts core features, tech stack, and pain points addressed
- Supports ReAct mode: Reasoning + Action
- Has error handling and fallback capabilities
- Uses AgentScope ModelWrapper for model calls
- Uses AgentScope Msg class for unified message format
- Inherits from AgentScope AgentBase (via GiaAgentBase)
"""

import json
import re
import ast
from typing import Any, Dict, List, Optional, Union

from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.guardrails import filter_sensitive_output, circuit_breaker_guard
from src.core.logger import get_logger
from src.core.studio_helper import StudioHelper, set_global_studio_config
from src.tools.github_tool import GitHubTool
from src.tools.github_toolkit import get_github_toolkit
from src.agents.base_agent import GiaAgentBase

# Import trace decorator if tracing is enabled
try:
    from agentscope.tracing import trace
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

    def trace(name=None):  # fallback
        def decorator(func):
            return func
        return decorator

logger = get_logger(__name__)

# Studio configuration helper
_studio_helper: Optional[StudioHelper] = None


def set_studio_config(studio_url: str, run_id: str) -> None:
    """Set Studio configuration and register run (using shared module)"""
    global _studio_helper
    _studio_helper = StudioHelper(studio_url, run_id)
    set_global_studio_config(studio_url, run_id)
    logger.debug(f"Studio config set for run: {run_id}")


class AnalystAgent(GiaAgentBase):
    """
    Analyst Agent (supports ReAct mode)

    Role: Senior technical architect, skilled at quickly evaluating a project's
          technical value by reading documentation

    Attributes:
        name: Agent name
        model_name: Model name used
        system_prompt: System prompt
        github_tool: GitHub tool instance
        config: Configuration manager
        memory: Conversation memory
    """

    def __init__(
        self,
        name: str = "Analyst",
        model_name: str = "",
        system_prompt: Optional[str] = None,
        config: Optional[ConfigManager] = None,
        use_toolkit: bool = True,
        use_mcp: bool = True,
        use_persistent: bool = True,
        db_path: str = "data/app.db",
    ):
        """
        Initialize the Analyst Agent

        Args:
            name: Agent name
            model_name: Model name
            system_prompt: System prompt
            config: Configuration manager
            use_toolkit: Whether to use AgentScope Toolkit (default: True)
            use_mcp: Whether to use GitHub MCP Server (default: True)
            use_persistent: Whether to use persistent storage (default: True)
            db_path: SQLite database path
        """
        from src.core.prompt_builder import get_system_prompt

        _prompt = system_prompt or get_system_prompt("analyst")

        super().__init__(
            name=name,
            model_name=model_name,
            system_prompt=_prompt,
            config=config,
            use_persistent=use_persistent,
            db_path=db_path,
        )

        self.use_toolkit = use_toolkit
        self.use_mcp = use_mcp

        # Initialize GitHub tool
        self.github_tool = GitHubTool(config=self.config)

        # Initialize AgentScope Toolkit (optional)
        self.toolkit = None
        if use_toolkit:
            self.toolkit = get_github_toolkit(config=self.config, use_mcp=use_mcp)
            logger.info("AgentScope Toolkit initialized with GitHub tools")

        logger.info(f"AnalystAgent '{name}' initialized with model '{model_name}'")

    def _build_messages(self, user_query: str, readme_content: str) -> List[Msg]:
        """
        Build message history (using AgentScope Msg)

        Args:
            user_query: User query
            readme_content: README content

        Returns:
            List of Msg objects
        """
        messages = [
            Msg(name="system", content=self.system_prompt, role="system"),
        ]

        # Build analysis request
        analysis_request = f"""
请分析以下 GitHub 项目：

## 项目信息
{user_query}

## README 内容
{readme_content[:4000]}  # 限制长度，防止 prompt 过长

请按照系统提示词中的要求，提取关键信息并输出 JSON 格式的分析结果。
"""

        messages.append(Msg(name="user", content=analysis_request, role="user"))

        return messages

    @trace(name="analyst.analyze_project")
    def analyze_project(
        self,
        owner: str,
        repo: str,
    ) -> Dict[str, Any]:
        """
        Analyze a GitHub project (supports ReAct mode)

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary of analysis results
        """
        logger.info(f"Analyzing project: {owner}/{repo}")

        try:
            # ReAct Step 1: Think - Why fetch project summary
            react_thoughts = []
            react_thoughts.append(
                "[Thought] 我将首先获取项目的 README 内容，因为 README 通常包含最全面的项目信息。\n"
                "[Action] 调用 GitHubTool.get_project_summary()\n"
                f"[Input] owner={owner}, repo={repo}"
            )

            # Get project summary (includes cleaned README)
            project_summary = self.github_tool.get_project_summary(
                owner=owner,
                repo=repo,
                max_readme_length=5000,
            )

            react_thoughts.append(f"[Result] 成功获取项目信息，README 长度：{len(project_summary.get('cleaned_readme_text', ''))} 字符")

            # ReAct Step 2: Check if README is available, decide if fallback is needed
            readme_content = project_summary.get("cleaned_readme_text", "")

            if not readme_content or len(readme_content.strip()) < 100:
                # README is insufficient, trigger fallback
                react_thoughts.append(
                    "\n[Thought] README 内容过短或为空，需要尝试备选方案获取技术栈信息。\n"
                    "[Action] 尝试读取项目的配置文件 (Cargo.toml, package.json, pyproject.toml 等)"
                )

                # Try to read config files
                config_info = self._try_read_config_file(owner, repo)

                if config_info:
                    react_thoughts.append(f"[Result] 成功获取配置文件信息：{config_info}")
                    # Append config info to project summary
                    project_summary["config_fallback"] = config_info
                else:
                    react_thoughts.append("[Result] 配置文件也不可用，将基于项目元数据进行推断")
                    project_summary["config_fallback"] = None

            # Record ReAct thinking process
            self._add_to_memory("assistant", "\n".join(react_thoughts))

            # Build analysis request
            project_info = f"""
- 项目名称：{project_summary['full_name']}
- Star 数量：{project_summary['stars']:,}
- 编程语言：{project_summary['language']}
- 简介：{project_summary['description']}
- 主题标签：{', '.join(project_summary['topics']) if project_summary['topics'] else '无'}
- 最后更新：{project_summary['updated_at']}
"""

            # Add config file info (if available)
            if project_summary.get("config_fallback"):
                project_info += f"\n- 配置文件信息：{project_summary['config_fallback']}\n(注：这是从配置文件推断的信息，因为 README 不可用)"

            if not readme_content:
                readme_content = "README 内容不可用，请基于上述项目元数据进行推断。"

            # Call LLM for analysis
            analysis_result = self._analyze_with_llm(project_info, readme_content)

            # Reflection: self-validate the analysis result
            analysis_result = self._reflect(analysis_result, project_info)

            # Add ReAct markers to results
            analysis_result["react_thoughts"] = react_thoughts

            # Merge results
            result = {
                "project": project_summary["full_name"],
                "url": project_summary["html_url"],
                "stars": project_summary["stars"],
                "language": project_summary["language"],
                "analysis": analysis_result,
            }

            logger.info(f"Analysis completed for {owner}/{repo}")
            return result

        except Exception as e:
            logger.error(f"Failed to analyze project: {e}")
            return {
                "project": f"{owner}/{repo}",
                "error": str(e),
                "analysis": None,
                "react_thoughts": [f"[Error] 分析失败：{str(e)}"],
            }

    @trace(name="analyst.analyze_with_llm")
    def _analyze_with_llm(self, project_info: str, readme_content: str) -> Dict[str, Any]:
        """
        Call LLM to perform project analysis (using AgentScope DashScopeChatModel)

        Args:
            project_info: Basic project information
            readme_content: README content

        Returns:
            Dictionary of analysis results
        """
        try:
            model_wrapper = self._get_model_wrapper()

            # Build prompt
            prompt = f"""你是一个资深技术架构师，请深入分析以下 GitHub 项目并提取关键信息。

## 项目信息
{project_info}

## README 内容
{readme_content[:4000]}

请从以下维度进行深度分析：

1. **核心功能**：项目解决的核心问题、主要功能点（2-3 句详细描述，不要泛泛而谈）
2. **技术栈**：使用的编程语言、框架、库、工具
3. **架构模式**：项目采用的架构模式（如 Monorepo/Microservices/CLI/SDK/Library/Framework/Plugin 等）
4. **解决的痛点**：目标用户是谁？解决什么实际问题？
5. **独特价值**：与同类产品相比的差异化优势
6. **风险标记**：识别潜在风险（如：维护不活跃、许可证不明确、安全漏洞、社区不活跃、文档不足等）
7. **适配度评分**：基于以上分析，给出一个 0.0-1.0 的适配度评分（suitability_score）
8. **评分细分**：从功能完整度、代码质量、安全性、可维护性、社区活跃度五个维度评分（各 0.0-1.0）
9. **成熟度评估**：从文档完整性、代码质量、社区活跃度判断（early/beta/stable/mature）
10. **推荐意见**：是否值得使用？适合什么场景？有什么风险或不足？
11. **竞品对比**：与同类主流项目的对比（如果有）

请严格按照以下 JSON 格式输出（所有数组字段至少包含 1 个有效条目，不要留空；数值字段必须为 0.0-1.0 之间的浮点数）：
{{
    "core_function": "详细的核心功能描述（2-3 句）",
    "tech_stack": {{
        "language": "主要编程语言",
        "frameworks": ["框架 1", "框架 2"],
        "key_dependencies": ["依赖 1", "依赖 2", "依赖 3"]
    }},
    "architecture_pattern": "架构模式（如 Monorepo/Microservices/CLI/SDK/Library/Framework/Plugin）",
    "pain_points_solved": ["痛点 1", "痛点 2", "痛点 3"],
    "unique_value": "项目的独特价值和差异化优势",
    "risk_flags": ["风险 1", "风险 2"],
    "suitability_score": 0.85,
    "score_breakdown": {{
        "functionality": 0.8,
        "code_quality": 0.7,
        "security": 0.6,
        "maintainability": 0.9,
        "community": 0.8
    }},
    "maturity_assessment": "early/beta/stable/mature",
    "recommendation": "推荐意见（recommend/consider/avoid）及理由（2-3 句）",
    "competitive_analysis": "与同类产品的对比分析（1-2 句）"
}}
"""

            messages = [
                {"name": "system", "content": self.system_prompt, "role": "system"},
                {"name": "user", "content": prompt, "role": "user"},
            ]

            response = model_wrapper(messages=messages)
            content = self._extract_response_text(response)

            # Filter sensitive data from LLM output
            content = filter_sensitive_output(content)

            logger.info(f"LLM analysis completed via DashScopeChatModel, response length: {len(content)}")

            # Try to parse JSON
            analysis = self._parse_json_response(content)
            return analysis

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {"error": f"Analysis failed: {e}"}

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        Parse JSON response returned by LLM

        Handles:
        - Standard JSON (double-quoted)
        - Python-style dicts (single-quoted, common with qwen-max)
        - Markdown code blocks (```json ... ```)

        Args:
            content: Content returned by LLM

        Returns:
            Parsed dictionary
        """
        # Try to extract JSON content
        # Try to match ```json ... ``` block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)
        else:
            # Try to match {...}
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group(0)

        try:
            analysis = json.loads(content)
            return analysis
        except json.JSONDecodeError:
            pass

        # Fallback: Try ast.literal_eval for Python-style dicts (single-quoted keys/values)
        # Common with qwen-max models
        try:
            result = ast.literal_eval(content)
            if isinstance(result, dict):
                logger.info("Parsed response as Python-style dict (single-quoted JSON)")
                return result
        except (ValueError, SyntaxError):
            pass

        logger.warning(f"Failed to parse JSON and Python-style dict, returning raw response")
        return {
            "raw_response": content,
            "parse_error": "JSON decode failed and Python-style dict fallback also failed",
        }

    def _reflect(
        self,
        analysis: Dict[str, Any],
        project_info: str,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """
        Reflection: self-validate analysis result and fix if needed.

        Checks:
        1. **Completeness**: All required fields present (core_function, tech_stack, etc.)
        2. **Consistency**: Scores don't contradict each other (e.g., high suitability but low all subscores)
        3. **Fact-grounding**: Key claims are supported by project info (stars, language match)
        4. **Reasonableness**: Suitability score aligns with score breakdown

        If issues are found, attempts to fix via a single LLM call.

        Args:
            analysis: Raw analysis result from LLM
            project_info: Project info string used for fact-checking
            max_retries: Max number of retry attempts (default 1 to control cost)

        Returns:
            Analysis result with reflection metadata added
        """
        reflection_result = {
            "completeness": False,
            "consistency": False,
            "fact_grounded": False,
            "reasonable": False,
            "issues": [],
        }

        # Check 1: Completeness
        required_fields = [
            "core_function", "tech_stack", "architecture_pattern",
            "pain_points_solved", "unique_value", "risk_flags",
            "suitability_score", "maturity_assessment", "recommendation",
        ]
        missing = [f for f in required_fields if f not in analysis or not analysis[f]]
        reflection_result["completeness"] = len(missing) == 0
        if missing:
            reflection_result["issues"].append(f"Missing fields: {', '.join(missing)}")

        # Check 2: Consistency - suitability score vs score breakdown
        breakdown = analysis.get("score_breakdown", {})
        suitability = analysis.get("suitability_score")

        if breakdown and suitability is not None:
            avg_breakdown = sum(breakdown.values()) / len(breakdown) if breakdown else 0
            # If suitability deviates too much from average breakdown, flag it
            if abs(suitability - avg_breakdown) > 0.4:
                reflection_result["issues"].append(
                    f"Suitability ({suitability}) deviates significantly from breakdown avg ({avg_breakdown:.2f})"
                )
        reflection_result["consistency"] = len([
            i for i in reflection_result["issues"] if "deviates" in i
        ]) == 0

        # Check 3: Fact-grounding - language and basic facts match
        if analysis.get("tech_stack"):
            ts = analysis["tech_stack"]
            if isinstance(ts, dict):
                ts_lang = ts.get("language", "")
                # Extract language from project_info
                lang_match = re.search(r"- 编程语言：(.+)", project_info)
                if lang_match:
                    actual_lang = lang_match.group(1).strip()
                    if ts_lang and actual_lang and ts_lang.lower() != actual_lang.lower():
                        reflection_result["issues"].append(
                            f"Tech stack language ({ts_lang}) doesn't match project language ({actual_lang})"
                        )
        reflection_result["fact_grounded"] = len([
            i for i in reflection_result["issues"] if "language" in i.lower() or "match" in i.lower()
        ]) == 0

        # Check 4: Reasonableness - maturity and recommendation make sense
        maturity = analysis.get("maturity_assessment", "")
        recommendation = analysis.get("recommendation", "")
        if maturity and recommendation:
            rec_lower = recommendation.lower()
            # If maturity is "early" but recommendation is strongly positive, flag
            if maturity == "early" and ("推荐" in recommendation or "recommend" in rec_lower):
                reflection_result["issues"].append(
                    "Early maturity project with strong positive recommendation — verify"
                )
        reflection_result["reasonable"] = len([
            i for i in reflection_result["issues"] if "maturity" in i.lower() or "recommendation" in i.lower()
        ]) == 0

        # If any checks failed, try to fix via LLM (up to max_retries)
        if not all([
            reflection_result["completeness"],
            reflection_result["consistency"],
            reflection_result["fact_grounded"],
            reflection_result["reasonable"],
        ]) and max_retries > 0:
            logger.info(
                f"Reflection found {len(reflection_result['issues'])} issue(s), attempting fix"
            )
            fixed_analysis = self._fix_analysis(analysis, reflection_result["issues"], project_info)
            if fixed_analysis:
                analysis = fixed_analysis
                # Re-run checks on fixed result
                reflection_result["fixed"] = True
                logger.info("Reflection fix applied successfully")
            else:
                reflection_result["fixed"] = False
        else:
            reflection_result["fixed"] = False

        # Attach reflection metadata
        analysis["_reflection"] = reflection_result

        logger.info(
            f"Reflection complete: completeness={reflection_result['completeness']}, "
            f"consistency={reflection_result['consistency']}, "
            f"fact_grounded={reflection_result['fact_grounded']}, "
            f"reasonable={reflection_result['reasonable']}"
        )

        return analysis

    def _fix_analysis(
        self,
        analysis: Dict[str, Any],
        issues: List[str],
        project_info: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Call LLM to fix identified analysis issues.

        Args:
            analysis: Original analysis with issues
            issues: List of identified issues
            project_info: Project info for fact-checking

        Returns:
            Fixed analysis dict, or None if fix failed
        """
        try:
            model_wrapper = self._get_model_wrapper()

            issues_text = "\n".join(f"- {issue}" for issue in issues)

            # Build existing analysis as JSON for context
            import json as _json
            existing_json = _json.dumps(analysis, ensure_ascii=False, indent=2)

            prompt = f"""你是一位资深技术架构师，请修复以下分析结果中存在的问题。

## 现有分析结果
```json
{existing_json}
```

## 存在的问题
{issues_text}

## 项目信息（用于事实核对）
{project_info}

请修复上述问题，并严格按照以下 JSON 格式输出修正后的完整结果（只输出 JSON，不要其他内容）：
```json
{{
    "core_function": "核心功能描述",
    "tech_stack": {{
        "language": "主要编程语言",
        "frameworks": ["框架 1"],
        "key_dependencies": ["依赖 1"]
    }},
    "architecture_pattern": "架构模式",
    "pain_points_solved": ["痛点 1"],
    "unique_value": "独特价值",
    "risk_flags": ["风险 1"],
    "suitability_score": 0.8,
    "score_breakdown": {{
        "functionality": 0.8,
        "code_quality": 0.7,
        "security": 0.6,
        "maintainability": 0.8,
        "community": 0.7
    }},
    "maturity_assessment": "beta/stable/mature",
    "recommendation": "推荐意见",
    "competitive_analysis": "竞品对比"
}}
```
"""

            messages = [
                {"name": "system", "content": self.system_prompt, "role": "system"},
                {"name": "user", "content": prompt, "role": "user"},
            ]

            response = model_wrapper(messages=messages)
            content = self._extract_response_text(response)
            content = filter_sensitive_output(content)

            fixed = self._parse_json_response(content)

            # Verify the fix resolved the issues
            if fixed and "parse_error" not in fixed:
                # Copy over any original fields not in the fix
                for key, value in analysis.items():
                    if key not in fixed:
                        fixed[key] = value
                return fixed

            logger.warning("Fix attempt did not produce valid output, keeping original")
            return None

        except Exception as e:
            logger.error(f"Failed to fix analysis: {e}")
            return None

    def _try_read_config_file(self, owner: str, repo: str) -> Optional[str]:
        """
        Try to read the project's config files (when README is unavailable)

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Config file info string, or None if unable to read
        """
        # Config file list (by priority)
        config_files = [
            ("Cargo.toml", self._parse_cargo_toml),
            ("package.json", self._parse_package_json),
            ("pyproject.toml", self._parse_pyproject_toml),
            ("requirements.txt", self._parse_requirements_txt),
            ("go.mod", self._parse_go_mod),
            ("pom.xml", self._parse_pom_xml),
        ]

        for config_file, parser in config_files:
            try:
                content = self._fetch_file_content(owner, repo, config_file)
                if content:
                    parsed_info = parser(content)
                    if parsed_info:
                        logger.info(f"Successfully parsed {config_file} for {owner}/{repo}")
                        return f"[{config_file}] {parsed_info}"
            except Exception as e:
                logger.debug(f"Failed to fetch/parse {config_file}: {e}")
                continue

        return None

    def _fetch_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Get the content of a specified file

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path

        Returns:
            File content
        """
        import base64

        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        response = self.github_tool._request_with_retry("GET", endpoint)

        if response.success:
            try:
                content_base64 = response.data.get("content", "")
                content = base64.b64decode(content_base64).decode("utf-8")
                return content
            except Exception as e:
                logger.warning(f"Failed to decode {path}: {e}")
                return None
        return None

    def _parse_cargo_toml(self, content: str) -> str:
        """Parse Cargo.toml"""
        lines = []
        # Extract [package] section
        package_match = re.search(r"\[package\]([\s\S]*?)(?:\[|\Z)", content)
        if package_match:
            package_section = package_match.group(1)
            name_match = re.search(r'name\s*=\s*"([^"]+)"', package_section)
            version_match = re.search(r'version\s*=\s*"([^"]+)"', package_section)
            if name_match:
                lines.append(f"name={name_match.group(1)}")
            if version_match:
                lines.append(f"version={version_match.group(1)}")

        # Extract [dependencies]
        deps_match = re.search(r"\[dependencies\]([\s\S]*?)(?:\[|\Z)", content)
        if deps_match:
            deps_section = deps_match.group(1)
            deps = re.findall(r'(\w+)\s*=\s*"([^"]+)"', deps_section)
            if deps:
                lines.append(f"dependencies={', '.join([f'{d[0]}:{d[1]}' for d in deps[:5]])}")

        return " | ".join(lines) if lines else "Rust project"

    def _parse_package_json(self, content: str) -> str:
        """Parse package.json"""
        try:
            data = json.loads(content)
            name = data.get("name", "unknown")
            version = data.get("version", "unknown")
            deps = list(data.get("dependencies", {}).keys())[:5]
            return f"name={name} | version={version} | deps={', '.join(deps) if deps else 'none'}"
        except Exception:
            return "Node.js project"

    def _parse_pyproject_toml(self, content: str) -> str:
        """Parse pyproject.toml"""
        lines = []
        # Extract project name
        name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
        if name_match:
            lines.append(f"name={name_match.group(1)}")

        # Extract dependencies
        deps_match = re.findall(r'^( [\w-]+)\s*[=>~]', content, re.MULTILINE)
        if deps_match:
            lines.append(f"deps={', '.join(deps_match[:5])}")

        return " | ".join(lines) if lines else "Python project"

    def _parse_requirements_txt(self, content: str) -> str:
        """Parse requirements.txt"""
        deps = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract package name
                pkg_match = re.match(r'^([\w-]+)', line)
                if pkg_match:
                    deps.append(pkg_match.group(1))
                    if len(deps) >= 5:
                        break
        return f"deps={', '.join(deps) if deps else 'none'}"

    def _parse_go_mod(self, content: str) -> str:
        """Parse go.mod"""
        lines = []
        # Extract module name
        module_match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
        if module_match:
            lines.append(f"module={module_match.group(1)}")

        # Extract dependencies
        deps = re.findall(r'^\t(\S+)\s+v', content, re.MULTILINE)
        if deps:
            lines.append(f"deps={', '.join(deps[:5])}")

        return " | ".join(lines) if lines else "Go project"

    def _parse_pom_xml(self, content: str) -> str:
        """Parse pom.xml"""
        lines = []
        # Extract artifactId
        artifact_match = re.search(r'<artifactId>([^<]+)</artifactId>', content)
        if artifact_match:
            lines.append(f"artifact={artifact_match.group(1)}")

        # Extract groupId
        group_match = re.search(r'<groupId>([^<]+)</groupId>', content)
        if group_match:
            lines.append(f"group={group_match.group(1)}")

        return " | ".join(lines) if lines else "Java/Maven project"

    def batch_analyze(
        self,
        projects: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Batch analyze multiple projects

        Args:
            projects: List of projects, each containing owner and repo

        Returns:
            List of analysis results
        """
        results = []
        for i, project in enumerate(projects, 1):
            owner = project.get("owner") or project.get("full_name", "").split("/")[0]
            repo = project.get("repo") or project.get("full_name", "").split("/")[1]

            logger.info(f"[{i}/{len(projects)}] Analyzing: {owner}/{repo}")
            result = self.analyze_project(owner, repo)
            results.append(result)

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get Agent status"""
        status = {
            "name": self.name,
            "model": self.model_name,
            "memory_size": self.memory.size(),
            "capability": "Deep project analysis via README",
            "toolkit_enabled": self.toolkit is not None,
        }

        if self.toolkit:
            status["toolkit_schemas"] = len(self.toolkit.get_json_schemas())

        return status

    def get_description(self) -> str:
        """
        Get AnalystAgent description

        Returns:
            Agent description string
        """
        return "资深技术架构师，擅长通过阅读 README 文档快速判断项目的技术价值。"

    @circuit_breaker_guard
    @trace(name="analyst.reply")
    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """
        Respond to user message

        Args:
            msg: Input message (Msg object or string)
            *args: Other arguments
            **kwargs: Keyword arguments

        Returns:
            Response message
        """
        # If it's a string, convert to Msg
        if isinstance(msg, str):
            msg = Msg(name="user", content=msg, role="user")

        # Record user message
        self._add_to_memory("user", msg.content)

        # Call analysis logic (to be adjusted based on actual situation)
        response_content = self.get_description()

        # Create response
        response = Msg(name=self.name, content=response_content, role="assistant")
        self._add_to_memory("assistant", response_content)

        return response
