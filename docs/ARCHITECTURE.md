# GitHub Insight Agent - 架构文档

**版本:** v2.2.0  
**最后更新:** 2026-04-30

---

## 一、系统架构图

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitHub Insight Agent                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                  ┌─────────────┐                         │
│  │   CLI       │                  │  Hermes     │                         │
│  │  命令行接口  │                  │  定时任务   │                         │
│  └──────┬──────┘                  └──────┬──────┘                         │
│         │                                │                                 │
│         └────────────────────────────────┘                                 │
│                            │                                            │
│                   ┌────────▼────────┐                                   │
│                   │ AgentPipeline   │                                   │
│                   │ SequentialPipeline编排 │                             │
│                   └────────┬────────┘                                   │
│                            │                                            │
│         ┌──────────────────┼──────────────────┐                         │
│         │                  │                  │                         │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐                 │
│  │ Researcher  │    │  Analyst    │    │   Custom    │                 │
│  │   Agent     │    │   Agent     │    │   Agent     │                 │
│  │  研究员智能体 │    │  分析师智能体 │    │  自定义智能体 │                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         │                  │                  │                         │
│         └──────────────────┼──────────────────┘                         │
│                            │                                            │
│                   ┌────────▼────────┐                                   │
│                   │ GiaAgentBase    │                                   │
│                   │ (AgentScope)    │                                   │
│                   └────────┬────────┘                                   │
│                            │                                            │
│                   ┌────────▼────────┐                                   │
│                   │ DashScope       │                                   │
│                   │ Wrapper (同步)  │                                   │
│                   └─────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 1.2 模块依赖图

```
                    ┌─────────────────┐
                    │   main.py /     │
                    │   CLI Entry     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼──────┐ ┌────▼────────┐ ┌──▼──────────┐
    │  ConfigManager │ │  Workflow   │ │   Tools     │
    │   配置管理      │ │  工作流     │ │   工具集    │
    └────────┬───────┘ └─────┬───────┘ └─────┬───────┘
             │               │               │
             │        ┌──────┴──────┐        │
             │        │             │        │
    ┌────────▼───────┐ ▼      ┌────▼─────────┴────┐
    │  Logger        │Agents  │  GitHubTool       │
    │  日志系统       │        │  MCP Client       │
    │                │        │  OWASP Scanner    │
    │ GIA_DASHSCOPE  │        └─────────┬─────────┘
    │ _API_KEY       │                  │
    └────────────────┘        ┌─────────▼─────────┐
                              │   External APIs   │
                              │  - GitHub API     │
                              │  - DashScope LLM  │
                              │  - OpenAI API     │
                              └───────────────────┘
```

---

### 1.3 数据流图

```
用户请求
   │
   ▼
┌─────────────────┐
│  CLI / Web     │
│  接收用户输入    │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│ AgentPipeline / 意图路由     │
│ NaturalLanguageParser /      │
│ LLM _understand_intent()     │
└────────┬─────────────────────┘
         │
         ├── 搜索 ──────────────────────┐
         ▼                              ▼
┌───────────────────────┐      ┌───────────────────────┐
│ ResearcherAgent       │      │  GitHub API           │
│ _execute_search()     │──────│  获取数据              │
└────────┬──────────────┘      └───────────────────────┘
         │
         │ 项目列表
         ▼
┌───────────────────────┐
│ AnalystAgent          │◄── GitHub 数据
│ analyze_project       │    代码质量
│ x N 项目              │    OWASP 检测
└────────┬──────────────┘
         │
         │ 分析报告
         ▼
┌───────────────────────┐
│ ReportGenerator       │
│ 汇总生成报告           │
│ (含 intent routing)    │
└────────┬──────────────┘
         │
         ├──► 输出到 CLI 渲染
         │
         └──► AgentScope Studio (通过 agent.print hook)
              - 消息推送 (Msg)
              - 跟踪 (OpenTelemetry Span)
              - Token 用量 (ChatUsage)
```

---

## 二、核心模块详解

### 2.1 智能体层 (src/agents/)

```
src/agents/
├── base_agent.py         # 基础智能体 (继承 AgentScope AgentBase)
├── researcher_agent.py   # 研究员智能体
├── analyst_agent.py      # 分析师智能体
└── __init__.py
```

#### BaseAgent
- **职责**: 定义智能体通用接口
- **功能**: 记忆管理、工具调用、配置驱动
- **子类**: ResearcherAgent, AnalystAgent

