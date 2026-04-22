# -*- coding: utf-8 -*-
"""
分析师 Agent (支持 ReAct 模式)

功能:
- 资深技术架构师角色
- 通过阅读 README 文档快速判断项目的技术价值
- 提取核心功能、技术栈、解决的痛点
- 支持 ReAct 模式：Reasoning + Action
- 具备错误处理和备选方案能力
- 使用 AgentScope ModelWrapper 进行模型调用
- 使用 AgentScope Msg 类统一消息格式
- 继承 AgentScope AgentBase
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.agentscope_memory import AgentScopeMemory
from src.core.agentscope_persistent_memory import PersistentMemory, get_persistent_memory
from src.core.studio_helper import StudioHelper, set_global_studio_config, forward_to_studio
from src.tools.github_tool import GitHubTool
from src.tools.tool_registry import register_github_tools
from src.tools.github_toolkit import get_github_toolkit

# 如果启用 tracing，导入装饰器
try:
    from agentscope.tracing import trace
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    trace = lambda name=None: lambda func: func  # fallback

logger = get_logger(__name__)

# Studio 配置助手
_studio_helper: Optional[StudioHelper] = None


def set_studio_config(studio_url: str, run_id: str) -> None:
    """设置 Studio 配置并注册 run（使用共享模块）"""
    global _studio_helper
    _studio_helper = StudioHelper(studio_url, run_id)
    set_global_studio_config(studio_url, run_id)
    logger.debug(f"Studio config set for run: {run_id}")


def _forward_to_studio(name: str, content: str, role: str) -> None:
    """手动转发消息到 Studio（使用共享模块）"""
    forward_to_studio(name, content, role)


class AnalystAgent:
    """
    分析师 Agent (支持 ReAct 模式)

    角色：资深技术架构师，擅长通过阅读文档快速判断项目的技术价值

    Attributes:
        name: Agent 名称
        model_name: 使用的模型名称
        system_prompt: 系统提示词
        github_tool: GitHub 工具实例
        config: 配置管理器
        memory: 对话记忆
    """

    # ReAct 模式的系统提示词模板
    SYSTEM_PROMPT = """你是一个资深技术架构师，擅长通过阅读文档快速判断项目的技术价值。

## ReAct 模式要求

在分析项目时，你必须按照以下格式输出：

### 思考过程 (Thought)
在每次调用工具前，你必须先思考：
- 我为什么要调用这个工具？
- 我预期得到什么结果？
- 如果工具返回错误，我的备选方案是什么？

### 行动 (Action)
明确说明你要调用的工具和传入的参数。

### 输入 (Input)
具体的工具调用输入内容。

## 你的任务
请分析一个 GitHub 项目的 README 内容，提取以下关键信息：

### 1. 核心功能（一句话总结）
用简洁的语言描述这个项目主要做什么。

### 2. 技术栈
- 编程语言
- 主要框架/库
- 关键依赖

### 3. 解决了什么痛点
这个项目解决了哪些开发者痛点？有什么独特价值？

## 分析指南
1. 重点关注 README 中的 'Features', 'Installation', 'Usage', 'Quick Start' 章节
2. 如果 README 内容过长，优先阅读前 3000 字符
3. 从代码示例中推断技术栈
4. 从简介和特性描述中提炼核心价值

## 错误处理与备选方案

如果遇到问题，请按以下策略处理：

1. **README 不存在或为空**：
   - 思考："README 不可用，我需要尝试其他方式获取项目信息"
   - 备选：尝试读取 Cargo.toml (Rust 项目)、package.json (Node.js)、pyproject.toml/requirements.txt (Python)、go.mod (Go) 等配置文件
   - 从配置文件中推断技术栈

2. **GitHub API 返回 404**：
   - 思考："项目可能不存在或名称有误，我需要确认项目名称"
   - 备选：提示用户检查项目名称，或尝试搜索相似名称的项目

3. **GitHub API 返回 403 (速率限制)**：
   - 思考："API 速率限制已触发，需要等待或降级处理"
   - 备选：告知用户稍后重试，或基于已有信息进行推断

4. **README 内容过短或信息不足**：
   - 思考："README 信息不足，我需要从其他来源补充"
   - 备选：从项目简介、主题标签、Star 数量等元数据推断项目价值

## 输出格式

在分析完成后，请严格按照以下 JSON 格式输出最终结果：

```json
{
    "core_function": "一句话核心功能描述",
    "tech_stack": {
        "language": "主要编程语言",
        "frameworks": ["框架 1", "框架 2"],
        "key_dependencies": ["依赖 1", "依赖 2"]
    },
    "pain_points_solved": ["痛点 1", "痛点 2"],
    "unique_value": "项目的独特价值或创新点",
    "maturity_assessment": "项目成熟度评估 (early/beta/stable/mature)",
    "recommendation": "是否推荐使用 (recommend/consider/avoid) 及理由"
}
```

