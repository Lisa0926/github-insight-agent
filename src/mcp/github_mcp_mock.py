# -*- coding: utf-8 -*-
"""
GitHub MCP Mock 客户端

用于测试环境，模拟 GitHub MCP Server 的行为，不依赖真实二进制文件。

使用示例:
    from src.mcp.github_mcp_mock import MockGitHubMCPClient

    client = MockGitHubMCPClient()
    await client.connect()
    tools = await client.list_tools()
    result = await client.call_tool("search_repositories", {"query": "python"})
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MockTool:
    """模拟工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MockGitHubMCPClient:
    """
    GitHub MCP Mock 客户端

    模拟真实 MCP 客户端的接口，返回模拟数据。
    用于单元测试和不依赖真实 GitHub API 的集成测试。
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        初始化 Mock 客户端

        Args:
            github_token: GitHub Token（可选，仅用于兼容性）
        """
        self.github_token = github_token or "mock_token"
        self._connected = False
        self._tools: List[MockTool] = []

        # 初始化模拟工具列表
        self._init_mock_tools()

    def _init_mock_tools(self) -> None:
        """初始化模拟工具"""
        self._tools = [
            MockTool(
                name="search_repositories",
                description="Search for GitHub repositories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "sort": {"type": "string", "description": "Sort field"},
                        "order": {"type": "string", "description": "Sort order"},
                        "perPage": {"type": "string", "description": "Results per page"},
                    },
                    "required": ["query"],
                },
            ),
            MockTool(
                name="get_readme",
                description="Get README content for a repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repo": {"type": "string", "description": "Repository name"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            MockTool(
                name="get_repo_info",
                description="Get detailed repository information",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            MockTool(
                name="list_issues",
                description="List repository issues",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {"type": "string"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            MockTool(
                name="list_pull_requests",
                description="List repository pull requests",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {"type": "string"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
        ]

        logger.info(f"Mock GitHub MCP Client initialized with {len(self._tools)} tools")

    @property
    def is_connected(self) -> bool:
        """连接状态"""
        return self._connected

    async def connect(self) -> None:
        """连接到 MCP Server（模拟）"""
        await asyncio.sleep(0.1)  # 模拟连接延迟
        self._connected = True
        logger.debug("Mock MCP Client connected")

    async def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        logger.debug("Mock MCP Client disconnected")

    async def list_tools(self) -> List[MockTool]:
        """获取工具列表"""
        await asyncio.sleep(0.05)  # 模拟延迟
        return self._tools

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        调用工具（返回模拟数据）

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        await asyncio.sleep(0.1)  # 模拟执行延迟

        # 根据工具名称返回模拟数据
        if name == "search_repositories":
            return self._mock_search_repositories(arguments)
        elif name == "get_readme":
            return self._mock_get_readme(arguments)
        elif name == "get_repo_info":
            return self._mock_get_repo_info(arguments)
        elif name == "list_issues":
            return self._mock_list_issues(arguments)
        elif name == "list_pull_requests":
            return self._mock_list_pull_requests(arguments)
        else:
            return {"error": f"Unknown tool: {name}"}

    def _mock_search_repositories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """模拟仓库搜索"""
        query = args.get("query", "test")
        per_page = int(args.get("perPage", 5))

        # 返回模拟搜索结果
        return {
            "total_count": 100,
            "items": [
                {
                    "full_name": f"{query}-org/{query}-project-{i}",
                    "html_url": f"https://github.com/{query}-org/{query}-project-{i}",
                    "description": f"A mock project for {query}",
                    "stargazers_count": 1000 * (5 - i),
                    "language": "Python",
                    "topics": ["mock", "test", "demo"],
                    "updated_at": "2026-04-20T00:00:00Z",
                }
                for i in range(1, min(per_page + 1, 6))
            ],
        }

    def _mock_get_readme(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 README 获取"""
        owner = args.get("owner", "test")
        repo = args.get("repo", "project")

        import base64

        readme_content = f"""# {repo}

A mock project for testing purposes.

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

```bash
pip install {repo}
```

## Usage

```python
import {repo}
```

## License

MIT
"""

        return {
            "content": base64.b64encode(readme_content.encode()).decode(),
            "encoding": "base64",
        }

    def _mock_get_repo_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """模拟仓库信息获取"""
        owner = args.get("owner", "test")
        repo = args.get("repo", "project")

        return {
            "full_name": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "description": f"Mock repository {repo}",
            "stargazers_count": 5000,
            "forks_count": 500,
            "language": "Python",
            "topics": ["mock", "test", "demo"],
            "updated_at": "2026-04-20T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
        }

    def _mock_list_issues(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 issue 列表"""
        return {
            "issues": [
                {
                    "number": 1,
                    "title": "Bug: Something is broken",
                    "state": "open",
                    "labels": ["bug"],
                },
                {
                    "number": 2,
                    "title": "Feature: Add new functionality",
                    "state": "open",
                    "labels": ["enhancement"],
                },
            ]
        }

    def _mock_list_pull_requests(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """模拟 PR 列表"""
        return {
            "pull_requests": [
                {
                    "number": 10,
                    "title": "Fix bug in module X",
                    "state": "open",
                    "author": "contributor1",
                },
                {
                    "number": 11,
                    "title": "Add feature Y",
                    "state": "merged",
                    "author": "contributor2",
                },
            ]
        }


# 便捷函数：创建 Mock 客户端或真实客户端
def create_mcp_client(
    github_token: Optional[str] = None,
    bin_path: Optional[str] = None,
    use_mock: bool = False,
):
    """
    创建 MCP 客户端的工厂函数

    Args:
        github_token: GitHub Token
        bin_path: MCP Server 二进制路径
        use_mock: 是否使用 Mock 客户端

    Returns:
        MCP 客户端实例
    """
    if use_mock:
        return MockGitHubMCPClient(github_token)

    # 尝试创建真实客户端
    if bin_path is None:
        # 如果没有指定路径且不使用 mock，返回 mock 客户端
        logger.warning("MCP Server binary not specified, using Mock client")
        return MockGitHubMCPClient(github_token)

    from src.mcp.github_mcp_client import GitHubMCPClient
    return GitHubMCPClient(github_token=github_token, bin_path=bin_path)
