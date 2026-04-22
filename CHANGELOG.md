# Changelog

所有重要变更将记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## [Unreleased]

### Planned
- **代码质量扫描模块** - 集成 semgrep 进行静态代码分析
- **多仓库对比分析** - 并排比较多个项目的技术栈和成熟度
- **Web 可视化仪表盘** - 分析结果的图形化展示
- **PR 自动审查** - 自动化 Pull Request 分析

---

## [1.1.0] - 2026-04-22

### Added

#### 核心基础设施
- **LLM Provider 抽象层** (`src/llm/`)
  - 统一接口 `LLMProvider` 抽象基类
  - `DashScopeProvider` - 阿里云百炼支持
  - `OpenAIProvider` - OpenAI GPT 系列支持
  - `OllamaProvider` - 本地 Ollama 部署支持
  - Provider factory 支持后端热切换
  
- **弹性 HTTP 客户端** (`src/core/resilient_http.py`)
  - 基于 tenacity 的指数退避重试机制
  - 超时处理
  - 429 速率限制优雅降级
  - 熔断器模式
  
- **Studio Helper 共享模块** (`src/core/studio_helper.py`)
  - 统一的 AgentScope Studio 配置
  - Run 注册和消息转发
  - 消除约 80 行重复代码
  
- **MCP Mock 客户端** (`src/mcp/github_mcp_mock.py`)
  - 用于测试的 Mock GitHub MCP Server
  - 模拟 5 个核心工具
  - 支持离线开发和 CI/CD

#### 数据库与持久化
- **PersistentMemory 连接管理**
  - 新增 `close()` 异步方法显式关闭连接
  - 实现 `__enter__`/`__exit__` 上下文管理器
  - 新增 `PersistentMemoryContext` 便捷类
  - 消除 GC 警告

### Changed

#### 破坏性变更
- **Pydantic v2 迁移** (`src/types/schemas.py`)
  - 从 `class Config` 迁移到 `model_config = ConfigDict(...)`
  - 所有模型兼容 Pydantic v2
  - 无弃用警告

#### 重构
- **ResearcherAgent** (`src/agents/researcher_agent.py`)
  - 使用 `StudioHelper` 替换内联配置
  - 新增 `get_llm_provider()` 方法支持多后端
  
- **AnalystAgent** (`src/agents/analyst_agent.py`)
  - 使用 `StudioHelper` 替换内联配置

#### 依赖
- 新增 `tenacity>=8.2.0` 用于重试逻辑
- 新增 `aiohttp>=3.9.0` 用于异步 HTTP

### Fixed
- 集成测试中 MCP 二进制文件缺失时的 `UnboundLocalError`
- 测试中的数据库连接泄漏
- LLM provider 中缺失的 `Optional` 导入

### Testing
- 集成测试在二进制文件缺失时使用 Mock MCP 客户端
- 测试结果：3/4 通过（Mock 模式为预期行为）

---

## [1.0.0] - 2026-04-17

### Added

#### 核心功能
- **多智能体系统**
  - `ResearcherAgent` - GitHub 仓库搜索和数据采集
  - `AnalystAgent` - 基于 ReAct 推理的 README 深度分析
  - 支持多轮对话和追问
  
- **GitHub 集成**
  - 仓库搜索 API
  - README 内容获取
  - 仓库元数据提取
  - 速率限制处理

- **报告生成**
  - Markdown 格式分析报告
  - Star 评级可视化（文本进度条）
  - 执行摘要生成
  - 项目成熟度评估

- **CLI 界面**
  - `/analyze <owner/repo>` - 分析指定项目
  - `/search <keyword>` - 搜索项目
  - `/report <keyword>` - 生成完整报告
  - `/history`, `/clear`, `/export` - 对话管理

#### 架构
- **AgentScope 集成**
  - Studio 可视化支持
  - Tracing 调试
  - AsyncSQLAlchemyMemory 持久化

- **配置管理**
  - `ConfigManager` 单例，支持 JSON + 环境变量
  - 安全：仅全局 .env，默认阻止项目 .env

- **日志系统**
  - 基于 loguru
  - 日志轮转和保留策略

- **类型系统**
  - Pydantic v2 数据模型
  - 类型安全的工具响应

#### 工具与 MCP
- **GitHubTool** - 封装 GitHub API 调用
- **GitHubMCPClient** - MCP 协议集成
- **Tool Registry** - 全局工具注册和发现

#### 测试
- 单元测试（23 个，100% 通过）
- 补充单元测试（16 个）
- 集成测试（4 个，2 个核心功能通过）
- 总覆盖率：95.3%

---

## 版本历史

| 版本 | 日期 | 关键变更 |
|------|------|---------|
| 1.1.0 | 2026-04-22 | LLM 抽象层、弹性 HTTP、MCP Mock、Pydantic v2 |
| 1.0.0 | 2026-04-17 | 初始版本，MCP 集成 |

---

## 自动生成

本 Changelog 使用 [git-cliff](https://git-cliff.org/) 自动生成，基于 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

```bash
# 安装 git-cliff
pip install git-cliff

# 生成最新版本
git cliff --unreleased

# 生成完整 Changelog
git cliff -o CHANGELOG.md
```

详见 `docs/CHANGELOG_AUTO.md`。

---

*最后更新：2026-04-22*