#### ResearcherAgent
- **职责**: 数据采集、LLM 意图理解、工具路由
- **核心方法**:
  - `search_and_analyze(query, sort, per_page)` — 数据采集
  - `_understand_intent(query)` — LLM 意图识别（5 类工具：搜索/获取/分析/对比/对话）
  - `_execute_search(params)` — 执行搜索（含时间范围、排序）
  - `_execute_get_repo_info(params)` — 获取仓库详情
  - `_execute_analyze_project(params)` — 委托 Analyst 深度分析
  - `_execute_compare(params)` — 多项目对比
- **INTENT_TOOLS**: 5 个 function calling 工具定义 (search_repositories, get_repo_info, analyze_project, compare_repositories, chat)
- **INTENT_SYSTEM_PROMPT**: LLM 提示词，定义工具选择规则和 JSON 输出格式
- **输出**: 结构化搜索结果 (项目名、Stars、语言、简介)

#### AnalystAgent
- **职责**: 深度分析与报告生成
- **核心方法**: `analyze_project(owner, repo)`
- **功能**: 代码质量评分、安全漏洞检测、技术栈识别

---

### 2.2 核心层 (src/core/)

```
src/core/
├── config_manager.py           # 配置管理 (单例模式)
├── logger.py                   # 日志系统 (loguru 封装)
├── agentscope_memory.py        # AgentScope 内存封装
├── agentscope_persistent_memory.py  # 持久化内存 (SQLite, 按 db_path 缓存)
├── conversation.py             # 会话管理
├── resilient_http.py           # 弹性 HTTP 客户端
├── guardrails.py               # 安全护栏 (注入防护/输出过滤/熔断器/人工确认)
├── dashscope_wrapper.py        # DashScope 同步调用包装 (兼容 AgentScope ChatResponse)
├── studio_helper.py            # AgentScope Studio 自定义转发 (仅 set_studio_config)
└── studio_integration.py       # AgentScope 官方 Studio 集成 (agent.print hook)
```

#### ConfigManager
```python
config = ConfigManager()  # 单例
api_key = config.get_api_key("YOUR_MODEL_NAME_HERE")
```

#### PersistentMemory
- **存储**: SQLite (`data/app.db`)
- **表结构**: `conversation_history`, `memory_index`
- **功能**: 对话历史持久化、向量索引
- **缓存策略**: 按 `db_path` 键缓存实例，避免连接竞争

#### Studio 集成 (双模式)

**官方 Hook 模式** (推荐，`studio_integration.py`):
- 通过 `agentscope.init(studio_url=...)` 注册 `pre_print` hook
- 使用 `_StudioPushAgent.print(msg)` 推送消息到 Studio
- 支持 OpenTelemetry 跟踪（`@trace` 装饰器自动记录 Span）
- CLI 层统一推送，确保 CLI 和 Studio 内容一致

**自定义转发模式** (仅保留用于 agent 级 studio 配置，`studio_helper.py`):
- 提供 `set_studio_config()` 为 agent 设置自定义 Studio 转发
- 由 `_setup_studio()` 在 CLI 启动时调用

#### Guardrails (`guardrails.py`)
- **职责**: Agent 级安全护栏与治理
- **功能**:
  1. **Prompt 注入防护**: 15 种正则模式检测 (DAN/jailbreak/ignore instructions/act as/reveal prompt 等)，`sanitize_user_input()` 在 LLM 调用前拦截
  2. **输出过滤**: 8 种敏感数据模式脱敏 (API Key/GitHub Token/AWS Key/DB URI/内部路径等)，`filter_sensitive_output()` 应用于所有 LLM 响应
  3. **Agent 熔断器**: `AgentCircuitBreaker` 追踪步数(50)、时间(180s)、Token(5000)，超限自动中断
  4. **人工确认**: 工具风险分级 (safe/moderate/dangerous)，高危操作 (create_issue/merge_pr/create_repo 等) 需人工审批
- **集成点**: ResearcherAgent 意图理解 → CLI 输入路径 → ReportGenerator 执行管线 → Toolkit 工具响应

---

### 2.3 工具层 (src/tools/)

```
src/tools/
├── github_tool.py          # GitHub API 封装
├── github_toolkit.py       # AgentScope Toolkit 集成 (含 audit_tool_call 装饰器)
├── pr_review_tool.py       # PR 审查工具
├── code_quality_tool.py    # 代码质量评分
├── owasp_security_rules.py # OWASP Top 10 检测 (53 条规则)
└── __init__.py
```

#### GitHubTool
- **方法**: `search_repositories`, `get_readme`, `get_repo_info`
- **认证**: GitHub Personal Access Token

#### OWASPRuleEngine
- **覆盖**: OWASP Top 10 2021 (A01-A10)
- **检测**: 注入、XSS、CSRF、敏感信息泄露等

---

### 2.4 MCP 集成 (src/github_mcp/)

