# -*- coding: utf-8 -*-
"""
LLM-as-Judge evaluation system

Uses a lightweight scoring rubric approach:
- Task: input + expected output criteria
- Metric: scoring dimensions (relevance, accuracy, completeness, actionability)
- Judge: LLM-powered scorer that evaluates outputs against rubrics
- Multi-model: supports different judge models (GPT-4o, Claude, Qwen)

Architecture:
- LLMJudge: orchestrates evaluation (calls LLM once per task)
- ScoringRubric: defines dimensions and point ranges
- LLMJudgeMetric: implements AgentScope MetricBase interface
"""

import json
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from agentscope.evaluate import MetricBase, MetricResult, MetricType
from agentscope.evaluate._solution import SolutionOutput

from src.core.logger import get_logger

logger = get_logger(__name__)

# ---- Scoring Dimensions ----


@dataclass
class ScoringDimension:
    """A single scoring dimension in a rubric."""

    name: str
    description: str
    max_score: float = 5.0
    weight: float = 1.0


# ---- Default Rubric ----

DEFAULT_RUBRIC: List[ScoringDimension] = [
    ScoringDimension(
        name="relevance",
        description="How well does the response address the user's query?",
        max_score=5.0,
        weight=1.0,
    ),
    ScoringDimension(
        name="accuracy",
        description="Is the information factually correct and precise?",
        max_score=5.0,
        weight=1.5,
    ),
    ScoringDimension(
        name="completeness",
        description="Does the response cover all aspects of the query?",
        max_score=5.0,
        weight=1.0,
    ),
    ScoringDimension(
        name="actionability",
        description="Are the insights actionable and specific?",
        max_score=5.0,
        weight=1.0,
    ),
]


# ---- LLM-as-Judge Metric ----


class LLMJudgeMetric(MetricBase):
    """
    LLM-as-Judge metric that scores solution output against a rubric.

    This metric calls an LLM (via the provided model function) to score
    the solution on multiple dimensions simultaneously, reducing API calls.
    """

    SYSTEM_PROMPT = """You are an expert evaluator for GitHub analysis tool outputs.
Score the assistant's response based on the following rubric.

Rubric dimensions:
{rubric}

Return ONLY a JSON object with this structure:
{{
    "scores": {{
        "dimension_name": <score 1-5>,
        ...
    }},
    "reasoning": "<brief explanation of scores>"
}}

Do NOT include any text before or after the JSON."""

    def __init__(
        self,
        name: str = "llm_judge",
        model_fn=None,
        rubric: Optional[List[ScoringDimension]] = None,
        categories: Optional[List[str]] = None,
    ):
        if rubric is None:
            rubric = DEFAULT_RUBRIC

        super().__init__(
            name=name,
            metric_type=MetricType.NUMERICAL,
            description="LLM-as-Judge multi-dimensional scoring",
            categories=categories,
        )
        self.model_fn = model_fn
        self.rubric = rubric

    def _build_prompt(self, task_input: str, solution_output: str) -> str:
        """Build the evaluation prompt."""
        rubric_text = "\n".join(
            f"- **{d.name}** (max {d.max_score}): {d.description}"
            for d in self.rubric
        )
        return f"""{self.SYSTEM_PROMPT.format(rubric=rubric_text)}

---

## User Query
{task_input}

## Assistant Response
{solution_output}

---

Please provide your scores as JSON."""

    def _parse_score(self, raw_score: float) -> float:
        """Clamp a score to valid range."""
        return max(1.0, min(5.0, float(raw_score)))

    def compute_weighted_score(self, scores: Dict[str, float]) -> float:
        """Compute weighted average from individual dimension scores."""
        total_weight = sum(d.weight for d in self.rubric)
        weighted_sum = sum(
            scores.get(d.name, 3.0) * d.weight
            for d in self.rubric
        )
        return round(weighted_sum / total_weight, 2) if total_weight > 0 else 3.0

    async def __call__(
        self,
        solution: SolutionOutput,
        task_input: str = "",
    ) -> MetricResult:
        """
        Score a solution output.

        Args:
            solution: The solution to evaluate
            task_input: The original user query (for context)

        Returns:
            MetricResult with weighted score and dimension breakdown
        """
        output_text = str(solution.output) if solution.output else ""

        if self.model_fn is None:
            # Fallback: return neutral score without LLM call
            return MetricResult(
                name=self.name,
                result=3.0,
                message=json.dumps({"dimensions": {}, "reasoning": "Skipped (no model available)"}),
            )

        try:
            prompt = self._build_prompt(task_input, output_text)
            response = self.model_fn(messages=[
                {"role": "system", "content": "You are an expert evaluator."},
                {"role": "user", "content": prompt},
            ])
            content = response.get("content", "")

            # Parse JSON from response
            # Handle cases where JSON is embedded in markdown code blocks
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                score_data = json.loads(content[json_start:json_end])
            else:
                raise ValueError("No JSON found in response")

            scores = score_data.get("scores", {})
            reasoning = score_data.get("reasoning", "")

            # Validate scores
            for dim in self.rubric:
                if dim.name not in scores:
                    scores[dim.name] = 3.0  # Default if missing
                else:
                    scores[dim.name] = self._parse_score(scores[dim.name])

            weighted = self.compute_weighted_score(scores)

            # Store dimension scores in message (JSON) since MetricResult's
            # DictMixin inheritance causes metadata field to be silently dropped.
            import json as _json
            detail = _json.dumps({
                "dimensions": scores,
                "reasoning": reasoning,
            }, ensure_ascii=False)

            return MetricResult(
                name=self.name,
                result=weighted,
                message=detail,
            )

        except Exception as e:
            logger.warning(f"LLM judge scoring failed: {e}")
            return MetricResult(
                name=self.name,
                result=3.0,
                message=json.dumps({"dimensions": {}, "error": str(e)}),
            )


