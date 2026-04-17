# -*- coding: utf-8 -*-
"""
工具注册模块

功能:
- 实现简单的工具注册机制
- 将工具方法注册为全局可用的工具列表
- 方便后续注入到 Agent 中

使用示例:
    from src.tools import tool_registry, GitHubTool

    # 注册工具
    tool_registry.register_tool(GitHubTool)

    # 获取已注册的工具列表
    tools = tool_registry.get_registered_tools()
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolInfo:
    """工具信息数据类"""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    工具注册器单例类

    用于管理和注册项目中所有的工具函数，方便 Agent 调用。
    """

    _instance: Optional["ToolRegistry"] = None
    _initialized: bool = False

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ToolRegistry._initialized:
            return
        self._tools: Dict[str, ToolInfo] = {}
        ToolRegistry._initialized = True

    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        注册一个工具函数

        Args:
            name: 工具名称
            description: 工具描述
            func: 工具函数
            parameters: 参数描述字典
        """
        self._tools[name] = ToolInfo(
            name=name,
            description=description,
            func=func,
            parameters=parameters or {},
        )
        logger.debug(f"Tool registered: {name}")

    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """
        获取已注册的工具

        Args:
            name: 工具名称

        Returns:
            ToolInfo 或 None
        """
        return self._tools.get(name)

    def get_registered_tools(self) -> List[str]:
        """
        获取所有已注册的工具名称

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def call_tool(self, name: str, **kwargs) -> Any:
        """
        调用已注册的工具

        Args:
            name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具调用结果

        Raises:
            KeyError: 工具未注册时抛出
        """
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Tool '{name}' not registered")
        return tool.func(**kwargs)

    def to_agent_scope_format(self) -> List[Dict[str, Any]]:
        """
        转换为 AgentScope 兼容的工具格式

        Returns:
            AgentScope 工具配置列表
        """
        return [
            {
                "name": info.name,
                "description": info.description,
                "parameters": info.parameters,
            }
            for info in self._tools.values()
        ]

    def clear(self) -> None:
        """清空所有已注册的工具"""
        self._tools.clear()
        logger.debug("All tools cleared")


# 全局工具注册器实例
global_registry = ToolRegistry()


def register_github_tools(github_tool_instance: Any) -> None:
    """
    将 GitHubTool 的方法注册到全局注册器

    Args:
        github_tool_instance: GitHubTool 实例
    """
    global global_registry

    # 注册 search_repositories
    global_registry.register_tool(
        name="search_repositories",
        description="Search for GitHub repositories by keyword. Returns a list of repos with stars, language, and description.",
        func=github_tool_instance.search_repositories,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query keyword (e.g., 'large language model language:python')",
                },
                "sort": {
                    "type": "string",
                    "description": "Sort field: stars, forks, or updated",
                    "enum": ["stars", "forks", "updated"],
                    "default": "stars",
                },
                "order": {
                    "type": "string",
                    "description": "Sort order: asc or desc",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                },
                "per_page": {
                    "type": "integer",
                    "description": "Number of results per page (max 100)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    )

    # 注册 get_readme
    global_registry.register_tool(
        name="get_readme",
        description="Get the README content of a specific GitHub repository.",
        func=github_tool_instance.get_readme,
        parameters={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (username or organization)",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch name or commit SHA (default: HEAD)",
                    "default": "HEAD",
                },
            },
            "required": ["owner", "repo"],
        },
    )

    # 注册 get_repo_info
    global_registry.register_tool(
        name="get_repo_info",
        description="Get detailed information about a specific GitHub repository.",
        func=github_tool_instance.get_repo_info,
        parameters={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (username or organization)",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
            },
            "required": ["owner", "repo"],
        },
    )

    # 注册 get_project_summary (Day 5-6 新增)
    global_registry.register_tool(
        name="get_project_summary",
        description="Get a comprehensive project summary including repo info and cleaned README text. Use this to deeply understand a project.",
        func=github_tool_instance.get_project_summary,
        parameters={
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "Repository owner (username or organization)",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository name",
                },
                "max_readme_length": {
                    "type": "integer",
                    "description": "Maximum length of README text to return (default 5000, to avoid token limits)",
                    "default": 5000,
                },
            },
            "required": ["owner", "repo"],
        },
    )

    logger.info(
        f"GitHub tools registered: {global_registry.get_registered_tools()}"
    )
