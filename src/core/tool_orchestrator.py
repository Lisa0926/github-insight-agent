# -*- coding: utf-8 -*-
"""
Tool Orchestrator — Tool→Tool chaining for GitHub analysis workflows.

Supports chaining multiple tools where the output of one tool feeds into
the input of the next. Useful for multi-step analysis pipelines like:
  search_repositories → get_repo_info → get_readme → evaluate_code_quality

Usage:
    from src.core.tool_orchestrator import ToolOrchestrator

    orchestrator = ToolOrchestrator(toolkit, github_tool)

    # Run a predefined pipeline
    result = orchestrator.execute_pipeline(
        "repo_analysis",
        {"query": "fastapi", "owner": "tiangolo", "repo": "fastapi"},
    )

    # Or run an ad-hoc chain
    result = orchestrator.execute_tool_chain([
        {"tool": "search_repositories", "params": {"query": "react"}},
        {"tool": "get_repo_info", "params": {"owner": "{result.0.owner}", "repo": "{result.0.repo}"}},
    ])
"""

import re
from typing import Any, Callable, Dict, List, Optional

from src.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Predefined Pipeline Definitions
# ============================================================

# Each pipeline is a list of steps. Each step has:
#   - tool: tool name (str)
#   - params: parameter dict with optional {context_ref} placeholders
#   - output_key: optional key to store result in context (defaults to step index)

PIPELINES: Dict[str, List[Dict[str, Any]]] = {
    "repo_analysis": [
        {
            "tool": "get_repo_info",
            "params": {"owner": "{owner}", "repo": "{repo}"},
            "output_key": "repo_info",
        },
        {
            "tool": "get_readme",
            "params": {"owner": "{owner}", "repo": "{repo}"},
            "output_key": "readme",
        },
        {
            "tool": "evaluate_code_quality",
            "params": {
                "readme_content": "{readme}",
                "repo_info_json": "{repo_info}",
            },
            "output_key": "quality_report",
        },
    ],
    "search_and_analyze": [
        {
            "tool": "search_repositories",
            "params": {"query": "{query}", "sort": "stars", "per_page": "{per_page|5}"},
            "output_key": "search_results",
        },
        {
            "tool": "get_repo_info",
            "params": {"owner": "{result.0.owner}", "repo": "{result.0.repo}"},
            "output_key": "top_repo_info",
            "condition": "result.0.exists",
        },
    ],
    "security_scan": [
        {
            "tool": "get_readme",
            "params": {"owner": "{owner}", "repo": "{repo}"},
            "output_key": "readme",
        },
        {
            "tool": "get_repo_info",
            "params": {"owner": "{owner}", "repo": "{repo}"},
            "output_key": "repo_info",
        },
        {
            "tool": "scan_security_code",
            "params": {"file_path": "{file_path|main.py}", "code_content": "{code_content}"},
            "output_key": "security_report",
        },
    ],
    "pr_review": [
        {
            "tool": "review_code_changes",
            "params": {
                "pr_title": "{pr_title}",
                "pr_description": "{pr_description}",
                "diff_content": "{diff_content}",
            },
            "output_key": "pr_report",
        },
    ],
}


# ============================================================
# Tool Orchestrator
# ============================================================

