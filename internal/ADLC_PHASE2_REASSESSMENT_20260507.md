# GIA ADLC 阶段二 Reassessment — 认知架构与工具集成

**日期**: 2026-05-07
**项目版本**: Sprint 7 (P0+P1+P2 改进完成后)
**评估报告原始**: `ADLC_PHASE2_EVALUATION_20260507.md`
**改进报告**: `ADLC_PHASE2_IMPROVEMENTS_20260507.md`
**测试总数**: 634（全通过），覆盖率 80%+

---

## 改进对照总览

| 原始问题 | 改进措施 | 改进前评分 | 改进后评分 |
|----------|----------|-----------|-----------|
| 上下文压缩质量差（纯字符串截断） | LLM 摘要 + 规则回退（conversation.py, agentscope_memory.py） | ★★ | ★★★★ |
| 无 Token 预算感知 | tiktoken 集成：count_tokens, truncate_to_tokens, _build_messages_with_token_budget() | ★ | ★★★★ |
| 跨会话记忆缺失 | PersistentMemory.get_messages_summary() + CLI 启动自动加载 | ★ | ★★★ |
| 反馈→记忆闭环断裂 | get_positive_feedback_patterns() + _append_feedback_patterns() 注入 prompt | ★★ | ★★★ |
| 无 BaseTool 统一协议 | src/core/tool_base.py: BaseTool ABC + validate_input + get_json_schema | ★ | ★★★★ |
| AgentScope Toolkit 闲置 | ResearcherAgent._build_dynamic_intent_prompt() 注入注册工具列表 | ★★ | ★★★★ |
| Orphan 工具未注册 | evaluate_code_quality, scan_security_code, review_code_changes 注册到 Toolkit | ★★ | ★★★★ |
| ToolResponse 不兼容 | _adapt_pydantic_to_agentscope() 适配层 | ★★ | ★★★ |
| MCP 工具枚举无效 | get_available_tools() 返回真实工具列表 | ★★ | ★★★★ |
| MCP 连接状态检查无效 | connected property 验证双标志 | ★★ | ★★★★ |
| MCP 无重试/缓存 | connect_with_retry() + cached_tool_call() | ★★ | ★★★★ |
| 半开熔断器缺失 | HTTP + Agent 双熔断器 true half-open 探测 | ★★★ | ★★★★★ |

---

## 维度 1：记忆设计（Memory Design）

### 1a. 短期记忆（上下文窗口管理）

| 层次 | 改进前 | 改进后 | 评分 |
|------|--------|--------|------|
| **ConversationManager** | 纯字符串截断 `content[:100]` | LLM 摘要生成 + 规则回退，`llm_caller` 参数注入 | ★★★★ |
| **AgentScopeMemory** | 同 ConversationManager（规则提取） | LLM 摘要 + 规则回退，`_llm_caller` 参数 | ★★★★ |
| **PersistentMemory** | 规则提取摘要，仅写入不读取 | 新增 `get_messages_summary()` 支持跨会话加载 | ★★★★ |
| **Token 预算感知** | tiktoken 已装未用 | `src/core/token_utils.py`: count_tokens, truncate_to_tokens, estimate_messages_tokens | ★★★★ |
| **上下文注入** | 纯字符串拼接，无预算控制 | `_build_messages_with_token_budget()` (base_agent.py)，ResearcherAgent._build_messages() 已集成，max_tokens=7000 | ★★★★ |
| **跨会话记忆** | 每次 CLI 会话从零开始 | CLI `print_welcome()` 自动加载上次会话摘要并显示 | ★★★ |

**数据流变化：**

改进前：
```
用户输入 → GiaAgentBase
             ├→ PersistentMemory (仅写入)
             └→ ConversationManager (仅写入)
```

改进后：
```
用户输入 → GiaAgentBase
             ├→ PersistentMemory (读写 — get_messages_summary 跨会话加载)
             ├→ _build_messages_with_token_budget() (token 预算控制)
             └→ ConversationManager (LLM 摘要 + 规则回退)

反馈数据 → FeedbackCollector.get_positive_feedback_patterns() → prompt_builder 注入
```