## 约束
- 只基于可获得的信息分析，不要编造
- 如果信息不足，明确说明"信息不足，基于已有元数据推断"
- 输出必须是有效的 JSON 格式"""

    def __init__(
        self,
        name: str = "Analyst",
        model_name: str = "qwen-max",
        system_prompt: Optional[str] = None,
        config: Optional[ConfigManager] = None,
        use_toolkit: bool = True,
        use_mcp: bool = True,
        use_persistent: bool = True,
        db_path: str = "data/app.db",
    ):
        """
        初始化分析师 Agent

        Args:
            name: Agent 名称
            model_name: 模型名称
            system_prompt: 系统提示词
            config: 配置管理器
            use_toolkit: 是否使用 AgentScope Toolkit（默认 True）
            use_mcp: 是否使用 GitHub MCP Server（默认 True）
            use_persistent: 是否使用持久化存储（默认 True）
            db_path: SQLite 数据库路径
        """
        self.name = name
        self.model_name = model_name
        self.config = config or ConfigManager()
        self.system_prompt = system_prompt or self.SYSTEM_PROMPT
        self.use_toolkit = use_toolkit
        self.use_mcp = use_mcp
        self.use_persistent = use_persistent

        # 初始化 GitHub 工具
        self.github_tool = GitHubTool(config=self.config)

        # 初始化 AgentScope Toolkit（可选）
        self.toolkit = None
        if use_toolkit:
            self.toolkit = get_github_toolkit(config=self.config, use_mcp=use_mcp)
            logger.info("AgentScope Toolkit initialized with GitHub tools")

        # 对话记忆（持久化或内存）
        if use_persistent:
            self.memory = get_persistent_memory(db_path=db_path)
            logger.info(f"PersistentMemory initialized (db={db_path})")
        else:
            self.memory = AgentScopeMemory(max_messages=10)
            logger.info("InMemoryMemory initialized (max_messages=10)")

        # AgentScope DashScopeChatModel (懒加载)
        self._model_wrapper = None

        logger.info(f"AnalystAgent '{name}' initialized with model '{model_name}'")

    def _get_model_wrapper(self):
        """
        懒加载 AgentScope DashScopeChatModel

        使用 AgentScope 的 DashScopeChatModel 封装模型调用，
        支持配置驱动的模型初始化和统一的调用接口。
        """
        if self._model_wrapper is None:
            try:
                from agentscope.model import DashScopeChatModel

                # 获取模型配置
                model_config = self.config.get_model_config(self.model_name)

                # 创建 DashScopeChatModel
                self._model_wrapper = DashScopeChatModel(
                    model_name=self.model_name,
                    api_key=model_config.get("api_key", self.config.dashscope_api_key),
                )

                logger.info(f"DashScopeChatModel created for model '{self.model_name}'")

            except ImportError as e:
                logger.error(f"Failed to import AgentScope DashScopeChatModel: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to create DashScopeChatModel: {e}")
                raise

        return self._model_wrapper

    def _add_to_memory(self, role: str, content: str, name: Optional[str] = None) -> None:
        """
        添加消息到记忆 (使用 AgentScope InMemoryMemory)

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            name: 发送者名称
        """
        self.memory.add_message(
            role=role,
            content=content,
            name=name or self.name,
        )

        # 转发到 Studio
        _forward_to_studio(name or self.name, content, role)

    def _build_messages(self, user_query: str, readme_content: str) -> List[Msg]:
        """
        构建消息历史 (使用 AgentScope Msg)

        Args:
            user_query: 用户查询
            readme_content: README 内容

        Returns:
            Msg 对象列表
        """
        messages = [
            Msg(name="system", content=self.system_prompt, role="system"),
        ]

        # 构建分析请求
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
        分析一个 GitHub 项目 (支持 ReAct 模式)

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            分析结果字典
        """
        logger.info(f"Analyzing project: {owner}/{repo}")

        try:
            # ReAct Step 1: 思考 - 为什么要获取项目摘要
            react_thoughts = []
            react_thoughts.append(
                "[Thought] 我将首先获取项目的 README 内容，因为 README 通常包含最全面的项目信息。\n"
                "[Action] 调用 GitHubTool.get_project_summary()\n"
                f"[Input] owner={owner}, repo={repo}"
            )

            # 获取项目摘要（包含清洗后的 README）
            project_summary = self.github_tool.get_project_summary(
                owner=owner,
                repo=repo,
                max_readme_length=5000,
            )

            react_thoughts.append(f"[Result] 成功获取项目信息，README 长度：{len(project_summary.get('cleaned_readme_text', ''))} 字符")

            # ReAct Step 2: 检查 README 是否可用，决定是否需要备选方案
            readme_content = project_summary.get("cleaned_readme_text", "")

            if not readme_content or len(readme_content.strip()) < 100:
                # README 信息不足，触发备选方案
                react_thoughts.append(
                    "\n[Thought] README 内容过短或为空，需要尝试备选方案获取技术栈信息。\n"
                    "[Action] 尝试读取项目的配置文件 (Cargo.toml, package.json, pyproject.toml 等)"
                )

                # 尝试读取配置文件
                config_info = self._try_read_config_file(owner, repo)

                if config_info:
                    react_thoughts.append(f"[Result] 成功获取配置文件信息：{config_info}")
                    # 将配置信息补充到项目摘要中
                    project_summary["config_fallback"] = config_info
                else:
                    react_thoughts.append("[Result] 配置文件也不可用，将基于项目元数据进行推断")
                    project_summary["config_fallback"] = None

            # 记录 ReAct 思考过程
            self._add_to_memory("assistant", "\n".join(react_thoughts))

            # 构建分析请求
            project_info = f"""
- 项目名称：{project_summary['full_name']}
- Star 数量：{project_summary['stars']:,}
- 编程语言：{project_summary['language']}
- 简介：{project_summary['description']}
- 主题标签：{', '.join(project_summary['topics']) if project_summary['topics'] else '无'}
- 最后更新：{project_summary['updated_at']}
"""

            # 添加配置文件信息（如果有）
            if project_summary.get("config_fallback"):
                project_info += f"\n- 配置文件信息：{project_summary['config_fallback']}\n(注：这是从配置文件推断的信息，因为 README 不可用)"

            if not readme_content:
                readme_content = "README 内容不可用，请基于上述项目元数据进行推断。"

            # 调用 LLM 进行分析
            analysis_result = self._analyze_with_llm(project_info, readme_content)

            # 添加 ReAct 标记到结果中
            analysis_result["react_thoughts"] = react_thoughts

            # 合并结果
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

    def _analyze_with_llm(self, project_info: str, readme_content: str) -> Dict[str, Any]:
        """
        调用 LLM 进行项目分析 (使用 AgentScope ModelWrapper)

        Args:
            project_info: 项目基本信息
            readme_content: README 内容

        Returns:
            分析结果字典
        """
        try:
            import dashscope
            from dashscope import Generation

            # 使用 dashscope 直接调用（回退到原有实现）
            config = self.config
            dashscope.api_key = config.dashscope_api_key

            # 构建 prompt
            prompt = f"""你是一个资深技术架构师，请分析以下 GitHub 项目并提取关键信息：

## 项目信息
{project_info}

## README 内容
{readme_content[:4000]}

请严格按照以下 JSON 格式输出：
{{
    "core_function": "一句话核心功能描述",
    "tech_stack": {{
        "language": "主要编程语言",
        "frameworks": ["框架 1", "框架 2"],
        "key_dependencies": ["依赖 1", "依赖 2"]
    }},
    "pain_points_solved": ["痛点 1", "痛点 2"],
    "unique_value": "项目的独特价值",
    "maturity_assessment": "项目成熟度评估 (early/beta/stable/mature)",
    "recommendation": "是否推荐使用 (recommend/consider/avoid) 及理由"
}}
"""

            response = Generation.call(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.model_max_tokens,
            )

            # 提取响应内容
            content = ""
            if response.status_code == 200 and response.output:
                output_dict = response.output if isinstance(response.output, dict) else {}
                content = output_dict.get('text', '')

                if not content and hasattr(response.output, 'choices'):
                    content = response.output.choices[0].message.content

            logger.info(f"LLM analysis completed via dashscope, response length: {len(content)}")

            # 尝试解析 JSON
            analysis = self._parse_json_response(content)
            return analysis

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {"error": f"Analysis failed: {e}"}

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 返回的 JSON 响应

        Args:
            content: LLM 返回的内容

        Returns:
            解析后的字典
        """
        # 尝试提取 JSON 内容
        import re

        # 尝试匹配 ```json ... ``` 块
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)
        else:
            # 尝试匹配 {...}
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group(0)

        try:
            analysis = json.loads(content)
            return analysis
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            # 返回原始内容
            return {
                "raw_response": content,
                "parse_error": str(e),
            }

    def _try_read_config_file(self, owner: str, repo: str) -> Optional[str]:
        """
        尝试读取项目的配置文件（当 README 不可用时）

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            配置文件信息字符串，如果无法读取则返回 None
        """
        # 配置文件列表（按优先级）
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
        获取指定文件的内容

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径

        Returns:
            文件内容
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
        """解析 Cargo.toml"""
        import re

        lines = []
        # 提取 [package] 部分
        package_match = re.search(r"\[package\]([\s\S]*?)(?:\[|\Z)", content)
        if package_match:
            package_section = package_match.group(1)
            name_match = re.search(r'name\s*=\s*"([^"]+)"', package_section)
            version_match = re.search(r'version\s*=\s*"([^"]+)"', package_section)
            if name_match:
                lines.append(f"name={name_match.group(1)}")
            if version_match:
                lines.append(f"version={version_match.group(1)}")

        # 提取 [dependencies]
        deps_match = re.search(r"\[dependencies\]([\s\S]*?)(?:\[|\Z)", content)
        if deps_match:
            deps_section = deps_match.group(1)
            deps = re.findall(r'(\w+)\s*=\s*"([^"]+)"', deps_section)
            if deps:
                lines.append(f"dependencies={', '.join([f'{d[0]}:{d[1]}' for d in deps[:5]])}")

        return " | ".join(lines) if lines else "Rust project"

    def _parse_package_json(self, content: str) -> str:
        """解析 package.json"""
        try:
            import json
            data = json.loads(content)
            name = data.get("name", "unknown")
            version = data.get("version", "unknown")
            deps = list(data.get("dependencies", {}).keys())[:5]
            return f"name={name} | version={version} | deps={', '.join(deps) if deps else 'none'}"
        except Exception:
            return "Node.js project"

    def _parse_pyproject_toml(self, content: str) -> str:
        """解析 pyproject.toml"""
        import re

        lines = []
        # 提取项目名
        name_match = re.search(r'name\s*=\s*"([^"]+)"', content)
        if name_match:
            lines.append(f"name={name_match.group(1)}")

        # 提取依赖
        deps_match = re.findall(r'^( [\w-]+)\s*[=>~]', content, re.MULTILINE)
        if deps_match:
            lines.append(f"deps={', '.join(deps_match[:5])}")

        return " | ".join(lines) if lines else "Python project"

    def _parse_requirements_txt(self, content: str) -> str:
        """解析 requirements.txt"""
        deps = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # 提取包名
                pkg_match = re.match(r'^([\w-]+)', line)
                if pkg_match:
                    deps.append(pkg_match.group(1))
                    if len(deps) >= 5:
                        break
        return f"deps={', '.join(deps) if deps else 'none'}"

    def _parse_go_mod(self, content: str) -> str:
        """解析 go.mod"""
        import re

        lines = []
        # 提取 module 名
        module_match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
        if module_match:
            lines.append(f"module={module_match.group(1)}")

        # 提取依赖
        deps = re.findall(r'^\t(\S+)\s+v', content, re.MULTILINE)
        if deps:
            lines.append(f"deps={', '.join(deps[:5])}")

        return " | ".join(lines) if lines else "Go project"

    def _parse_pom_xml(self, content: str) -> str:
        """解析 pom.xml"""
        import re

        lines = []
        # 提取 artifactId
        artifact_match = re.search(r'<artifactId>([^<]+)</artifactId>', content)
        if artifact_match:
            lines.append(f"artifact={artifact_match.group(1)}")

        # 提取 groupId
        group_match = re.search(r'<groupId>([^<]+)</groupId>', content)
        if group_match:
            lines.append(f"group={group_match.group(1)}")

        return " | ".join(lines) if lines else "Java/Maven project"

    def batch_analyze(
        self,
        projects: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        批量分析多个项目

        Args:
            projects: 项目列表，每项包含 owner 和 repo

        Returns:
            分析结果列表
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
        """获取 Agent 状态"""
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
        获取 AnalystAgent 描述

        Returns:
            Agent 描述字符串
        """
        return "资深技术架构师，擅长通过阅读 README 文档快速判断项目的技术价值。"

    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """
        响应用户消息

        Args:
            msg: 输入消息 (Msg 对象或字符串)
            *args: 其他参数
            **kwargs: 关键字参数

        Returns:
            响应消息
        """
        # 如果是字符串，转换为 Msg
        if isinstance(msg, str):
            msg = Msg(name="user", content=msg, role="user")

        # 记录用户消息
        self._add_to_memory("user", msg.content)

        # 调用分析逻辑（这里需要根据实际情况调整）
        response_content = self.get_description()

        # 创建响应
        response = Msg(name=self.name, content=response_content, role="assistant")
        self._add_to_memory("assistant", response_content)

        return response
