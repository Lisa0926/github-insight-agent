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
import re
from datetime import datetime, timedelta

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
    """

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
        self.name = name
        self.model_name = model_name
        self.config = config or ConfigManager()
        self.system_prompt = self.SYSTEM_PROMPT
        self.use_toolkit = use_toolkit
        self.use_mcp = use_mcp
        self.use_persistent = use_persistent

        self.github_tool = GitHubTool(config=self.config)
        register_github_tools(self.github_tool)

        self.toolkit = None
        if use_toolkit:
            self.toolkit = get_github_toolkit(config=self.config, use_mcp=use_mcp)
            logger.info("AgentScope Toolkit initialized with GitHub tools")

        if use_persistent:
            self.memory = get_persistent_memory(db_path=db_path)
            logger.info(f"PersistentMemory initialized (db={db_path})")
        else:
            self.memory = AgentScopeMemory(max_messages=10)
            logger.info("InMemoryMemory initialized (max_messages=10)")

        self._model_wrapper = None
        logger.info(f"ResearcherAgent '{name}' initialized with model '{model_name}'")

    def _get_model_wrapper(self):
        """懒加载 AgentScope DashScopeChatModel"""
        if self._model_wrapper is None:
            from agentscope.model import DashScopeChatModel
            model_config = self.config.get_model_config(self.model_name)
            self._model_wrapper = DashScopeChatModel(
                model_name=self.model_name,
                api_key=model_config.get("api_key", self.config.dashscope_api_key),
            )
            logger.info(f"DashScopeChatModel created for model '{self.model_name}'")
        return self._model_wrapper

    def _parse_time_range(self, user_query: str) -> Optional[int]:
        """
        从用户查询中提取时间范围（天数）

        支持的自然语言格式：
        - 最近 N 天 / 近 N 天 / 过去 N 天
        - 今天/今日/昨天/本周/本月
        - N 天内（如：三天内、五天内）
        """
        # 动态匹配：最近 N 天 / 近 N 天 / 过去 N 天
        days_match = re.search(r"(?:最近 | 近|过去)\s*(\d+)\s*天", user_query)
        if days_match:
            return int(days_match.group(1))

        # N 天内格式（三天内、五天内等）- 中文数字映射
        chinese_nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        for cn, val in chinese_nums.items():
            if f"{cn}天内" in user_query:
                return val

        # 固定匹配
        if any(kw in user_query for kw in ["今天", "今日"]):
            return 0
        if "昨天" in user_query:
            return 1
        if any(kw in user_query for kw in ["本周", "最近一周"]):
            return 7
        if any(kw in user_query for kw in ["本月", "最近一月"]):
            return 30

        return None

    def _build_search_params(self, user_query: str) -> dict:
        """
        构建 GitHub Search API 参数

        使用简单规则解析：
        1. 检测时间范围，添加 created 条件
        2. 提取项目数量（如"前 3 个"）
        3. 检测排序偏好（star 最高 → sort=stars）
        """
        # 默认参数
        params = {
            "search_query": user_query,
            "sort": "stars",
            "per_page": 10,
        }

        # 1. 解析时间范围
        days = self._parse_time_range(user_query)
        if days is not None:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            params["search_query"] = f"created:{start_date}..{end_date}"

        # 2. 提取项目数量
        count_match = re.search(r"前?\s*(\d+)\s*个", user_query)
        if count_match:
            params["per_page"] = min(int(count_match.group(1)), 20)

        # 3. 检测排序偏好
        if "fork" in user_query:
            params["sort"] = "forks"
        elif "updated" in user_query or "最新" in user_query:
            params["sort"] = "updated"

        return params

    @trace(name="researcher.search_and_analyze")
    def search_and_analyze(
        self,
        query: str,
        sort: str = None,
        order: str = "desc",
        per_page: int = None,
    ) -> Dict[str, Any]:
        """
        搜索并分析 GitHub 仓库

        Args:
            query: 搜索关键词（自然语言或 GitHub Search 语法）
            sort: 排序字段（可选，不传则自动解析）
            order: 排序顺序
            per_page: 结果数量（可选，不传则自动解析）

        Returns:
            搜索结果字典
        """
        # 构建搜索参数（自动解析自然语言）
        params = self._build_search_params(query)

        # 如果外部指定了 sort/per_page，优先使用
        if sort:
            params["sort"] = sort
        if per_page:
            params["per_page"] = per_page

        search_query = params["search_query"]
        logger.info(f"Original query: {query}")
        logger.info(f"Search query: {search_query}, sort={params['sort']}, per_page={params['per_page']}")

        try:
            repos = self.github_tool.search_repositories(
                query=search_query,
                sort=params["sort"],
                order=order,
                per_page=params["per_page"],
            )

            result = {
                "query": query,
                "search_query": search_query,
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
                "search_query": search_query,
                "error": str(e),
                "repositories": [],
            }

    def generate_summary(self, search_result: Dict[str, Any]) -> str:
        """生成搜索结果的摘要"""
        if search_result.get("error"):
            return f"搜索失败：{search_result['error']}"

        repos = search_result.get("repositories", [])
        if not repos:
            return "未找到匹配的仓库。"

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

        return "\n".join(lines)

    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """响应用户消息"""
        if isinstance(msg, str):
            msg = Msg(name="user", content=msg, role="user")

        self._add_to_memory("user", msg.content, name="user")
        response_content = self.reply_to_message(msg.content)
        response = Msg(name=self.name, content=response_content, role="assistant")
        self._add_to_memory("assistant", response_content)
        return response

    def reply_to_message(self, user_query: str) -> str:
        """响应用户查询"""
        logger.info(f"Received query: {user_query}")

        query_lower = user_query.lower()
        if any(kw in query_lower for kw in ["搜索", "search", "find", "github", "项目", "仓库"]):
            search_result = self.search_and_analyze(query=user_query)
            return self.generate_summary(search_result)
        else:
            return self._call_llm(user_query)

    def _add_to_memory(self, role: str, content: str, name: Optional[str] = None) -> None:
        """添加消息到记忆"""
        self.memory.add_message(role=role, content=content, name=name or self.name)
        _forward_to_studio(name or self.name, content, role)

    def _build_messages(self, user_query: str) -> List[Dict[str, Any]]:
        """构建消息历史"""
        messages = [{"name": "system", "content": self.system_prompt, "role": "system"}]
        memory_messages = self.memory.get_messages_for_prompt()
        messages.extend(memory_messages)
        messages.append({"name": "user", "content": user_query, "role": "user"})
        return messages

    def _call_llm(self, user_query: str) -> str:
        """调用 LLM 进行回复"""
        try:
            model_wrapper = self._get_model_wrapper()
            messages = self._build_messages(user_query)
            response = model_wrapper(messages=messages)
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
        """获取 Agent 状态"""
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
        """获取 ResearcherAgent 描述"""
        return "专业的开源情报研究员，擅长使用 GitHub 工具搜索项目并提取关键信息。"
