# -*- coding: utf-8 -*-
"""
GitHub API 工具类

功能:
- 封装 GitHub REST API 调用
- 支持仓库搜索、README 获取等
- 统一的错误处理和重试机制
- 防御性编程和类型安全

工程化要求:
- 处理 HTTP 错误 (401, 403, 404)
- 实现重试逻辑 (最多 3 次)
- 返回类型化的 ToolResponse
"""

import base64
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.types.schemas import GitHubRepo, GitHubSearchResult, ToolResponse

logger = get_logger(__name__)


class GitHubTool:
    """
    GitHub API 工具类

    提供对 GitHub REST API v3 的封装，支持:
    - 仓库搜索 (search_repositories)
    - README 获取 (get_readme)
    - 统一的错误处理和重试机制

    Attributes:
        BASE_URL: GitHub API 基础 URL
        MAX_RETRIES: 最大重试次数
        RETRY_DELAY: 重试延迟 (秒)
    """

    BASE_URL = "https://api.github.com"
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
        config: Optional[ConfigManager] = None,
    ):
        """
        初始化工具类

        Args:
            token: GitHub Personal Access Token，可从环境变量 GITHUB_TOKEN 读取
            timeout: 请求超时时间 (秒)
            config: 配置管理器实例
        """
        self._config = config or ConfigManager()

        # 从配置或参数获取 token
        self._token = token or self._config.github_token or os.getenv("GITHUB_TOKEN")
        self._timeout = timeout or self._config.github_timeout

        # 初始化 HTTP Session
        self._session = requests.Session()

        # 配置请求头
        self._setup_headers()

        # 速率限制配置
        self._rate_limit = self._config.github_rate_limit
        self._last_request_time: float = 0

        logger.info(
            f"GitHubTool initialized (token: {'configured' if self._token else 'not configured'}, "
            f"timeout: {self._timeout}s)"
        )

    def _setup_headers(self) -> None:
        """设置 HTTP 请求头"""
        self._session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Insight-Agent/0.1.0",
        })

        if self._token:
            self._session.headers.update({
                "Authorization": f"Bearer {self._token}",
            })
            logger.debug("Authorization header configured")
        else:
            logger.warning("No GitHub token configured. Rate limits may apply.")

    def _enforce_rate_limit(self) -> None:
        """执行速率限制"""
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
        发送 HTTP 请求 (带重试逻辑)

        Args:
            method: HTTP 方法
            endpoint: API 端点
            max_retries: 最大重试次数
            **kwargs: 传递给 requests 的其他参数

        Returns:
            ToolResponse 包装的响应
        """
        url = f"{self.BASE_URL}{endpoint}"
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                self._enforce_rate_limit()
                logger.debug(f"Request #{attempt}: {method} {url}")

                response = self._session.request(
                    method, url, timeout=self._timeout, **kwargs
                )

                # 处理不同状态码
                if response.status_code == 401:
                    return ToolResponse.fail(
                        error_message="Unauthorized: Invalid or expired GitHub token",
                    )
                elif response.status_code == 403:
                    # 检查是否是速率限制
                    if response.headers.get("X-RateLimit-Remaining") == "0":
                        reset_time = response.headers.get("X-RateLimit-Reset", "unknown")
                        return ToolResponse.fail(
                            error_message=f"Rate limit exceeded. Reset at: {reset_time}",
                        )
                    return ToolResponse.fail(
                        error_message=f"Forbidden: Access denied (403)",
                    )
                elif response.status_code == 404:
                    return ToolResponse.fail(
                        error_message=f"Not Found: {endpoint}",
                    )
                elif response.status_code >= 500:
                    # 服务器错误，可重试
                    logger.warning(f"Server error {response.status_code}, retrying...")
                    last_error = Exception(f"Server error: {response.status_code}")
                    time.sleep(self.RETRY_DELAY * attempt)
                    continue

                response.raise_for_status()
                return ToolResponse.ok(data=response.json())

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Request timeout (attempt {attempt}/{max_retries})")
                time.sleep(self.RETRY_DELAY * attempt)
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.error(f"Request failed: {e}")
                return ToolResponse.fail(error_message=str(e))

        # 所有重试失败
        return ToolResponse.fail(
            error_message=f"Request failed after {max_retries} attempts: {last_error}",
        )

    def search_repositories(
        self,
        query: str,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 10,
    ) -> List[GitHubRepo]:
        """
        搜索 GitHub 仓库

        Args:
            query: 搜索关键词
            sort: 排序字段 (stars/forks/updated)
            order: 排序顺序 (asc/desc)
            per_page: 每页数量 (最多 100)

        Returns:
            GitHubRepo 列表

        Raises:
            RuntimeError: API 调用失败时抛出
        """
        logger.info(f"Searching repositories: '{query}' (sort={sort}, order={order})")

        endpoint = "/search/repositories"
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100),  # GitHub API 限制
        }

        response = self._request_with_retry("GET", endpoint, params=params)

        if not response.success:
            raise RuntimeError(f"GitHub API error: {response.error_message}")

        # 解析为类型化的结果
        search_result = GitHubSearchResult.from_api_response(response.data)
        logger.info(f"Found {search_result.total_count} repositories")

        return search_result.items

    def get_readme(self, owner: str, repo: str, ref: str = "HEAD") -> str:
        """
        获取指定仓库的 README 内容

        Args:
            owner: 仓库所有者 (用户名或组织名)
            repo: 仓库名称
            ref: 分支名或提交 SHA，默认 HEAD

        Returns:
            README 的纯文本内容

        Raises:
            RuntimeError: API 调用失败时抛出
            ValueError: README 不存在时抛出
        """
        logger.info(f"Fetching README: {owner}/{repo} (ref={ref})")

        endpoint = f"/repos/{owner}/{repo}/readme"
        params = {"ref": ref} if ref != "HEAD" else {}

        response = self._request_with_retry("GET", endpoint, params=params)

        if not response.success:
            if "Not Found" in response.error_message:
                raise ValueError(f"Repository '{owner}/{repo}' not found or has no README")
            raise RuntimeError(f"GitHub API error: {response.error_message}")

        # 解码 base64 内容
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
        获取单个仓库的详细信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            GitHubRepo 实例

        Raises:
            RuntimeError: API 调用失败时抛出
            ValueError: 仓库不存在时抛出
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
        检查当前 API 速率限制状态

        Returns:
            速率限制信息字典
        """
        if not self._token:
            # 未认证请求
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
        清洗 README 内容，去除 Markdown 符号

        Args:
            content: 原始 README 内容
            max_length: 最大字符数，超过则截取前 N 字符

        Returns:
            清洗后的纯文本
        """
        # 如果内容过长，先截取
        if len(content) > max_length:
            content = content[:max_length]
            # 尝试在完整行处截断
            newline_pos = content.rfind("\n")
            if newline_pos > max_length - 500:
                content = content[:newline_pos]

        text = content

        # 移除代码块 ```xxx ... ```
        text = re.sub(r"```[\s\S]*?```", "", text)

        # 移除行内代码 `xxx`
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # 移除标题标记 ###
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)

        # 移除粗体 **xxx**
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

        # 移除斜体 *xxx*
        text = re.sub(r"\*([^*]+)\*", r"\1", text)

        # 移除链接 [text](url) -> text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # 移除图片 ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)

        # 移除引用 >
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

        # 移除列表标记 - 或 * 或 1.
        text = re.sub(r"^[\s]*[-*+]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s*", "", text, flags=re.MULTILINE)

        # 移除水平线 ---
        text = re.sub(r"^---$", "", text, flags=re.MULTILINE)

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)

        # 移除多余空白行（超过 2 个连续空行缩减为 1 个）
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 清理每行首尾空白
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def get_project_summary(self, owner: str, repo: str, max_readme_length: int = 5000) -> Dict[str, Any]:
        """
        获取项目的综合摘要信息

        组合调用多个 API，获取项目的详细信息，包括：
        - 基本信息（名称、stars、语言）
        - README 内容（已清洗为纯文本）

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            max_readme_length: README 最大字符数（默认 5000，防止 Token 超限）

        Returns:
            包含以下字段的字典:
            - name: 仓库名称
            - full_name: 完整名称
            - html_url: GitHub URL
            - stars: Star 数量
            - language: 主要编程语言
            - description: 简介
            - topics: 主题标签
            - cleaned_readme_text: 清洗后的 README 纯文本
            - readme_truncated: README 是否被截断

        Raises:
            RuntimeError: API 调用失败时抛出
        """
        logger.info(f"Fetching project summary: {owner}/{repo}")

        # 获取仓库信息
        try:
            repo_info = self.get_repo_info(owner, repo)
        except RuntimeError as e:
            logger.error(f"Failed to get repo info: {e}")
            raise

        # 获取 README
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
            "name": repo_info.full_name.split("/")[-1],  # 从 full_name 提取仓库名
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
