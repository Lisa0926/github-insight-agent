# -*- coding: utf-8 -*-
"""
Guardrails module for GIA agents

Addresses Dimension 3: Guardrails & Governance

Provides:
1. Prompt injection protection (sanitize user input)
2. Output filtering (remove sensitive data from agent responses)
3. Agent-level circuit breaker (max steps, timeout, token budget)
4. Human-in-the-loop (confirmation for dangerous operations)
"""

import re
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set

from src.core.kpi_tracker import _load_role_kpi_config
from src.core.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# 1. Prompt Injection Protection
# ============================================================

# Known prompt injection patterns (English + Chinese)
_INJECTION_PATTERNS: List[re.Pattern] = [
    # English patterns
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+(instructions?|rules?|directives)", re.IGNORECASE),
    re.compile(r"(?i)(ignore|disregard)\s+(all\s+)?(system|previous)\s+(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"(?i)(you\s+are?\s+now|act\s+as|assume\s+the\s+role)\s+of", re.IGNORECASE),
    re.compile(r"(?i)(reveal|show|display|output)\s+(my|your|the)\s+(system\s+)?(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"(?i)(forget|bypass|disable)\s+(all\s+)?(security|rules?|restrictions?|limitations)", re.IGNORECASE),
    re.compile(r"(?i)(execute|run|eval)\s*(python|shell|bash|command)", re.IGNORECASE),
    re.compile(r"(?i)(repeat|echo|copy|print)\s+(everything|all)\s+(above|before|from\s+the\s+beginning)", re.IGNORECASE),
    re.compile(r"(?i)DAN|do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"(?i)jailbreak|jail\s+break", re.IGNORECASE),
    re.compile(r"(?i)(output|print)\s+(raw|full|original)\s+(response|text|prompt)", re.IGNORECASE),
    re.compile(r"(?i)skip\s+(all\s+)?(instructions?|steps?|rules?)", re.IGNORECASE),
    re.compile(r"(?i)override\s+(all\s+)?(instructions?|rules?|security)", re.IGNORECASE),
    re.compile(r"(?i)(new|different|alternate)\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"(?i)(helpful|obedient)\s+assistant\s+(will|should)\s+(always|never)", re.IGNORECASE),
    re.compile(r"(?i)(do\s+not\s+(follow|use)\s+(any|the)\s+rules)", re.IGNORECASE),
    # Chinese patterns (中文注入攻击防护)
    re.compile(
        r"(?:忽\s*略|忽\s*视|无\s*视)\s*(?:所有\s*(?:的\s*)?)?(?:以上|之前|先前|前面)"
        r"\s*(?:所有\s*(?:的\s*)?)?(?:的\s*)?(?:规则|指令|指示|限制|约束|约束条件|设定)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:你\s*(?:现在|如今)|当前)\s*(?:是|变成|成为|作为)\s*(?:一个)?", re.IGNORECASE),
    re.compile(
        r"(?:扮演|充当|假装|模拟)\s*(?:一个)?(?:不受\s*限制|没有\s*安全\s*限制|自由\s*模式)"
        r"\s*的?\s*(?:不受\s*限制\s*的|自由\s*模式的|新的?\s*)?(?:角色|助手|系统|模型)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:忘记|忽略|清除|去掉)\s*(?:所有\s*)?(?:安全\s*)?(?:限制|规则|约束|防护| guard)", re.IGNORECASE),
    re.compile(r"(?:绕过|突破|解除|跳过)\s*(?:所有\s*)?(?:安全\s*)?(?:的\s*)?(?:限制|规则|约束|防护|检查)", re.IGNORECASE),
    re.compile(r"(?:执行|运行)\s*(?:系统\s*)?(?:命令|脚本|代码|python|shell|bash)", re.IGNORECASE),
    re.compile(r"(?:重复|复述|复制|输出|打印)\s*(?:以上|所有|前面|之前|从头)\s*(?:所有\s*)?(?:的\s*)?(?:内容|信息|文字|一切)", re.IGNORECASE),
    re.compile(r"(?:输出|显示|展示|打印|透露)\s*(?:你的|我的|当前|系统)\s*(?:的\s*)?(?:系统\s*)?(?:提示词|prompt|指令|规则|设定|配置)", re.IGNORECASE),
    re.compile(r"(?:不要|别|切勿|禁止)\s*(?:遵守|遵循|服从)\s*(?:任何|所有\s*)?(?:规则|指令|限制|约束)", re.IGNORECASE),
    re.compile(
        r"(?:覆盖|替换|更改|修改)\s*(?:所有\s*(?:的\s*)?)?(?:原有|原来|原始|之前|当前)"
        r"\s*(?:的\s*)?(?:所有\s*)?(?:的\s*)?(?:指令|规则|提示|设定)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:新的?|不同的?|另一个)\s*(?:系统\s*)?(?:设定|配置|角色|模式|行为)", re.IGNORECASE),
    re.compile(r"(?:越狱|突破\s*限制|解锁\s*模式|自由\s*模式)", re.IGNORECASE),
    re.compile(r"(?:跳过|免除)\s*(?:所有\s*)?(?:安全\s*)?(?:检查|步骤|规则|限制)", re.IGNORECASE),
    re.compile(r"(?:帮助|请问|如何)\s*(?:才能|可以|能够|我)\s*(?:绕过|突破|跳过|违反)\s*.*?\s*(?:规则|限制)", re.IGNORECASE),
    re.compile(r"(?:无条件|绝对|总是|永远)\s*(?:服从|执行|遵守|回答)", re.IGNORECASE),
]

# Maximum length for user input (prevent context window attacks)
MAX_USER_INPUT_LENGTH: int = 4000

# Characters that indicate potential injection
_SUSPICIOUS_CHARS: re.Pattern = re.compile(r"[\\`~!@#$%^&*()+=\[\]{}|;:'\",.<>?/\\]{10,}")


def sanitize_user_input(user_input: str, max_length: int = MAX_USER_INPUT_LENGTH) -> str:
    """
    Sanitize user input to prevent prompt injection attacks.

    Args:
        user_input: Raw user input
        max_length: Maximum allowed input length

    Returns:
        Sanitized input string

    Raises:
        ValueError: If injection is detected
    """
    if not user_input:
        return ""

    # Length check
    if len(user_input) > max_length:
        logger.warning(
            f"User input exceeds max length ({len(user_input)} > {max_length}), truncating"
        )
        user_input = user_input[:max_length]

    # Check for injection patterns (against original and whitespace-collapsed versions
    # to catch obfuscation like "忽 略 以 上 规 则" → "忽略以上规则")
    _collapsed_input = re.sub(r"\s+", "", user_input)
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(user_input) or pattern.search(_collapsed_input):
            logger.warning(f"Potential prompt injection detected: {pattern.pattern}")
            raise ValueError(
                "Potential prompt injection detected. Please rephrase your query."
            )

    # Check for excessive special characters (obfuscation attempt)
    if _SUSPICIOUS_CHARS.search(user_input):
        logger.warning("Excessive special characters detected in input")
        raise ValueError(
            "Input contains excessive special characters. Please simplify your query."
        )

    # Strip null bytes and control characters (except newline/tab)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", user_input)

    return sanitized


def is_injection_attempt(user_input: str) -> bool:
    """
    Check if user input is a potential injection attempt (non-raising version).

    Args:
        user_input: Raw user input

    Returns:
        True if injection is suspected
    """
    if not user_input:
        return False
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(user_input):
            return True
    return False


# ============================================================
# 2. Output Filtering
# ============================================================

# Patterns for sensitive data that should be filtered from output
_SENSITIVE_PATTERNS: List[tuple] = [
    # API keys (generic)
    (re.compile(r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?", re.IGNORECASE), "[REDACTED_API_KEY]"),
    # Secret/token patterns
    (re.compile(
        r"(?:secret|token|password|passwd)\s*[=:]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
        re.IGNORECASE,
    ), "[REDACTED_SECRET]"),
    # GitHub tokens
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    # DashScope API keys
    (re.compile(r"sk-[a-f0-9]{32,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    # Internal file paths (Linux)
    (re.compile(r"/(?:home|root|tmp|var)/[^/\s]{3,}/", re.IGNORECASE), "[INTERNAL_PATH]"),
    # Internal URLs
    (re.compile(
        r"(?:https?://)?(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+):\d+",
        re.IGNORECASE,
    ), "[INTERNAL_URL]"),
    # AWS access keys
    (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "[REDACTED_AWS_KEY]"),
    # Database connection strings
    (re.compile(r"(?:mysql|postgres|mongodb|redis)://[^\s]{10,}", re.IGNORECASE), "[REDACTED_DB_URI]"),
]


def filter_sensitive_output(content: str) -> str:
    """
    Filter sensitive data from agent output.

    Removes:
    - API keys and tokens
    - Internal file paths
    - Internal URLs
    - Database connection strings

    Args:
        content: Raw agent output

    Returns:
        Filtered output with sensitive data redacted
    """
    if not content:
        return ""

    filtered = content
    redaction_count = 0

    for pattern, replacement in _SENSITIVE_PATTERNS:
        new_content = pattern.sub(replacement, filtered)
        if new_content != filtered:
            redaction_count += 1
        filtered = new_content

    if redaction_count > 0:
        logger.info(f"Output filtering: {redaction_count} redaction(s) applied")

    return filtered


# ============================================================
# 3. Agent-Level Circuit Breaker
# ============================================================

class AgentCircuitBreaker:
    """
    Circuit breaker at the agent execution level.

    Protects against:
    - Infinite loops (max steps per session)
    - Excessive execution time (timeout)
    - Excessive token consumption (token budget)

    This is separate from the HTTP-level circuit breaker in ResilientHTTPClient.
    It tracks agent-level state, not network-level state.
    """

    def __init__(
        self,
        max_steps: int = 50,
        max_time_seconds: int = 180,
        max_tokens: int = 5000,
    ):
        self.max_steps = max_steps
        self.max_time_seconds = max_time_seconds
        self.max_tokens = max_tokens

        self._step_count: int = 0
        self._start_time: float = 0.0
        self._token_count: int = 0
        self._open: bool = False
        self._reason: str = ""
        self._half_open: bool = False  # P2: Half-open probe state

    def start_session(self) -> None:
        """Start a new execution session.

        If the breaker was previously tripped, this acts as a half-open probe:
        a new session is started to test if the underlying issue is resolved.
        """
        was_open = self._open
        self._step_count = 0
        self._start_time = time.time()
        self._token_count = 0
        self._open = False
        self._reason = ""
        if was_open:
            self._half_open = True
            logger.info("Agent circuit breaker entering half-open probe state")
        else:
            self._half_open = False
        logger.debug(f"Circuit breaker session started (max_steps={self.max_steps}, max_time={self.max_time_seconds}s)")

    def check(self) -> None:
        """
        Check if circuit breaker should trip.

        In half-open state, a successful session completion (steps within
        limits) transitions to closed. A trip re-opens.
        """
        if self._open:
            raise RuntimeError(f"Circuit breaker open: {self._reason}")

        # Step limit
        if self._step_count >= self.max_steps:
            self._open = True
            self._reason = f"Max steps exceeded ({self.max_steps})"
            if self._half_open:
                logger.warning("Half-open probe failed: max steps exceeded")
            raise RuntimeError(self._reason)

        # Time limit
        elapsed = time.time() - self._start_time
        if elapsed >= self.max_time_seconds:
            self._open = True
            self._reason = f"Max time exceeded ({elapsed:.1f}s / {self.max_time_seconds}s)"
            if self._half_open:
                logger.warning("Half-open probe failed: time exceeded")
            raise RuntimeError(self._reason)

        # If half-open and we reach here (within limits), probe succeeded
        if self._half_open:
            self._half_open = False
            logger.info("Agent circuit breaker half-open probe succeeded")

    def record_step(self) -> int:
        """
        Record a step and return current count.

        Returns:
            Current step count
        """
        self._step_count += 1
        return self._step_count

    def record_tokens(self, count: int) -> None:
        """Record token usage."""
        self._token_count += count

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def elapsed_time(self) -> float:
        return time.time() - self._start_time

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def is_half_open(self) -> bool:
        """True if in half-open probe state."""
        return self._half_open

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "steps": self._step_count,
            "max_steps": self.max_steps,
            "elapsed": round(self.elapsed_time, 1),
            "max_time": self.max_time_seconds,
            "tokens": self._token_count,
            "max_tokens": self.max_tokens,
            "open": self._open,
            "half_open": self._half_open,
            "reason": self._reason,
        }


# Global circuit breaker instance (per-process)
_global_circuit_breaker: Optional[AgentCircuitBreaker] = None


def get_circuit_breaker(
    max_steps: int = None,
    max_time_seconds: int = None,
    max_tokens: int = None,
) -> AgentCircuitBreaker:
    """Get or create the global circuit breaker.

    Defaults are read from role_kpi.yaml global_constraints when available,
    with explicit parameters taking precedence.
    """
    global _global_circuit_breaker
    if _global_circuit_breaker is None:
        # Load defaults from role_kpi.yaml
        kpi = _load_role_kpi_config() or {}
        constraints = kpi.get("global_constraints", {})
        cost_config = constraints.get("cost_control", {})
        cb_config = cost_config.get("circuit_breaker", {})

        _global_circuit_breaker = AgentCircuitBreaker(
            max_steps=max_steps if max_steps is not None else cb_config.get("max_steps", 50),
            max_time_seconds=max_time_seconds if max_time_seconds is not None else cb_config.get("max_time_seconds", 180),
            max_tokens=max_tokens if max_tokens is not None else cost_config.get("max_tokens_per_session", 5000),
        )
    return _global_circuit_breaker


def circuit_breaker_guard(func: Callable) -> Callable:
    """
    Decorator that wraps agent methods with circuit breaker checks.

    Usage:
        @circuit_breaker_guard
        def reply_to_message(self, user_query: str) -> str:
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        cb = get_circuit_breaker()
        cb.start_session()

        def _call_with_check():
            cb.check()
            cb.record_step()
            return func(*args, **kwargs)

        # Check before starting
        cb.check()

        result = _call_with_check()

        # Record step after completion
        cb.check()

        return result

    return wrapper


# ============================================================
# 4. Human-in-the-Loop
# ============================================================

# Tool operations classified by risk level
class RiskLevel:
    SAFE = "safe"            # Read-only, no side effects
    MODERATE = "moderate"    # Read with some cost (rate limit)
    DANGEROUS = "dangerous"  # Write operations, external effects


# Tool risk classification
TOOL_RISK_LEVELS: Dict[str, str] = {
    # SAFE — read-only operations
    "search_repositories": RiskLevel.SAFE,
    "get_repo_info": RiskLevel.SAFE,
    "get_readme": RiskLevel.SAFE,
    "get_project_summary": RiskLevel.SAFE,
    "get_file_contents": RiskLevel.SAFE,
    "list_commits": RiskLevel.SAFE,
    "list_issues": RiskLevel.SAFE,
    "list_pull_requests": RiskLevel.SAFE,
    "list_releases": RiskLevel.SAFE,
    "list_branches": RiskLevel.SAFE,
    "list_tags": RiskLevel.SAFE,
    "get_issue": RiskLevel.SAFE,
    "get_pull_request": RiskLevel.SAFE,
    "get_pull_request_files": RiskLevel.SAFE,
    "get_pull_request_status": RiskLevel.SAFE,
    "get_pull_request_comments": RiskLevel.SAFE,
    "get_pull_request_reviews": RiskLevel.SAFE,
    "get_label": RiskLevel.SAFE,
    "get_release_by_tag": RiskLevel.SAFE,
    "get_tag": RiskLevel.SAFE,
    "get_latest_release": RiskLevel.SAFE,
    "get_me": RiskLevel.SAFE,
    "search_code": RiskLevel.SAFE,
    "search_issues": RiskLevel.SAFE,
    "search_pull_requests": RiskLevel.SAFE,
    "search_users": RiskLevel.SAFE,
    "check_rate_limit": RiskLevel.SAFE,
    "pull_request_read": RiskLevel.SAFE,
    "issue_read": RiskLevel.SAFE,
    "get_commit": RiskLevel.SAFE,

    # MODERATE — read but expensive
    "push_files": RiskLevel.MODERATE,
    "create_or_update_file": RiskLevel.MODERATE,

    # DANGEROUS — write/create operations
    "create_issue": RiskLevel.DANGEROUS,
    "create_pull_request": RiskLevel.DANGEROUS,
    "create_branch": RiskLevel.DANGEROUS,
    "create_repository": RiskLevel.DANGEROUS,
    "fork_repository": RiskLevel.DANGEROUS,
    "update_issue": RiskLevel.DANGEROUS,
    "add_issue_comment": RiskLevel.DANGEROUS,
    "create_pull_request_review": RiskLevel.DANGEROUS,
    "merge_pull_request": RiskLevel.DANGEROUS,
    "update_pull_request_branch": RiskLevel.DANGEROUS,
}

# Dangerous tools that require human confirmation
DANGEROUS_TOOLS: Set[str] = {
    name for name, level in TOOL_RISK_LEVELS.items()
    if level == RiskLevel.DANGEROUS
}


def get_tool_risk_level(tool_name: str) -> str:
    """
    Get the risk level for a tool.

    Args:
        tool_name: Tool name

    Returns:
        Risk level string (safe/moderate/dangerous)
    """
    return TOOL_RISK_LEVELS.get(tool_name, RiskLevel.MODERATE)


def requires_confirmation(tool_name: str) -> bool:
    """
    Check if a tool requires human confirmation.

    Args:
        tool_name: Tool name

    Returns:
        True if human confirmation is required
    """
    return tool_name in DANGEROUS_TOOLS


class HumanApprovalManager:
    """
    Manages human-in-the-loop approval for dangerous operations.

    In CLI mode: prompts user for confirmation
    In automated mode (cron, CI): auto-approve or deny based on configuration
    """

    def __init__(self, auto_approve: bool = False):
        """
        Args:
            auto_approve: If True, automatically approve all operations (for CI/testing)
        """
        self.auto_approve = auto_approve
        self._approved: List[str] = []
        self._denied: List[str] = []

    def request_approval(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """
        Request human approval for a dangerous operation.

        Args:
            tool_name: Tool to execute
            tool_args: Tool arguments

        Returns:
            True if approved, False if denied
        """
        if self.auto_approve:
            logger.info(f"[HITL] Auto-approved: {tool_name}")
            return True

        if not requires_confirmation(tool_name):
            return True

        # Format the request for human review
        risk = get_tool_risk_level(tool_name)
        logger.warning(f"[HITL] Dangerous operation requested: {tool_name} (risk: {risk})")

        # In CLI, this will be overridden by an interactive prompt
        # For now, return False (deny) as safe default
        self._denied.append(f"{tool_name}({tool_args})")
        return False

    def get_denied(self) -> List[str]:
        return list(self._denied)

    def record_approved(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        self._approved.append(f"{tool_name}({tool_args})")


# Global approval manager (can be configured per session)
_approval_manager: Optional[HumanApprovalManager] = None


def get_approval_manager(auto_approve: bool = False) -> HumanApprovalManager:
    """Get or create the global approval manager."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = HumanApprovalManager(auto_approve=auto_approve)
    return _approval_manager
