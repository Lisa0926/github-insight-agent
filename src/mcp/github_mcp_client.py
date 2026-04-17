# -*- coding: utf-8 -*-
"""
GitHub MCP Client - AgentScope 集成

功能:
- 使用 AgentScope StdIOStatefulClient 连接 GitHub MCP Server
- 支持工具列表获取和调用
- 与现有 Toolkit 集成
"""

import asyncio
from typing import Any, Dict, List, Optional
from agentscope.mcp import StdIOStatefulClient
from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)


class GitHubMCPClient(StdIOStatefulClient):
    """
    GitHub MCP 客户端

    通过 StdIO 协议与 GitHub MCP Server 通信

    Args:
        github_token: GitHub Personal Access Token
        bin_path: github-mcp-server 二进制文件路径
    """

    def __init__(
        self,
        github_token: str,
        bin_path: Optional[str] = None,
        config: Optional[ConfigManager] = None,
    ):
        self._config = config or ConfigManager()
        self._token = github_token or self._config.github_token

        # 使用配置的 bin 路径或环境变量
        if bin_path is None:
            bin_path = os.environ.get(
                "GITHUB_MCP_SERVER_BIN",
                str(Path(__file__).parent.parent.parent / "bin" / "github-mcp-server")
            )
        self._bin_path = bin_path

        if not self._token:
            raise ValueError("GitHub Token is required for MCP client")

        # 初始化 StdIO 客户端 - 需要使用 stdio 子命令
        super().__init__(
            name="github_mcp",
            command=bin_path,
            args=["stdio"],  # 使用 stdio 子命令
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": self._token},
        )

        logger.info(f"GitHub MCP Client initialized with bin: {bin_path}")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取 MCP Server 可用的工具列表

        Returns:
            工具描述字典列表
        """
        # StdIOStatefulClient 会自动在连接时获取工具列表
        # 通过 get_callable_function 可以获取每个工具的 callable 函数
        return []

    def is_connected(self) -> bool:
        """检查是否已连接到 MCP Server"""
        # 检查底层连接状态
        return hasattr(self, '_session') and self._session is not None


def create_github_mcp_client(
    config: Optional[ConfigManager] = None,
    github_token: Optional[str] = None,
    bin_path: Optional[str] = None,
) -> GitHubMCPClient:
    """
    创建 GitHub MCP 客户端实例

    Args:
        config: 配置管理器
        github_token: GitHub Token（可选，从配置或环境变量读取）
        bin_path: MCP Server 二进制路径

    Returns:
        GitHubMCPClient 实例
    """
    config = config or ConfigManager()
    token = github_token or config.github_token

    if not token:
        logger.warning("No GitHub token configured, MCP client will not be initialized")
        return None

    # 默认 bin 路径（使用环境变量或相对路径）
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
    """运行异步协程"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def register_github_mcp_tools(
    toolkit,
    client: GitHubMCPClient,
    group_name: str = "github_mcp",
) -> int:
    """
    将 MCP 工具注册到 Toolkit

    Args:
        toolkit: AgentScope Toolkit 实例
        client: GitHub MCP Client 实例
        group_name: 工具组名称

    Returns:
        注册的工具数量
    """
    try:
        # 连接并注册 MCP 客户端到 Toolkit (异步方法)
        async def _connect_and_register():
            # 先连接
            await client.connect()
            # 再注册
            await toolkit.register_mcp_client(client, group_name=group_name)

        _run_async(_connect_and_register())
        logger.info(f"GitHub MCP tools registered to group '{group_name}'")

        # 获取注册的工具数量
        schemas = toolkit.get_json_schemas()
        mcp_count = sum(1 for s in schemas if 'github' in s.get('function', {}).get('name', '').lower())
        return mcp_count

    except Exception as e:
        logger.error(f"Failed to register MCP tools: {e}")
        return 0
