# ADLC 阶段二改进报告（实施）

**日期**: 2026/05/07
**阶段**: P0 + P1 + P2 + P3 改进实施
**评估报告**: `ADLC_PHASE2_EVALUATION_20260507.md`
**遗留改进来源**: `ADLC_PHASE2_REASSESSMENT_20260507.md`

---

## 改进总览

| 优先级 | 改进项 | 状态 | 涉及文件 |
|--------|--------|------|----------|
| P0-1 | BaseTool 统一协议 | ✅ 已完成 | `src/core/tool_base.py` (新建), `src/tools/github_tool.py` |
| P0-2 | 统一 ToolResponse 适配层 | ✅ 已完成 | `src/tools/github_toolkit.py` |
| P0-3 | Orphan 工具注册到 Toolkit | ✅ 已完成 | `src/tools/github_toolkit.py` |
| P0-4 | 主循环打通 — 动态 Intent Prompt | ✅ 已完成 | `src/agents/researcher_agent.py` |
| P1-5 | Token 计数工具 | ✅ 已完成 | `src/core/token_utils.py` (新建), `src/agents/base_agent.py` |
| P1-6 | 工具协议 — BaseTool 实现 | ✅ 已完成 | `src/core/tool_base.py`, `src/tools/github_tool.py` |
| P2-1 | MCP 连接健壮性增强 | ✅ 已完成 | `src/github_mcp/github_mcp_client.py` |
| P2-2 | 半开熔断器 | ✅ 已完成 | `src/core/resilient_http.py`, `src/core/guardrails.py` |
| P2-3 | 跨会话记忆 | ✅ 已完成 | `src/core/agentscope_persistent_memory.py`, `src/cli/app.py` |
| P2-4 | 反馈→提示注入 | ✅ 已完成 | `src/core/feedback.py`, `src/core/prompt_builder.py` |
| S3-P1 | AgentScope 原生 Function Calling | ✅ 已完成 | `src/core/dashscope_wrapper.py`, `src/agents/researcher_agent.py` |
| S3-P2 | Tool→Tool 编排 | ✅ 已完成 | `src/core/tool_orchestrator.py` (新建) |
| S3-P2 | 记忆跨层数据流 | ✅ 已完成 | `src/core/unified_memory.py` (新建) |

---

## P0 改进详情

### P0-1: BaseTool 统一协议

**新建**: `src/core/tool_base.py`

定义了 `BaseTool` ABC，提供统一的工具接口协议：

```python
class BaseTool(ABC):
    @abstractmethod
    def get_name(self) -> str: ...
    @abstractmethod
    def get_description(self) -> str: ...
    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]: ...
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any: ...
    def validate_input(self, input_data: Dict) -> bool: ...  # JSON Schema 校验
    def get_json_schema(self) -> Dict[str, Any]: ...  # Function-call 格式
```

附加辅助函数：`tools_to_schemas()`、`tools_to_prompt_text()`

**测试**: `tests/test_tool_base.py` — 11 个测试用例

### P0-2: 统一 ToolResponse 适配层

**修改**: `src/tools/github_toolkit.py`

问题：Pydantic `ToolResponse` 与 AgentScope `ToolResponse` 不兼容。

方案：在 orphan 工具注册时使用 `_adapt_pydantic_to_agentscope()` 适配函数，将 Pydantic `ToolResponse` 的 `.success`、`.data`、`.error_message` 字段转换成 AgentScope 的 `ToolResponse(content=[...])` 格式。

### P0-3: Orphan 工具注册到 Toolkit

**修改**: `src/tools/github_toolkit.py`

新增 3 组 orphan 工具注册：

| 工具名 | 底层函数 | 参数 |
|--------|----------|------|
| `evaluate_code_quality` | `CodeQualityScorer.score()` | `readme, repo_info_json, use_llm` |
| `scan_security_code` | `OWASPRuleEngine.scan()` | `file_path, code_content` |
| `review_code_changes` | `PRReviewer.review()` | `pr_title, pr_description, diff_content, use_llm` |

每个工具使用闭包 + asyncio 事件循环执行异步函数，返回 AgentScope `ToolResponse`。

### P0-4: 主循环打通 — 动态 Intent Prompt

**修改**: `src/agents/researcher_agent.py`

- 新增 `_build_dynamic_intent_prompt()` 方法：从 Toolkit 的 `get_json_schemas()` 动态构建 intent prompt
- `_understand_intent()` 使用动态 prompt 替代硬编码 `INTENT_SYSTEM_PROMPT`
- LLM 可以看到实际注册的工具列表

---

## P1 改进详情

### P1-5: Token 计数工具

