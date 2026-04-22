# -*- coding: utf-8 -*-
"""
AgentScope Studio 配置共享模块

功能:
- 提取 ResearcherAgent 和 AnalystAgent 中重复的 Studio 配置逻辑
- 提供统一的 Studio 消息转发接口
- 支持 run 注册和消息推送

使用示例:
    from src.core.studio_helper import StudioHelper

    helper = StudioHelper(studio_url, run_id)
    helper.register_run()
    helper.forward_message("agent_name", "message content", "assistant")
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class StudioHelper:
    """
    AgentScope Studio 配置助手

    提供 Studio 相关的公共功能:
    - Run 注册
    - 消息转发

    Attributes:
        studio_url: Studio 服务器 URL
        run_id: 运行 ID
    """

    def __init__(self, studio_url: Optional[str] = None, run_id: Optional[str] = None):
        """
        初始化 Studio 助手

        Args:
            studio_url: Studio 服务器 URL
            run_id: 运行 ID
        """
        self.studio_url = studio_url
        self.run_id = run_id

    def register_run(
        self,
        project: str = "GitHub Insight Agent",
        name: Optional[str] = None,
        status: str = "running",
    ) -> bool:
        """
        注册 run 到 Studio

        Args:
            project: 项目名称
            name: run 名称（默认为 run_id）
            status: run 状态

        Returns:
            注册是否成功
        """
        if not self.studio_url or not self.run_id:
            logger.debug("Studio not configured, skipping run registration")
            return False

        try:
            import requests

            requests.post(
                f"{self.studio_url}/trpc/registerRun",
                json={
                    "id": self.run_id,
                    "project": project,
                    "name": name or self.run_id,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "pid": os.getpid(),
                    "status": status,
                    "run_dir": "",
                },
                timeout=5,
            )
            logger.debug(f"Registered run {self.run_id} to Studio at {self.studio_url}")
            return True
        except Exception as e:
            logger.debug(f"Failed to register run to Studio: {e}")
            return False

    def forward_message(
        self,
        name: str,
        content: str,
        role: str,
        reply_id: Optional[str] = None,
    ) -> bool:
        """
        转发消息到 Studio

        Args:
            name: 发送者名称
            content: 消息内容
            role: 角色 (user/assistant/system/tool)
            reply_id: 回复 ID（默认为 name）

        Returns:
            转发是否成功
        """
        if not self.studio_url or not self.run_id:
            return False

        try:
            import requests

            requests.post(
                f"{self.studio_url}/trpc/pushMessage",
                json={
                    "runId": self.run_id,
                    "replyId": reply_id or name,
                    "replyName": name,
                    "replyRole": role,
                    "msg": {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "content": content,
                        "role": role,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    },
                },
                timeout=5,
            )
            logger.debug(f"Forwarded message to Studio: {name} ({role})")
            return True
        except Exception as e:
            logger.debug(f"Failed to forward message to Studio: {e}")
            return False


# 全局 Studio 配置（用于兼容旧的 API）
_studio_url: Optional[str] = None
_run_id: Optional[str] = None
_studio_helper: Optional[StudioHelper] = None


def set_global_studio_config(studio_url: Optional[str], run_id: Optional[str]) -> None:
    """
    设置全局 Studio 配置（兼容旧 API）

    Args:
        studio_url: Studio 服务器 URL
        run_id: 运行 ID
    """
    global _studio_url, _run_id, _studio_helper
    _studio_url = studio_url
    _run_id = run_id
    _studio_helper = StudioHelper(studio_url, run_id)

    # 自动注册 run
    if studio_url and run_id:
        _studio_helper.register_run()


def forward_to_studio(name: str, content: str, role: str) -> None:
    """
    转发消息到 Studio（兼容旧 API）

    Args:
        name: 发送者名称
        content: 消息内容
        role: 角色
    """
    if _studio_helper:
        _studio_helper.forward_message(name, content, role)


def get_studio_helper() -> Optional[StudioHelper]:
    """
    获取全局 Studio 助手实例

    Returns:
        StudioHelper 实例或 None
    """
    return _studio_helper
