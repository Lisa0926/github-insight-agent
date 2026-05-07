# ADLC 阶段三改进报告（实施）

**日期**: 2026/05/07
**阶段**: S3-P1 + S3-P2 改进实施
**来源**: `ADLC_PHASE2_REASSESSMENT_20260507.md` 遗留改进项

---

## 改进总览

| 优先级 | 改进项 | 状态 | 涉及文件 |
|--------|--------|------|----------|
| S3-P1 | AgentScope 原生 Function Calling | ✅ 已完成 | `src/core/dashscope_wrapper.py`, `src/agents/researcher_agent.py` |
| S3-P2 | Tool→Tool 编排 | ✅ 已完成 | `src/core/tool_orchestrator.py` (新建) |
| S3-P2 | 记忆跨层数据流 | ✅ 已完成 | `src/core/unified_memory.py` (新建) |

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
| `tests/test_s3_native_function_calling.py` | DashScopeWrapper 工具调用、ResearcherAgent 路由 | 14 |
| `tests/test_tool_orchestrator.py` | 管道执行、占位符解析、条件跳过、错误恢复 | 17 |
| `tests/test_unified_memory.py` | 跨层记录、上下文聚合、搜索、统计 | 13 |
| **总计** | | **44** |

**全量测试**: 678 用例全部通过，无回归。覆盖率 92%。

---

## 文件变更统计

| 类别 | 新建文件 | 修改文件 | 新增代码行 |
|------|----------|----------|-----------|
| Core | 2 (`tool_orchestrator.py`, `unified_memory.py`) | 2 (`dashscope_wrapper.py`, `researcher_agent.py`) | +1200+ |
| Tests | 3 | 1 (`test_nl_understanding.py`) | +300+ |

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
