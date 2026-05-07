# -*- coding: utf-8 -*-
"""Tests for BaseTool ABC and tool_base utilities."""

from src.core.tool_base import BaseTool, tools_to_schemas, tools_to_prompt_text


class DummyTool(BaseTool):
    """A minimal tool for testing."""

    def get_name(self) -> str:
        return "dummy_tool"

    def get_description(self) -> str:
        return "A dummy tool for testing."

    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "verbose": {"type": "boolean"},
            },
            "required": ["query"],
        }

    def execute(self, input_data):
        return {"query": input_data.get("query")}


class TestBaseTool:
    """Test BaseTool ABC and concrete implementations."""

    def test_get_json_schema(self):
        tool = DummyTool()
        schema = tool.get_json_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy_tool"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]

    def test_validate_input_valid(self):
        tool = DummyTool()
        assert tool.validate_input({"query": "test", "limit": 5}) is True

    def test_validate_input_missing_required(self):
        tool = DummyTool()
        assert tool.validate_input({"limit": 5}) is False

    def test_validate_input_wrong_type_string(self):
        tool = DummyTool()
        assert tool.validate_input({"query": 123}) is False

    def test_validate_input_wrong_type_integer(self):
        tool = DummyTool()
        assert tool.validate_input({"query": "test", "limit": "five"}) is False

    def test_validate_input_wrong_type_boolean(self):
        tool = DummyTool()
        assert tool.validate_input({"query": "test", "verbose": "yes"}) is False

    def test_validate_input_missing_field_none(self):
        tool = DummyTool()
        assert tool.validate_input({"query": None}) is False

    def test_execute(self):
        tool = DummyTool()
        result = tool.execute({"query": "hello"})
        assert result == {"query": "hello"}


class TestToolHelpers:
    """Test tools_to_schemas and tools_to_prompt_text."""

    def test_tools_to_schemas(self):
        tools = [DummyTool()]
        schemas = tools_to_schemas(tools)
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "dummy_tool"

    def test_tools_to_prompt_text(self):
        assert tools_to_prompt_text([]) == "No tools available."

        tools = [DummyTool()]
        text = tools_to_prompt_text(tools)
        assert "dummy_tool" in text
        assert "A dummy tool for testing." in text

    def test_tools_to_prompt_text_multiple(self):
        class AnotherTool(DummyTool):
            def get_name(self):
                return "another_tool"

        text = tools_to_prompt_text([DummyTool(), AnotherTool()])
        assert "dummy_tool" in text
        assert "another_tool" in text
