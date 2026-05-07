# -*- coding: utf-8 -*-
"""Tests for LLM-based conversation summarization (compression)."""

import asyncio

from src.core.conversation import ConversationManager
from src.core.agentscope_memory import AgentScopeMemory


class TestConversationManagerLLMSummary:
    """Test ConversationManager LLM summarization with fallback."""

    def test_fallback_summary_without_llm(self):
        """Without LLM caller, should use rule-based fallback."""
        cm = ConversationManager(max_turns=1)
        cm.add_message("user", "Search for react framework")
        cm.add_message("assistant", "Here are some results...")
        cm.add_message("tool", "[search] done", metadata={"tool_name": "search"})
        # Trigger compression
        cm.add_message("user", "Compare with vue")
        assert cm.summary != ""
        assert "Historical" in cm.summary or "History" in cm.summary

    def test_llm_summary_success(self):
        """With working LLM caller, should use it."""
        async def mock_llm(messages):
            return "This conversation covered React search and Vue comparison."

        cm = ConversationManager(max_turns=1, llm_caller=mock_llm)
        cm.add_message("user", "Search for react")
        cm.add_message("assistant", "Results here.")
        cm.add_message("user", "What about vue?")
        assert "React search and Vue comparison" in cm.summary

    def test_llm_summary_failure_fallback(self):
        """LLM caller raises → should fall back to rule-based."""
        async def failing_llm(messages):
            raise ConnectionError("LLM unavailable")

        cm = ConversationManager(max_turns=1, llm_caller=failing_llm)
        cm.add_message("user", "Search for react")
        cm.add_message("assistant", "Results here.")
        cm.add_message("user", "What about vue?")
        # Should still have a summary from fallback
        assert cm.summary != ""


class TestAgentScopeMemoryLLMSummary:
    """Test AgentScopeMemory LLM summarization with fallback."""

    def test_fallback_summary_without_llm(self):
        mem = AgentScopeMemory(max_messages=2)
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        mem.add_user_message("Search react")
        # Should trigger compression
        assert mem.compressed_summary != ""

    def test_llm_summary_success(self):
        async def mock_llm(messages):
            return "LLM summarized: user asked about React."

        mem = AgentScopeMemory(max_messages=2, llm_caller=mock_llm)
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        mem.add_user_message("Search react")
        assert "React" in mem.compressed_summary

    def test_llm_summary_failure_fallback(self):
        async def failing_llm(messages):
            raise RuntimeError("LLM down")

        mem = AgentScopeMemory(max_messages=2, llm_caller=failing_llm)
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        mem.add_user_message("Search react")
        assert mem.compressed_summary != ""
