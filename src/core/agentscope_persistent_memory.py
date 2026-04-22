# -*- coding: utf-8 -*-
"""
AgentScope 持久化记忆模块

功能:
- 基于 AgentScope AsyncSQLAlchemyMemory 实现本地持久化
- 数据存储于 SQLite 文件，完全本地化，不上传
- 与现有 AgentScope Memory API 兼容
- 提供同步接口（内部处理异步）
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
    持久化记忆类

    基于 AgentScope AsyncSQLAlchemyMemory，将对话历史持久化到本地 SQLite 数据库。

    Attributes:
        memory: AgentScope AsyncSQLAlchemyMemory 实例
        db_path: SQLite 数据库文件路径
    """

    DEFAULT_MAX_MESSAGES = 100  # 持久化存储可以保留更多消息

    def __init__(
        self,
        db_path: str = "data/app.db",
        table_name: str = "agent_messages",
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ):
        """
        初始化持久化记忆

        Args:
            db_path: SQLite 数据库文件路径（自动创建目录）
            table_name: 存储消息的表名
            max_messages: 最大消息数量，超过后触发压缩
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建 SQLAlchemy 异步引擎（SQLite）
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            echo=False,
        )

        # 创建异步 Session
        self.async_session = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # 初始化 AgentScope AsyncSQLAlchemyMemory
        self.memory = AsyncSQLAlchemyMemory(
            engine_or_session=self.engine,
        )

        # 初始化数据库表
        self._init_db()

        self.max_messages = max_messages
        self.compressed_summary: str = ""

        logger.info(f"PersistentMemory initialized (db={self.db_path}, max_messages={max_messages})")

    def _init_db(self):
        """初始化数据库表"""
        async def _create_tables():
            # 使用 AsyncSQLAlchemyMemory 内部的表模型
            from agentscope.memory import AsyncSQLAlchemyMemory

            # 创建所有表
            async with self.engine.begin() as conn:
                await conn.run_sync(AsyncSQLAlchemyMemory.MessageTable.metadata.create_all)

        self._run_async(_create_tables())
        logger.debug("Database tables created successfully")

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.engine.dispose()
        logger.debug("PersistentMemory database connection closed")

    def __enter__(self) -> "PersistentMemory":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self._run_async(self.close())

    def _run_async(self, coro):
        """运行异步协程"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # Already in an async context - use nest_asyncio or run in new thread
            import concurrent.futures
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
        添加消息到持久化存储

        Args:
            role: 角色 (user/assistant/system)
            content: 消息内容
            name: 发送者名称
            mark: 消息标记（用于过滤）
            metadata: 元数据
        """
        msg = Msg(
            name=name,
            content=content,
            role=role,
            metadata=metadata or {},
        )

        self._run_async(self.memory.add(msg, mark=mark))
        logger.debug(f"Added {role} message to persistent storage (total: {self.size()})")

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
        """获取消息数量"""
        return self._run_async(self.memory.size())

    def get_memory(self) -> List[Msg]:
        """获取所有消息"""
        return self._run_async(self.memory.get_memory())

    def get_messages_for_prompt(self) -> List[Dict[str, Any]]:
        """
        获取用于构建 Prompt 的消息列表

        Returns:
            消息字典列表
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
            logger.info(f"PersistentMemory exceeds {self.max_messages} messages, triggering compression...")
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
        to_compress = messages[:len(messages) - self.max_messages + 2]

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
            if msg.role == "assistant" and msg.metadata.get("tool_name")
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
        logger.info("PersistentMemory cleared")

    def get_state_dict(self) -> Dict[str, Any]:
        """获取记忆状态字典"""
        return self._run_async(self.memory.state_dict())

    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """从状态字典加载记忆"""
        self._run_async(self.memory.load_state_dict(state_dict))


# 便捷函数：获取单例的 PersistentMemory
_persistent_memory_cache: Optional[PersistentMemory] = None


def get_persistent_memory(
    db_path: str = "data/app.db",
    table_name: str = "agent_messages",
    force_new: bool = False,
) -> PersistentMemory:
    """
    获取 PersistentMemory 实例（单例模式）

    Args:
        db_path: SQLite 数据库文件路径
        table_name: 表名
        force_new: 是否强制创建新实例

    Returns:
        PersistentMemory 实例
    """
    global _persistent_memory_cache

    if force_new or _persistent_memory_cache is None:
        _persistent_memory_cache = PersistentMemory(
            db_path=db_path,
            table_name=table_name,
        )

    return _persistent_memory_cache


class PersistentMemoryContext:
    """
    PersistentMemory 上下文管理器

    使用示例:
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
        # 清理单例缓存，允许下次创建新实例
        global _persistent_memory_cache
        _persistent_memory_cache = None
