# -*- coding: utf-8 -*-
"""
Pydantic 数据模型定义

功能:
- 定义 GitHub 相关数据的类型约束
- 提供数据校验和序列化能力
- 支持类型驱动开发

使用类型注解和 Pydantic v2 标准。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class GitHubRepoInfo(BaseModel):
    """GitHub 仓库信息模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "github-insight-agent",
                "full_name": "example/github-insight-agent",
                "url": "https://github.com/example/github-insight-agent",
                "description": "企业级多智能体情报分析系统",
                "stars": 150,
                "forks": 30,
                "watchers": 20,
                "open_issues": 5,
                "language": "Python",
                "topics": ["ai", "github", "analysis"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-04-09T00:00:00Z",
                "owner": "example",
                "is_private": False,
                "license": "MIT",
            }
        }
    )

    name: str = Field(..., description="仓库名称")
    full_name: str = Field(..., description="完整名称 (owner/repo)")
    url: HttpUrl = Field(..., description="仓库 URL")
    description: Optional[str] = Field(None, description="仓库描述")
    stars: int = Field(0, description="星标数量")
    forks: int = Field(0, description="Fork 数量")
    watchers: int = Field(0, description="Watch 数量")
    open_issues: int = Field(0, description="未关闭 Issue 数量")
    language: Optional[str] = Field(None, description="主要编程语言")
    topics: List[str] = Field(default_factory=list, description="仓库主题")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    owner: str = Field(..., description="仓库所有者")
    is_private: bool = Field(False, description="是否为私有仓库")
    license: Optional[str] = Field(None, description="许可证")


class GitHubIssueInfo(BaseModel):
    """GitHub Issue 信息模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "number": 1,
                "title": "Feature request: Add multi-agent support",
                "url": "https://github.com/example/github-insight-agent/issues/1",
                "state": "open",
                "body": "We need multi-agent support for...",
                "user": "example-user",
                "labels": ["enhancement", "priority-high"],
                "comments": 3,
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-05T00:00:00Z",
                "closed_at": None,
                "assignees": ["dev-user"],
            }
        }
    )

    number: int = Field(..., description="Issue 编号")
    title: str = Field(..., description="Issue 标题")
    url: HttpUrl = Field(..., description="Issue URL")
    state: str = Field(..., description="状态 (open/closed)")
    body: Optional[str] = Field(None, description="Issue 正文")
    user: str = Field(..., description="创建者")
    labels: List[str] = Field(default_factory=list, description="标签列表")
    comments: int = Field(0, description="评论数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    closed_at: Optional[datetime] = Field(None, description="关闭时间")
    assignees: List[str] = Field(default_factory=list, description="指派人员")


class GitHubPRInfo(BaseModel):
    """GitHub Pull Request 信息模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "number": 42,
                "title": "feat: Add GitHub API integration",
                "url": "https://github.com/example/github-insight-agent/pull/42",
                "state": "open",
                "body": "This PR adds GitHub API integration...",
                "user": "contributor",
                "base_branch": "main",
                "head_branch": "feature/github-integration",
                "commits": 5,
                "additions": 350,
                "deletions": 20,
                "changed_files": 8,
                "labels": ["feature", "needs-review"],
                "reviewers": ["maintainer"],
                "created_at": "2026-04-07T00:00:00Z",
                "updated_at": "2026-04-09T00:00:00Z",
                "merged_at": None,
                "merged_by": None,
            }
        }
    )

    number: int = Field(..., description="PR 编号")
    title: str = Field(..., description="PR 标题")
    url: HttpUrl = Field(..., description="PR URL")
    state: str = Field(..., description="状态 (open/closed/merged)")
    body: Optional[str] = Field(None, description="PR 正文")
    user: str = Field(..., description="创建者")
    base_branch: str = Field(..., description="目标分支")
    head_branch: str = Field(..., description="源分支")
    commits: int = Field(0, description="提交数量")
    additions: int = Field(0, description="新增行数")
    deletions: int = Field(0, description="删除行数")
    changed_files: int = Field(0, description="修改文件数")
    labels: List[str] = Field(default_factory=list, description="标签列表")
    reviewers: List[str] = Field(default_factory=list, description="审查人员")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    merged_at: Optional[datetime] = Field(None, description="合并时间")
    merged_by: Optional[str] = Field(None, description="合并操作者")