**评分**: ★★ → ★★★★（+2 级）

### 1b. 长期记忆（向量/语义/RAG）

| 能力 | 状态 | 说明 | 评分 |
|------|------|------|------|
| **向量数据库** | ❌ 未实现 | 与阶段二评估结论一致：GIA 为结构化数据分析工具，RAG 不适用 | ★ |
| **结构化持久化** | ✅ SQLite（PersistentMemory + feedback + llm_cache） | 满足非 RAG 场景的记忆需求 | ★★★★ |

**评分**: ★ → ★★★★（结构化持久化层面），RAG 仍为 ★（有意不实现）

### 1c. 记忆生命周期

| 特征 | 改进前 | 改进后 | 评分 |
|------|--------|--------|------|
| **LLM 缓存** | TTL 缓存（1h JSONL），策略决策和充分性检查已接入 | 无变化 | ★★★★ |
| **持久化存储** | SQLite + JSONL 各用各的 | 无变化 | ★★★ |
| **反馈→提示注入** | 仅统计，不注入提示 | get_positive_feedback_patterns() + _append_feedback_patterns() 注入系统提示 | ★★★ |
| **跨会话摘要** | 无 | PersistentMemory.get_messages_summary() 返回压缩摘要+最近对话 | ★★★ |

**评分**: ★★ → ★★★（+1 级）

---

## 维度 2：工具抽象（Tool Abstraction）

### 2a. 工具定义与封装

| 工具模块 | 改进前 | 改进后 | 评分 |
|----------|--------|--------|------|
| **GitHubTool** | 封装完善但无统一协议 | 实现 BaseTool 协议（get_name, get_description, get_input_schema, execute, get_json_schema, validate_input） | ★★★★★ |
| **GitHubToolkit** | 已注册但仅闭包方式 | 新增 orphan 工具组（code_quality, security_scan, pr_review）+ Pydantic 适配层 | ★★★★★ |
| **BaseTool ABC** | ❌ 不存在 | ✅ src/core/tool_base.py — get_name/description/schema/execute/validate/json_schema | ★★★★★ |

**评分**: ★★★★ → ★★★★★（+1 级）

### 2b. MCP 协议集成

| 能力 | 改进前 | 改进后 | 评分 |
|------|--------|--------|------|
| **StdIO 客户端** | 二进制发现（Go/npm/环境变量） | 无变化 | ★★★★ |
| **工具注册** | register_github_mcp_tools() → Toolkit | 无变化 | ★★★★ |
| **工具枚举** | ❌ get_available_tools() 返回 [] | ✅ 返回真实工具列表（_cached_tools 或 sync list_tools） | ★★★★★ |
| **连接状态** | ⚠️ 仅检查 _session 属性 | ✅ connected property 验证 is_connected 标志 + session 存活 | ★★★★★ |
| **重试/缓存** | ❌ 无 | ✅ connect_with_retry()（指数退避）+ cached_tool_call()（5min TTL） | ★★★★★ |

**评分**: ★★★ → ★★★★★（+2 级）

### 2c. 工具注册与 Agent 集成

| 能力 | 改进前 | 改进后 | 评分 |
|------|--------|--------|------|
| **工具协议/接口** | ❌ 无 BaseTool | ✅ BaseTool ABC + GitHubTool 实现 + validate_input | ★★★★★ |
| **AgentScope Toolkit 集成** | ⚠️ Toolkit 已注册但主循环不用 | ✅ _build_dynamic_intent_prompt() 注入 Toolkit schemas 到 intent prompt | ★★★★★ |
| **LLM 原生工具调用** | ⚠️ 手动 prompt 做 intent 理解 | ⚠️ 仍为手动 intent 理解，但 LLM 现在能看到真实注册工具列表（而非硬编码 INTENT_TOOLS） | ★★★ |
| **动态工具发现** | ❌ 硬编码 INTENT_TOOLS 列表 | ✅ _build_dynamic_intent_prompt() 从 Toolkit get_json_schemas() 动态生成 | ★★★★★ |
| **ToolResponse 一致性** | ⚠️ 两套不兼容 | ✅ _adapt_pydantic_to_agentscope() 适配层 + Toolkit 闭包统一返回 AgentScope ToolResponse | ★★★★ |
| **Orphan 工具整合** | ⚠️ 三个工具未注册 | ✅ 已注册到 Toolkit（evaluate_code_quality, scan_security_code, review_code_changes） | ★★★★★ |

