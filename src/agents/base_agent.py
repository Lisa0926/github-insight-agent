# -*- coding: utf-8 -*-
"""
Base Agent Class (based on AgentScope AgentBase)

Features:
- Defines the common interface for agents
- Inherits from AgentScope's AgentBase
- Provides unified memory management and tool calling capabilities
- Supports configuration-driven initialization

Note:
- Since AgentScope AgentBase uses a custom metaclass, it cannot be directly
  mixed with ABC
- Uses runtime checks instead of ABC's abstract method checks
"""

from typing import Any, Dict, List, Optional, Union

from agentscope.agent import AgentBase
from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)


class GiaAgentBase(AgentBase):
    """
    GIA Agent Base Class (inherits from AgentScope AgentBase)

    All GIA agents should inherit from this class and implement specific
    analysis logic. Supports:
    - Configuration-driven model initialization
    - Memory management (conversation history)
    - AgentScope hook support

    Subclasses must implement the following methods:
    - reply(msg, *args, **kwargs) -> Msg: Respond to user messages
    - get_description() -> str: Get agent description
    """

    def __init__(
        self,
        name: str,
        model_name: str = "",
        system_prompt: Optional[str] = None,
        config: Optional[ConfigManager] = None,
        use_persistent: bool = True,
        db_path: str = "data/app.db",
    ):
        """
        Initialize the base agent

        Args:
            name: Agent name
            model_name: Model name (default: from DASHSCOPE_MODEL env var)
            system_prompt: System prompt
            config: Configuration manager
            use_persistent: Whether to use persistent storage (default: True)
            db_path: SQLite database path
        """
        super().__init__()

        self.name = name
        self.config = config or ConfigManager()
        self.model_name = model_name or self.config.dashscope_model_name
        self.system_prompt = system_prompt or self._default_system_prompt()

        # Memory: reuse existing wrappers
        if use_persistent:
            from src.core.agentscope_persistent_memory import get_persistent_memory
            self.memory = get_persistent_memory(db_path=db_path)
            logger.info(f"GiaAgentBase PersistentMemory initialized (db={db_path})")
        else:
            from src.core.agentscope_memory import AgentScopeMemory
            self.memory = AgentScopeMemory(max_messages=10)
            logger.info("GiaAgentBase InMemoryMemory initialized (max_messages=10)")

        # Model wrapper: lazy loading
        self._model_wrapper = None

        logger.info(f"GiaAgentBase '{name}' initialized with model '{model_name}'")

    def _default_system_prompt(self) -> str:
        """Return the default system prompt"""
        return f"""You are {self.name}, an intelligent agent for GitHub repository analysis.
You help users analyze GitHub repositories, understand code quality, track issues, and provide insights.
Always be helpful, accurate, and provide actionable recommendations."""

    # -- Shared methods (extracted from ResearcherAgent / AnalystAgent) ---

    def _get_model_wrapper(self):
        """
        Lazily load the model caller

        Wraps dashscope.Generation.call() (synchronous),
        compatible with AgentScope ChatResponse interface.
        """
        if self._model_wrapper is None:
            try:
                from src.core.dashscope_wrapper import DashScopeWrapper

                self._model_wrapper = DashScopeWrapper(
                    model_name=self.model_name,
                    api_key=self.config.dashscope_api_key,
                    base_url=self.config.dashscope_base_url,
                )
                logger.info(f"DashScopeWrapper created for model '{self.model_name}'")

            except Exception as e:
                logger.error(f"Failed to create DashScopeWrapper: {e}")
                raise

        return self._model_wrapper

    def _extract_response_text(self, response) -> str:
        """
        Extract text content from a model response

        Compatible formats:
        - ChatResponse (dict subclass, content is str or list)
        - Object with .text attribute
        - Plain dict
        """
        # ChatResponse is a dict subclass; hasattr would trigger KeyError, so use dict methods
        if isinstance(response, dict):
            content = response.get("content", "")
            if isinstance(content, list):
                # text block list
                return "".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            return content
        # Object with .text attribute
        if hasattr(response, "text"):
            return response.text
        # Object with .content attribute
        if hasattr(response, "content"):
            return response.content
        return ""

    def _add_to_memory(self, role: str, content: str, name: Optional[str] = None) -> None:
        """
        Add a message to memory and forward to Studio

        Args:
            role: Role (user/assistant/system)
            content: Message content
            name: Sender name
        """
        self.memory.add_message(
            role=role,
            content=content,
            name=name or self.name,
        )
        self._forward_to_studio(name or self.name, content, role)

    def _forward_to_studio(self, name: str, content: str, role: str) -> None:
        """Forward message to Studio (if enabled)"""
        try:
            from src.core.studio_helper import forward_to_studio
            forward_to_studio(name, content, role)
        except Exception:
            pass  # Silent failure, does not affect main flow

    # -- AgentBase interface (must be implemented by subclasses) ---

    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """
        Respond to user message (must be implemented by subclasses)

        Args:
            msg: Input message (Msg object or string)
            *args: Other arguments
            **kwargs: Keyword arguments

        Returns:
            Response message

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement 'reply' method")

    def get_description(self) -> str:
        """
        Get agent description (must be implemented by subclasses)

        Returns:
            Agent description string

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError("Subclasses must implement 'get_description' method")


# Backward compatibility alias
BaseAgent = GiaAgentBase
