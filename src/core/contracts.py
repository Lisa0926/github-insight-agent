# -*- coding: utf-8 -*-
"""
Agent data contracts (Pydantic v2 models)

Defines typed interfaces between agents, sourced from role_kpi.yaml contracts:
- ProjectFact: ResearcherAgent output
- ProjectAnalysisReport: AnalystAgent output

Usage:
    from src.core.contracts import ProjectFact, ProjectAnalysisReport

    fact = ProjectFact(owner="langchain-ai", repo="langchain", stars=90000, lang="Python")
    report = ProjectAnalysisReport.model_validate(analysis_dict)
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectFact(BaseModel):
    """
    ResearcherAgent output contract.

    Fields sourced from role_kpi.yaml → agents.researcher.contracts.fields
    """

    model_config = ConfigDict(extra="ignore")

    owner: str = Field(..., description="Repository owner (username or org)")
    repo: str = Field(..., description="Repository name")
    stars: int = Field(..., ge=0, description="Star count")
    lang: str = Field(default="", description="Primary programming language")
    readme_snippet: Optional[str] = Field(None, description="First 2000 chars of README")
    trend_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    last_commit_days: Optional[int] = Field(None, ge=-1)
    tags: List[str] = Field(default_factory=list)

    @field_validator("trend_score", mode="before")
    @classmethod
    def clamp_trend(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return max(0.0, min(1.0, float(v)))

    @field_validator("lang", mode="before")
    @classmethod
    def default_lang(cls, v: Optional[str]) -> str:
        return v or ""

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


class ProjectAnalysisReport(BaseModel):
    """
    AnalystAgent output contract.

    Fields sourced from role_kpi.yaml → agents.analyst.contracts.fields
    """

    model_config = ConfigDict(extra="ignore")

    core_function: str = Field(..., description="One-sentence core function description")
    tech_stack: List[str] = Field(default_factory=list)
    architecture_pattern: str = Field(default="")
    pain_points: List[str] = Field(default_factory=list)
    suitability: str = Field(default="")
    risk_flags: List[str] = Field(default_factory=list)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    suitability_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("suitability_score", mode="before")
    @classmethod
    def clamp_score(cls, v: float) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

    def score(self, dimension: str) -> float:
        """Get score for a specific dimension from score_breakdown."""
        return self.score_breakdown.get(dimension, 0.0)
