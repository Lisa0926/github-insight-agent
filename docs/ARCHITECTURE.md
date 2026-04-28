# GitHub Insight Agent - 架构文档

**版本:** v2.0.0  
**最后更新:** 2026-04-28

---

## 一、系统架构图

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         GitHub Insight Agent                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                 │
│  │   CLI       │    │   Web UI    │    │  Hermes     │                 │
│  │  命令行接口  │    │  可视化界面  │    │  定时任务   │                 │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                 │
│         │                  │                  │                         │
│         └──────────────────┼──────────────────┘                         │
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
│  CLI / Web UI   │
│  接收用户输入    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AgentPipeline   │
│ SequentialPipeline编排 │
└────────┬────────┘
         │
         ├── 搜索 ──────────────────┐
         ▼                          ▼
┌─────────────────┐         ┌─────────────────┐
│ ResearcherAgent │         │  GitHub API     │
│ SequentialPipeline │──────│  获取数据       │
└────────┬────────┘         └─────────────────┘
         │
         │ 项目列表
         ▼
┌─────────────────┐
│ AnalystAgent    │◄── GitHub 数据
│ analyze_project │    代码质量
│ x N 项目        │    OWASP 检测
└────────┬────────┘
         │
         │ 分析报告
         ▼
┌─────────────────┐
│ ReportGenerator │
│ 汇总生成报告     │
│ (内部格式化引擎) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  输出到 CLI /   │
│  Web / 微信     │
└─────────────────┘
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
- **职责**: 数据采集与初步分析
- **核心方法**: `search_and_analyze(query, sort, order, per_page)`
- **输出**: 结构化搜索结果 (项目名、Stars、语言、简介)

#### AnalystAgent
- **职责**: 深度分析与报告生成
- **核心方法**: `analyze_project(owner, repo)`
- **功能**: 代码质量评分、安全漏洞检测、技术栈识别

---

### 2.2 核心层 (src/core/)

```
src/core/
├── config_manager.py        # 配置管理 (单例模式)
├── logger.py                # 日志系统 (loguru 封装)
├── agentscope_memory.py     # AgentScope 内存封装
├── agentscope_persistent_memory.py  # 持久化内存 (SQLite)
├── conversation.py          # 会话管理
├── resilient_http.py        # 弹性 HTTP 客户端
└── studio_helper.py         # AgentScope Studio 集成
```

#### ConfigManager
```python
config = ConfigManager()  # 单例
api_key = config.get_api_key("qwen-max")
```

#### PersistentMemory
- **存储**: SQLite (`data/app.db`)
- **表结构**: `conversation_history`, `memory_index`
- **功能**: 对话历史持久化、向量索引

---

### 2.3 工具层 (src/tools/)

```
src/tools/
├── github_tool.py          # GitHub API 封装
├── github_toolkit.py       # AgentScope Toolkit 集成
├── tool_registry.py        # 工具注册表
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
```

---

### 2.6 CLI 层 (src/cli/)

```
src/cli/
├── app.py                  # CLI 主入口
├── cli_renderer.py         # 美化输出 (rich 库)
├── interactive_cli.py      # 交互式 CLI (prompt_toolkit)
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

### 2.7 Web 层 (src/web/)

```
src/web/
├── dashboard_api.py        # FastAPI 后端
└── __init__.py
```

#### API 端点
- `GET /api/projects` - 项目列表
- `GET /api/projects/{owner}/{repo}` - 项目详情
- `GET /api/radar` - 雷达图数据

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
  "qwen-max": {
    "provider": "dashscope",
    "api_key": "DASHSCOPE_API_KEY",
    "temperature": 0.7
  },
  "gpt-4": {
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
