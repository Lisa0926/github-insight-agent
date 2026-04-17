# -*- coding: utf-8 -*-
"""
对话管理器

功能:
- 记录对话历史（User -> Assistant -> Tool Result -> Final Answer）
- 上下文压缩（超过阈值时自动总结为摘要）
- 支持多轮对话记忆
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    对话管理器

    负责管理多轮对话历史，支持：
    - 对话记录存储
    - 上下文压缩（防止 Token 超限）
    - 对话历史持久化（可选 JSON 文件存储）
    - 摘要生成和注入

    Attributes:
        max_turns: 最大对话轮数阈值，超过后触发压缩
        storage_path: 对话历史存储路径（可选）
        conversation_history: 对话历史列表
        summary: 对话摘要
    """

    # 默认对话轮数阈值
    DEFAULT_MAX_TURNS = 3

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        storage_path: Optional[str] = None,
        auto_save: bool = False,
    ):
        """
        初始化对话管理器

        Args:
            max_turns: 最大对话轮数阈值，超过后触发压缩
            storage_path: 对话历史 JSON 文件路径（可选，不传则不持久化）
            auto_save: 是否每次添加消息后自动保存
        """
        self.max_turns = max_turns
        self.storage_path = storage_path
        self.auto_save = auto_save

        # 对话历史：每条消息包含 role, content, timestamp, metadata
        self.conversation_history: List[Dict[str, Any]] = []

        # 对话摘要（压缩后的历史）
        self.summary: str = ""

        # 加载已有历史（如果 storage_path 存在）
        if storage_path and os.path.exists(storage_path):
            self._load_from_file()

        logger.info(
            f"ConversationManager initialized (max_turns={max_turns}, "
            f"storage={storage_path or 'memory-only'})"
        )

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加一条消息到对话历史

        Args:
            role: 角色名（user/assistant/tool）
            content: 消息内容
            metadata: 元数据（可选，如工具调用信息）
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self.conversation_history.append(message)
        logger.debug(f"Added {role} message to conversation (total: {len(self.conversation_history)})")

        # 检查是否需要压缩
        self._check_and_compress()

        # 自动保存
        if self.auto_save:
            self.save_to_file()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message("user", content)

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """添加助手消息"""
        self.add_message("assistant", content, metadata)

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """添加工具调用结果"""
        content = f"[{tool_name}] Result: {json.dumps(result) if not isinstance(result, str) else result}"
        self.add_message("tool", content, metadata={"tool_name": tool_name, "result": result})

    def get_turn_count(self) -> int:
        """
        获取对话轮数

        Returns:
            轮数（user + assistant 为一轮）
        """
        user_count = sum(1 for msg in self.conversation_history if msg["role"] == "user")
        return user_count

    def _check_and_compress(self) -> None:
        """检查对话轮数，超过阈值则压缩"""
        if self.get_turn_count() > self.max_turns:
            logger.info(f"Conversation exceeds {self.max_turns} turns, triggering compression...")
            self._compress_history()

    def _compress_history(self) -> None:
        """
        压缩对话历史

        策略：
        1. 保留最近 N 轮完整对话
        2. 将早期对话总结为摘要
        """
        # 找到最近 max_turns 轮对话的起始位置
        user_indices = [
            i for i, msg in enumerate(self.conversation_history)
            if msg["role"] == "user"
        ]

        if len(user_indices) <= self.max_turns:
            return

        # 计算需要保留的起始索引
        keep_from_index = user_indices[-self.max_turns]

        # 提取需要压缩的历史
        to_compress = self.conversation_history[:keep_from_index]

        # 生成摘要
        if to_compress:
            self.summary = self._generate_summary(to_compress)
            logger.info(f"Generated summary: {len(self.summary)} chars")

        # 保留最近的对话
        self.conversation_history = self.conversation_history[keep_from_index:]

    def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        生成对话摘要

        Args:
            messages: 需要压缩的消息列表

        Returns:
            摘要字符串
        """
        # 简单策略：提取关键信息
        # TODO: 可以调用 LLM 生成更智能的摘要

        summary_parts = []

        # 统计工具调用
        tool_calls = [
            msg["metadata"].get("tool_name")
            for msg in messages
            if msg["role"] == "tool" and msg["metadata"].get("tool_name")
        ]
        if tool_calls:
            summary_parts.append(f"调用的工具：{', '.join(set(tool_calls))}")

        # 提取用户查询主题
        user_queries = [
            msg["content"][:100]
            for msg in messages
            if msg["role"] == "user"
        ]
        if user_queries:
            summary_parts.append(f"用户查询：{' | '.join(user_queries[:3])}")

        # 提取助手的关键回复
        assistant_responses = [
            msg["content"][:200]
            for msg in messages
            if msg["role"] == "assistant"
        ]
        if assistant_responses:
            summary_parts.append(f"助手回复：{' | '.join(assistant_responses[:2])}")

        summary = "【历史对话摘要】\n" + "\n".join(summary_parts) + "\n【结束】\n"
        return summary

    def get_context_for_prompt(self) -> str:
        """
        获取用于注入 Prompt 的上下文

        Returns:
            格式化的上下文字符串（包含摘要和最近对话）
        """
        context_parts = []

        # 如果有摘要，先注入摘要
        if self.summary:
            context_parts.append(self.summary)

        # 添加最近的对话历史
        if self.conversation_history:
            recent_history = []
            for msg in self.conversation_history:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    recent_history.append(f"用户：{content}")
                elif role == "assistant":
                    recent_history.append(f"助手：{content}")
                elif role == "tool":
                    tool_name = msg["metadata"].get("tool_name", "tool")
                    recent_history.append(f"[{tool_name}] 结果：{content[:200]}")

            context_parts.append("\n".join(recent_history))

        return "\n\n".join(context_parts) if context_parts else ""

    def get_full_history(self) -> List[Dict[str, Any]]:
        """获取完整对话历史"""
        return self.conversation_history.copy()

    def clear_history(self) -> None:
        """清空对话历史"""
        self.conversation_history.clear()
        self.summary = ""
        logger.info("Conversation history cleared")

        if self.storage_path and self.auto_save:
            self.save_to_file()

    def save_to_file(self) -> bool:
        """
        保存对话历史到 JSON 文件

        Returns:
            是否成功
        """
        if not self.storage_path:
            logger.warning("No storage path configured, cannot save")
            return False

        try:
            data = {
                "summary": self.summary,
                "history": self.conversation_history,
                "last_updated": datetime.now().isoformat(),
            }

            # 确保目录存在
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Conversation saved to: {self.storage_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False

    def _load_from_file(self) -> None:
        """从 JSON 文件加载对话历史"""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.summary = data.get("summary", "")
            self.conversation_history = data.get("history", [])

            logger.info(f"Conversation loaded from: {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")

    def export_markdown(self, output_path: str) -> bool:
        """
        导出对话为 Markdown 格式

        Args:
            output_path: 输出文件路径

        Returns:
            是否成功
        """
        try:
            lines = [
                "# 对话记录",
                f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"对话轮数：{self.get_turn_count()}",
                "",
            ]

            if self.summary:
                lines.extend(["## 对话摘要", "", self.summary, ""])

            lines.extend(["## 详细对话", ""])

            for msg in self.conversation_history:
                role = msg["role"].upper()
                content = msg["content"]
                timestamp = msg.get("timestamp", "")
                lines.extend([
                    f"### [{role}] - {timestamp}",
                    "",
                    content,
                    "",
                ])

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            logger.info(f"Conversation exported to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export conversation: {e}")
            return False