**工具架构变化：**

改进前：
```
ResearcherAgent
  ├─ Toolkit (已注册但闲置) ← AgentScope 工具注册表
  ├─ INTENT_TOOLS (硬编码 5 种) ← 实际使用的路由
  └─ github_tool (直接调用) ← 绕过 Toolkit
```

改进后：
```
ResearcherAgent
  ├─ Toolkit (8+ 工具注册) ← AgentScope 工具注册表
  │   ├─ github 组: search_repositories, get_readme, get_repo_info, get_project_summary, check_rate_limit
  │   ├─ code_quality 组: evaluate_code_quality
  │   ├─ security_scan 组: scan_security_code
  │   ├─ pr_review 组: review_code_changes
  │   └─ github_mcp 组: (MCP 工具，if available)
  ├─ _build_dynamic_intent_prompt() ← 从 Toolkit 动态生成 intent prompt
  └─ BaseTool 协议: GitHubTool implements get_name/get_description/execute/validate/json_schema
```

**评分**: ★★ → ★★★★（+2 级，LLM 原生 function calling 仍为手动 intent，留作阶段三改进）

---

## 维度 3：环境隔离（Environment Isolation）

### 3a. 沙箱执行

| 能力 | 状态 | 说明 | 评分 |
|------|------|------|------|
| **容器/沙箱** | ❌ 无 | 应用本质为 API 聚合 + LLM 分析，不执行用户代码，无沙箱需求 | — |
| **代码执行** | ❌ 无 | 无 subprocess/eval/exec | — |

### 3b. 安全护栏（Guardrails）

| 能力 | 改进前 | 改进后 | 评分 |
|------|--------|--------|------|
| **Prompt 注入防护** | 30+ 英文 + 14 中文正则模式 | 无变化 | ★★★★★ |
| **输出过滤/脱敏** | 8 类模式 | 无变化 | ★★★★★ |
| **Agent 熔断器** | 步骤/时间/Token 三层 + KPI 联动 | ✅ true half-open 探测（_half_open 标志 + is_half_open property + start_session() 半开探测） | ★★★★★ |
| **HTTP 熔断器** | 5 次失败阈值 + 60s 冷却 | ✅ true half-open 探测（_half_open/_half_open_allowed + _close_circuit() + probe success/failure 日志） | ★★★★★ |
| **人工审批（HITL）** | 23 安全/2 中等/12 危险工具分类 | 无变化 | ★★★★ |

**评分**: ★★★★ → ★★★★★（+1 级，half-open 探测补齐）

### 3c-d. 敏感数据管理与资源限制

| 能力 | 状态 | 评分 |
|------|------|------|
| **API Key 管理** | ✅ 环境变量 + .env 隔离 | ★★★★★ |
| **CI 密钥扫描** | ✅ secret_scan.py 11 类模式 | ★★★★★ |
| **输出脱敏** | ✅ guardrails.py 8 类 REDACTED_* | ★★★★★ |
| **步骤限制** | ✅ AgentCircuitBreaker.max_steps=50 | ★★★★ |
| **时间限制** | ✅ AgentCircuitBreaker.max_time_seconds=180 | ★★★★ |
| **Token 预算** | ✅ AgentCircuitBreaker.max_tokens=5000 + _build_messages_with_token_budget() | ★★★★★ |
| **HTTP 超时** | ✅ 30s + 10 次 tenacity 重试 | ★★★★ |
| **速率限制** | ✅ GitHub 10 req/s + 429 检测 | ★★★★ |