**新建**: `src/core/token_utils.py`

提供 token 级别的内容预算管理能力：

```python
def count_tokens(text: str, encoding=None) -> int
def truncate_to_tokens(text: str, max_tokens: int, encoding=None) -> str  # 二分查找截断
def estimate_messages_tokens(messages: list, encoding=None) -> int
```

使用 tiktoken `cl100k_base` 编码（兼容 qwen 模型）。

**测试**: `tests/test_token_utils.py` — 14 个测试用例

**集成**: `src/agents/base_agent.py` 新增 `_build_messages_with_token_budget()` 方法，支持：
- 自动估算 messages token 数
- 超出预算时从前截断历史
- 最小保留 recent_messages 数量

### P1-6: LLM 摘要压缩

**修改**: `src/core/conversation.py`、`src/core/agentscope_memory.py`

- 两个模块的 `_generate_summary()` 方法改为先尝试调用 LLM 生成结构化摘要
- LLM 失败时回退到规则提取（提取 user/assistant 消息片段）
- 通过 `llm_caller` 参数注入 LLM 提供商

### P1-7: 工具协议

`GitHubTool` 实现 `BaseTool` 协议，提供 `get_name()`, `get_description()`, `get_input_schema()`, `execute()`, `get_json_schema()` 方法。

---

## P2 改进详情

### P2-1: MCP 连接健壮性增强

**修改**: `src/github_mcp/github_mcp_client.py`

| 改进 | 说明 |
|------|------|
| `get_available_tools()` | 返回 MCP server 的真实工具列表（从 `_cached_tools` 缓存或同步 `list_tools()` 获取） |
| `connected` property | 同时检查父类 `is_connected` 标志和 session 存活状态 |
| `connect_with_retry()` | 指数退避重试（默认 3 次尝试，1s 基础延迟） |
| `cached_tool_call()` | 内存缓存 MCP 工具调用结果（5 分钟 TTL） |

### P2-2: 半开熔断器

**修改**: `src/core/resilient_http.py`, `src/core/guardrails.py`

HTTP 熔断器和 Agent 熔断器均增加 true half-open 探测：

**HTTP Circuit Breaker** (`ResilientHTTPClient`):
- 新增 `_half_open` / `_half_open_allowed` 状态标志
- 超时后进入 half-open，允许一个探测请求通过
- 探测成功 → 关闭熔断器
- 探测失败 → 重新打开熔断器

**Agent Circuit Breaker** (`AgentCircuitBreaker`):
- 新增 `_half_open` 标志和 `is_half_open` property
- `start_session()` 在熔断后触发半开探测
- 新 session 步数/时间达标 → 探测成功，关闭熔断器
- 否则 → 再次熔断
- `get_state()` 输出增加 `half_open` 字段

### P2-3: 跨会话记忆

**修改**: `src/core/agentscope_persistent_memory.py`, `src/cli/app.py`

- `PersistentMemory.get_messages_summary(max_messages)` — 返回压缩摘要 + 最近 N 条对话的格式化字符串
- CLI `print_welcome()` 新增 `_show_cross_session_summary()` — 启动时加载上次会话摘要，在黄色面板显示

### P2-4: 反馈→提示注入

**修改**: `src/core/feedback.py`, `src/core/prompt_builder.py`

- `FeedbackCollector.get_positive_feedback_patterns(limit)` — 从 `good` 反馈中提取去重原因字符串
- `get_system_prompt()` 新增 `feedback_patterns` 参数，注入为「用户偏好（历史正向反馈）」段落

---

---

## S3-P1: AgentScope 原生 Function Calling

**修改文件**: `src/core/dashscope_wrapper.py`, `src/agents/researcher_agent.py`

### DashScopeWrapper 升级

- 新增 `tools` 参数支持：`__call__(messages, tools=...)` 传递 OpenAI 格式工具 schema
- 解析 DashScope API 返回的 `tool_calls` 字段，构建 `ToolUseBlock` 内容
- 新增 `extract_tool_calls(response)` 方法：从 ChatResponse 提取工具调用列表
- 新增 `has_tool_calls(response)` 方法：快速检查是否包含工具调用

### ResearcherAgent 升级

- 新增 `_call_with_native_tools()`：传递工具 schema 给模型，解析 ToolUseBlock 响应
- 新增 `_execute_tool_call()` + `_dispatch_tool()`：路由工具调用到对应的执行方法
- 新增 `_format_search_results()`：格式化搜索结果为 Markdown
- 新增 `reply_with_native_tools()`：原生 Function Calling 主循环（最多 5 次迭代）
- 新增 `_reply_with_prompt_based_intent()`：保留原有 prompt-based intent 理解作为 fallback
- 改造 `reply_to_message()`：有 toolkit 时用原生 function calling，无 toolkit 时回退到 prompt-based

