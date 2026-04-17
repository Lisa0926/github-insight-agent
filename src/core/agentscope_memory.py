# -*- coding: utf-8 -*-
"""
AgentScope Memory 封装层

功能:
- 基于 AgentScope InMemoryMemory 实现短期记忆
- 支持消息标记 (marks) 用于压缩和过滤
- 提供同步接口（内部处理异步）
- 与现有 ConversationManager API 兼容
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from src.core.logger import get_logger

logger = get_logger(__name__)


class AgentScopeMemory:
    """
    AgentScope Memory 封装层

    提供同步接口来使用 AgentScope 的 InMemoryMemory，
    支持消息标记、记忆压缩等功能。

    Attributes:
        memory: AgentScope InMemoryMemory 实例
        max_messages: 最大消息数量阈值，超过后触发压缩
        compressed_summary: 压缩后的摘要
    """

    DEFAULT_MAX_MESSAGES = 10

    def __init__(
        self,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ):
        """
        初始化 AgentScope Memory

        Args:
            max_messages: 最大消息数量阈值
        """
        self.memory = InMemoryMemory()
        self.max_messages = max_messages
        self.compressed_summary: str = ""

        logger.info(f"AgentScopeMemory initialized (max_messages={max_messages})")

    def _run_async(self, coro):
        """运行异步协程"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def add_message(
        self,
        role: str,
        content: str,
        name: str = "user",
        mark: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        添加一条消息到记忆

        Args:
            role: 角色 (user/assistant/tool/system)
            content: 消息内容
            name: 发送者名称
            mark: 消息标记（用于过滤和压缩）
            metadata: 元数据
        """
        msg = Msg(
            name=name,
            content=content,
            role=role,
            metadata=metadata or {},
        )

        self._run_async(self.memory.add(msg))

        # 如果提供了 mark，更新消息标记
        if mark:
            self._run_async(self.memory.update_messages_mark(mark))

        logger.debug(f"Added {role} message to memory (total: {self.size()})")

        # 检查是否需要压缩
        self._check_and_compress()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message("user", content, name="user")

    def add_assistant_message(
        self,
        content: str,
        name: str = "assistant",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加助手消息"""
        self.add_message("assistant", content, name=name, metadata=metadata)

    def add_tool_result(
        self,
        tool_name: str,
        result: Any,
        name: str = "assistant",
    ) -> None:
        """添加工具调用结果"""
        content = f"[{tool_name}] Result: {result if isinstance(result, str) else str(result)}"
        self.add_message(
            "assistant",
            content,
            name=name,
            mark="tool_result",
            metadata={"tool_name": tool_name, "result": result},
        )

    def size(self) -> int:
        """获取记忆中的消息数量"""
        return self._run_async(self.memory.size())

    def get_memory(self) -> List[Msg]:
        """获取所有记忆消息"""
        return self._run_async(self.memory.get_memory())

    def get_messages_for_prompt(self) -> List[Dict[str, Any]]:
        """
        获取用于构建 Prompt 的消息列表

        Returns:
            消息字典列表，包含 role, content, name 等字段
        """
        messages = self.get_memory()
        result = []

        # 先添加摘要（如果有）
        if self.compressed_summary:
            result.append({
                "role": "system",
                "content": self.compressed_summary,
                "name": "system",
            })

        # 添加所有消息
        for msg in messages:
            result.append({
                "role": msg.role,
                "content": msg.content,
                "name": msg.name,
                "metadata": getattr(msg, "metadata", {}),
            })

        return result

    def _check_and_compress(self) -> None:
        """检查消息数量，超过阈值则压缩"""
        if self.size() > self.max_messages:
            logger.info(f"Memory exceeds {self.max_messages} messages, triggering compression...")
            self._compress_memory()

    def _compress_memory(self) -> None:
        """
        压缩记忆

        策略：
        1. 保留最近的 N 条消息
        2. 将早期消息总结为摘要
        """
        messages = self.get_memory()

        if len(messages) <= self.max_messages:
            return

        # 提取需要压缩的消息
        to_compress = messages[:len(messages) - self.max_messages + 2]  # 保留最近 2 条

        # 生成摘要
        if to_compress:
            self.compressed_summary = self._generate_summary(to_compress)
            logger.info(f"Generated memory summary: {len(self.compressed_summary)} chars")

            # 清除旧消息并保留最近的
            self._run_async(self.memory.clear())

            # 重新添加摘要和最近的消息
            recent_messages = messages[-(self.max_messages - 2):]
            for msg in recent_messages:
                self._run_async(self.memory.add(msg))

    def _generate_summary(self, messages: List[Msg]) -> str:
        """
        生成记忆摘要

        Args:
            messages: 需要压缩的消息列表

        Returns:
            摘要字符串
        """
        summary_parts = ["【历史对话摘要】"]

        # 统计工具调用
        tool_calls = [
            msg.metadata.get("tool_name")
            for msg in messages
            if msg.role == "tool" and msg.metadata.get("tool_name")
        ]
        if tool_calls:
            summary_parts.append(f"调用的工具：{', '.join(set(tool_calls))}")

        # 提取用户查询
        user_queries = [
            msg.content[:100]
            for msg in messages
            if msg.role == "user"
        ]
        if user_queries:
            summary_parts.append(f"用户查询：{' | '.join(user_queries[:3])}")

        # 提取助手回复
        assistant_responses = [
            msg.content[:200]
            for msg in messages
            if msg.role == "assistant"
        ]
        if assistant_responses:
            summary_parts.append(f"助手回复：{' | '.join(assistant_responses[:2])}")

        summary_parts.append("【结束】")
        return "\n".join(summary_parts)

    def clear(self) -> None:
        """清空记忆"""
        self._run_async(self.memory.clear())
        self.compressed_summary = ""
        logger.info("AgentScopeMemory cleared")

    def delete_message(self, msg_id: str) -> None:
        """删除指定 ID 的消息"""
        self._run_async(self.memory.delete(msg_id))

    def delete_by_mark(self, mark: str) -> None:
        """删除指定标记的所有消息"""
        self._run_async(self.memory.delete_by_mark(mark))

    def get_state_dict(self) -> Dict[str, Any]:
        """获取记忆状态字典（用于序列化）"""
        return self._run_async(self.memory.state_dict())

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """从状态字典加载记忆"""
        self._run_async(self.memory.load_state_dict(state_dict))

    def export_to_conversation_manager(self) -> List[Dict[str, Any]]:
        """
        导出为 ConversationManager 兼容的格式

        Returns:
            对话历史列表
        """
        messages = self.get_memory()
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "name": msg.name,
                "timestamp": datetime.now().isoformat(),
                "metadata": getattr(msg, "metadata", {}),
            }
            for msg in messages
        ]
