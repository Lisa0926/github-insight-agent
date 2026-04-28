# -*- coding: utf-8 -*-
"""
GitHub API tool class

Features:
- Wraps GitHub REST API calls
- Supports repository search, README retrieval, etc.
- Unified error handling and retry mechanism
- Defensive programming and type safety

Engineering requirements:
- Handle HTTP errors (401, 403, 404)
- Implement retry logic (up to 3 times)
- Return typed ToolResponse
"""

import base64
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.resilient_http import ResilientHTTPClient, RateLimitError
from src.types.schemas import GitHubRepo, GitHubSearchResult, ToolResponse

logger = get_logger(__name__)


class GitHubTool:
    """
    GitHub API tool class

    Provides a wrapper around the GitHub REST API v3, supporting:
    - Repository search (search_repositories)
    - README retrieval (get_readme)
    - Unified error handling and retry mechanism

    Attributes:
        BASE_URL: GitHub API base URL
        MAX_RETRIES: Maximum number of retries
        RETRY_DELAY: Retry delay (seconds)
    """

    BASE_URL = "https://api.github.com"
    MAX_RETRIES = 5  # Increased to 5 with exponential backoff
    RETRY_DELAY = 1.0

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
        config: Optional[ConfigManager] = None,
    ):
        """
        Initialize the tool

        Args:
            token: GitHub Personal Access Token, can be read from GITHUB_TOKEN environment variable
            timeout: Request timeout (seconds)
            config: Config manager instance
        """
        self._config = config or ConfigManager()

        # Get token from config or parameter
        self._token = token or self._config.github_token or os.getenv("GITHUB_TOKEN")
        self._timeout = timeout or self._config.github_timeout or 30

        # Initialize resilient HTTP client (with exponential backoff, circuit breaker, rate limiting)
        self._http_client = ResilientHTTPClient(
            timeout=self._timeout,
            max_retries=self.MAX_RETRIES,
            max_wait=60,  # Max wait 60 seconds
            circuit_breaker_threshold=5,  # Open circuit breaker after 5 failures
            circuit_breaker_timeout=60,   # Circuit breaker recovery after 60 seconds
        )

        # Configure request headers
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Insight-Agent/0.1.0",
        }

        if self._token:
            self._headers["Authorization"] = f"token {self._token}"
            logger.info("GitHub auth configured")
        else:
            logger.warning("GitHub auth not configured. Rate limits may apply.")

        # Rate limit configuration
        self._rate_limit = self._config.github_rate_limit
        self._last_request_time: float = 0
        self._rate_limit_remaining: int = -1  # -1 indicates unknown
        self._rate_limit_reset: int = 0

        logger.info(
            f"GitHubTool initialized (token: {'configured' if self._token else 'not configured'}, "
            f"timeout: {self._timeout}s, max_retries: {self.MAX_RETRIES})"
        )

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting"""
        if self._rate_limit <= 0:
            return

        min_interval = 1.0 / self._rate_limit
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        max_retries: int = MAX_RETRIES,
        **kwargs,
    ) -> ToolResponse:
        """
        Send HTTP request (with retry logic)

        Uses ResilientHTTPClient to provide:
        - Exponential backoff retry
        - Timeout handling
        - Graceful degradation for 429 rate limiting
        - Circuit breaker pattern

        Args:
            method: HTTP method
            endpoint: API endpoint
            max_retries: Maximum number of retries
            **kwargs: Parameters passed to requests

        Returns:
            ToolResponse-wrapped response
        """
        url = f"{self.BASE_URL}{endpoint}"

        # Merge request headers
        headers = self._headers.copy()
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
            del kwargs["headers"]

        try:
            # Execute rate limit control
            self._enforce_rate_limit()

            logger.debug(f"Request: {method} {url}")

            # Send request using resilient HTTP client
            response = self._http_client.request(
                method,
                url,
                timeout=self._timeout,
                headers=headers,
                **kwargs,
            )

            # Extract rate limit information
            self._rate_limit_remaining = int(
                response.headers.get("X-RateLimit-Remaining", -1)
            )
            self._rate_limit_reset = int(
                response.headers.get("X-RateLimit-Reset", 0)
            )

            # Successful response
            return ToolResponse.ok(data=response.json())

        except RateLimitError as e:
            logger.warning(f"Rate limited: {e}")
            self._rate_limit_remaining = 0
            self._rate_limit_reset = int(time.time()) + (e.retry_after or 60)
            return ToolResponse.fail(
                error_message=f"Rate limit exceeded. Retry after {e.retry_after or 60}s",
            )
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            logger.error(f"Request failed: {error_msg}")

            # Extract specific error information
            if "401" in error_msg or "Unauthorized" in error_msg:
                return ToolResponse.fail(
                    error_message="Unauthorized: Invalid or expired GitHub token",
                )
            elif "403" in error_msg or "Forbidden" in error_msg:
                return ToolResponse.fail(
                    error_message="Forbidden: Access denied",
                )
            elif "404" in error_msg or "Not Found" in error_msg:
                return ToolResponse.fail(
                    error_message=f"Not Found: {endpoint}",
                )
            elif "Circuit breaker" in error_msg:
                return ToolResponse.fail(
                    error_message="Service temporarily unavailable (circuit breaker open)",
                )
            else:
                return ToolResponse.fail(error_message=error_msg)

    def search_repositories(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 10,
    ) -> List[GitHubRepo]:
        """
        Search GitHub repositories

        Args:
            query: Search keyword
            sort: Sort field (stars/forks/updated)
            order: Sort order (asc/desc)
            per_page: Number per page (max 100)

        Returns:
            List of GitHubRepo

        Raises:
            RuntimeError: Raised when API call fails
        """
        logger.info(f"Searching repositories: '{query}' (sort={sort}, order={order})")

        endpoint = "/search/repositories"
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),  # GitHub API limit
        }

        response = self._request_with_retry("GET", endpoint, params=params)

        if not response.success:
            raise RuntimeError(f"GitHub API error: {response.error_message}")

        # Parse into typed result
        search_result = GitHubSearchResult.from_api_response(response.data)
        logger.info(f"Found {search_result.total_count} repositories")

        return search_result.items

    def get_readme(self, owner: str, repo: str, ref: str = "HEAD") -> str:
        """
        Get the README content of a specified repository

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
            ref: Branch name or commit SHA, default HEAD

        Returns:
            Plain text content of the README

        Raises:
            RuntimeError: Raised when API call fails
            ValueError: Raised when README does not exist
        """
        logger.info(f"Fetching README: {owner}/{repo} (ref={ref})")

        endpoint = f"/repos/{owner}/{repo}/readme"
        params = {"ref": ref} if ref != "HEAD" else {}

        response = self._request_with_retry("GET", endpoint, params=params)

        if not response.success:
            if "Not Found" in response.error_message:
                raise ValueError(f"Repository '{owner}/{repo}' not found or has no README")
            raise RuntimeError(f"GitHub API error: {response.error_message}")

        # Decode base64 content
        try:
            content_base64 = response.data.get("content", "")
            content = base64.b64decode(content_base64).decode("utf-8")
            logger.info(f"README fetched successfully ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"Failed to decode README: {e}")
            raise RuntimeError(f"Failed to decode README content: {e}")

    def get_repo_info(self, owner: str, repo: str) -> GitHubRepo:
        """
        Get detailed information for a single repository

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            GitHubRepo instance

        Raises:
            RuntimeError: Raised when API call fails
            ValueError: Raised when repository does not exist
        """
        logger.info(f"Fetching repo info: {owner}/{repo}")

        endpoint = f"/repos/{owner}/{repo}"
        response = self._request_with_retry("GET", endpoint)

        if not response.success:
            if "Not Found" in response.error_message:
                raise ValueError(f"Repository '{owner}/{repo}' not found")
            raise RuntimeError(f"GitHub API error: {response.error_message}")

        return GitHubRepo.from_api_response(response.data)

    def check_rate_limit(self) -> Dict[str, Any]:
        """
        Check current API rate limit status

        Returns:
            Dictionary of rate limit information
        """
        if not self._token:
            # Unauthenticated request
            return {
                "limit": 60,
                "remaining": "unknown",
                "reset": "unknown",
                "authenticated": False,
            }

        endpoint = "/rate_limit"
        response = self._request_with_retry("GET", endpoint)

        if response.success:
            resources = response.data.get("resources", {})
            core = resources.get("core", {})
            return {
                "limit": core.get("limit", 0),
                "remaining": core.get("remaining", 0),
                "reset": core.get("reset", 0),
                "authenticated": True,
            }

        return {"error": response.error_message}

    @staticmethod
    def clean_readme_text(content: str, max_length: int = 5000) -> str:
        """
        Clean README content by removing Markdown symbols

        Args:
            content: Raw README content
            max_length: Maximum character count; truncates to first N characters if exceeded

        Returns:
            Cleaned plain text
        """
        # Truncate if content is too long
        if len(content) > max_length:
            content = content[:max_length]
            # Try to truncate at a complete line
            newline_pos = content.rfind("\n")
            if newline_pos > max_length - 500:
                content = content[:newline_pos]

        text = content

        # Remove code blocks ```xxx ... ```
        text = re.sub(r"```[\s\S]*?```", "", text)

        # Remove inline code `xxx`
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Remove heading markers ###
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)

        # Remove bold **xxx**
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

        # Remove italic *xxx*
        text = re.sub(r"\*([^*]+)\*", r"\1", text)

        # Remove links [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # Remove images ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)

        # Remove quotes >
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

        # Remove list markers - or * or 1.
        text = re.sub(r"^[\s]*[-*+]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s*", "", text, flags=re.MULTILINE)

        # Remove horizontal rules ---
        text = re.sub(r"^---$", "", text, flags=re.MULTILINE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove excess blank lines (more than 2 consecutive blank lines reduced to 1)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Trim leading/trailing whitespace on each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def get_project_summary(self, owner: str, repo: str, max_readme_length: int = 5000) -> Dict[str, Any]:
        """
        Get a comprehensive project summary

        Combines multiple API calls to get detailed project information including:
        - Basic info (name, stars, language)
        - README content (cleaned to plain text)

        Args:
            owner: Repository owner
            repo: Repository name
            max_readme_length: README maximum character count (default 5000, to prevent Token overflow)

        Returns:
            Dictionary with the following fields:
            - name: Repository name
            - full_name: Full name
            - html_url: GitHub URL
            - stars: Star count
            - language: Primary programming language
            - description: Description
            - topics: Topic tags
            - cleaned_readme_text: Cleaned README plain text
            - readme_truncated: Whether README was truncated

        Raises:
            RuntimeError: Raised when API call fails
        """
        logger.info(f"Fetching project summary: {owner}/{repo}")

        # Fetch repository info
        try:
            repo_info = self.get_repo_info(owner, repo)
        except RuntimeError as e:
            logger.error(f"Failed to get repo info: {e}")
            raise

        # Fetch README
        readme_text = ""
        readme_truncated = False
        try:
            raw_readme = self.get_readme(owner, repo)
            if len(raw_readme) > max_readme_length:
                readme_truncated = True
                logger.info(f"README truncated from {len(raw_readme)} to {max_readme_length} chars")
            cleaned_text = self.clean_readme_text(raw_readme, max_length=max_readme_length)
            readme_text = cleaned_text
        except ValueError as e:
            logger.warning(f"No README available: {e}")
        except RuntimeError as e:
            logger.warning(f"Failed to fetch README: {e}")

        summary = {
            "name": repo_info.full_name.split("/")[-1],  # Extract repo name from full_name
            "full_name": repo_info.full_name,
            "html_url": repo_info.html_url,
            "stars": repo_info.stargazers_count,
            "forks": repo_info.forks_count,
            "language": repo_info.language or "N/A",
            "description": repo_info.description or "N/A",
            "topics": repo_info.topics,
            "updated_at": repo_info.updated_at,
            "cleaned_readme_text": readme_text,
            "readme_truncated": readme_truncated,
        }

        logger.info(
            f"Project summary fetched: {summary['full_name']} "
            f"(stars={summary['stars']}, readme={len(readme_text)} chars)"
        )

        return summary
