# -*- coding: utf-8 -*-
"""
Conversation manager

Features:
- Record conversation history (User -> Assistant -> Tool Result -> Final Answer)
- Context compression (auto-summarize when threshold exceeded)
- Support multi-turn conversation memory
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class ConversationManager:
    """
    Conversation manager

    Responsible for managing multi-turn conversation history, supports:
    - Conversation record storage
    - Context compression (prevents token overflow)
    - Conversation history persistence (optional JSON file storage)
    - Summary generation and injection

    Attributes:
        max_turns: Maximum conversation turn threshold, triggers compression when exceeded
        storage_path: Conversation history storage path (optional)
        conversation_history: Conversation history list
        summary: Conversation summary
    """

    # Default conversation turn threshold
    DEFAULT_MAX_TURNS = 3

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        storage_path: Optional[str] = None,
        auto_save: bool = False,
    ):
        """
        Initialize conversation manager

        Args:
            max_turns: Maximum conversation turn threshold, triggers compression when exceeded
            storage_path: Conversation history JSON file path (optional, no persistence if not provided)
            auto_save: Whether to auto-save after each message is added
        """
        self.max_turns = max_turns
        self.storage_path = storage_path
        self.auto_save = auto_save

        # Conversation history: each message contains role, content, timestamp, metadata
        self.conversation_history: List[Dict[str, Any]] = []

        # Conversation summary (compressed history)
        self.summary: str = ""

        # Load existing history (if storage_path exists)
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
        Add a message to conversation history

        Args:
            role: Role name (user/assistant/tool)
            content: Message content
            metadata: Metadata (optional, e.g. tool call info)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        self.conversation_history.append(message)
        logger.debug(f"Added {role} message to conversation (total: {len(self.conversation_history)})")

        # Check if compression is needed
        self._check_and_compress()

        # Auto-save
        if self.auto_save:
            self.save_to_file()

    def add_user_message(self, content: str) -> None:
        """Add a user message"""
        self.add_message("user", content)

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add an assistant message"""
        self.add_message("assistant", content, metadata)

    def add_tool_result(self, tool_name: str, result: Any) -> None:
        """Add a tool call result"""
        content = f"[{tool_name}] Result: {json.dumps(result) if not isinstance(result, str) else result}"
        self.add_message("tool", content, metadata={"tool_name": tool_name, "result": result})

    def get_turn_count(self) -> int:
        """
        Get conversation turn count

        Returns:
            Turn count (user + assistant = one turn)
        """
        user_count = sum(1 for msg in self.conversation_history if msg["role"] == "user")
        return user_count

    def _check_and_compress(self) -> None:
        """Check conversation turn count, compress if threshold exceeded"""
        if self.get_turn_count() > self.max_turns:
            logger.info(f"Conversation exceeds {self.max_turns} turns, triggering compression...")
            self._compress_history()

    def _compress_history(self) -> None:
        """
        Compress conversation history

        Strategy:
        1. Keep the most recent N complete turns
        2. Summarize earlier turns into a summary
        """
        # Find the starting index of the most recent max_turns turns
        user_indices = [
            i for i, msg in enumerate(self.conversation_history)
            if msg["role"] == "user"
        ]

        if len(user_indices) <= self.max_turns:
            return

        # Calculate the starting index to keep
        keep_from_index = user_indices[-self.max_turns]

        # Extract history to compress
        to_compress = self.conversation_history[:keep_from_index]

        # Generate summary
        if to_compress:
            self.summary = self._generate_summary(to_compress)
            logger.info(f"Generated summary: {len(self.summary)} chars")

        # Keep the recent conversation
        self.conversation_history = self.conversation_history[keep_from_index:]

    def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a conversation summary

        Args:
            messages: List of messages to compress

        Returns:
            Summary string
        """
        # Simple strategy: extract key information
        # TODO: Can call LLM for smarter summary generation

        summary_parts = []

        # Count tool calls
        tool_calls = [
            msg["metadata"].get("tool_name")
            for msg in messages
            if msg["role"] == "tool" and msg["metadata"].get("tool_name")
        ]
        if tool_calls:
            summary_parts.append(f"Tools used: {', '.join(set(tool_calls))}")

        # Extract user query topics
        user_queries = [
            msg["content"][:100]
            for msg in messages
            if msg["role"] == "user"
        ]
        if user_queries:
            summary_parts.append(f"User queries: {' | '.join(user_queries[:3])}")

        # Extract key assistant responses
        assistant_responses = [
            msg["content"][:200]
            for msg in messages
            if msg["role"] == "assistant"
        ]
        if assistant_responses:
            summary_parts.append(f"Assistant responses: {' | '.join(assistant_responses[:2])}")

        summary = "【Historical Conversation Summary】\n" + "\n".join(summary_parts) + "\n【End】\n"
        return summary

    def get_context_for_prompt(self) -> str:
        """
        Get context for prompt injection

        Returns:
            Formatted context string (contains summary and recent conversation)
        """
        context_parts = []

        # If there is a summary, inject it first
        if self.summary:
            context_parts.append(self.summary)

        # Add recent conversation history
        if self.conversation_history:
            recent_history = []
            for msg in self.conversation_history:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    recent_history.append(f"User: {content}")
                elif role == "assistant":
                    recent_history.append(f"Assistant: {content}")
                elif role == "tool":
                    tool_name = msg["metadata"].get("tool_name", "tool")
                    recent_history.append(f"[{tool_name}] Result: {content[:200]}")

            context_parts.append("\n".join(recent_history))

        return "\n\n".join(context_parts) if context_parts else ""

    def get_full_history(self) -> List[Dict[str, Any]]:
        """Get full conversation history"""
        return self.conversation_history.copy()

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history.clear()
        self.summary = ""
        logger.info("Conversation history cleared")

        if self.storage_path and self.auto_save:
            self.save_to_file()

    def save_to_file(self) -> bool:
        """
        Save conversation history to JSON file

        Returns:
            Whether successful
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

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Conversation saved to: {self.storage_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False

    def _load_from_file(self) -> None:
        """Load conversation history from JSON file"""
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
        Export conversation as Markdown format

        Args:
            output_path: Output file path

        Returns:
            Whether successful
        """
        try:
            lines = [
                "# Conversation Record",
                f"\nGenerated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Conversation turns: {self.get_turn_count()}",
                "",
            ]

            if self.summary:
                lines.extend(["## Conversation Summary", "", self.summary, ""])

            lines.extend(["## Detailed Conversation", ""])

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
