# -*- coding: utf-8 -*-
"""
GitHub MCP Client - AgentScope Integration

Features:
- Connect to GitHub MCP Server using AgentScope StdIOStatefulClient
- Supports tool listing and invocation
- Integrates with existing Toolkit
- Connection retry with exponential backoff
- Tool result caching
"""

import asyncio
import os
import shutil
import time
from typing import Any, Dict, List, Optional
from agentscope.mcp import StdIOStatefulClient
from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)

# MCP server binary discovery
_NPM_BIN = shutil.which("mcp-server-github") or os.path.join(
    os.environ.get("NPM_CONFIG_PREFIX", "/usr/local/node"), "bin", "mcp-server-github"
)
_OFFICIAL_BIN = shutil.which("github-mcp-server")


def _resolve_mcp_binary() -> str:
    """Find an available GitHub MCP server binary.

    Priority:
    1. Official github-mcp-server (Go binary, needs 'stdio' subcommand)
    2. @modelcontextprotocol/server-github (npm, runs in stdio mode directly)
    3. User-provided path via GITHUB_MCP_SERVER_BIN env var
    """
    if _OFFICIAL_BIN:
        return _OFFICIAL_BIN
    if os.path.isfile(_NPM_BIN):
        return _NPM_BIN
    return ""


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

        # Resolve binary path with fallback strategy
        if bin_path is None:
            bin_path = os.environ.get(
                "GITHUB_MCP_SERVER_BIN",
                _resolve_mcp_binary(),
            )
        self._bin_path = bin_path

        # Detect which binary we're using
        self._is_official = bool(
            bin_path and "github-mcp-server" in bin_path
            and "mcp-server-github" not in bin_path
        )

        if not self._token:
            raise ValueError("GitHub Token is required for MCP client")

        # Initialize StdIO client
        # Official Go binary needs 'stdio' subcommand; npm package runs in stdio mode directly
        args = ["stdio"] if self._is_official else []

        super().__init__(
            name="github_mcp",
            command=bin_path,
            args=args,
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": self._token},
        )

        logger.info(
            f"GitHub MCP Client initialized: bin={bin_path}, mode={'official(stdio)' if self._is_official else 'npm(stdio)'}"
        )

        # P2: Connection retry config
        self._max_reconnect_attempts = 3
        self._base_reconnect_delay = 1.0

        # P2: Tool result cache (in-memory, per-session)
        self._tool_result_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP Server.

        Returns cached tools if already fetched during this session.

        Returns:
            List of tool description dictionaries with name, description, and schema.
        """
        # Use cached tools from parent's list_tools() call
        if hasattr(self, "_cached_tools") and self._cached_tools:
            return [
                {
                    "name": tool.name,
                    "title": getattr(tool, "title", None),
                    "description": getattr(tool, "description", ""),
                    "inputSchema": tool.inputSchema,
                }
                for tool in self._cached_tools
            ]

        # If tools were not fetched via connect(), attempt sync fetch
        if self.connected:
            try:
                loop = asyncio.new_event_loop()
                tools = loop.run_until_complete(self.list_tools())
                loop.close()
                return [
                    {
                        "name": tool.name,
                        "title": getattr(tool, "title", None),
                        "description": getattr(tool, "description", ""),
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in tools
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch available tools: {e}")

        return []

    @property
    def connected(self) -> bool:
        """Check if connected to MCP Server.

        Verifies both the connection flag and session liveliness.

        Note: Parent class uses `self.is_connected = True` (instance attribute)
        after connect(). We check __dict__ directly to avoid collision with
        any class-level descriptor of the same name.
        """
        # Parent's is_connected boolean attribute (set to True after connect())
        # Use __dict__ to read instance attribute directly (bypass descriptor)
        parent_flag = self.__dict__.get('is_connected', False)
        has_parent_conn = parent_flag is True
        has_session = hasattr(self, 'session') and self.session is not None
        return has_parent_conn and has_session

    def connect_with_retry(self) -> bool:
        """Connect to MCP server with exponential backoff retry.

        Returns:
            True if connection succeeded, False otherwise.
        """
        async def _do_connect():
            try:
                await self.connect()
                # Also fetch tools on connect so get_available_tools() works
                await self.list_tools()
                return True
            except Exception:
                return False

        last_error = None
        for attempt in range(1, self._max_reconnect_attempts + 1):
            try:
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(_do_connect())
                loop.close()
                if result:
                    logger.info(f"MCP client connected (attempt {attempt})")
                    return True
            except Exception as e:
                last_error = e
                if attempt < self._max_reconnect_attempts:
                    delay = self._base_reconnect_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"MCP connect failed (attempt {attempt}/{self._max_reconnect_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)

        logger.error(f"MCP client failed to connect after {self._max_reconnect_attempts} attempts: {last_error}")
        return False

    def cached_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool with result caching.

        Args:
            tool_name: Name of the MCP tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            Tool call result (cached if within TTL).
        """
        cache_key = f"{tool_name}:{hash(frozenset(arguments.items()))}"
        now = time.time()

        if cache_key in self._tool_result_cache:
            cached_time, cached_result = self._tool_result_cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_result

        # Call the tool
        async def _do_call():
            func = await self.get_callable_function(tool_name, wrap_tool_result=False)
            return await func(arguments)

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_do_call())
            loop.close()
            self._tool_result_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            logger.error(f"Tool call failed for '{tool_name}': {e}")
            raise


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