**兼容**: 原有 `_understand_intent()`、`_execute_search()` 等方法全部保留作为 fallback 路径。

---

## S3-P2: Tool→Tool 编排

**新建文件**: `src/core/tool_orchestrator.py`

### 核心功能

- `ToolOrchestrator` 类：管理多步工具串联管道
- `_resolve_params()`：支持 `{key}` 和 `{key|default}` 占位符从上下文自动解析
- `_evaluate_condition()`：支持 `.exists` 条件跳过不满足的步骤
- `execute_pipeline(name, params)`：执行预定义管道
- `execute_tool_chain(steps, context)`：执行自定义步骤链
- `register_pipeline(name, steps)`：注册自定义管道

### 预定义管道

| 管道名 | 步骤 | 说明 |
|--------|------|------|
| `repo_analysis` | get_repo_info → get_readme → evaluate_code_quality | 项目全面分析 |
| `search_and_analyze` | search_repositories → get_repo_info | 搜索并分析首个结果 |
| `security_scan` | get_readme → get_repo_info → scan_security_code | 安全扫描 |
| `pr_review` | review_code_changes | PR 自动审查 |

### 上下文传递

每一步的结果自动存入上下文（通过 `output_key` 或 `result_N`），后续步骤通过 `{result.N}` 或 `{output_key}` 引用。

---

## S3-P2: 记忆跨层数据流

**新建文件**: `src/core/unified_memory.py`

### 核心功能

- `UnifiedMemory` 类：聚合 PersistentMemory + ConversationManager + FeedbackCollector
- `record_interaction()`：一次性写入所有记忆层（persistent + conversation + tool results）
- `get_context()`：聚合所有层的上下文（persistent summary + conversation context + feedback patterns + stats）
- `get_feedback_patterns()`：提取正向反馈模式用于 prompt 注入
- `get_cross_session_context()`：跨会话上下文聚合（CLI 启动时显示）
- `search_relevant(query)`：跨层搜索（persistent + conversation + feedback）
- `get_stats()`：所有层的统计聚合

### 跨层数据流

```
UnifiedMemory
  ├─ PersistentMemory (SQLite — 长期存储)
  ├─ ConversationManager (LLM 摘要 — 短期压缩)
  └─ FeedbackCollector (SQLite — 用户偏好)

record_interaction() → 写入所有层
get_context() → 聚合所有层
search_relevant() → 跨层检索
```

---

## 测试覆盖

| 测试文件 | 测试内容 | 用例数 |
|----------|----------|--------|
| `tests/test_tool_base.py` | BaseTool 协议、validate_input、GitHubTool 实现 | 11 |
| `tests/test_token_utils.py` | count_tokens、truncate_to_tokens | 14 |
| `tests/test_llm_compression.py` | LLM 摘要生成、回退逻辑 | 6 |
| `tests/test_orphan_tools.py` | Orphan 工具注册 + Toolkit 集成 | 8 |
| `tests/test_github_toolkit.py` | Toolkit 创建、singleton | 7 |
| `tests/test_coverage_boost.py` | OWASP、PR Review、GitHubTool execute | 17 |
| `tests/test_p2_improvements.py` | MCP 健壮性、熔断器、跨会话记忆、反馈注入 | 20 |
| `tests/test_s3_native_function_calling.py` | DashScopeWrapper 工具调用、ResearcherAgent 路由 | 14 |
| `tests/test_tool_orchestrator.py` | 管道执行、占位符解析、条件跳过、错误恢复 | 17 |
| `tests/test_unified_memory.py` | 跨层记录、上下文聚合、搜索、统计 | 13 |
| **总计** | | **127** |

**全量测试**: 678 用例全部通过，无回归。覆盖率 92%。

---

## 文件变更统计

| 类别 | 新建文件 | 修改文件 | 新增代码行 |
|------|----------|----------|-----------|
| Core | 4 (`token_utils.py`, `tool_base.py`, `tool_orchestrator.py`, `unified_memory.py`) | 10 | +2200+ |
| Tests | 9 | 1 (`test_nl_understanding.py`) | +790+ |
| CLI | 0 | 1 | +20 |
| MCP | 0 | 1 | +139 |

---

## 验证

```bash
# 全量测试
python3 -m pytest tests/ --tb=short -q
# 结果: 678 passed

# 覆盖率
python3 -m pytest tests/ --cov=src --cov-fail-under=80 -q
# 结果: 92% coverage
```
