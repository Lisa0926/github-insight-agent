# -*- coding: utf-8 -*-
"""
MCP module

Provides MCP (Model Context Protocol) client integration
"""

from src.github_mcp.github_mcp_client import GitHubMCPClient, create_github_mcp_client, register_github_mcp_tools

__all__ = [
    "GitHubMCPClient",
    "create_github_mcp_client",
    "register_github_mcp_tools",
]
