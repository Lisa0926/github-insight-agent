# -*- coding: utf-8 -*-
"""
Unified Memory — Cross-layer memory data flow for GIA.

Aggregates three memory layers into a single context-aware interface:
- PersistentMemory: Long-term conversation storage (SQLite)
- ConversationManager: Short-term context compression (LLM summarization)
- FeedbackCollector: User preference learning (feedback → prompt injection)

Usage:
    from src.core.unified_memory import UnifiedMemory

    memory = UnifiedMemory(db_path="data/app.db")

    # Record an interaction (writes to all layers)
    memory.record_interaction(
        user_message="Search for React projects",
        assistant_response="Found 5 projects...",
    )

    # Get aggregated context for a new prompt
    context = memory.get_context()

    # Get feedback patterns for prompt injection
    patterns = memory.get_feedback_patterns()

    # Search across all memory layers
    results = memory.search_relevant("React")
"""

from typing import Any, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


class UnifiedMemory:
    """
    Unified memory layer that coordinates PersistentMemory, ConversationManager,
    and FeedbackCollector for cross-layer data flow.
    """

    def __init__(
        self,
        db_path: str = "data/app.db",
        conversation_max_turns: int = 3,
        feedback_collector=None,
        persistent_memory=None,
        conversation_manager=None,
    ):
        """
        Initialize unified memory.

        Any of the three components can be injected for testing.
        If not provided, they are lazily created.
        """
        self.db_path = db_path
        self._conversation_max_turns = conversation_max_turns

        # Injected or lazy-created components
        self._persistent: Any = persistent_memory
        self._conversation: Any = conversation_manager
        self._feedback: Any = feedback_collector

    @property
    def persistent(self):
        """Lazy-create PersistentMemory."""
        if self._persistent is None:
            from src.core.agentscope_persistent_memory import PersistentMemory
            self._persistent = PersistentMemory(db_path=self.db_path)
        return self._persistent

    @property
    def conversation(self):
        """Lazy-create ConversationManager."""
        if self._conversation is None:
            from src.core.conversation import ConversationManager
            self._conversation = ConversationManager(max_turns=self._conversation_max_turns)
        return self._conversation

    @property
    def feedback(self):
        """Lazy-create FeedbackCollector."""
        if self._feedback is None:
            from src.core.feedback import FeedbackCollector
            self._feedback = FeedbackCollector(db_path=self.db_path)
        return self._feedback

    def record_interaction(
        self,
        user_message: str,
        assistant_response: str,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Record an interaction across all memory layers.

        Args:
            user_message: User's input text
            assistant_response: Assistant's response text
            tool_results: Optional list of tool call results
        """
        # 1. Persistent storage
        self.persistent.add_user_message(user_message)
        self.persistent.add_assistant_message(assistant_response)

        # 2. Conversation history (for context compression)
        self.conversation.add_user_message(user_message)
        self.conversation.add_assistant_message(assistant_response)

        if tool_results:
            for tr in tool_results:
                self.conversation.add_tool_result(
                    tool_name=tr.get("tool_name", "unknown"),
                    result=tr.get("result", ""),
                )

        logger.debug(
            f"Interaction recorded across all memory layers "
            f"(persistent: {self.persistent.size()}, conversation: {self.conversation.get_turn_count()})"
        )

    def record_feedback(
        self,
        rating: str,
        reason: str = "",
        user_message: str = "",
        assistant_response: str = "",
    ) -> int:
        """
        Record user feedback.

        Args:
            rating: "good", "bad", or "neutral"
            reason: Optional reason string
            user_message: User input that generated the response
            assistant_response: Response that was rated

        Returns:
            Feedback row id
        """
        return self.feedback.record(
            rating=rating,
            reason=reason,
            user_input=user_message,
            assistant_output=assistant_response,
        )

    def get_context(
        self,
        include_feedback: bool = True,
        include_conversation_summary: bool = True,
        max_feedback_patterns: int = 5,
    ) -> Dict[str, Any]:
        """
        Get aggregated context from all memory layers.

        Returns:
            Dict with 'persistent_summary', 'conversation_context',
            'feedback_patterns', and 'stats'.
        """
        context: Dict[str, Any] = {}

        # 1. Persistent memory summary (cross-session context)
        persistent_summary = self.persistent.get_messages_summary(max_messages=5)
        if persistent_summary:
            context["persistent_summary"] = persistent_summary

        # 2. Conversation context (compressed recent history)
        if include_conversation_summary:
            conv_context = self.conversation.get_context_for_prompt()
            if conv_context:
                context["conversation_context"] = conv_context

        # 3. Feedback patterns (user preferences)
        if include_feedback:
            patterns = self.feedback.get_positive_feedback_patterns(
                limit=max_feedback_patterns
            )
            if patterns:
                context["feedback_patterns"] = patterns

        # 4. Stats
        context["stats"] = {
            "persistent_messages": self.persistent.size(),
            "conversation_turns": self.conversation.get_turn_count(),
            "feedback_stats": self.feedback.get_stats(),
        }

        return context

    def get_feedback_patterns(
        self,
        limit: int = 5,
    ) -> List[str]:
        """
        Get positive feedback patterns for prompt injection.

        Args:
            limit: Maximum number of patterns to return

        Returns:
            List of positive feedback reason strings
        """
        return self.feedback.get_positive_feedback_patterns(limit=limit)

    def get_cross_session_context(self) -> str:
        """
        Get formatted context for cross-session loading (CLI startup).

        Combines persistent summary + recent feedback patterns into a single
        string suitable for display or system prompt injection.

        Returns:
            Formatted context string
        """
        parts: List[str] = []

        # Persistent memory summary
        summary = self.persistent.get_messages_summary(max_messages=10)
        if summary:
            parts.append(f"## 上次会话摘要\n{summary}\n")

        # Feedback patterns
        patterns = self.feedback.get_positive_feedback_patterns(limit=3)
        if patterns:
            parts.append(
                "## 用户偏好\n"
                + "\n".join(f"- {p}" for p in patterns)
            )

        return "\n\n".join(parts) if parts else ""

    def search_relevant(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across all memory layers for relevant content.

        Uses simple keyword matching. For semantic search, a vector store
        would be needed (not implemented per user preference).

        Args:
            query: Search query string
            max_results: Maximum results per layer

        Returns:
            Dict with 'persistent', 'conversation', 'feedback' lists
        """
        query_lower = query.lower()

        # Search persistent memory
        persistent_results = []
        for msg in self.persistent.get_memory():
            content = str(msg.content).lower()
            if _matches_query(content, query_lower):
                persistent_results.append({
                    "role": msg.role,
                    "content": str(msg.content)[:200],
                    "source": "persistent_memory",
                })
                if len(persistent_results) >= max_results:
                    break

        # Search conversation history
        conversation_results = []
        for msg in self.conversation.get_full_history():
            content = msg.get("content", "").lower()
            if _matches_query(content, query_lower):
                conversation_results.append({
                    "role": msg.get("role", ""),
                    "content": msg.get("content", "")[:200],
                    "timestamp": msg.get("timestamp", ""),
                    "source": "conversation_history",
                })
                if len(conversation_results) >= max_results:
                    break

        # Search feedback
        feedback_results = []
        for fb in self.feedback.get_recent(limit=max_results * 2):
            content = (
                (fb.get("reason", "") or "")
                + " "
                + (fb.get("user_input", "") or "")
                + " "
                + (fb.get("assistant_output", "") or "")
            ).lower()
            if _matches_query(content, query_lower):
                feedback_results.append({
                    "rating": fb.get("rating", ""),
                    "reason": fb.get("reason", ""),
                    "source": "feedback",
                })
                if len(feedback_results) >= max_results:
                    break

        return {
            "persistent": persistent_results,
            "conversation": conversation_results,
            "feedback": feedback_results,
        }

    def clear(self) -> None:
        """Clear all memory layers."""
        self.persistent.clear()
        self.conversation.clear_history()
        logger.info("Unified memory cleared across all layers")

    def get_stats(self) -> Dict[str, Any]:
        """Get stats from all memory layers."""
        return {
            "persistent_messages": self.persistent.size(),
            "conversation_turns": self.conversation.get_turn_count(),
            "conversation_summary_length": len(self.conversation.summary),
            "feedback": self.feedback.get_stats(),
        }


def _matches_query(content: str, query: str) -> bool:
    """Check if content matches query (simple word-level matching)."""
    # Split query into words and check if any word appears in content
    words = query.split()
    return any(word in content for word in words)
