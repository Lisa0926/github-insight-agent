# -*- coding: utf-8 -*-
"""
AgentScope Memory wrapper layer

Features:
- Short-term memory based on AgentScope InMemoryMemory
- Supports message marks for compression and filtering
- Provides synchronous interface (handles async internally)
- Compatible with existing ConversationManager API
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
    AgentScope Memory wrapper layer

    Provides synchronous interface to use AgentScope's InMemoryMemory,
    supporting message marks, memory compression, and more.

    Attributes:
        memory: AgentScope InMemoryMemory instance
        max_messages: Maximum message count threshold, triggers compression when exceeded
        compressed_summary: Compressed summary
    """

    DEFAULT_MAX_MESSAGES = 10

    def __init__(
        self,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ):
        """
        Initialize AgentScope Memory

        Args:
            max_messages: Maximum message count threshold
        """
        self.memory = InMemoryMemory()
        self.max_messages = max_messages
        self.compressed_summary: str = ""

        logger.info(f"AgentScopeMemory initialized (max_messages={max_messages})")

    def _run_async(self, coro):
        """Run an async coroutine"""
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
        Add a message to memory

        Args:
            role: Role (user/assistant/tool/system)
            content: Message content
            name: Sender name
            mark: Message mark (for filtering and compression)
            metadata: Metadata
        """
        msg = Msg(
            name=name,
            content=content,
            role=role,
            metadata=metadata or {},
        )

        self._run_async(self.memory.add(msg))

        # If mark is provided, update message marks
        if mark:
            self._run_async(self.memory.update_messages_mark(mark))

        logger.debug(f"Added {role} message to memory (total: {self.size()})")

        # Check if compression is needed
        self._check_and_compress()

    def add_user_message(self, content: str) -> None:
        """Add a user message"""
        self.add_message("user", content, name="user")

    def add_assistant_message(
        self,
        content: str,
        name: str = "assistant",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an assistant message"""
        self.add_message("assistant", content, name=name, metadata=metadata)

    def add_tool_result(
        self,
        tool_name: str,
        result: Any,
        name: str = "assistant",
    ) -> None:
        """Add a tool call result"""
        content = f"[{tool_name}] Result: {result if isinstance(result, str) else str(result)}"
        self.add_message(
            "assistant",
            content,
            name=name,
            mark="tool_result",
            metadata={"tool_name": tool_name, "result": result},
        )

    def size(self) -> int:
        """Get message count in memory"""
        return self._run_async(self.memory.size())

    def get_memory(self) -> List[Msg]:
        """Get all memory messages"""
        return self._run_async(self.memory.get_memory())

    def get_messages_for_prompt(self) -> List[Dict[str, Any]]:
        """
        Get message list for building the prompt

        Returns:
            List of message dictionaries with fields role, content, name, etc.
        """
        messages = self.get_memory()
        result = []

        # Add summary first (if any)
        if self.compressed_summary:
            result.append({
                "role": "system",
                "content": self.compressed_summary,
                "name": "system",
            })

        # Add all messages
        for msg in messages:
            result.append({
                "role": msg.role,
                "content": msg.content,
                "name": msg.name,
                "metadata": getattr(msg, "metadata", {}),
            })

        return result

    def _check_and_compress(self) -> None:
        """Check message count, compress if threshold exceeded"""
        if self.size() > self.max_messages:
            logger.info(f"Memory exceeds {self.max_messages} messages, triggering compression...")
            self._compress_memory()

    def _compress_memory(self) -> None:
        """
        Compress memory

        Strategy:
        1. Keep the most recent N messages
        2. Summarize earlier messages into a summary
        """
        messages = self.get_memory()

        if len(messages) <= self.max_messages:
            return

        # Extract messages to compress
        to_compress = messages[:len(messages) - self.max_messages + 2]  # Keep the most recent 2

        # Generate summary
        if to_compress:
            self.compressed_summary = self._generate_summary(to_compress)
            logger.info(f"Generated memory summary: {len(self.compressed_summary)} chars")

            # Clear old messages and keep the recent ones
            self._run_async(self.memory.clear())

            # Re-add summary and recent messages
            recent_messages = messages[-(self.max_messages - 2):]
            for msg in recent_messages:
                self._run_async(self.memory.add(msg))

    def _generate_summary(self, messages: List[Msg]) -> str:
        """
        Generate a memory summary

        Args:
            messages: List of messages to compress

        Returns:
            Summary string
        """
        summary_parts = ["【Historical Conversation Summary】"]

        # Count tool calls
        tool_calls = [
            msg.metadata.get("tool_name")
            for msg in messages
            if msg.role == "tool" and msg.metadata.get("tool_name")
        ]
        if tool_calls:
            summary_parts.append(f"Tools used: {', '.join(set(tool_calls))}")

        # Extract user queries
        user_queries = [
            msg.content[:100]
            for msg in messages
            if msg.role == "user"
        ]
        if user_queries:
            summary_parts.append(f"User queries: {' | '.join(user_queries[:3])}")

        # Extract assistant responses
        assistant_responses = [
            msg.content[:200]
            for msg in messages
            if msg.role == "assistant"
        ]
        if assistant_responses:
            summary_parts.append(f"Assistant responses: {' | '.join(assistant_responses[:2])}")

        summary_parts.append("【End】")
        return "\n".join(summary_parts)

    def clear(self) -> None:
        """Clear memory"""
        self._run_async(self.memory.clear())
        self.compressed_summary = ""
        logger.info("AgentScopeMemory cleared")

    def delete_message(self, msg_id: str) -> None:
        """Delete message with specified ID"""
        self._run_async(self.memory.delete(msg_id))

    def delete_by_mark(self, mark: str) -> None:
        """Delete all messages with specified mark"""
        self._run_async(self.memory.delete_by_mark(mark))

    def get_state_dict(self) -> Dict[str, Any]:
        """Get memory state dictionary (for serialization)"""
        return self._run_async(self.memory.state_dict())

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """Load memory from state dictionary"""
        self._run_async(self.memory.load_state_dict(state_dict))

    def export_to_conversation_manager(self) -> List[Dict[str, Any]]:
        """
        Export in ConversationManager-compatible format

        Returns:
            Conversation history list
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
