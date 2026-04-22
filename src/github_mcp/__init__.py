# -*- coding: utf-8 -*-
"""
MCP 模块

提供 MCP (Model Context Protocol) 客户端集成
"""

from src.github_mcp.github_mcp_client import GitHubMCPClient, create_github_mcp_client, register_github_mcp_tools

__all__ = [
    "GitHubMCPClient",
    "create_github_mcp_client",
    "register_github_mcp_tools",
]
