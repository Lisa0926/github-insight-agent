# -*- coding: utf-8 -*-
"""
GitHub MCP Client - AgentScope Integration

Features:
- Connect to GitHub MCP Server using AgentScope StdIOStatefulClient
- Supports tool listing and invocation
- Integrates with existing Toolkit
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from agentscope.mcp import StdIOStatefulClient
from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)


class GitHubMCPClient(StdIOStatefulClient):
    """
    GitHub MCP client

    Communicates with GitHub MCP Server via StdIO protocol

    Args:
        github_token: GitHub Personal Access Token
        bin_path: github-mcp-server binary file path
    """

    def __init__(
        self,
        github_token: str,
        bin_path: Optional[str] = None,
        config: Optional[ConfigManager] = None,
    ):
        self._config = config or ConfigManager()
        self._token = github_token or self._config.github_token

        # Use configured bin path or environment variable
        if bin_path is None:
            bin_path = os.environ.get(
                "GITHUB_MCP_SERVER_BIN",
                str(Path(__file__).parent.parent.parent / "bin" / "github-mcp-server")
            )
        self._bin_path = bin_path

        if not self._token:
            raise ValueError("GitHub Token is required for MCP client")

        # Initialize StdIO client - requires stdio subcommand
        super().__init__(
            name="github_mcp",
            command=bin_path,
            args=["stdio"],  # Use stdio subcommand
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": self._token},
        )

        logger.info(f"GitHub MCP Client initialized with bin: {bin_path}")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP Server

        Returns:
            List of tool description dictionaries
        """
        # StdIOStatefulClient automatically retrieves the tool list on connect
        # Each tool's callable can be obtained via get_callable_function
        return []

    def is_connected(self) -> bool:
        """Check if connected to MCP Server"""
        # Check underlying connection status
        return hasattr(self, '_session') and self._session is not None


def create_github_mcp_client(
    config: Optional[ConfigManager] = None,
    github_token: Optional[str] = None,
    bin_path: Optional[str] = None,
) -> GitHubMCPClient:
    """
    Create a GitHub MCP client instance

    Args:
        config: Configuration manager
        github_token: GitHub Token (optional, read from config or environment)
        bin_path: MCP Server binary path

    Returns:
        GitHubMCPClient instance
    """
    config = config or ConfigManager()
    token = github_token or config.github_token

    if not token:
        logger.warning("No GitHub token configured, MCP client will not be initialized")
        return None

    # Default bin path (use environment variable or relative path)
    if bin_path is None:
        bin_path = os.environ.get(
            "GITHUB_MCP_SERVER_BIN",
            str(Path(__file__).parent.parent.parent / "bin" / "github-mcp-server")
        )

    try:
        client = GitHubMCPClient(
            github_token=token,
            bin_path=bin_path,
            config=config,
        )
        logger.info("GitHub MCP Client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create GitHub MCP Client: {e}")
        return None


def _run_async(coro):
    """Run an async coroutine"""
    try:
        asyncio.get_running_loop()
        raise RuntimeError("_run_async cannot be called from a running event loop")
    except RuntimeError as e:
        if "no running event loop" in str(e):
            pass
        else:
            raise
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def register_github_mcp_tools(
    toolkit,
    client: GitHubMCPClient,
    group_name: str = "github_mcp",
) -> int:
    """
    Register MCP tools to a Toolkit

    Args:
        toolkit: AgentScope Toolkit instance
        client: GitHub MCP Client instance
        group_name: Tool group name

    Returns:
        Number of registered tools
    """
    try:
        # Connect and register MCP client to Toolkit (async method)
        async def _connect_and_register():
            # First connect
            await client.connect()
            # Then register
            await toolkit.register_mcp_client(client, group_name=group_name)

        _run_async(_connect_and_register())
        logger.info(f"GitHub MCP tools registered to group '{group_name}'")

        # Get number of registered tools
        schemas = toolkit.get_json_schemas()
        mcp_count = sum(1 for s in schemas if 'github' in s.get('function', {}).get('name', '').lower())
        return mcp_count

    except Exception as e:
        logger.error(f"Failed to register MCP tools: {e}")
        return 0
