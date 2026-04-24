# GitHub Insight Agent - 文档索引

**最后更新:** 2026-04-24

---

## 📚 文档导航

### 入门必读

| 文档 | 描述 | 适合人群 |
|------|------|---------|
| [快速参考](QUICK_REFERENCE.md) | 命令速查、配置位置 | 所有人 |
| [用户手册](USER_GUIDE.md) | 完整使用指南 | 终端用户 |
| [架构总结](ARCHITECTURE_SUMMARY.md) | 架构概览、学习路径 | 开发者 |
| [Pre-commit Hooks](PRE_COMMIT_HOOKS.md) | 安全扫描配置和使用 | 贡献者 |

---

### 深入理解

| 文档 | 描述 | 适合人群 |
|------|------|---------|
| [架构文档](ARCHITECTURE.md) | 详细架构说明、模块详解 | 架构师、开发者 |
| [流程图集](FLOWCHARTS.md) | 12 个 Mermaid 流程图 | 视觉学习者 |
| [项目仓库](https://github.com/Lisa0926/github-insight-agent) | 源代码、Issues | 贡献者 |

---

## 🗺️ 使用场景导航

### 我想...

| 目标 | 阅读文档 | 使用命令 |
|------|---------|---------|
| 快速上手 | 用户手册 - 快速开始 | `gia` |
| 分析项目 | 用户手册 - 示例 1 | `/analyze owner/repo` |
| 搜索竞品 | 用户手册 - 示例 2 | `/search "关键词"` |
| 生成报告 | 用户手册 - 示例 3 | `/report "关键词"` |
| 审查 PR | 用户手册 - 示例 4 | `/pr` |
| 安全扫描 | 用户手册 - 示例 5 | `/scan <file>` |
| 理解架构 | 架构总结 → 架构文档 | - |
| 查看流程 | 流程图集 | - |
| 故障排除 | 用户手册 - 故障排除 | - |

---

## 📊 架构图快速查看

### 整体架构

```
用户接口 → 工作流 → 智能体 → 工具 → 外部 API
                ↓
            持久化存储
```

### 核心模块

- **智能体层**: ResearcherAgent, AnalystAgent
- **工具层**: GitHubTool, OWASPRuleEngine, PRReviewer
- **核心层**: ConfigManager, Logger, PersistentMemory

---

## 🔑 关键位置

| 资源 | 路径 |
|------|------|
| 配置文件 | `~/.env` |
| 任务历史 | `.hermes/tasks/{project}/INDEX.md` |
| 数据库 | `data/app.db` |
| 日志 | `logs/` |
| 测试 | `tests/` |

---

## ⏰ 定时任务

GIA 项目有两个定时任务，每日自动执行：

| 任务 | 执行时间 | 内容 | 查看历史 |
|------|---------|------|---------|
| Part 1: 技术迭代 | 每日 21:00 | 架构审查、安全修复、测试补充 | `.hermes/tasks/github-insight-agent/INDEX.md` |
| Part 2: 产品迭代 | 每日 21:00 | 竞品分析、待办列表、迭代计划 | `.hermes/tasks/github-insight-agent/INDEX.md` |

**推送渠道:** 微信 + 飞书

---

## 🛠️ 开发者入口

### 代码结构

```
src/
├── agents/         # 智能体入口
├── core/           # 核心工具
├── tools/          # 工具集
├── workflows/      # 工作流
└── cli/            # CLI 入口
```

### 关键文件

- `src/workflows/report_generator.py` - 主工作流
- `src/agents/researcher_agent.py` - 搜索逻辑
- `src/agents/analyst_agent.py` - 分析逻辑
- `src/tools/github_tool.py` - API 封装

---

## 📝 更新日志

- **2026-04-24**: 新增架构梳理文档集合
- 查看完整变更：[CHANGELOG.md](../CHANGELOG.md)

---

*文档由 Hermes Agent 生成和维护*
