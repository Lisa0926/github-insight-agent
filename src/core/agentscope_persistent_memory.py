# -*- coding: utf-8 -*-
"""
AgentScope persistent memory module

Features:
- Local persistence based on AgentScope AsyncSQLAlchemyMemory
- Data stored in SQLite file, fully local, no uploads
- Compatible with existing AgentScope Memory API
- Provides synchronous interface (handles async internally)
"""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.message import Msg

from src.core.logger import get_logger

logger = get_logger(__name__)


class PersistentMemory:
    """
    Persistent memory class

    Based on AgentScope AsyncSQLAlchemyMemory, persists conversation history to a local SQLite database.

    Attributes:
        memory: AgentScope AsyncSQLAlchemyMemory instance
        db_path: SQLite database file path
    """

    DEFAULT_MAX_MESSAGES = 100  # Persistent storage can keep more messages

    def __init__(
        self,
        db_path: str = "data/app.db",
        table_name: str = "agent_messages",
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ):
        """
        Initialize persistent memory

        Args:
            db_path: SQLite database file path (directory auto-created)
            table_name: Table name for storing messages
            max_messages: Maximum message count, triggers compression when exceeded
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create SQLAlchemy async engine (SQLite)
        # pool_pre_ping ensures connections are validated before use
        # pool_reset_on_return ensures connections are properly returned to pool
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
            pool_pre_ping=True,
        )

        # Create async Session
        self.async_session = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Initialize AgentScope AsyncSQLAlchemyMemory
        self.memory = AsyncSQLAlchemyMemory(
            engine_or_session=self.engine,
        )

        # Initialize database tables
        self._init_db()

        self.max_messages = max_messages
        self.compressed_summary: str = ""

        logger.info(f"PersistentMemory initialized (db={self.db_path}, max_messages={max_messages})")

    def _init_db(self):
        """Initialize database tables"""
        async def _create_tables():
            # Use internal table model from AsyncSQLAlchemyMemory
            from agentscope.memory import AsyncSQLAlchemyMemory

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(AsyncSQLAlchemyMemory.MessageTable.metadata.create_all)

        self._run_async(_create_tables())
        logger.debug("Database tables created successfully")

    async def close(self) -> None:
        """Close database connection"""
        # First ensure the async_session factory is disposed
        if hasattr(self, 'async_session') and self.async_session:
            # Close any lingering sessions
            try:
                async with self.engine.begin():
                    pass  # Ensure all connections are returned
            except Exception:
                pass  # Ignore errors during cleanup
        # Dispose the engine - this closes all pooled connections
        await self.engine.dispose()
        logger.debug("PersistentMemory database connection closed")

    def __del__(self) -> None:
        """Ensure connections are properly cleaned up during GC"""
        try:
            if hasattr(self, 'engine') and self.engine:
                self._run_async(self.close())
        except Exception:
            pass  # During GC, cleanup may fail — suppress errors

    def __enter__(self) -> "PersistentMemory":
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit — close connection"""
        self._run_async(self.close())

    def _run_async(self, coro):
        """Run an async coroutine"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context - use nest_asyncio or run in new thread
            import threading
            result = None
            exception = None

            def _run_in_thread():
                nonlocal result, exception
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                except Exception as e:
                    exception = e
                finally:
                    new_loop.close()

            thread = threading.Thread(target=_run_in_thread)
            thread.start()
            thread.join()
            if exception:
                raise exception
            return result
        else:
            if loop is None:
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
        Add a message to persistent storage

        Args:
            role: Role (user/assistant/system)
            content: Message content
            name: Sender name
            mark: Message mark (for filtering)
            metadata: Metadata
        """
        msg = Msg(
            name=name,
            content=content,
            role=role,
            metadata=metadata or {},
        )

        self._run_async(self.memory.add(msg, mark=mark))
        logger.debug(f"Added {role} message to persistent storage (total: {self.size()})")

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
        """Get message count"""
        return self._run_async(self.memory.size())

    def get_memory(self) -> List[Msg]:
        """Get all messages"""
        return self._run_async(self.memory.get_memory())

    def get_messages_for_prompt(self) -> List[Dict[str, Any]]:
        """
        Get message list for building the prompt

        Returns:
            List of message dictionaries
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
            logger.info(f"PersistentMemory exceeds {self.max_messages} messages, triggering compression...")
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
        to_compress = messages[:len(messages) - self.max_messages + 2]

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
            if msg.role == "assistant" and msg.metadata.get("tool_name")
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
        logger.info("PersistentMemory cleared")

    def get_state_dict(self) -> Dict[str, Any]:
        """Get memory state dictionary"""
        return self._run_async(self.memory.state_dict())

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """Load memory from state dictionary"""
        self._run_async(self.memory.load_state_dict(state_dict))


# Convenience function: get singleton PersistentMemory
_persistent_memory_cache: Dict[str, PersistentMemory] = {}


def get_persistent_memory(
    db_path: str = "data/app.db",
    table_name: str = "agent_messages",
    force_new: bool = False,
) -> PersistentMemory:
    """
    Get a PersistentMemory instance (singleton per db_path)

    Args:
        db_path: SQLite database file path
        table_name: Table name
        force_new: Whether to force creation of a new instance

    Returns:
        PersistentMemory instance
    """
    global _persistent_memory_cache

    cache_key = db_path

    if force_new or cache_key not in _persistent_memory_cache:
        _persistent_memory_cache[cache_key] = PersistentMemory(
            db_path=db_path,
            table_name=table_name,
        )

    return _persistent_memory_cache[cache_key]


class PersistentMemoryContext:
    """
    PersistentMemory context manager

    Usage example:
        with PersistentMemoryContext(db_path="data/app.db") as pm:
            pm.add_user_message("Hello")
    """

    def __init__(self, db_path: str = "data/app.db", **kwargs):
        self.db_path = db_path
        self.kwargs = kwargs
        self.pm: Optional[PersistentMemory] = None

    def __enter__(self) -> PersistentMemory:
        self.pm = get_persistent_memory(db_path=self.db_path, **self.kwargs)
        return self.pm

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Clear singleton cache to allow new instance on next use
        global _persistent_memory_cache
        _persistent_memory_cache = {}
