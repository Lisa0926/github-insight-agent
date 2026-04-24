# GitHub Insight Agent

企业级多智能体情报分析系统，基于 AgentScope 框架和 GitHub MCP (Model Context Protocol) 实现自动化代码仓库分析。

## CI/CD 状态

| 测试 | 安全审计 | 覆盖率 |
|------|----------|--------|
| [![CI](https://github.com/Lisa0926/github-insight-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Lisa0926/github-insight-agent/actions) | ![pip-audit](https://img.shields.io/badge/pip--audit-pass-green) | ![codecov](https://img.shields.io/badge/codecov-100%25-green) |

**最近执行结果**: 90/90 测试通过，0 安全漏洞

## 功能特性

- 多智能体协作：研究员 Agent + 分析师 Agent
- GitHub 仓库数据自动采集
- 代码质量分析和趋势报告生成
- 支持本地工具和 MCP 协议扩展

## 快速开始

### 环境要求

- Python 3.9+
- GitHub Personal Access Token

### 安装步骤

```bash
# 克隆项目
git clone https://github.com/Lisa0926/github-insight-agent.git
cd github-insight-agent

# 安装依赖
pip install -r requirements.txt
```

### 配置

复制环境变量模板并配置必要的 API Key：

```bash
cp .env.sample .env
```

编辑 `.env` 文件，设置以下变量：

```bash
# 模型服务 API Key（阿里云百炼或兼容服务）
DASHSCOPE_API_KEY=your_api_key_here

# GitHub Personal Access Token
GITHUB_TOKEN=your_github_token_here
```

获取 GitHub Token：https://github.com/settings/tokens

### 运行

```bash
python main.py
```

## 项目结构

```
github-insight-agent/
├── src/
│   ├── core/           # 核心模块（配置、日志、内存）
│   ├── agents/         # 智能体实现
│   ├── tools/          # 工具封装（GitHub API、Toolkit）
│   ├── mcp/            # MCP 客户端
│   └── types/          # 数据模型
├── tests/              # 测试用例
├── configs/            # 配置文件
├── data/               # 数据目录（本地存储）
├── logs/               # 日志目录
├── main.py             # 入口文件
├── requirements.txt    # Python 依赖
└── .env.sample         # 环境变量模板
```

## 核心模块

### 配置管理

使用 `ConfigManager` 统一管理配置：

```python
from src.core.config_manager import ConfigManager

config = ConfigManager()
api_key = config.get_api_key("qwen-max")
```

### 日志系统

封装 loguru 日志：

```python
from src.core.logger import get_logger

logger = get_logger(__name__)
logger.info("操作成功")
```

### 智能体

- `ResearcherAgent`: 负责数据采集和初步分析
- `AnalystAgent`: 负责深度分析和报告生成

## 扩展开发

### 添加新智能体

在 `src/agents/` 目录创建新文件，继承 `BaseAgent` 类：

```python
from src.agents.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def analyze(self, data):
        pass
    
    def get_description(self):
        return "自定义智能体描述"
```

### 添加新工具

在 `src/tools/` 目录创建工具封装：

```python
class CustomTool:
    def execute(self, params):
        pass
```

## License

MIT
