# -*- coding: utf-8 -*-
"""
BaseTool ABC — Unified tool protocol for GIA agents.

All tools should implement this protocol to ensure consistent interfaces
for name, description, input schema, execution, and validation.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from src.core.logger import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all GIA tools.

    Provides:
    - Standardized interface (name, description, schema, execute)
    - JSON Schema-based input validation
    - AgentScope Toolkit integration via get_json_schema()
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return unique tool name (snake_case, e.g. 'search_repositories')."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Return tool description for LLM consumption."""
        ...

    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Return JSON Schema for tool input parameters.

        Returns:
            JSON Schema object, e.g.:
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        """
        ...

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any:
        """
        Execute the tool with validated input.

        Args:
            input_data: Validated input parameters

        Returns:
            Tool result (str, dict, or AgentScope ToolResponse)
        """
        ...

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate input data against JSON Schema.

        Args:
            input_data: Input parameters to validate

        Returns:
            True if valid, False otherwise (logs warnings)
        """
        schema = self.get_input_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in input_data or input_data[field] is None:
                logger.warning(f"[{self.get_name()}] Missing required field: {field}")
                return False

        for field, value in input_data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    logger.warning(f"[{self.get_name()}] Field '{field}' expected string, got {type(value).__name__}")
                    return False
                if expected_type == "integer" and not isinstance(value, int):
                    logger.warning(f"[{self.get_name()}] Field '{field}' expected integer, got {type(value).__name__}")
                    return False
                if expected_type == "boolean" and not isinstance(value, bool):
                    logger.warning(f"[{self.get_name()}] Field '{field}' expected boolean, got {type(value).__name__}")
                    return False

        return True

    def get_json_schema(self) -> Dict[str, Any]:
        """
        Return AgentScope-compatible JSON Schema for function calling.

        Returns:
            JSON Schema in function calling format:
            {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        return {
            "type": "function",
            "function": {
                "name": self.get_name(),
                "description": self.get_description(),
                "parameters": self.get_input_schema(),
            },
        }


def tools_to_schemas(tools: List[BaseTool]) -> List[Dict[str, Any]]:
    """Convert a list of BaseTool instances to AgentScope JSON schemas."""
    return [t.get_json_schema() for t in tools]


def tools_to_prompt_text(tools: List[BaseTool]) -> str:
    """Convert a list of BaseTool instances to a prompt-friendly text description."""
    if not tools:
        return "No tools available."
    parts = []
    for i, tool in enumerate(tools, 1):
        schema_json = json.dumps(tool.get_input_schema(), ensure_ascii=False, indent=2)
        parts.append(f"{i}. **{tool.get_name()}** — {tool.get_description()}\n   Schema:\n```json\n{schema_json}\n```")
    return "\n\n".join(parts)