class ToolOrchestrator:
    """
    Orchestrates multi-step tool pipelines.

    Manages a context dict that flows through each step. Each step can
    reference values from the context using {key} placeholders in params.
    Results are stored back into the context for subsequent steps.
    """

    def __init__(
        self,
        toolkit: Any = None,
        github_tool: Any = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            toolkit: AgentScope Toolkit instance (for registered tools)
            github_tool: GitHubTool instance (for direct tool access)
        """
        self.toolkit = toolkit
        self.github_tool = github_tool
        self._custom_pipelines: Dict[str, List[Dict[str, Any]]] = {}

    def register_pipeline(
        self,
        name: str,
        steps: List[Dict[str, Any]],
    ) -> None:
        """
        Register a custom pipeline.

        Args:
            name: Pipeline name
            steps: List of step dicts with 'tool', 'params', 'output_key'
        """
        self._custom_pipelines[name] = steps
        logger.info(f"Registered pipeline '{name}' with {len(steps)} steps")

    def get_available_pipelines(self) -> List[str]:
        """Get list of available pipeline names."""
        return list(PIPELINES.keys()) + list(self._custom_pipelines.keys())

    def execute_pipeline(
        self,
        pipeline_name: str,
        initial_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a predefined pipeline.

        Args:
            pipeline_name: Name of the pipeline to execute
            initial_params: Initial context params (e.g., owner, repo)

        Returns:
            Dict with 'success', 'context' (final state), and 'steps' (per-step results)
        """
        # Check custom pipelines first, then built-in
        steps = self._custom_pipelines.get(pipeline_name)
        if steps is None:
            steps = PIPELINES.get(pipeline_name)

        if steps is None:
            return {
                "success": False,
                "error": f"Pipeline '{pipeline_name}' not found. "
                f"Available: {self.get_available_pipelines()}",
                "context": initial_params,
                "steps": [],
            }

        return self.execute_tool_chain(steps, initial_params)

    def execute_tool_chain(
        self,
        steps: List[Dict[str, Any]],
        initial_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a chain of tools, passing context between steps.

        Each step receives resolved params (context placeholders replaced),
        executes the tool, and stores the result back into context.

        Args:
            steps: List of step dicts
            initial_context: Initial context dict

        Returns:
            Dict with 'success', 'context', 'steps' (per-step results)
        """
        context = dict(initial_context)
        step_results: List[Dict[str, Any]] = []

        for idx, step in enumerate(steps):
            tool_name = step.get("tool", "")
            raw_params = step.get("params", {})
            output_key = step.get("output_key", f"result_{idx}")

            # Check condition (optional)
            condition = step.get("condition")
            if condition and not self._evaluate_condition(condition, context):
                logger.info(f"Step {idx} ({tool_name}): condition not met, skipping")
                step_results.append({
                    "step": idx,
                    "tool": tool_name,
                    "skipped": True,
                    "reason": f"Condition not met: {condition}",
                })
                continue

            # Resolve parameter placeholders from context
            params = self._resolve_params(raw_params, context)

            logger.info(
                f"Step {idx}/{len(steps)}: Executing '{tool_name}' "
                f"with params={params}"
            )

            # Execute the tool
            try:
                result = self._execute_tool(tool_name, params)
                step_results.append({
                    "step": idx,
                    "tool": tool_name,
                    "success": True,
                    "result_length": len(str(result)),
                })

                # Store result in context for subsequent steps
                context[output_key] = result
                # Also store by index for cross-step references
                context[f"result_{idx}"] = result
                context[f"result_{idx}.value"] = result

                # If result is a string, store raw string for interpolation
                if isinstance(result, str):
                    context[f"result_{idx}.text"] = result

            except Exception as e:
                logger.error(f"Step {idx} ({tool_name}) failed: {e}")
                step_results.append({
                    "step": idx,
                    "tool": tool_name,
                    "success": False,
                    "error": str(e),
                })
                # Continue to next step (don't abort chain)

        return {
            "success": all(
                s.get("success") or s.get("skipped")
                for s in step_results
                if isinstance(s, dict)
            ),
            "context": context,
            "steps": step_results,
        }

    def _resolve_params(
        self,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve {placeholder} references in params from context.

        Supports:
        - {key}: Direct context lookup
        - {key|default}: Lookup with default value
        - {result.0}: Result of step 0 (stored as result_0)
        - {result.0.text}: Alias for result_0 value

        Args:
            params: Parameter dict with potential {placeholders}
            context: Current context dict

        Returns:
            Resolved parameter dict
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and "{" in value:
                resolved[key] = self._resolve_string(value, context)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_params(value, context)
            else:
                resolved[key] = value
        return resolved

    def _resolve_string(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> str:
        """Resolve all {key} references in a string."""

        def _replace(match: re.Match) -> str:
            ref = match.group(1).strip()

            # Support default values: {key|default}
            if "|" in ref:
                ref_name, default = ref.split("|", 1)
                ref_name = ref_name.strip()
                default = default.strip()
                value = context.get(ref_name, default)
            else:
                value = context.get(ref)

            if value is None:
                return ""

            # If value is not a simple string (e.g., stored result object),
            # convert to string representation
            if isinstance(value, (dict, list)):
                import json
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        return re.sub(r"\{([^}]+)\}", _replace, text)

    def _evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any],
    ) -> bool:
        """
        Evaluate a condition string against context.

        Supports:
        - "result.0.exists": Checks if step 0 result is non-empty
        - "key": Checks if key exists and is truthy

        Args:
            condition: Condition string
            context: Current context

        Returns:
            True if condition is met
        """
        if ".exists" in condition:
            key = condition.replace(".exists", "").strip()
            # Map result.N to result_N
            ref_key = re.sub(r"result\.(\d+)", r"result_\1", key)
            value = context.get(ref_key, context.get(key))
            return value is not None and value != "" and value != []

        return condition in context and context[condition]

    def _execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> str:
        """
        Execute a single tool by name.

        Routes to the appropriate execution method based on tool name.

        Args:
            tool_name: Tool name
            params: Resolved parameters

        Returns:
            Tool result as string
        """
        # Route to GitHubTool direct methods
        if self.github_tool and hasattr(self.github_tool, tool_name):
            method = getattr(self.github_tool, tool_name)
            if callable(method):
                result = method(**params)
                return self._format_tool_result(result)

        # Route to toolkit registered tools
        if self.toolkit:
            try:
                schemas = self.toolkit.get_json_schemas()
                tool_names = [
                    s.get("function", {}).get("name", "")
                    for s in schemas
                ]
                if tool_name in tool_names:
                    # Toolkit tools are registered as functions; try calling via toolkit
                    result = self.toolkit.call_tool_function(tool_name, params)
                    return self._format_tool_result(result)
            except Exception:
                pass

        raise ValueError(f"Tool '{tool_name}' not found in toolkit or github_tool")

    def _format_tool_result(self, result: Any) -> str:
        """Format a tool result to string for context storage."""
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list)):
            import json
            return json.dumps(result, ensure_ascii=False, default=str)
        return str(result)


# ============================================================
# Convenience functions
# ============================================================

def get_builtin_pipelines() -> Dict[str, List[Dict[str, Any]]]:
    """Return all built-in pipeline definitions."""
    return dict(PIPELINES)


def describe_pipeline(name: str) -> Optional[Dict[str, Any]]:
    """Get description of a pipeline and its steps."""
    steps = PIPELINES.get(name)
    if steps is None:
        return None

    return {
        "name": name,
        "steps": [
            {
                "index": idx,
                "tool": step.get("tool", ""),
                "params": step.get("params", {}),
                "output_key": step.get("output_key", f"result_{idx}"),
                "condition": step.get("condition"),
            }
            for idx, step in enumerate(steps)
        ],
    }
