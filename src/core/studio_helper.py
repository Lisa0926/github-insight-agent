# -*- coding: utf-8 -*-
"""
AgentScope Studio configuration sharing module

Features:
- Extract repeated Studio configuration logic from ResearcherAgent and AnalystAgent
- Provide unified Studio message forwarding interface
- Support run registration and message push

Usage example:
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
    AgentScope Studio configuration helper

    Provides common Studio-related features:
    - Run registration
    - Message forwarding

    Attributes:
        studio_url: Studio server URL
        run_id: Run ID
    """

    def __init__(self, studio_url: Optional[str] = None, run_id: Optional[str] = None):
        """
        Initialize Studio helper

        Args:
            studio_url: Studio server URL
            run_id: Run ID
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
        Register run to Studio

        Args:
            project: Project name
            name: Run name (defaults to run_id)
            status: Run status

        Returns:
            Whether registration was successful
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
        Forward message to Studio

        Args:
            name: Sender name
            content: Message content
            role: Role (user/assistant/system/tool)
            reply_id: Reply ID (defaults to name)

        Returns:
            Whether forwarding was successful
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


# Global Studio configuration (for backward compatibility with old API)
_studio_url: Optional[str] = None
_run_id: Optional[str] = None
_studio_helper: Optional[StudioHelper] = None


def set_global_studio_config(studio_url: Optional[str], run_id: Optional[str]) -> None:
    """
    Set global Studio configuration (backward compatible with old API)

    Args:
        studio_url: Studio server URL
        run_id: Run ID
    """
    global _studio_url, _run_id, _studio_helper
    _studio_url = studio_url
    _run_id = run_id
    _studio_helper = StudioHelper(studio_url, run_id)

    # Auto-register run
    if studio_url and run_id:
        _studio_helper.register_run()


def forward_to_studio(name: str, content: str, role: str) -> None:
    """
    Forward message to Studio (backward compatible with old API)

    Args:
        name: Sender name
        content: Message content
        role: Role
    """
    if _studio_helper:
        _studio_helper.forward_message(name, content, role)


def get_studio_helper() -> Optional[StudioHelper]:
    """
    Get global Studio helper instance

    Returns:
        StudioHelper instance or None
    """
    return _studio_helper