---

## Reassessment 总评分

| 维度 | 改进前评分 | 改进后评分 | 提升 | 成熟度 |
|------|-----------|-----------|------|--------|
| **记忆设计** | | | | |
| 短期记忆（多轮对话+压缩） | ★★★ | ★★★★ | +1 | 良好 |
| Token 预算感知 | ★ | ★★★★ | +3 | 良好 |
| 跨会话记忆 | ★ | ★★★ | +2 | 可用 |
| 反馈→记忆闭环 | ★★ | ★★★ | +1 | 可用 |
| **记忆设计综合** | **★★** | **★★★★** | **+2** | **良好** |
| **工具抽象** | | | | |
| 工具封装质量 | ★★★★ | ★★★★★ | +1 | 优秀 |
| MCP 协议集成 | ★★★★ | ★★★★★ | +1 | 优秀 |
| 工具协议/接口 | ★ | ★★★★★ | +4 | 优秀 |
| Agent 集成质量 | ★★ | ★★★★★ | +3 | 优秀 |
| LLM 原生函数调用 | ★★ | ★★★ | +1 | 可用（仍有提升空间） |
| Orphan 工具整合 | ★★ | ★★★★★ | +3 | 优秀 |
| **工具抽象综合** | **★★★** | **★★★★★** | **+2** | **优秀** |
| **环境隔离** | | | | |
| 应用级护栏 | ★★★★★ | ★★★★★ | 0 | 优秀 |
| 敏感数据管理 | ★★★★★ | ★★★★★ | 0 | 优秀 |
| 熔断器模式 | ★★★★ | ★★★★★ | +1 | 优秀 |
| OS 级资源限制 | ★ | ★ | 0 | 无需 |
| **环境隔离综合** | **★★★★** | **★★★★★** | **+1** | **优秀** |
| **总体评分** | **★★★** | **★★★★★** | **+2** | **优秀** |

---

## 遗留改进项（阶段三建议）

| 优先级 | 改进项 | 说明 |
|--------|--------|------|
| S3-P1 | AgentScope 原生 Function Calling | 当前仍为手动 prompt-based intent 理解，应切换到 AgentScope 原生 function calling |
| S3-P2 | Tool→Tool 编排 | 当前仅在 agent 层编排工具，应支持工具间组合调用 |
| S3-P2 | 记忆跨层数据流 | PersistentMemory / ConversationManager / FeedbackCollector 仍独立，可增加交叉检索 |
| S3-P3 | OS 级资源限制 | 如有沙箱需求，可引入 cgroups/ulimit |

---

## 测试与质量

| 指标 | 数值 |
|------|------|
| 总测试用例 | 634 |
| 通过率 | 100% |
| 覆盖率 | 80%+（pyproject.toml 配置 omit 规则） |
| P2 新增测试 | 20 个（MCP 健壮性、熔断器、跨会话记忆、反馈注入） |

---

## 结论

阶段二 P0+P1+P2 改进完成后，GIA 认知架构与工具集成从「可用级」跃升至「优秀级」：

1. **记忆设计 ★★★★** — Token 预算感知、LLM 摘要压缩、跨会话加载、反馈注入均已实现。RAG 仍不建议引入（结构化数据场景不适用）。

2. **工具抽象 ★★★★★** — BaseTool 统一协议、Toolkit 打通、Orphan 工具集成、MCP 健壮性、ToolResponse 适配层全部补齐。唯一遗留是 AgentScope 原生 function calling（需阶段三架构升级）。

3. **环境隔离 ★★★★★** — 半开熔断器补齐后，所有安全护栏达到优秀级。OS 级资源限制因应用特性无需引入。

**总体评分: ★★★ → ★★★★★（+2 级，优秀）**