# ---- Convenience Functions ----


def create_judge_task(
    task_id: str,
    user_input: str,
    assistant_output: str,
    model_fn=None,
    rubric: Optional[List[ScoringDimension]] = None,
) -> "JudgeTask":
    """
    Create a simple judge task for evaluation.

    Returns a JudgeTask which can be evaluated by calling its methods.
    This is a simplified interface for the full AgentScope evaluate pipeline.
    """
    metric = LLMJudgeMetric(model_fn=model_fn, rubric=rubric)
    return JudgeTask(
        id=task_id,
        input_text=user_input,
        output_text=assistant_output,
        metric=metric,
    )


@dataclass
class JudgeTask:
    """Simplified evaluation task for single-output scoring."""

    id: str
    input_text: str
    output_text: str
    metric: LLMJudgeMetric

    async def score(self) -> MetricResult:
        """Score the task's output."""
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(
            success=True,
            output=self.output_text,
            trajectory=[],
            meta={"task_id": self.id},
        )
        return await self.metric(solution, task_input=self.input_text)

    def score_sync(self) -> MetricResult:
        """Score the task synchronously."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.score())


# ---- Rule-based Scoring (no LLM needed) ----


class RuleBasedScorer:
    """
    Lightweight rule-based scorer for automated testing.

    Scores outputs based on structural criteria without needing LLM calls.
    Useful for CI/CD validation and quick feedback.
    """

    @staticmethod
    def score_relevance(output: str, keywords: List[str]) -> float:
        """Score based on keyword overlap (0-5 scale)."""
        if not output or not keywords:
            return 1.0
        lower_output = output.lower()
        matches = sum(1 for kw in keywords if kw.lower() in lower_output)
        ratio = matches / len(keywords)
        return round(1.0 + ratio * 4.0, 2)  # Map 0-1 to 1-5

    @staticmethod
    def score_completeness(output: str, required_sections: List[str]) -> float:
        """Score based on section presence (0-5 scale)."""
        if not output:
            return 1.0
        if not required_sections:
            return 3.0
        lower_output = output.lower()
        present = sum(1 for s in required_sections if s.lower() in lower_output)
        ratio = present / len(required_sections)
        return round(1.0 + ratio * 4.0, 2)

    @staticmethod
    def score_accuracy(output: str, expected_fields: List[str]) -> float:
        """Score based on expected data presence (0-5 scale)."""
        if not output:
            return 1.0
        if not expected_fields:
            return 3.0
        matches = sum(1 for f in expected_fields if f in output)
        ratio = matches / len(expected_fields)
        return round(1.0 + ratio * 4.0, 2)

    @staticmethod
    def score_actionability(output: str) -> float:
        """Score based on presence of actionable language (0-5 scale)."""
        action_words = [
            "recommend", "suggest", "should", "must", "consider",
            "implement", "use", "avoid", "replace", "migrate",
            "first", "best", "important", "note", "warning",
        ]
        if not output:
            return 1.0
        lower_output = output.lower()
        present = sum(1 for w in action_words if w in lower_output)
        if present >= 4:
            return 5.0
        elif present >= 3:
            return 4.0
        elif present >= 2:
            return 3.0
        elif present >= 1:
            return 2.0
        return 1.0

    @staticmethod
    def score_total(
        output: str,
        keywords: Optional[List[str]] = None,
        required_sections: Optional[List[str]] = None,
        expected_fields: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """Compute all scoring dimensions."""
        return {
            "relevance": RuleBasedScorer.score_relevance(output, keywords or []),
            "completeness": RuleBasedScorer.score_completeness(output, required_sections or []),
            "accuracy": RuleBasedScorer.score_accuracy(output, expected_fields or []),
            "actionability": RuleBasedScorer.score_actionability(output),
        }


# ---- Multi-Model Judge Support ----


@dataclass
class JudgeModelConfig:
    """Configuration for a judge model."""

    name: str
    description: str
    model_id: str
    temperature: float = 0.0
    max_tokens: int = 1024
    # Some models may need different system prompt styles
    system_prompt: Optional[str] = None
    # Score normalization: maps model-specific range to 1-5
    score_min: float = 1.0
    score_max: float = 5.0


# Pre-configured judge models
JUDGE_MODELS: Dict[str, JudgeModelConfig] = {
    "gpt-4o": JudgeModelConfig(
        name="GPT-4o",
        description="OpenAI GPT-4o — high-quality judge",
        model_id="gpt-4o",
    ),
    "claude": JudgeModelConfig(
        name="Claude",
        description="Anthropic Claude — conservative judge",
        model_id="claude-3-opus",
    ),
    "qwen": JudgeModelConfig(
        name="Qwen",
        description="Alibaba Qwen-Max — balanced judge",
        model_id="qwen-max",
    ),
}


class ModelScoreNormalizer:
    """
    Normalizes scores from different judge models to a common 1-5 range.

    Some models have systematic biases (e.g., Claude tends to be more
    conservative). This normalizer applies linear scaling to bring scores
    to a common distribution.
    """

    # Empirically-derived normalization factors (can be tuned)
    NORMALIZATION_MAP: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"slope": 1.0, "intercept": 0.0},    # Baseline
        "claude": {"slope": 1.1, "intercept": 0.2},     # Slightly compressed → expand
        "qwen": {"slope": 1.0, "intercept": -0.1},      # Slightly generous → shrink
    }

    @staticmethod
    def normalize(score: float, model_key: str = "gpt-4o") -> float:
        """Normalize a single score to 1-5 range."""
        config = ModelScoreNormalizer.NORMALIZATION_MAP.get(model_key, {"slope": 1.0, "intercept": 0.0})
        normalized = score * config["slope"] + config["intercept"]
        return max(1.0, min(5.0, round(normalized, 2)))

    @staticmethod
    def normalize_scores(
        scores: Dict[str, float],
        model_key: str = "gpt-4o",
    ) -> Dict[str, float]:
        """Normalize all dimension scores."""
        return {dim: ModelScoreNormalizer.normalize(s, model_key) for dim, s in scores.items()}

    @staticmethod
    def get_model_keys() -> List[str]:
        """Return available model keys."""
        return list(ModelScoreNormalizer.NORMALIZATION_MAP.keys())


class MultiModelJudge:
    """
    Orchestrates scoring across multiple judge models.

    Usage:
        judge = MultiModelJudge()
        results = judge.score_all(
            user_input="Search Python web frameworks",
            assistant_output="Found FastAPI, Django, Flask...",
        )
        # results["gpt-4o"] = {"weighted": 4.2, "dimensions": {...}}
        # results["claude"] = {"weighted": 3.8, "dimensions": {...}}
        # results["consensus"] = {"weighted": 4.0, "dimensions": {...}}
    """

    def __init__(
        self,
        model_fns: Optional[Dict[str, Callable]] = None,
        rubric: Optional[List[ScoringDimension]] = None,
    ):
        """
        Args:
            model_fns: Dict mapping model key to model function.
                e.g., {"gpt-4o": openai_fn, "claude": anthropic_fn}
            rubric: Optional custom scoring rubric.
        """
        self.model_fns = model_fns or {}
        self.rubric = rubric or DEFAULT_RUBRIC

    def score_with_model(
        self,
        model_key: str,
        user_input: str,
        assistant_output: str,
    ) -> Optional[Dict[str, Any]]:
        """Score with a single model, returning normalized scores."""
        if model_key not in self.model_fns:
            return None

        model_fn = self.model_fns[model_key]
        metric = LLMJudgeMetric(model_fn=model_fn, rubric=self.rubric)

        import asyncio
        from agentscope.evaluate._solution import SolutionOutput

        solution = SolutionOutput(
            success=True,
            output=assistant_output,
            trajectory=[],
        )

        try:
            result = asyncio.get_event_loop().run_until_complete(
                metric(solution, task_input=user_input)
            )
            # Parse dimension scores from message
            import json
            detail = json.loads(result.message)
            dims = detail.get("dimensions", {})
            normalized = ModelScoreNormalizer.normalize_scores(dims, model_key)
            weighted = metric.compute_weighted_score(normalized)
            return {
                "model": model_key,
                "raw_weighted": result.result,
                "normalized_weighted": weighted,
                "dimensions": dims,
                "normalized_dimensions": normalized,
                "reasoning": detail.get("reasoning", ""),
            }
        except Exception:
            return None

    def score_all(
        self,
        user_input: str,
        assistant_output: str,
    ) -> Dict[str, Any]:
        """Score with all configured models and compute consensus."""
        results: Dict[str, Any] = {}
        weighted_scores: List[float] = []
        dim_sums: Dict[str, float] = {}
        dim_counts: Dict[str, int] = {}

        for model_key in self.model_fns:
            score = self.score_with_model(model_key, user_input, assistant_output)
            if score:
                results[model_key] = score
                weighted_scores.append(score["normalized_weighted"])
                for dim, s in score["normalized_dimensions"].items():
                    dim_sums[dim] = dim_sums.get(dim, 0) + s
                    dim_counts[dim] = dim_counts.get(dim, 0) + 1

        if weighted_scores:
            consensus_weighted = sum(weighted_scores) / len(weighted_scores)
            consensus_dims = {
                dim: round(dim_sums[dim] / dim_counts[dim], 2)
                for dim in dim_sums
            }
            results["consensus"] = {
                "model": "consensus",
                "normalized_weighted": round(consensus_weighted, 2),
                "dimensions": consensus_dims,
                "model_count": len(weighted_scores),
            }

        return results
