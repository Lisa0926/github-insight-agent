# GitHub Insight Agent

企业级多智能体情报分析系统 - 基于 AgentScope 和多模型支持

## 快速开始

### 1. 环境准备

- Python 3.9+
- WSL (Linux) 环境

### 2. 激活虚拟环境

```bash
cd github-insight-agent
source .venv/bin/activate
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入 LLM API Key
nano .env
```

**必要配置:**
- `DASHSCOPE_API_KEY` - 模型服务 API Key（兼容阿里云百炼、OpenAI 等）
- `DASHSCOPE_ORGANIZATION_ID` - 组织 ID (可选)
- `GITHUB_TOKEN` - GitHub Personal Access Token (可选，用于增强功能)

获取 API Key: 
- 阿里云百炼：https://bailian.console.aliyun.com/
- OpenAI: https://platform.openai.com/api-keys

### 4. 测试环境

```bash
# 运行入口文件测试模型连接
python main.py
```

## 项目结构

```
github-insight-agent/
├── configs/
│   ├── model_configs.json       # LLM 模型配置
│   └── prompt_templates/        # 系统提示词模板
├── src/
│   ├── core/
│   │   ├── config_manager.py    # 配置加载器 (单例)
│   │   ├── logger.py            # 日志封装 (loguru)
│   │   ├── agentscope_memory.py # AgentScope 内存封装
│   │   └── agentscope_persistent_memory.py  # 持久化存储 (SQLite)
│   ├── agents/
│   │   ├── researcher_agent.py  # 研究员 Agent
│   │   └── analyst_agent.py     # 分析师 Agent
│   ├── tools/
│   │   ├── github_tool.py       # GitHub API 封装
│   │   ├── github_toolkit.py    # AgentScope Toolkit 集成
│   │   └── tool_registry.py     # 工具注册器
│   ├── mcp/
│   │   └── github_mcp_client.py # GitHub MCP 客户端
│   └── types/
│       └── schemas.py           # Pydantic 数据模型
├── data/                        # 持久化数据库目录
├── bin/                         # 外部工具二进制
│   └── github-mcp-server        # GitHub MCP Server v0.32.0
├── docs/                        # 文档目录
│   ├── github_mcp_integration.md
│   └── external_tools_analysis.md
├── logs/                        # 运行日志目录
├── tests/                       # 测试目录
├── .env                         # 环境变量 (不提交)
├── .env.example                 # 环境变量模板
├── .gitignore
├── main.py                      # 入口文件
└── requirements.txt
```

## 核心功能

### 配置管理

```python
from src.core.config_manager import ConfigManager

config = ConfigManager()
api_key = config.get_api_key("qwen-max")
model_config = config.get_model_config("qwen-max")
```

### 日志系统

```python
from src.core.logger import get_logger

logger = get_logger(__name__)
logger.info("这是一条信息日志")
logger.error("这是一条错误日志")
```

### 数据模型

```python
from src.types.schemas import GitHubRepoInfo

repo = GitHubRepoInfo(
    name="github-insight-agent",
    full_name="example/github-insight-agent",
    url="https://github.com/example/github-insight-agent",
    description="企业级多智能体情报分析系统",
    stars=150,
    # ...
)
```

### GitHub 工具

```python
from src.tools.github_tool import GitHubTool

tool = GitHubTool(token="your_token")
repo_info = tool.get_repo_stats("owner", "repo")
issues = tool.get_issues("owner", "repo")
```

### AgentScope Toolkit

项目已集成 AgentScope Toolkit，支持本地工具和 MCP (Model Context Protocol) 工具：

```python
from src.tools.github_toolkit import get_github_toolkit

toolkit = get_github_toolkit(config=config, use_mcp=True)
schemas = toolkit.get_json_schemas()  # 获取工具 JSON Schema
```

**可用工具:**
- 本地工具 (5 个): `search_repositories`, `get_readme`, `get_repo_info`, `get_project_summary`, `check_rate_limit`
- MCP 工具 (20 个): `get_commit`, `list_commits`, `list_issues`, `search_code`, 等

详见 [GitHub MCP 集成指南](docs/github_mcp_integration.md)

### 持久化存储

对话历史自动持久化到本地 SQLite 数据库，数据完全本地存储，不上传：

```python
from src.agents.researcher_agent import ResearcherAgent

# 启用持久化（默认）
researcher = ResearcherAgent(config=config, use_persistent=True, db_path='data/app.db')

# 禁用持久化（仅内存）
researcher = ResearcherAgent(config=config, use_persistent=False)
```

数据库文件位置：`data/app.db`

## 开发说明

### 添加新的智能体

1. 在 `src/agents/` 目录下创建新文件
2. 继承 `BaseAgent` 类
3. 实现 `analyze()` 和 `get_description()` 抽象方法

### 添加新的工具

1. 在 `src/tools/` 目录下创建新文件
2. 封装外部 API 调用
3. 统一错误处理和日志记录

## 日志

日志文件位于 `logs/app.log`，支持:
- 自动轮转 (10MB)
- 保留 7 天
- 同时输出到控制台

## License

MIT
