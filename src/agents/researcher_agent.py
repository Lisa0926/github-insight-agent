# -*- coding: utf-8 -*-
"""
Researcher Agent

Features:
- Professional open-source intelligence researcher
- Uses LLM intent understanding to select tools and generate parameters
- Supports arbitrary natural language input without predefined patterns
- Uses AgentScope ModelWrapper for model calls
- Uses AgentScope Msg class for unified message format
- Inherits from AgentScope AgentBase
"""

import json
from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime, timedelta

from agentscope.message import Msg

from src.core.config_manager import ConfigManager
from src.core.guardrails import sanitize_user_input, filter_sensitive_output, circuit_breaker_guard
from src.core.kpi_tracker import KPITracker
from src.core.logger import get_logger
from src.core.studio_helper import StudioHelper, set_global_studio_config
from src.core.span_attributes import set_span_attributes
from src.tools.github_tool import GitHubTool
from src.tools.github_toolkit import get_github_toolkit
from src.agents.base_agent import GiaAgentBase

# Import trace decorator if tracing is enabled
try:
    from agentscope.tracing import trace
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

    def trace(name=None):  # fallback
        def decorator(func):
            return func
        return decorator

logger = get_logger(__name__)

# Studio configuration helper
_studio_helper: Optional[StudioHelper] = None


def set_studio_config(studio_url: str, run_id: str) -> None:
    """Set Studio configuration and register run (using shared module)"""
    global _studio_helper
    _studio_helper = StudioHelper(studio_url, run_id)
    set_global_studio_config(studio_url, run_id)
    logger.debug(f"Studio config set for run: {run_id}")


# Tool definitions for LLM intent understanding
INTENT_TOOLS = [
    {
        "name": "search_repositories",
        "description": (
            "搜索GitHub仓库。当用户想找某类项目、框架、工具时使用。"
            "支持按stars/forks/更新时间排序。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "搜索关键词（必须是英文技术术语或项目名，"
                        "如'AI agent framework', 'React', 'FastAPI'）"
                    )
                },
                "sort": {
                    "type": "string",
                    "enum": ["stars", "forks", "updated"],
                    "description": "排序方式"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量"
                },
                "time_range_days": {
                    "type": "integer",
                    "description": (
                        "只搜索最近N天内创建的项目。"
                        "0或不填表示不限时间。"
                    )
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_repo_info",
        "description": (
            "获取单个GitHub仓库的详细信息（stars、语言、描述等）。"
            "当用户问某个具体项目的信息时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "仓库所有者（用户名或组织名）"
                },
                "repo": {
                    "type": "string",
                    "description": "仓库名"
                }
            },
            "required": ["owner", "repo"]
        }
    },
    {
        "name": "analyze_project",
        "description": (
            "深度分析一个GitHub项目（技术栈、核心功能、推荐度等）。"
            "当用户说'分析'某个项目时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "仓库所有者"
                },
                "repo": {
                    "type": "string",
                    "description": "仓库名"
                }
            },
            "required": ["owner", "repo"]
        }
    },
    {
        "name": "compare_repositories",
        "description": (
            "比较两个或多个GitHub项目。"
            "当用户说'比较'、'对比'项目时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "repositories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "要比较的仓库列表，每项格式为 'owner/repo'"
                    )
                }
            },
            "required": ["repositories"]
        }
    },
    {
        "name": "chat",
        "description": (
            "纯对话。当用户只是在聊天、提问、不需要查询GitHub时使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "用户的原始问题或消息"
                }
            },
            "required": ["message"]
        }
    }
]

INTENT_SYSTEM_PROMPT = """你是一个AI助手，负责理解用户的意图并选择合适的工具。

## 可用工具

1. **search_repositories** - 搜索GitHub仓库
   - 当用户想找"最火的"、"最热门的"、"推荐"某类项目时使用
   - 将中文技术话题转化为英文搜索关键词

2. **get_repo_info** - 获取单个仓库信息
   - 当用户问某个具体项目的stars、语言、描述等时使用

3. **analyze_project** - 深度分析项目
   - 当用户说"分析"某个项目时使用

4. **compare_repositories** - 比较多个项目
   - 当用户说"比较"、"对比"项目时使用

5. **chat** - 纯对话
   - 当用户只是在聊天或提问、不需要查GitHub时使用

## 输出格式

你必须只输出一个JSON对象，不要输出任何其他内容。格式如下：
```json
{"action": "工具名", "params": {参数对象}}
```

## 示例

用户："搜索并翻译，单个项目的star数最高的排名前3的项目"
-> 用户想找热门AI项目
```json
{"action": "search_repositories", "params": {"query": "AI agent framework", "sort": "stars", "limit": 3}}
```

用户："langchain的star数是多少"
```json
{"action": "get_repo_info", "params": {"owner": "langchain-ai", "repo": "langchain"}}
```

用户："帮我搜索最近一周最火的Rust项目"
```json
{"action": "search_repositories", "params": {"query": "Rust", "sort": "stars", "limit": 10, "time_range_days": 7}}
```

用户："比较langchain和autogen"
```json
{"action": "compare_repositories", "params": {"repositories": ["langchain-ai/langchain", "microsoft/autogen"]}}
```

用户："你好"
```json
{"action": "chat", "params": {"message": "你好"}}
```

## 注意
- 搜索关键词必须是英文技术术语
- 如果用户没有指定数量，搜索默认返回5个
- 如果用户没有指定排序，默认按stars排序
- 输出必须是可以被json.loads解析的有效JSON
"""