class AnalysisResult(BaseModel):
    """分析结果模型"""

    repo_name: str = Field(..., description="仓库名称")
    analysis_type: str = Field(..., description="分析类型")
    summary: str = Field(..., description="分析摘要")
    insights: List[str] = Field(default_factory=list, description="关键洞察")
    recommendations: List[str] = Field(default_factory=list, description="建议")
    risk_level: str = Field("medium", description="风险等级 (low/medium/high)")
    timestamp: datetime = Field(default_factory=datetime.now, description="分析时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


# ===========================================
# Day 3-4: 新增核心数据模型
# ===========================================


class GitHubRepo(BaseModel):
    """
    GitHub 仓库数据模型

    用于表示 GitHub 搜索和仓库查询的结果。
    """

    full_name: str = Field(..., description="完整名称 (owner/repo)")
    html_url: str = Field(..., description="GitHub HTML URL")
    stargazers_count: int = Field(0, description="Star 数量")
    language: str = Field("", description="主要编程语言")
    description: str = Field("", description="仓库描述")
    topics: List[str] = Field(default_factory=list, description="仓库主题标签")
    updated_at: str = Field("", description="最后更新时间 (ISO 8601)")

    # 额外可选字段
    forks_count: int = Field(0, description="Fork 数量")
    watchers_count: int = Field(0, description="Watch 数量")
    open_issues_count: int = Field(0, description="未关闭 Issue 数量")
    owner_login: str = Field("", description="所有者用户名")
    is_fork: bool = Field(False, description="是否为 Fork 仓库")
    is_archived: bool = Field(False, description="是否已归档")

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GitHubRepo":
        """
        从 GitHub API 响应数据创建实例

        Args:
            data: GitHub API 返回的原始数据

        Returns:
            GitHubRepo 实例
        """
        owner = data.get("owner", {})
        return cls(
            full_name=data.get("full_name", ""),
            html_url=data.get("html_url", ""),
            stargazers_count=data.get("stargazers_count", 0),
            language=data.get("language") or "",
            description=data.get("description") or "",
            topics=data.get("topics", []),
            updated_at=data.get("updated_at", ""),
            forks_count=data.get("forks_count", 0),
            watchers_count=data.get("watchers_count", 0),
            open_issues_count=data.get("open_issues_count", 0),
            owner_login=owner.get("login", "") if owner else "",
            is_fork=data.get("fork", False),
            is_archived=data.get("archived", False),
        )


class GitHubSearchResult(BaseModel):
    """
    GitHub 搜索结果数据模型

    封装 GitHub Search API 的响应结构。
    """

    total_count: int = Field(0, description="匹配的仓库总数")
    items: List[GitHubRepo] = Field(default_factory=list, description="仓库列表")
    incomplete_results: bool = Field(False, description="搜索结果是否完整")

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GitHubSearchResult":
        """
        从 GitHub API 响应数据创建实例

        Args:
            data: GitHub Search API 返回的原始数据

        Returns:
            GitHubSearchResult 实例
        """
        items = [GitHubRepo.from_api_response(item) for item in data.get("items", [])]
        return cls(
            total_count=data.get("total_count", 0),
            items=items,
            incomplete_results=data.get("incomplete_results", False),
        )

    def to_markdown_table(self) -> str:
        """
        将搜索结果转换为 Markdown 表格

        Returns:
            Markdown 格式的表格字符串
        """
        if not self.items:
            return "No results found."

        lines = [
            "| # | Repository | Stars | Language | Description |",
            "|---|------------|-------|----------|-------------|",
        ]

        for i, repo in enumerate(self.items[:10], 1):  # 最多显示 10 条
            desc = (repo.description[:40] + "...") if len(repo.description) > 40 else repo.description
            desc = desc.replace("\n", " ")
            lines.append(
                f"| {i} | **{repo.full_name}** | {repo.stargazers_count:,} | "
                f"{repo.language} | {desc} |"
            )

        return "\n".join(lines)


class ToolResponse(BaseModel):
    """
    通用工具响应包装类

    用于统一工具调用的返回格式，便于 Agent 处理。
    """

    success: bool = Field(..., description="操作是否成功")
    data: Optional[Any] = Field(None, description="成功时返回的数据")
    error_message: str = Field("", description="失败时的错误消息")

    @classmethod
    def ok(cls, data: Any, message: str = "") -> "ToolResponse":
        """创建成功响应"""
        return cls(success=True, data=data, error_message=message)

    @classmethod
    def fail(cls, error_message: str, data: Any = None) -> "ToolResponse":
        """创建失败响应"""
        return cls(success=False, data=data, error_message=error_message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json(indent=2)


class ModelResponse(BaseModel):
    """
    模型响应包装类

    用于统一 LLM 调用的返回格式。
    """

    content: str = Field(..., description="响应内容")
    role: str = Field("assistant", description="角色")
    model: str = Field("", description="使用的模型")
    usage: Dict[str, int] = Field(default_factory=dict, description="Token 使用情况")
