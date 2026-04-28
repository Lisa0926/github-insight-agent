# Workflows module
"""Workflow module: defines multi-step automated pipelines"""

from .report_generator import ReportGenerator
from .agent_pipeline import AgentPipeline

__all__ = ["ReportGenerator", "AgentPipeline"]