```
src/github_mcp/
├── github_mcp_client.py    # MCP 客户端
├── github_mcp_mock.py      # Mock 客户端 (测试用)
└── __init__.py
```

#### 功能
- 与 GitHub MCP Server 握手
- 工具注册与调用
- 断线自动重连

---

### 2.5 工作流层 (src/workflows/)

```
src/workflows/
├── report_generator.py     # 报告生成器
└── __init__.py
```

#### ReportGenerator 工作流

```python
# 1. 搜索阶段
researcher.search_and_analyze(query="python web framework")

# 2. 分析阶段 (遍历每个项目)
for repo in search_results:
    analysis = analyst.analyze_project(repo.owner, repo.name)

# 3. 报告生成
report = generator.generate_report(search_results, analyses)

# 4. 追问处理（含 LLM 意图路由）
response = generator.handle_followup(user_query)
# 内部: _understand_intent() → 路由到 _execute_search / _execute_get_repo_info / _execute_compare
# 或降级: LLM 对话（有上下文）
```

---

### 2.6 CLI 层 (src/cli/)

```
src/cli/
├── app.py                  # CLI 主入口 (agentscope.init, Studio 推送, 自然语言路由)
├── cli_renderer.py         # 美化输出 (rich 库)
├── interactive_cli.py      # 交互式 CLI (prompt_toolkit, 自动补全, 历史)
├── natural_language_parser.py  # 自然语言参数提取 (时间/数量/排序)
└── __init__.py
```

#### 命令
```bash
gia /analyze owner/repo     # 分析单个项目
gia /search <关键词>        # 搜索项目
gia /report <关键词>        # 生成详细报告
gia /pr                     # PR 审查
gia /scan <文件>            # 安全扫描
```

---

### 2.8 类型定义 (src/types/)

```
src/types/
├── schemas.py              # Pydantic 数据模型
└── __init__.py
```

#### 核心模型
- `GitHubRepo` - 仓库信息
- `GitHubSearchResult` - 搜索结果
- `ToolResponse` - 工具响应

---

## 三、配置文件

### 3.1 环境变量 (.env)

```bash
# 全局配置：~/.env

# 模型服务 API Key
DASHSCOPE_API_KEY=sk-xxx

# GitHub Token
GITHUB_TOKEN=ghp_xxx

# 通知渠道
WECHAT_CHANNEL_ID=xxx
FEISHU_GROUP_ID=xxx
```

### 3.2 模型配置 (configs/model_configs.json)

```json
{
  "YOUR_MODEL_A": {
    "provider": "dashscope",
    "api_key": "DASHSCOPE_API_KEY",
    "temperature": 0.7
  },
  "YOUR_MODEL_B": {
    "provider": "openai",
    "api_key": "OPENAI_API_KEY",
    "temperature": 0.7
  }
}
```

---

## 四、部署架构

### 4.1 本地部署

```
┌─────────────────┐
│   User Terminal │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   gia CLI       │
│  (Python 3.12)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SQLite (data/) │
│  Logs (logs/)   │
└─────────────────┘
```

### 4.2 定时任务 (Hermes Agent)

```
┌─────────────────┐
│  Hermes Cron    │
│  (每日 21:00)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GIA Agent      │
│  Part 1 + Part 2│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  微信/飞书推送   │
└─────────────────┘
```

---

## 五、安全架构

### 5.1 信息安全

```
┌─────────────────┐
│     ~/.env      │  ← 敏感信息集中存储
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ConfigManager  │  ← 加载时验证
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  项目代码       │  ← 不存储任何密钥
└─────────────────┘
```

### 5.2 代码安全

- **OWASP Top 10 检测**: 53 条规则
- **PR 审查**: 规则 + LLM 双重检测
- **CI/CD**: flake8 + mypy + pip-audit

### 5.3 Agent 安全护栏

- **Prompt 注入防护**: 15 种模式在 LLM 调用前拦截注入攻击
- **输出脱敏**: 自动脱敏 API Key、GitHub Token、AWS Key、DB URI 等 8 类敏感数据
- **Agent 熔断器**: 最大步数 50 / 超时 180s / Token 预算 5000，防止无限循环和资源耗尽
- **人工确认**: 高危工具 (写操作/外部影响) 需人工审批，安全工具 (只读操作) 自动放行

---

## 六、性能优化

### 6.1 缓存策略

- **HTTP 缓存**: resilient_http.py (指数退避)
- **记忆压缩**: 超过阈值自动压缩历史对话
- **SQLite 连接池**: 单例模式复用连接

### 6.2 异步处理

- **aiohttp**: 异步 HTTP 客户端
- **并发搜索**: 批量 API 调用
- **流式响应**: 支持 AgentScope 流式输出

---

*文档由 Hermes Agent 自动生成*