class ResearcherAgent(GiaAgentBase):
    """
    Researcher Agent

    Role: Professional open-source intelligence researcher
    Task: Understand user intent via LLM, select appropriate tool,
          execute it, and return structured results.
    """

    def __init__(
        self,
        name: str = "Researcher",
        model_name: str = "",
        config: Optional[ConfigManager] = None,
        use_toolkit: bool = True,
        use_mcp: bool = True,
        use_persistent: bool = True,
        db_path: str = "data/app.db",
    ):
        from src.core.prompt_builder import get_system_prompt

        system_prompt = get_system_prompt("researcher")

        super().__init__(
            name=name,
            model_name=model_name,
            system_prompt=system_prompt,
            config=config,
            use_persistent=use_persistent,
            db_path=db_path,
        )

        self.use_toolkit = use_toolkit
        self.use_mcp = use_mcp
        self.use_persistent = use_persistent

        self.github_tool = GitHubTool(config=self.config)

        self.kpi_tracker = KPITracker(self.config)

        self.toolkit = None
        if use_toolkit:
            self.toolkit = get_github_toolkit(config=self.config, use_mcp=use_mcp)
            logger.info("AgentScope Toolkit initialized with GitHub tools")

        # Build dynamic intent prompt from toolkit schemas
        self._dynamic_intent_prompt = self._build_dynamic_intent_prompt()

        logger.info(f"ResearcherAgent '{name}' initialized with model '{model_name}'")

    def _build_dynamic_intent_prompt(self) -> str:
        """Build intent system prompt from actual toolkit schemas."""
        if self.toolkit is None:
            return INTENT_SYSTEM_PROMPT

        # Get toolkit tool descriptions as prompt text
        try:
            schemas = self.toolkit.get_json_schemas()
            tool_names = []
            for s in schemas:
                fn = s.get("function", {})
                tool_names.append(
                    f"- **{fn.get('name', 'unknown')}**: {fn.get('description', '')}"
                )
            tools_section = "\n".join(tool_names)
        except Exception as e:
            logger.warning(f"Failed to build dynamic intent prompt: {e}")
            return INTENT_SYSTEM_PROMPT

        dynamic_prompt = INTENT_SYSTEM_PROMPT.replace(
            "## 可用工具\n",
            f"## 可用工具（动态注册）\n\n{tools_section}\n\n"
        )
        return dynamic_prompt

    # ============================================================
    # Native Function Calling (S3-P1)
    # ============================================================

    MAX_NATIVE_TOOL_CALLS = 5

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-format tool schemas from the toolkit."""
        if self.toolkit is None:
            return []
        return self.toolkit.get_json_schemas()

    def _call_with_native_tools(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 7000,
    ) -> Dict[str, Any]:
        """
        Call the model with native function calling.

        Args:
            messages: Message list (system + history + user)
            max_tokens: Token budget

        Returns:
            Dict with 'text' (str, optional) and 'tool_calls' (list, optional)
        """
        schemas = self._get_tool_schemas()
        model_wrapper = self._get_model_wrapper()

        response = model_wrapper(
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
            tools=schemas if schemas else None,
        )

        # Extract tool calls from response
        tool_calls = model_wrapper.extract_tool_calls(response)

        # Extract text content
        content = self._extract_response_text(response)

        if tool_calls:
            return {"text": None, "tool_calls": tool_calls}
        else:
            return {"text": content, "tool_calls": []}

    def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool call from native function calling.

        Routes tool names to the appropriate execution method.

        Args:
            tool_call: Dict with 'id', 'name', 'input' keys

        Returns:
            Dict with 'tool_call_id', 'name', 'result' keys
        """
        tool_name = tool_call.get("name", "")
        params = tool_call.get("input", {})
        tool_call_id = tool_call.get("id", "")

        logger.info(f"Executing native tool call: {tool_name} with params={params}")

        try:
            result_text = self._dispatch_tool(tool_name, params)
            return {
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "result": result_text,
            }
        except Exception as e:
            logger.error(f"Tool call {tool_name} failed: {e}")
            return {
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "result": f"Error: {e}",
            }

    def _dispatch_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Dispatch a tool call to the appropriate handler.

        Maps toolkit tool names to execution methods.
        """
        # GitHub tool group
        if tool_name == "search_repositories":
            query = params.get("query", "")
            sort = params.get("sort", "stars")
            order = params.get("order", "desc")
            per_page = params.get("per_page", params.get("limit", 5))
            time_range_days = params.get("time_range_days", 0)

            if time_range_days and time_range_days > 0:
                start_date = (
                    datetime.now() - timedelta(days=time_range_days)
                ).strftime("%Y-%m-%d")
                end_date = datetime.now().strftime("%Y-%m-%d")
                query = f"created:{start_date}..{end_date} {query}"

            repos = self.github_tool.search_repositories(
                query=query, sort=sort, order=order, per_page=min(per_page, 100)
            )
            return self._format_search_results(repos, query, per_page)

        elif tool_name == "get_repo_info":
            owner = params.get("owner", "")
            repo = params.get("repo", "")
            return self._execute_get_repo_info({"owner": owner, "repo": repo})

        elif tool_name == "get_readme":
            owner = params.get("owner", "")
            repo = params.get("repo", "")
            readme = self.github_tool.get_readme(owner, repo)
            return self.github_tool.clean_readme_text(readme)[:5000]

        elif tool_name == "get_project_summary":
            owner = params.get("owner", "")
            repo = params.get("repo", "")
            summary = self.github_tool.get_project_summary(
                owner, repo, max_readme_length=params.get("max_readme_length", 3000)
            )
            lines = [
                f"**{summary['full_name']}**",
                f"Stars: {summary['stars']:,} | Forks: {summary['forks']:,}",
                f"Language: {summary['language']}",
                f"Description: {summary['description']}",
            ]
            return "\n".join(lines)

        elif tool_name == "check_rate_limit":
            rate_info = self.github_tool.check_rate_limit()
            if "error" in rate_info:
                return f"Rate limit error: {rate_info['error']}"
            return (
                f"Limit: {rate_info['limit']:,}/hr | "
                f"Remaining: {rate_info['remaining']:,} | "
                f"Authenticated: {'Yes' if rate_info.get('authenticated') else 'No'}"
            )

        # Orphan tool groups
        elif tool_name == "evaluate_code_quality":
            import asyncio
            from src.tools.code_quality_tool import evaluate_code_quality as _eval_cq
            repo_info_json = params.get("repo_info_json", "{}")
            result = asyncio.get_event_loop().run_until_complete(
                _eval_cq(
                    params.get("readme_content", ""),
                    json.loads(repo_info_json) if isinstance(repo_info_json, str) else repo_info_json,
                    use_llm=params.get("use_llm", True),
                )
            )
            if result.success:
                data = result.data
                if isinstance(data, dict) and "report_text" in data:
                    return data["report_text"]
                return str(data)
            return f"Error: {result.error_message}"

        elif tool_name == "scan_security_code":
            import asyncio
            from src.tools.owasp_security_rules import scan_security as _scan_sec
            result = asyncio.get_event_loop().run_until_complete(
                _scan_sec(params.get("file_path", ""), params.get("code_content", ""))
            )
            if result.success:
                data = result.data
                if isinstance(data, dict) and "report_text" in data:
                    return data["report_text"]
                return str(data)
            return f"Error: {result.error_message}"

        elif tool_name == "review_code_changes":
            import asyncio
            from src.tools.pr_review_tool import review_pull_request as _review_pr
            result = asyncio.get_event_loop().run_until_complete(
                _review_pr(
                    params.get("pr_title", ""),
                    params.get("pr_description", ""),
                    params.get("diff_content", ""),
                    use_llm=params.get("use_llm", True),
                )
            )
            if result.success:
                data = result.data
                if isinstance(data, dict) and "report_text" in data:
                    return data["report_text"]
                return str(data)
            return f"Error: {result.error_message}"

        # Fallback: try direct method call on github_tool
        elif hasattr(self.github_tool, tool_name):
            method = getattr(self.github_tool, tool_name)
            if callable(method):
                result = method(**params)
                return str(result)

        # Unknown tool
        return f"Unknown tool: {tool_name}"

    def _format_search_results(
        self, repos: List[Any], query: str, limit: int
    ) -> str:
        """Format search results as markdown."""
        if not repos:
            return f"没有找到与「{query}」相关的仓库。"

        lines = [
            f"## 搜索结果：{query}",
            "",
            f"找到 **{len(repos)}** 个相关仓库：",
            "",
            "| # | 仓库 | Stars | 语言 | 简介 |",
            "|---|------|-------|------|------|",
        ]
        for i, repo in enumerate(repos[:limit], 1):
            desc = repo.description or "*无描述*"
            if len(desc) > 60:
                desc = desc[:57] + "..."
            lines.append(
                f"| {i} | **[{repo.full_name}]({repo.html_url})** "
                f"| {repo.stargazers_count:,} | "
                f"{repo.language or 'N/A'} | {desc} |"
            )
        return "\n".join(lines)

    def reply_with_native_tools(
        self,
        user_query: str,
        analyst=None,
    ) -> str:
        """
        Respond to user query using AgentScope native function calling.

        Flow:
        1. Build messages (system + history + user)
        2. Call model with tool schemas
        3. If model returns tool calls, execute them and loop
        4. If model returns text, return it
        5. Max MAX_NATIVE_TOOL_CALLS iterations

        Args:
            user_query: User's natural language query
            analyst: Optional AnalystAgent (ignored in native mode, kept for compat)

        Returns:
            Formatted response text
        """
        schemas = self._get_tool_schemas()
        if not schemas:
            # No toolkit available, fall back to prompt-based intent
            logger.info("No toolkit schemas, falling back to prompt-based intent")
            return self._reply_with_prompt_based_intent(user_query, analyst=analyst)

        # Build messages
        system_prompt = self.system_prompt
        history = self.memory.get_messages_for_prompt()

        # Build message list for the model
        messages = [{"role": "system", "content": system_prompt}]

        # Add history (last 20 messages to control token count)
        for msg in history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_query})

        # Tool call loop
        for iteration in range(self.MAX_NATIVE_TOOL_CALLS):
            result = self._call_with_native_tools(messages)

            # If text response, we're done
            if result.get("text"):
                return filter_sensitive_output(result["text"])

            # If tool calls, execute them and continue
            tool_calls = result.get("tool_calls", [])
            if tool_calls:
                # Add assistant message with tool calls
                tool_call_blocks = []
                for tc in tool_calls:
                    tool_call_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    })
                messages.append({
                    "role": "assistant",
                    "content": tool_call_blocks,
                })

                # Execute each tool call
                for tc in tool_calls:
                    tool_result = self._execute_tool_call(tc)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": tool_result["result"],
                    })

                    logger.info(
                        f"Tool call result ({tool_result['name']}): "
                        f"{len(str(tool_result['result']))} chars"
                    )

                continue

            # No text and no tool calls — fallback to plain LLM call
            logger.warning("Model returned neither text nor tool calls")
            return self._call_llm(user_query)

        # Exceeded max iterations — generate final summary
        messages.append({
            "role": "user",
            "content": "基于以上工具调用结果，给出简洁的回答。",
        })
        result = self._call_with_native_tools(messages)
        if result.get("text"):
            return filter_sensitive_output(result["text"])
        return "处理完成，但未能生成最终回答。"

    def _reply_with_prompt_based_intent(
        self, user_query: str, analyst=None
    ) -> str:
        """
        Fallback: respond using prompt-based intent understanding.

        This method preserves the original _understand_intent() logic
        for when the toolkit is unavailable.
        """
        logger.info(f"Received query (prompt-based): {user_query}")

        # Step 1: Check if this is a direct repo lookup
        repo_name = self._is_repo_lookup_query(user_query)
        if repo_name:
            repo_result = self._resolve_repo_by_name(repo_name)
            if repo_result:
                return repo_result

        # Step 2: Use LLM to understand intent
        intent = self._understand_intent(user_query)
        action = intent["action"]
        params = intent["params"]

        logger.info(f"Executing action: {action}")

        # Step 3: Route to appropriate handler
        result = None
        success = False
        result_count = 0

        if action == "search_repositories":
            result = self._execute_search(params)
            success = result is not None and "搜索失败" not in result
            result_count = params.get("limit", 5)
        elif action == "get_repo_info":
            result = self._execute_get_repo_info(params)
            success = result is not None and "未找到" not in result
        elif action == "analyze_project":
            result = self._execute_analyze_project(params, analyst=analyst)
            success = result is not None and "失败" not in result
        elif action == "compare_repositories":
            result = self._execute_compare(params, analyst=analyst)
            success = result is not None
        elif action == "chat":
            result = self._call_llm(user_query)
            success = True
        else:
            logger.warning(f"Unknown action: {action}")
            result = self._call_llm(user_query)
            success = True

        # Track researcher KPIs
        self.kpi_tracker.track_researcher_kpis(
            intent_action=action,
            intent_params=params,
            success=success,
            result_count=result_count,
        )

        return result

    def _calculate_trend_score(self, repo) -> float:
        """
        Calculate trend score for a repository (0.0-1.0).

        Composite metric based on:
        - Star count (logarithmic scaling)
        - Fork-to-star ratio (community engagement)
        - Topic count (project categorization)
        - Language presence (language popularity proxy)
        """
        try:
            score = 0.0

            # Star score (0-0.4): logarithmic scaling
            stars = getattr(repo, 'stargazers_count', 0) or 0
            if stars > 0:
                score += min(0.4, 0.4 * (1.0 - 1.0 / (1.0 + stars / 1000.0)))

            # Fork score (0-0.2): fork-to-star ratio
            forks = getattr(repo, 'forks_count', 0) or 0
            if stars > 0 and forks > 0:
                fork_ratio = min(forks / max(stars, 1), 0.5)
                score += 0.2 * (fork_ratio / 0.5)

            # Topic score (0-0.2): more topics = better categorized
            topics = getattr(repo, 'topics', []) or []
            score += 0.2 * min(len(topics) / 10.0, 1.0)

            # Language score (0-0.2): active language presence
            lang = getattr(repo, 'language', '') or ''
            if lang:
                score += 0.1
            watchers = getattr(repo, 'watchers_count', 0) or 0
            if watchers > 0:
                score += 0.1 * min(watchers / max(stars, 1), 1.0)

            return round(min(score, 1.0), 3)
        except Exception as e:
            logger.warning(f"Failed to calculate trend score: {e}")
            return 0.0

    def _calculate_last_commit_days(self, repo) -> int:
        """
        Calculate days since last update (commit/activity).
        Returns -1 if unknown.
        """
        try:
            updated_at = getattr(repo, 'updated_at', None)
            if not updated_at:
                return -1
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            # Strip tzinfo for naive comparison
            if hasattr(updated_at, 'replace') and updated_at.tzinfo is not None:
                updated_at = updated_at.replace(tzinfo=None)
            delta = datetime.now() - updated_at
            return delta.days
        except Exception as e:
            logger.warning(f"Failed to calculate last commit days: {e}")
            return -1

    @trace(name="researcher.understand_intent")
    def _understand_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Use LLM to understand user intent and select the appropriate tool.

        This is the core method that replaces all regex-based parsing.
        The LLM understands the natural language query and outputs a
        structured action + parameters.

        Returns:
            Dict with 'action' and 'params' keys.
            Falls back to {"action": "chat", "params": {"message": user_query}}
            on failure.
        """
        try:
            # Sanitize user input to prevent prompt injection
            safe_query = sanitize_user_input(user_query)

            model_wrapper = self._get_model_wrapper()
            messages = [
                {"name": "system", "content": self._dynamic_intent_prompt, "role": "system"},
                {"name": "user", "content": safe_query, "role": "user"},
            ]
            response = model_wrapper(
                messages=messages,
                max_tokens=512,
                temperature=0.1,  # Low temperature for consistent output
            )
            # Check if the response indicates an API error
            if self._is_response_error(response):
                logger.warning(
                    f"LLM returned API error during intent understanding: "
                    f"{self._extract_response_text(response)[:200]}"
                )
                return {
                    "action": "search_repositories",
                    "params": {"query": user_query, "sort": "stars", "limit": 5},
                }
            content = self._extract_response_text(response).strip()

            # Extract JSON from response
            # Try to find JSON block (```json ... ``` or just {...})
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    content = json_match.group(0)

            intent = json.loads(content)
            action = intent.get("action", "chat")
            params = intent.get("params", {})

            logger.info(f"Intent understood: action='{action}', params={params}")
            return {"action": action, "params": params}

        except Exception as e:
            logger.warning(f"Intent understanding failed: {e}")
            # Instead of falling back to "chat", fall back to "search_repositories"
            # with the raw query — this ensures the user's search intent is still honored
            return {
                "action": "search_repositories",
                "params": {"query": user_query, "sort": "stars", "limit": 5},
            }

    def _execute_search(self, params: Dict[str, Any]) -> str:
        """Execute a search_repositories action"""
        query = params.get("query", "")
        sort = params.get("sort", "stars")
        limit = params.get("limit", 5)
        time_range_days = params.get("time_range_days", 0)

        # Build GitHub search query
        search_query = query
        if time_range_days and time_range_days > 0:
            start_date = (
                datetime.now() - timedelta(days=time_range_days)
            ).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")
            search_query = f"created:{start_date}..{end_date} {query}"

        logger.info(f"Searching: '{search_query}' sort={sort} limit={limit}")

        try:
            repos = self.github_tool.search_repositories(
                query=search_query,
                sort=sort,
                order="desc",
                per_page=min(limit, 100),
            )

            if not repos:
                return f"没有找到与「{query}」相关的仓库。"

            # Build result markdown
            lines = [
                f"## 搜索结果：{query}",
                "",
                f"找到 **{len(repos)}** 个相关仓库：",
                "",
                "| # | 仓库 | Stars | 语言 | 简介 |",
                "|---|------|-------|------|------|",
            ]

            for i, repo in enumerate(repos[:limit], 1):
                desc = repo.description or "*无描述*"
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                lines.append(
                    f"| {i} | **[{repo.full_name}]({repo.html_url})** "
                    f"| {repo.stargazers_count:,} | "
                    f"{repo.language or 'N/A'} | {desc} |"
                )

            return "\n".join(lines)

        except RuntimeError as e:
            logger.error(f"Search failed: {e}")
            return f"搜索失败：{e}"

    def _execute_get_repo_info(self, params: Dict[str, Any]) -> str:
        """Execute a get_repo_info action, with fuzzy matching fallback."""
        owner = params.get("owner", "")
        repo = params.get("repo", "")

        # Try exact match first
        exact_error = None
        try:
            repo_info = self.github_tool.get_repo_info(owner, repo)
            return (
                f"**{repo_info.full_name}**\n"
                f"- Stars: {repo_info.stargazers_count:,}\n"
                f"- Forks: {repo_info.forks_count:,}\n"
                f"- 语言: {repo_info.language or 'N/A'}\n"
                f"- 描述: {repo_info.description or 'N/A'}\n"
                f"- 最后更新: {repo_info.updated_at}\n"
                f"- 地址: {repo_info.html_url}"
            )
        except Exception as e:
            exact_error = str(e)
            logger.info(f"Exact lookup failed for {owner}/{repo}: {e}, "
                        "falling back to search")

        # Fuzzy fallback: search for the repo name
        search_keyword = f"{owner} {repo}".strip()
        if not search_keyword:
            return "请提供仓库名。"

        try:
            repos = self.github_tool.search_repositories(
                query=search_keyword,
                sort="stars",
                order="desc",
                per_page=5,
            )

            if not repos:
                return (
                    f"未找到与「{search_keyword}」相关的仓库。"
                )

            lines = [
                f"未找到精确匹配「{owner}/{repo}」的项目，以下是相关项目：\n"
            ]
            for i, repo_info in enumerate(repos[:5], 1):
                desc = repo_info.description or "*无描述*"
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                lines.append(
                    f"{i}. **[{repo_info.full_name}]({repo_info.html_url})**\n"
                    f"   Stars: {repo_info.stargazers_count:,} | "
                    f"语言: {repo_info.language or 'N/A'}\n"
                    f"   {desc}"
                )
            lines.append("\n请回复序号选择你要查询的项目，或说「分析」+ 项目名进行深度分析。")
            return "\n".join(lines)

        except Exception as e2:
            logger.error(f"Fuzzy search also failed: {e2}")
            return f"获取仓库信息失败：{exact_error}"

    def _execute_analyze_project(
        self, params: Dict[str, Any], analyst=None
    ) -> str:
        """Execute an analyze_project action, with fuzzy matching fallback."""
        owner = params.get("owner", "")
        repo = params.get("repo", "")

        # Try exact match first
        if analyst:
            result = analyst.analyze_project(owner=owner, repo=repo)
            if not result.get("error"):
                analysis = result.get("analysis", {})
                return (
                    f"## 项目分析：{result.get('project', f'{owner}/{repo}')}\n\n"
                    f"- Stars: {result.get('stars', 'N/A')}\n"
                    f"- 语言: {result.get('language', 'N/A')}\n"
                    f"- 核心功能: {analysis.get('core_function', 'N/A')}\n"
                    f"- 技术栈: {analysis.get('tech_stack', {}).get('language', 'N/A')}\n"
                    f"- 推荐意见: {analysis.get('recommendation', 'N/A')}"
                )

        # Fallback to get_repo_info (which has its own fuzzy search)
        logger.info(f"Exact analysis failed for {owner}/{repo}, "
                    "falling back to fuzzy search")
        return self._execute_get_repo_info(params)

    def _execute_compare(
        self, params: Dict[str, Any], analyst=None
    ) -> str:
        """Execute a compare_repositories action"""
        repos = params.get("repositories", [])
        if not repos:
            return "请提供要比较的仓库列表。"

        lines = ["## 项目对比\n"]
        for repo_str in repos:
            parts = repo_str.split("/")
            if len(parts) == 2:
                owner, repo = parts
                info = self._execute_get_repo_info({"owner": owner, "repo": repo})
                lines.append(f"### {repo_str}")
                lines.append(info)
                lines.append("")

        return "\n".join(lines)

    @trace(name="researcher.search_and_analyze")
    def search_and_analyze(
        self,
        query: str,
        sort: str = None,
        order: str = "desc",
        per_page: int = None,
    ) -> Dict[str, Any]:
        """
        Search and analyze GitHub repositories.

        Uses LLM intent understanding to parse the query.
        If sort/per_page are specified externally, they override LLM output.

        Returns:
            Dictionary of search results
        """
        # Use LLM to understand intent
        intent = self._understand_intent(query)
        action = intent["action"]
        params = intent["params"]

        # If external sort/per_page specified, use those
        if sort:
            params["sort"] = sort
        if per_page:
            params["limit"] = per_page

        # Only handle search actions via this method
        if action != "search_repositories":
            # If the intent is not a search, use the default search behavior
            # with the raw query as fallback
            logger.warning(
                f"Intent action is '{action}', expected 'search_repositories'. "
                "Using raw query for search."
            )
            params["query"] = query
            params.setdefault("sort", "stars")
            params.setdefault("limit", per_page or 5)

        search_query = params.get("query", query)
        sort_field = params.get("sort", "stars")
        limit = params.get("limit", 5)

        logger.info(
            f"Original query: {query}"
        )
        logger.info(
            f"Search query: {search_query}, sort={sort_field}, per_page={limit}"
        )

        try:
            repos = self.github_tool.search_repositories(
                query=search_query,
                sort=sort_field,
                order="desc",
                per_page=min(limit, 100),
            )

            result = {
                "query": query,
                "search_query": search_query,
                "total_found": len(repos),
                "repositories": [
                    {
                        "full_name": repo.full_name,
                        "html_url": repo.html_url,
                        "stars": repo.stargazers_count,
                        "language": repo.language,
                        "description": repo.description,
                        "topics": repo.topics,
                        "trend_score": self._calculate_trend_score(repo),
                        "readme_snippet": "",  # Fetched on-demand by AnalystAgent
                        "last_commit_days": self._calculate_last_commit_days(repo),
                        "tags": repo.topics or [],
                    }
                    for repo in repos
                ],
            }

            logger.info(f"Found {len(repos)} repositories")

            set_span_attributes({
                "researcher.query": query,
                "researcher.search_query": search_query,
                "researcher.result_count": len(repos),
                "researcher.total_found": len(repos),
            })

            return result

        except RuntimeError as e:
            logger.error(f"Search failed: {e}")
            return {
                "query": query,
                "search_query": search_query,
                "error": str(e),
                "repositories": [],
            }

    def generate_summary(self, search_result: Dict[str, Any]) -> str:
        """Generate a summary of search results"""
        if search_result.get("error"):
            return f"搜索失败：{search_result['error']}"

        repos = search_result.get("repositories", [])
        if not repos:
            return "未找到匹配的仓库。"

        lines = [
            f"## 搜索结果：{search_result.get('query', 'Unknown')}",
            "",
            f"找到 **{search_result.get('total_found', 0)}** 个相关仓库，以下是 Top {len(repos)}：",
            "",
            "| # | 仓库 | Stars | 语言 | 简介 |",
            "|---|------|-------|------|------|",
        ]

        for i, repo in enumerate(repos, 1):
            desc = repo.get("description", "")
            if desc:
                desc = (desc[:50] + "...") if len(desc) > 50 else desc
                desc = desc.replace("\n", " ")
            else:
                desc = "*无描述*"

            lines.append(
                f"| {i} | **[{repo['full_name']}]({repo['html_url']})** | "
                f"⭐ {repo['stars']:,} | {repo['language'] or 'N/A'} | {desc} |"
            )

        return "\n".join(lines)

    @circuit_breaker_guard
    @trace(name="researcher.reply")
    def reply(self, msg: Union[Msg, str], *args: Any, **kwargs: Any) -> Msg:
        """Respond to user message"""
        if isinstance(msg, str):
            msg = Msg(name="user", content=msg, role="user")

        self._add_to_memory("user", msg.content, name="user")
        response_content = self.reply_to_message(msg.content)
        response = Msg(name=self.name, content=response_content, role="assistant")
        self._add_to_memory("assistant", response_content)
        return response

    def _resolve_repo_by_name(self, name: str) -> Optional[str]:
        """
        Resolve a project name (e.g. 'langchain', 'react') to repo info.

        Tries exact owner/repo match first, then fuzzy search by name.

        Args:
            name: Project name or owner/repo string

        Returns:
            Formatted repo info string, or None if not found
        """
        # Check if it's owner/repo format
        parts = name.split("/")
        if len(parts) == 2:
            owner, repo = parts[0].strip(), parts[1].strip()
            try:
                repo_info = self.github_tool.get_repo_info(owner, repo)
                return (
                    f"**{repo_info.full_name}**\n"
                    f"- Stars: {repo_info.stargazers_count:,}\n"
                    f"- Forks: {repo_info.forks_count:,}\n"
                    f"- 语言: {repo_info.language or 'N/A'}\n"
                    f"- 描述: {repo_info.description or 'N/A'}\n"
                    f"- 地址: {repo_info.html_url}"
                )
            except Exception:
                pass  # Fall through to fuzzy search

        # Fuzzy search: try to find a repo matching the project name
        try:
            repos = self.github_tool.search_repositories(
                query=name,
                sort="stars",
                order="desc",
                per_page=5,
            )
            if repos:
                top = repos[0]
                return (
                    f"**{top.full_name}** (根据名称「{name}」匹配)\n"
                    f"- Stars: {top.stargazers_count:,}\n"
                    f"- 语言: {top.language or 'N/A'}\n"
                    f"- 描述: {top.description or 'N/A'}\n"
                    f"- 地址: {top.html_url}"
                )
        except Exception as e:
            logger.warning(f"Fuzzy repo search failed for '{name}': {e}")

        return None

    def _is_repo_lookup_query(self, query: str) -> Optional[str]:
        """
        Detect if the query looks like a direct repo lookup request.

        Matches patterns like:
        - "langchain/langchain" (owner/repo)
        - "请分析 langchain" (action + project name)
        - "langchain 的 star 数" (project name + question)
        - "django star 多少" (project name + keyword)

        Args:
            query: Sanitized user query

        Returns:
            Extracted repo name string if detected, else None
        """
        query_lower = query.lower()

        # Pattern: owner/repo (GitHub-style path)
        owner_repo_match = re.search(
            r"[\s/]*(?:[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)", query
        )
        if owner_repo_match:
            path = owner_repo_match.group(0).strip().strip("/")
            # Validate it looks like owner/repo (no spaces, 2 parts)
            parts = path.split("/")
            if len(parts) == 2 and all(p.strip() for p in parts):
                return path

        # Pattern: project name followed by star/fork/lang/info questions
        # Handle Chinese-style: no space between name and keyword (e.g. "langchain的star数")
        star_keywords = r"的?[\s]*(?:star|stars|star数|fork|forks|语言|info|信息|介绍|分析|怎么样|如何|好吗|看看)"
        name_match = re.search(
            rf"(?:(?<=[\s(（])|^)([a-zA-Z][a-zA-Z0-9_.-]{{1,40}}){star_keywords}",
            query_lower,
        )
        if name_match:
            name = name_match.group(1)
            # Filter out common words that aren't project names
            common_words = {
                "not", "for", "the", "and", "with", "from", "have", "this",
                "that", "what", "how", "when", "where", "which", "your",
                "about", "请", "一个", "一些",
            }
            if name.lower() not in common_words:
                return name

        return None

    def reply_to_message(self, user_query: str, analyst=None) -> str:
        """
        Respond to user query using native function calling.

        Falls back to prompt-based intent understanding when toolkit is unavailable.

        Args:
            user_query: User's natural language query
            analyst: Optional AnalystAgent for analyze_project action
        """
        logger.info(f"Received query: {user_query}")

        # Sanitize user input to prevent prompt injection
        try:
            user_query = sanitize_user_input(user_query)
        except ValueError as e:
            logger.warning(f"Input blocked: {e}")
            return f"⚠️ {e}"

        # Use native function calling if toolkit is available
        if self.toolkit is not None:
            return self.reply_with_native_tools(user_query, analyst=analyst)

        # Fallback to prompt-based intent understanding
        return self._reply_with_prompt_based_intent(user_query, analyst=analyst)

    def _build_messages(self, user_query: str) -> List[Dict[str, Any]]:
        """Build message history with token budget management"""
        return self._build_messages_with_token_budget(
            system_prompt=self.system_prompt,
            user_query=user_query,
            max_tokens=7000,
        )

    @trace(name="researcher.call_llm")
    def _call_llm(self, user_query: str) -> str:
        """Call LLM to generate a response"""
        try:
            model_wrapper = self._get_model_wrapper()
            messages = self._build_messages(user_query)
            response = model_wrapper(messages=messages)
            content = self._extract_response_text(response)
            # Filter sensitive data from LLM output
            content = filter_sensitive_output(content)
            self._add_to_memory("assistant", content)
            return content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"抱歉，AI 响应失败：{e}"

    def get_status(self) -> Dict[str, Any]:
        """Get Agent status"""
        # Get available tool names from toolkit
        tools_available = []
        if self.toolkit:
            schemas = self.toolkit.get_json_schemas()
            tools_available = [
                s.get('function', {}).get('name', '')
                for s in schemas if s.get('function', {}).get('name')
            ]
        status = {
            "name": self.name,
            "model": self.model_name,
            "memory_size": self.memory.size(),
            "tools_available": tools_available,
            "github_token_configured": bool(self.config.github_token),
            "toolkit_enabled": self.toolkit is not None,
            "mcp_enabled": self.use_mcp,
            "persistent_enabled": self.use_persistent,
            "intent_understanding": "LLM function calling",
            "mcp_tool_names": [
                'get_commit', 'get_file_contents', 'get_label', 'get_latest_release',
                'get_me', 'get_release_by_tag', 'get_tag', 'issue_read',
                'list_branches', 'list_commits', 'list_issues', 'list_pull_requests',
                'list_releases', 'list_tags', 'pull_request_read', 'search_code',
                'search_issues', 'search_pull_requests', 'search_repositories', 'search_users'
            ],
        }
        if self.toolkit:
            status["toolkit_schemas"] = len(schemas)
            mcp_schemas = [s for s in schemas if s.get('function', {}).get('name', '') in status["mcp_tool_names"]]
            status["mcp_tools_count"] = len(mcp_schemas)
        return status

    def get_description(self) -> str:
        """Get ResearcherAgent description"""
        return (
            "专业的开源情报研究员，通过LLM意图理解选择工具并执行GitHub查询。"
        )
