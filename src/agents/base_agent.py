# -*- coding: utf-8 -*-
"""
基础智能体类 (基于 AgentScope AgentBase)

功能:
- 定义智能体的通用接口
- 继承 AgentScope 的 AgentBase
- 提供统一的记忆管理和工具调用能力
- 支持配置驱动

注意:
- 由于 AgentScope AgentBase 使用自定义元类，不能直接与 ABC 混用
- 使用运行时检查替代 ABC 的抽象方法检查
"""

from typing import Any, Dict, List, Optional, Union

from agentscope.agent import AgentBase
from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger

logger = get_logger(__name__)


class BaseAgent(AgentBase):
    """
    基础智能体抽象类 (继承自 AgentScope AgentBase)

    所有智能体都应继承此类，实现特定的分析逻辑。
    支持:
    - 配置驱动的模型初始化
    - 记忆管理 (对话历史)
    - 工具调用
    - AgentScope 钩子支持

    子类必须实现以下方法:
    - reply(msg, *args, **kwargs) -> Msg: 响应用户消息
    - get_description() -> str: 获取智能体描述
    """

    def __init__(
        self,
        name: str,
        model_name: str = "qwen-max",
        system_prompt: Optional[str] = None,
        config: Optional[ConfigManager] = None,
    ):
        """
        初始化基础智能体

        Args:
            name: 智能体名称
            model_name: 模型名称 (默认 qwen-max)
            system_prompt: 系统提示词
            config: 配置管理器
        """
        super().__init__()

        self.name = name
        self.model_name = model_name
        self.config = config or ConfigManager()
        self.system_prompt = system_prompt or self._default_system_prompt()

        # 对话记忆 (使用 AgentScope Msg)
        self.memory: List[Msg] = []

        logger.info(f"BaseAgent '{name}' initialized with model '{model_name}'")

    def _default_system_prompt(self) -> str:
        """返回默认的系统提示词"""
        return f"""You are {self.name}, an intelligent agent for GitHub repository analysis.
You help users analyze GitHub repositories, understand code quality, track issues, and provide insights.
Always be helpful, accurate, and provide actionable recommendations."""

    def add_to_memory(self, msg: Union[Msg, Dict[str, Any]]) -> None:
        """
        添加消息到记忆

        Args:
            msg: 消息对象 (Msg 或字典)
        """
        if isinstance(msg, Msg):
            self.memory.append(msg)
        else:
            # 从字典创建 Msg
            msg = Msg(
                name=self.name,
                content=msg.get("content", ""),
                role=msg.get("role", "assistant"),
            )
            self.memory.append(msg)

        logger.debug(f"Added message to memory: {msg.role}")

    def clear_memory(self) -> None:
        """清空记忆"""
        self.memory = []
        logger.debug(f"Cleared memory for agent '{self.name}'")

    def get_memory(self) -> List[Msg]:
        """获取当前记忆"""
        return self.memory.copy()

    def get_model_config(self) -> Dict[str, Any]:
        """获取模型配置"""
        config = self.config.get_model_config(self.model_name)
        if not config:
            logger.warning(f"No config found for model '{self.model_name}'")
        return config

    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """
        响应用户消息 (子类必须实现)

        Args:
            msg: 输入消息 (Msg 对象或字符串)
            *args: 其他参数
            **kwargs: 关键字参数

        Returns:
            响应消息

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement 'reply' method")

    def get_description(self) -> str:
        """
        获取智能体描述 (子类必须实现)

        Returns:
            智能体描述字符串

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement 'get_description' method")
