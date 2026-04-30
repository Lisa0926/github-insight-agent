# -*- coding: utf-8 -*-
"""
GitHub Toolkit - AgentScope Toolkit Integration

Features:
- Registers GitHubTool methods as AgentScope Toolkit tools
- Auto-generates JSON Schema from docstrings
- Supports MCP (Model Context Protocol) integration
- Supports streaming return and unified invocation interface
"""

from functools import wraps
from typing import Any, Dict, List, Optional
import time
from agentscope.tool import Toolkit, ToolResponse

from src.core.config_manager import ConfigManager
from src.core.guardrails import filter_sensitive_output
from src.tools.github_tool import GitHubTool
from src.github_mcp import create_github_mcp_client, register_github_mcp_tools
from src.core.logger import get_logger

logger = get_logger(__name__)


def audit_tool_call(func):
    """
    Audit decorator for tool calls.

    Records tool call input/output/duration/errors for analysis and optimization.
    Logs every tool invocation with structured data.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()

        # Sanitize args for logging (avoid logging sensitive data like tokens)
        safe_kwargs = {k: v for k, v in kwargs.items()
                       if k.lower() not in ('token', 'secret', 'password', 'key', 'auth')}
        input_summary = {
            "tool": tool_name,
            "args_count": len(args),
            "kwargs": safe_kwargs,
        }

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # Determine result size for logging
            result_size = 0
            if isinstance(result, ToolResponse):
                result_size = len(str(result.content)) if result.content else 0
            elif isinstance(result, str):
                result_size = len(result)
            elif isinstance(result, (list, dict)):
                result_size = len(str(result))

            logger.info(
                f"[TOOL_AUDIT] tool={tool_name} status=success "
                f"duration={duration:.3f}s output_size={result_size} "
                f"input={input_summary}"
            )
            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.warning(
                f"[TOOL_AUDIT] tool={tool_name} status=error "
                f"duration={duration:.3f}s error={str(e)} "
                f"input={input_summary}"
            )
            raise

    return wrapper


def create_github_toolkit(  # noqa: C901
    config: Optional[ConfigManager] = None,
    github_token: Optional[str] = None,
    use_mcp: bool = True,
) -> Toolkit:
    """
    Create and configure the GitHub Toolkit

    Args:
        config: Config manager instance
        github_token: GitHub Token (optional, read from config if not provided)
        use_mcp: Whether to enable GitHub MCP Server (default True)

    Returns:
        Toolkit instance with registered GitHub tools
    """
    # Create Toolkit and specify available tool groups
    toolkit = Toolkit()

    # Create github tool group (active by default)
    toolkit.create_tool_group("github", description="GitHub API tools for repository search and analysis", active=True)

    # Create github_mcp tool group (if using MCP)
    if use_mcp:
        toolkit.create_tool_group("github_mcp", description="GitHub MCP Server tools", active=True)

    github_tool = GitHubTool(config=config, token=github_token)

    # Try to register MCP client
    mcp_tool_count = 0
    if use_mcp:
        try:
            mcp_client = create_github_mcp_client(config=config, github_token=github_token)
            if mcp_client:
                register_github_mcp_tools(toolkit, mcp_client, group_name="github_mcp")
                logger.info("GitHub MCP Server connected successfully")
        except Exception as e:
            logger.warning(f"MCP Server connection failed, falling back to local tools: {e}")
            use_mcp = False

    # 1. Register repository search tool
    def search_repositories(
        query: str,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 10,
    ) -> ToolResponse:
        """
        Search GitHub repositories by keyword.

        Args:
            query: Search keyword (e.g., "python web framework")
            sort: Sort field, one of: stars, forks, updated
            order: Sort order, one of: asc, desc
            per_page: Number of results per page (1-100)

        Returns:
            Formatted search results with repository name, stars, language, and description
        """
        try:
            repos = github_tool.search_repositories(
                query=query,
                sort=sort,
                order=order,
                per_page=per_page,
            )

            lines = [f"Found {len(repos)} repositories:\n"]
            for i, repo in enumerate(repos, 1):
                desc = repo.description or "No description"
                lines.append(
                    f"{i}. **{repo.full_name}** | "
                    f"⭐ {repo.stargazers_count:,} | "
                    f"💻 {repo.language or 'N/A'} | "
                    f"{desc[:80]}"
                )

            return ToolResponse(content=[{"text": "\n".join(lines)}])

        except RuntimeError as e:
            return ToolResponse.fail(error_message=str(e))

    toolkit.register_tool_function(
        search_repositories,
        group_name="github",
        namesake_strategy="skip",  # Skip duplicates with MCP tools
    )

    # 2. Register README retrieval tool
    def get_readme(
        owner: str,
        repo: str,
        ref: str = "HEAD",
        as_plain_text: bool = True,
    ) -> ToolResponse:
        """
        Get the README content of a GitHub repository.

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            ref: Branch name or commit SHA (default: HEAD)
            as_plain_text: If True, remove Markdown formatting

        Returns:
            README content (plain text or Markdown)
        """
        try:
            readme_content = github_tool.get_readme(owner, repo, ref=ref)
            if as_plain_text:
                readme_content = github_tool.clean_readme_text(readme_content)
            # Filter sensitive data from README content
            readme_content = filter_sensitive_output(readme_content)
            return ToolResponse(content=[{"text": readme_content}])

        except (RuntimeError, ValueError) as e:
            return ToolResponse.fail(error_message=str(e))

    toolkit.register_tool_function(
        get_readme,
        group_name="github",
        namesake_strategy="skip",  # Skip duplicates with MCP tools
    )

    # 3. Register repository info tool
    def get_repo_info(owner: str, repo: str) -> ToolResponse:
        """
        Get detailed information about a GitHub repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository details including name, stars, forks, language, topics
        """
        try:
            repo_info = github_tool.get_repo_info(owner, repo)

            info_lines = [
                f"**{repo_info.full_name}**",
                f"Description: {repo_info.description or 'N/A'}",
                f"Stars: {repo_info.stargazers_count:,}",
                f"Forks: {repo_info.forks_count:,}",
                f"Language: {repo_info.language or 'N/A'}",
                f"Topics: {', '.join(repo_info.topics) if repo_info.topics else 'N/A'}",
                f"URL: {repo_info.html_url}",
            ]

            return ToolResponse(content=[{"text": "\n".join(info_lines)}])

        except (RuntimeError, ValueError) as e:
            return ToolResponse.fail(error_message=str(e))

    toolkit.register_tool_function(
        get_repo_info,
        group_name="github",
        namesake_strategy="skip",  # Skip duplicates with MCP tools
    )

    # 4. Register project summary tool
    def get_project_summary(
        owner: str,
        repo: str,
        include_readme: bool = True,
        max_readme_length: int = 3000,
    ) -> ToolResponse:
        """
        Get a comprehensive summary of a GitHub project.

        Args:
            owner: Repository owner
            repo: Repository name
            include_readme: Whether to include cleaned README text
            max_readme_length: Maximum README character count

        Returns:
            Project summary with basic info and optional README excerpt
        """
        try:
            summary = github_tool.get_project_summary(
                owner, repo,
                max_readme_length=max_readme_length if include_readme else 0,
            )

            lines = [
                "**Project Summary: {name}**".format(name=summary['full_name']),
                "",
                "📊 Stars: {stars}".format(stars=f"{summary['stars']:,}"),
                "🔧 Forks: {forks}".format(forks=f"{summary['forks']:,}"),
                "💻 Language: {language}".format(language=summary['language']),
                "📝 Description: {description}".format(description=summary['description']),
                "🏷️ Topics: {topics}".format(topics=', '.join(summary['topics']) if summary['topics'] else 'N/A'),
            ]

            if include_readme and summary.get("cleaned_readme_text"):
                readme_preview = summary["cleaned_readme_text"][:max_readme_length]
                if len(summary["cleaned_readme_text"]) > max_readme_length:
                    readme_preview += "... (truncated)"
                lines.extend([
                    "",
                    "--- README Preview ---",
                    readme_preview,
                ])

            return ToolResponse(content=[{"text": "\n".join(lines)}])

        except (RuntimeError, ValueError) as e:
            return ToolResponse.fail(error_message=str(e))

    toolkit.register_tool_function(
        get_project_summary,
        group_name="github",
        namesake_strategy="skip",  # Skip duplicates with MCP tools
    )

    # 5. Register rate limit query tool
    def check_rate_limit() -> ToolResponse:
        """
        Check the current GitHub API rate limit status.

        Returns:
            Rate limit information including remaining requests and reset time
        """
        rate_info = github_tool.check_rate_limit()

        if "error" in rate_info:
            return ToolResponse.fail(error_message=rate_info["error"])

        lines = [
            "**GitHub API Rate Limit**",
            "Limit: {limit} requests/hour".format(limit=f"{rate_info['limit']:,}"),
            "Remaining: {remaining} requests".format(remaining=f"{rate_info['remaining']:,}"),
            "Authenticated: {auth}".format(auth='Yes' if rate_info.get('authenticated') else 'No'),
        ]

        if rate_info.get("reset"):
            lines.append(f"Reset: {rate_info['reset']}")

        return ToolResponse(content=[{"text": "\n".join(lines)}])

    toolkit.register_tool_function(
        check_rate_limit,
        group_name="github",
        namesake_strategy="skip",  # Skip duplicates with MCP tools
    )

    logger.info(f"GitHub Toolkit created with {len(toolkit.get_json_schemas())} tools registered (MCP: {mcp_tool_count})")
    return toolkit


def get_github_tool_schemas(toolkit: Toolkit) -> List[Dict[str, Any]]:
    """
    Get the list of JSON Schemas for GitHub tools

    Args:
        toolkit: GitHub Toolkit instance

    Returns:
        List of JSON Schemas for LLM tool invocation
    """
    return toolkit.get_json_schemas()


# Convenience function: get preset GitHub Toolkit
_github_toolkit_cache: Optional[Toolkit] = None


def get_github_toolkit(
    config: Optional[ConfigManager] = None,
    github_token: Optional[str] = None,
    force_new: bool = False,
    use_mcp: bool = True,
) -> Toolkit:
    """
    Get GitHub Toolkit instance (singleton pattern)

    Args:
        config: Config manager instance
        github_token: GitHub Token
        force_new: Whether to force creating a new instance
        use_mcp: Whether to enable GitHub MCP Server

    Returns:
        GitHub Toolkit instance
    """
    global _github_toolkit_cache

    if force_new or _github_toolkit_cache is None:
        _github_toolkit_cache = create_github_toolkit(
            config=config,
            github_token=github_token,
            use_mcp=use_mcp,
        )

    return _github_toolkit_cache
