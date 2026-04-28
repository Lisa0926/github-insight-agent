# -*- coding: utf-8 -*-
"""
Tool registry module

Features:
- Implements a simple tool registration mechanism
- Registers tool methods as a globally available tool list
- Facilitates later injection into the Agent

Usage example:
    from src.tools import tool_registry, GitHubTool

    # Register the tool
    tool_registry.register_tool(GitHubTool)

    # Get the list of registered tools
    tools = tool_registry.get_registered_tools()
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolInfo:
    """Tool information data class"""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Tool registry singleton class

    Manages and registers all tool functions in the project for Agent invocation.
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
        Register a tool function

        Args:
            name: Tool name
            description: Tool description
            func: Tool function
            parameters: Parameter description dictionary
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
        Get a registered tool

        Args:
            name: Tool name

        Returns:
            ToolInfo or None
        """
        return self._tools.get(name)

    def get_registered_tools(self) -> List[str]:
        """
        Get all registered tool names

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def call_tool(self, name: str, **kwargs) -> Any:
        """
        Call a registered tool

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool call result

        Raises:
            KeyError: Raised when the tool is not registered
        """
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Tool '{name}' not registered")
        return tool.func(**kwargs)

    def to_agent_scope_format(self) -> List[Dict[str, Any]]:
        """
        Convert to AgentScope-compatible tool format

        Returns:
            AgentScope tool configuration list
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
        """Clear all registered tools"""
        self._tools.clear()
        logger.debug("All tools cleared")


# Global tool registry instance
global_registry = ToolRegistry()


def register_github_tools(github_tool_instance: Any) -> None:
    """
    Register GitHubTool methods to the global registry

    Args:
        github_tool_instance: GitHubTool instance
    """
    global_registry = ToolRegistry()

    # Register search_repositories
    global_registry.register_tool(
        name="search_repositories",
        description="Search for GitHub repositories by keyword. "
                    "Returns a list of repos with stars, language, and description.",
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

    # Register get_readme
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

    # Register get_repo_info
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

    # Register get_project_summary (added in Day 5-6)
    global_registry.register_tool(
        name="get_project_summary",
        description="Get a comprehensive project summary including repo info "
                    "and cleaned README text. Use this to deeply understand a project.",
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
