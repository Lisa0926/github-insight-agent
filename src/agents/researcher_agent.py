# -*- coding: utf-8 -*-
"""
研究员 Agent

功能:
- 专业的开源情报研究员
- 使用 GitHub 工具搜索项目并提取关键信息
- 返回结构化数据或简洁总结
- 使用 AgentScope ModelWrapper 进行模型调用
- 使用 AgentScope Msg 类统一消息格式
- 继承 AgentScope AgentBase
"""

import json
from typing import Any, Dict, List, Optional, Union
import requests
import os

from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.agentscope_memory import AgentScopeMemory
from src.core.agentscope_persistent_memory import PersistentMemory, get_persistent_memory
from src.core.studio_helper import StudioHelper, set_global_studio_config, forward_to_studio
from src.tools.github_tool import GitHubTool
from src.tools.tool_registry import register_github_tools, global_registry
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


class ResearcherAgent:
    """
    研究员 Agent

    角色：专业的开源情报研究员
    任务：根据用户查询，使用 GitHub 工具搜索项目，并提取关键信息

    Attributes:
        name: Agent 名称
        model_name: 使用的模型名称
        system_prompt: 系统提示词
        github_tool: GitHub 工具实例
        config: 配置管理器
        memory: 对话记忆
    """

    # 系统提示词模板
    SYSTEM_PROMPT = """你是一个专业的开源情报研究员 (Open Source Intelligence Researcher)。

## 你的任务
1. 根据用户的查询，使用 GitHub 工具搜索相关项目
2. 提取关键信息：项目名称、Star 数量、主要编程语言、简介
3. 返回结构化数据或简洁的总结

## 可用工具
- search_repositories(query, sort, order, per_page): 搜索 GitHub 仓库
- get_readme(owner, repo, ref): 获取仓库 README 内容
- get_repo_info(owner, repo): 获取仓库详细信息

## 约束
1. 只返回结构化数据或简洁的总结，不要编造数据
2. 如果搜索结果为空，如实告知用户
3. 返回的数据必须来自 API 调用结果
4. 使用 Markdown 格式呈现结果，便于阅读

## 响应格式示例
```
## 搜索结果：{query}

找到 {total_count} 个相关仓库，以下是 Top {n}：

| # | 仓库 | Stars | 语言 | 简介 |
|---|------|-------|------|------|
| 1 | owner/repo | 10,000 | Python | 简介... |

### 详细分析
{分析内容}
```
"""

    def __init__(
        self,
        name: str = "Researcher",
        model_name: str = "qwen-max",
        config: Optional[ConfigManager] = None,
        use_toolkit: bool = True,
        use_mcp: bool = True,
        use_persistent: bool = True,
        db_path: str = "data/app.db",
    ):
        """
        初始化研究员 Agent

        Args:
            name: Agent 名称
            model_name: 模型名称
            config: 配置管理器
            use_toolkit: 是否使用 AgentScope Toolkit（默认 True）
            use_mcp: 是否使用 GitHub MCP Server（默认 True）
            use_persistent: 是否使用持久化存储（默认 True）
            db_path: SQLite 数据库路径
        """
        self.name = name
        self.model_name = model_name
        self.config = config or ConfigManager()
        self.system_prompt = self.SYSTEM_PROMPT
        self.use_toolkit = use_toolkit
        self.use_mcp = use_mcp
        self.use_persistent = use_persistent

        # 初始化 GitHub 工具
        self.github_tool = GitHubTool(config=self.config)

        # 注册工具到全局注册器
        register_github_tools(self.github_tool)

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

        logger.info(f"ResearcherAgent '{name}' initialized with model '{model_name}'")
        logger.info("GitHub tools registered and ready to use")

    def _get_model_wrapper(self):
        """
        懒加载 AgentScope DashScopeChatModel

        使用 AgentScope 的 DashScopeChatModel 封装模型调用，
        支持配置驱动的模型初始化和统一的调用接口。

        注意：如果需要支持多 LLM 后端，请使用 src.llm.provider_factory.get_provider()
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

    def get_llm_provider(self):
        """
        获取 LLM Provider（支持多后端）

        Returns:
            LLMProvider 实例

        使用示例:
            provider = agent.get_llm_provider()
            response = await provider.chat_async(messages)
        """
        from src.llm.provider_factory import get_provider

        # 根据模型名称判断提供商
        model_name = self.model_name.lower()
        if model_name.startswith("gpt"):
            return get_provider(
                "openai",
                api_key=self.config.dashscope_api_key,  # 复用环境变量
                model=self.model_name,
            )
        elif model_name.startswith("llama") or model_name.startswith("mistral"):
            return get_provider(
                "ollama",
                model=self.model_name,
            )
        else:
            # 默认使用 DashScope
            return get_provider(
                "dashscope",
                api_key=self.config.dashscope_api_key,
                model=self.model_name,
            )

    def _add_to_memory(self, role: str, content: str, name: Optional[str] = None) -> None:
        """
        添加消息到记忆 (使用 AgentScope InMemoryMemory)

        Args:
            role: 角色 (user/assistant/system/tool)
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

    def _build_messages(self, user_query: str) -> List[Dict[str, Any]]:
        """
        构建消息历史 (使用 AgentScope InMemoryMemory)

        Args:
            user_query: 用户查询

        Returns:
            消息字典列表
        """
        messages = [
            {"name": "system", "content": self.system_prompt, "role": "system"},
        ]

        # 获取记忆中的消息（包含摘要）
        memory_messages = self.memory.get_messages_for_prompt()
        messages.extend(memory_messages)

        # 添加当前查询
        messages.append({"name": "user", "content": user_query, "role": "user"})

        return messages

    @trace(name="researcher.search_and_analyze")
    def search_and_analyze(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 10,
    ) -> Dict[str, Any]:
        """
        搜索并分析 GitHub 仓库

        Args:
            query: 搜索关键词
            sort: 排序字段
            order: 排序顺序
            per_page: 结果数量

        Returns:
            搜索结果字典
        """
        logger.info(f"Searching for: {query}")

        try:
            repos = self.github_tool.search_repositories(
                query=query,
                sort=sort,
                order=order,
                per_page=per_page,
            )

            # 格式化结果
            result = {
                "query": query,
                "total_found": len(repos),
                "repositories": [
                    {
                        "full_name": repo.full_name,
                        "html_url": repo.html_url,
                        "stars": repo.stargazers_count,
                        "language": repo.language,
                        "description": repo.description,
                        "topics": repo.topics,
                    }
                    for repo in repos
                ],
            }

            logger.info(f"Found {len(repos)} repositories")
            return result

        except RuntimeError as e:
            logger.error(f"Search failed: {e}")
            return {
                "query": query,
                "error": str(e),
                "repositories": [],
            }

    def generate_summary(self, search_result: Dict[str, Any]) -> str:
        """
        生成搜索结果的摘要

        Args:
            search_result: 搜索结果字典

        Returns:
            摘要字符串
        """
        if search_result.get("error"):
            return f"搜索失败：{search_result['error']}"

        repos = search_result.get("repositories", [])
        if not repos:
            return "未找到匹配的仓库。"

        # 生成 Markdown 格式的摘要
        lines = [
            f"## 搜索结果：{search_result.get('query', 'Unknown')}",
            "",
            f"找到 **{search_result.get('total_found', 0)}** 个相关仓库，以下是 Top {len(repos)}：",
            "",
            "| # | 仓库 | Stars | 语言 | 简介 |",
            "|---|------|-------|------|------|",
        ]

        for i, repo in enumerate(repos, 1):
            desc = repo.get("description", "")
            if desc:
                desc = (desc[:50] + "...") if len(desc) > 50 else desc
                desc = desc.replace("\n", " ")
            else:
                desc = "*无描述*"

            lines.append(
                f"| {i} | **[{repo['full_name']}]({repo['html_url']})** | "
                f"⭐ {repo['stars']:,} | {repo['language'] or 'N/A'} | {desc} |"
            )

        # 添加主题标签
        top_repo = repos[0] if repos else {}
        if top_repo.get("topics"):
            lines.extend([
                "",
                "### 热门主题标签",
                ", ".join(f"`{t}`" for t in top_repo["topics"][:10]),
            ])

        return "\n".join(lines)

    def _extract_search_query(self, user_query: str) -> str:
        """
        从用户查询中提取搜索关键词

        Args:
            user_query: 用户查询

        Returns:
            搜索关键词
        """
        import re

        query = user_query

        # 移除常见的引导词
        patterns_to_remove = [
            r"帮我搜索\s*",
            r"搜索\s*",
            r"find\s+",
            r"search\s+",
            r"github 上\s*",
            r"github\s+",
            r"关于\s*",
            r"最火的\s*",
            r"最热门的\s*",
            r"\d+\s*个\s*",
            r"python\s*项目\s*",
            r"python\s+",
        ]

        for pattern in patterns_to_remove:
            query = re.sub(pattern, "", query, flags=re.IGNORECASE)

        # 提取引号内的内容作为搜索词
        quoted_match = re.search(r"['\"]([^'\"]+)['\"]", query)
        if quoted_match:
            return quoted_match.group(1).strip()

        # 清理剩余内容
        query = query.strip()

        # 如果为空，使用原始查询
        if not query:
            return user_query

        return query

    def _call_llm(self, user_query: str) -> str:
        """
        调用 LLM 进行回复 (使用 AgentScope ModelWrapper)

        Args:
            user_query: 用户查询

        Returns:
            LLM 响应
        """
        try:
            # 使用 AgentScope ModelWrapper
            model_wrapper = self._get_model_wrapper()

            messages = self._build_messages(user_query)

            # 通过 ModelWrapper 调用模型
            response = model_wrapper(
                messages=messages,
            )

            # 提取响应内容
            content = ""
            if hasattr(response, "text"):
                content = response.text
            elif isinstance(response, dict):
                content = response.get("content", "")
            elif hasattr(response, "__dict__"):
                content = getattr(response, "content", "") or getattr(response, "text", "")

            self._add_to_memory("assistant", content)
            return content

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"抱歉，AI 响应失败：{e}"

    def get_status(self) -> Dict[str, Any]:
        """
        获取 Agent 状态

        Returns:
            状态字典
        """
        status = {
            "name": self.name,
            "model": self.model_name,
            "memory_size": self.memory.size(),
            "tools_available": global_registry.get_registered_tools(),
            "github_token_configured": bool(self.config.github_token),
            "toolkit_enabled": self.toolkit is not None,
            "mcp_enabled": self.use_mcp,
            "persistent_enabled": self.use_persistent,
        }

        if self.toolkit:
            schemas = self.toolkit.get_json_schemas()
            # MCP 工具列表
            mcp_tool_names = [
                'get_commit', 'get_file_contents', 'get_label', 'get_latest_release',
                'get_me', 'get_release_by_tag', 'get_tag', 'issue_read',
                'list_branches', 'list_commits', 'list_issues', 'list_pull_requests',
                'list_releases', 'list_tags', 'pull_request_read', 'search_code',
                'search_issues', 'search_pull_requests', 'search_repositories', 'search_users'
            ]
            mcp_schemas = [s for s in schemas if s.get('function', {}).get('name', '') in mcp_tool_names]
            status["toolkit_schemas"] = len(schemas)
            status["mcp_tools_count"] = len(mcp_schemas)

        return status

    def get_description(self) -> str:
        """
        获取 ResearcherAgent 描述

        Returns:
            Agent 描述字符串
        """
        return "专业的开源情报研究员，擅长使用 GitHub 工具搜索项目并提取关键信息。"

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
        self._add_to_memory("user", msg.content, name="user")

        # 调用现有逻辑
        response_content = self.reply_to_message(msg.content)

        # 创建响应
        response = Msg(name=self.name, content=response_content, role="assistant")
        self._add_to_memory("assistant", response_content)

        return response

    def reply_to_message(self, user_query: str) -> str:
        """
        响应用户查询（原有逻辑）

        Args:
            user_query: 用户查询

        Returns:
            响应字符串
        """
        logger.info(f"Received query: {user_query}")

        # 简单的意图识别：判断是否需要搜索
        query_lower = user_query.lower()
        if any(kw in query_lower for kw in ["搜索", "search", "find", "github", "项目", "仓库"]):
            # 执行搜索
            search_query = self._extract_search_query(user_query)

            # 提取 per_page 参数
            per_page = 10
            import re
            match = re.search(r"(\d+)\s*个", user_query)
            if match:
                per_page = min(int(match.group(1)), 20)

            logger.info(f"Extracted search query: '{search_query}' (per_page={per_page})")

            # 执行搜索
            search_result = self.search_and_analyze(
                query=search_query,
                per_page=per_page,
            )

            # 生成摘要
            summary = self.generate_summary(search_result)

            return summary
        else:
            # 非搜索类查询，使用 LLM 直接回复
            return self._call_llm(user_query)
