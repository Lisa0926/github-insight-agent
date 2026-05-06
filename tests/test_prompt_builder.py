# -*- coding: utf-8 -*-
"""Tests for dynamic System Prompt Builder."""

from unittest.mock import patch

from src.core.prompt_builder import get_system_prompt


class TestPromptBuilderYamlLoading:
    """Test that prompts are loaded from role_kpi.yaml"""

    def test_researcher_prompt_from_yaml(self):
        prompt = get_system_prompt("researcher")
        assert len(prompt) > 50
        assert "开源情报" in prompt

    def test_analyst_prompt_from_yaml(self):
        prompt = get_system_prompt("analyst")
        assert len(prompt) > 100
        assert "技术架构师" in prompt

    def test_pipeline_prompt_from_yaml(self):
        prompt = get_system_prompt("pipeline")
        assert len(prompt) > 100
        assert "报告编排" in prompt or "交付" in prompt

    def test_pipeline_followup_prompt_from_yaml(self):
        prompt = get_system_prompt("pipeline", "followup_system_prompt")
        assert len(prompt) > 50
        assert "上下文" in prompt

    def test_in_scope_constraints_appended(self):
        prompt = get_system_prompt("researcher")
        assert "In-Scope" in prompt
        assert "禁止行为" in prompt

    def test_out_of_scope_constraints_appended(self):
        prompt = get_system_prompt("analyst")
        assert "禁止行为" in prompt


class TestPromptBuilderFallback:
    """Test hardcoded fallback when YAML is unavailable"""

    @patch("src.core.prompt_builder._load_role_kpi_config", return_value=None)
    def test_fallback_researcher(self, mock_load):
        prompt = get_system_prompt("researcher")
        assert len(prompt) > 50
        assert "开源情报" in prompt

    @patch("src.core.prompt_builder._load_role_kpi_config", return_value=None)
    def test_fallback_analyst(self, mock_load):
        prompt = get_system_prompt("analyst")
        assert len(prompt) > 100
        assert "技术架构师" in prompt

    @patch("src.core.prompt_builder._load_role_kpi_config", return_value=None)
    def test_fallback_pipeline(self, mock_load):
        prompt = get_system_prompt("pipeline")
        assert len(prompt) > 100
        assert "报告编排" in prompt or "交付" in prompt

    @patch("src.core.prompt_builder._load_role_kpi_config", return_value=None)
    def test_fallback_unknown_agent(self, mock_load):
        prompt = get_system_prompt("unknown_agent")
        assert len(prompt) > 0
        assert "unknown_agent" in prompt


class TestPromptBuilderConstraints:
    """Test constraint injection behavior"""

    def test_constraints_not_duplicated(self):
        """When use_constraints=False, no in_scope/out_of_scope appended"""
        prompt = get_system_prompt("pipeline", use_constraints=False)
        assert "In-Scope" not in prompt
        assert "禁止行为" not in prompt

    def test_constraints_with_flag(self):
        """When use_constraints=True, constraints are appended"""
        prompt = get_system_prompt("pipeline", use_constraints=True)
        assert "In-Scope" in prompt

    def test_constraints_only_appended_if_available(self):
        """Fallback agent without constraints should not add constraint section"""
        prompt = get_system_prompt("unknown_agent", use_constraints=True)
        # Should still work without error (no constraints for unknown agent)
        assert len(prompt) > 0


class TestPromptBuilderContentConsistency:
    """Test that YAML and fallback prompts contain the same key content"""

    def test_researcher_core_content(self):
        prompt = get_system_prompt("researcher")
        assert "开源情报研究员" in prompt
        assert "GitHub 工具" in prompt
        assert "不要编造" in prompt

    def test_analyst_core_content(self):
        prompt = get_system_prompt("analyst")
        assert "资深技术架构师" in prompt
        assert "ReAct" in prompt
        assert "JSON" in prompt

    def test_pipeline_core_content(self):
        prompt = get_system_prompt("pipeline")
        assert "报告编排" in prompt or "交付" in prompt
        assert "不编造" in prompt
        assert "数据驱动" in prompt
