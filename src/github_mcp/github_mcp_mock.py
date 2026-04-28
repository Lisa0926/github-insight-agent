# -*- coding: utf-8 -*-
"""
GitHub MCP Mock client

For test environments, simulates GitHub MCP Server behavior without
requiring a real binary.

Usage example:
    from src.mcp.github_mcp_mock import MockGitHubMCPClient

    client = MockGitHubMCPClient()
    await client.connect()
    tools = await client.list_tools()
    result = await client.call_tool("search_repositories", {"query": "python"})
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MockTool:
    """Mock tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MockGitHubMCPClient:
    """
    GitHub MCP Mock client

    Simulates the real MCP client interface, returning mock data.
    Used for unit tests and integration tests without a real GitHub API.
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the Mock client

        Args:
            github_token: GitHub Token (optional, for compatibility only)
        """
        self.github_token = github_token or "mock_token"
        self._connected = False
        self._tools: List[MockTool] = []

        # Initialize mock tool list
        self._init_mock_tools()

    def _init_mock_tools(self) -> None:
        """Initialize mock tools"""
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
        """Connection status"""
        return self._connected

    async def connect(self) -> None:
        """Connect to MCP Server (simulated)"""
        await asyncio.sleep(0.1)  # Simulate connection delay
        self._connected = True
        logger.debug("Mock MCP Client connected")

    async def disconnect(self) -> None:
        """Disconnect"""
        self._connected = False
        logger.debug("Mock MCP Client disconnected")

    async def list_tools(self) -> List[MockTool]:
        """Get tool list"""
        await asyncio.sleep(0.05)  # Simulate latency
        return self._tools

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call a tool (returns mock data)

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        await asyncio.sleep(0.1)  # Simulate execution delay

        # Return mock data based on tool name
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
        """Simulate repository search"""
        query = args.get("query", "test")
        per_page = int(args.get("perPage", 5))

        # Return mock search results
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
        """Simulate README retrieval"""
        repo = args.get("repo", "project")  # noqa: F841
        owner = args.get("owner", "test")  # noqa: F841

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
        """Simulate repository info retrieval"""
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
        """Simulate issue list"""
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
        """Simulate PR list"""
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


# Convenience function: create a Mock client or a real client
def create_mcp_client(
    github_token: Optional[str] = None,
    bin_path: Optional[str] = None,
    use_mock: bool = False,
):
    """
    Factory function to create an MCP client

    Args:
        github_token: GitHub Token
        bin_path: MCP Server binary path
        use_mock: Whether to use the Mock client

    Returns:
        MCP client instance
    """
    if use_mock:
        return MockGitHubMCPClient(github_token)

    # Try creating a real client
    if bin_path is None:
        # If no path specified and mock is not requested, return mock client
        logger.warning("MCP Server binary not specified, using Mock client")
        return MockGitHubMCPClient(github_token)

    from src.github_mcp.github_mcp_client import GitHubMCPClient
    return GitHubMCPClient(github_token=github_token, bin_path=bin_path)
