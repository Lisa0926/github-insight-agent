# GitHub Insight Agent - 架构梳理总结

**执行日期:** 2026-04-24  
**任务:** 梳理 GIA 项目架构，生成图表和使用说明

---

## 📋 梳理内容

### 1. 已生成文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **架构文档** | `docs/ARCHITECTURE.md` | 系统架构、模块详解、部署架构 |
| **用户手册** | `docs/USER_GUIDE.md` | 快速开始、使用示例、故障排除 |
| **流程图集** | `docs/FLOWCHARTS.md` | 12 个 Mermaid 流程图 |
| **快速参考** | `docs/QUICK_REFERENCE.md` | 命令速查、配置位置、checklist |

---

## 🏗️ 架构概览

### 核心层次

```
┌─────────────────────────────────────────────┐
│            用户接口层                        │
│    CLI / Web UI / Hermes Cron               │
├─────────────────────────────────────────────┤
│            工作流层                          │
│    ReportGenerator (协调 Researcher+Analyst) │
├─────────────────────────────────────────────┤
│            智能体层                          │
│    BaseAgent → ResearcherAgent, AnalystAgent │
├─────────────────────────────────────────────┤
│            工具层                            │
│    GitHubTool, OWASPRuleEngine, PRReviewer   │
├─────────────────────────────────────────────┤
│            核心层                            │
│    ConfigManager, Logger, PersistentMemory   │
└─────────────────────────────────────────────┘
```

---

## 📊 关键数据流

### 用户查询处理

```
用户输入 → 命令解析 → 工作流调度 → Agent 执行 → 工具调用 → API 请求
                                              ↓
用户输出 ← 格式化输出 ← 报告生成 ← 结果汇总 ← 数据返回
```

### 定时任务执行

```
Hermes Cron (21:00)
       ↓
Part 1: 技术迭代 (架构审查、安全修复、测试补充)
       ↓
Part 2: 产品迭代 (竞品分析、待办列表、迭代计划)
       ↓
微信/飞书推送 + 保存到 .hermes/tasks/
```

---

## 🔑 核心模块职责

| 模块 | 职责 | 关键方法 |
|------|------|---------|
| **ConfigManager** | 配置管理 (单例) | `get_model_config()`, `_load_env()` |
| **ResearcherAgent** | 数据采集 | `search_and_analyze()` |
| **AnalystAgent** | 深度分析 | `analyze_project()` |
| **ReportGenerator** | 工作流协调 | 遍历项目 → 汇总报告 |
| **GitHubTool** | GitHub API 封装 | `search_repositories()`, `get_readme()` |
| **OWASPRuleEngine** | 安全检测 | `detect_issues()` (53 条规则) |
| **PersistentMemory** | 持久化存储 | SQLite + 向量索引 |

---

## 📁 目录结构

```
github-insight-agent/
├── src/
│   ├── agents/              # 智能体实现
│   │   ├── base_agent.py    # 基础类 (AgentScope)
│   │   ├── researcher_agent.py
│   │   └── analyst_agent.py
│   ├── core/                # 核心模块
│   │   ├── config_manager.py
│   │   ├── logger.py
│   │   ├── agentscope_memory.py
│   │   └── resilient_http.py
│   ├── tools/               # 工具集
│   │   ├── github_tool.py
│   │   ├── pr_review_tool.py
│   │   └── owasp_security_rules.py
│   ├── workflows/           # 工作流
│   │   └── report_generator.py
│   ├── cli/                 # 命令行
│   ├── web/                 # Web API
│   ├── github_mcp/          # MCP 集成
│   └── types/               # 数据模型
├── docs/                    # 文档 (新增 4 个)
├── tests/                   # 测试用例
├── data/                    # SQLite 数据库
├── logs/                    # 日志文件
├── configs/                 # 配置文件
├── .hermes/                 # 定时任务输出
└── .github/workflows/       # CI/CD
```

---

## 🔒 安全架构

### 敏感信息管理

```
❌ 禁止项目中存储:
   - API Keys
   - GitHub Tokens
   - 微信/飞书 ID

✅ 统一存储位置:
   /home/lisa/.env
```

### OWASP Top 10 检测

- **A01**: 访问控制失效
- **A02**: 加密失败
- **A03**: 注入攻击
- **A04**: 不安全设计
- **A05**: 配置错误
- **A06**: 过时组件
- **A07**: 认证失败
- **A08**: 完整性失败
- **A09**: 日志监控失败
- **A10**: SSRF

---

## ⏰ 定时任务配置

| 任务 ID | 项目 | 时间 | 内容 |
|--------|------|------|------|
| `0b1e416f96a2` | GIA | 21:00 | Part 1 技术迭代 |
| `0e26789d8973` | GIA | 21:00 | Part 2 产品迭代 |
| `8ed22971fd35` | Resume | 02:00 | Part 1 + Part 2 |
| `65c080f606d5` | Wealth-Ops | 23:00 | Part 1 + Part 2 |

**输出位置:** `/home/lisa/.hermes/tasks/{project}/mission-log/`

---

## 🛠️ 使用场景

### 场景 1: 快速分析项目
```bash
gia /analyze microsoft/TypeScript
```

### 场景 2: 搜索竞品
```bash
gia /search "Python AI framework 前 5 个"
```

### 场景 3: 生成深度报告
```bash
gia /report "Rust web framework"
```

### 场景 4: PR 审查
```bash
gia /pr
# 粘贴 git diff
```

### 场景 5: 安全扫描
```bash
gia /scan src/handlers/auth.py
```

---

## 📈 性能指标

| 指标 | 目标值 | 当前值 |
|------|--------|--------|
| flake8 lint | 0 错误 | ✅ 0 |
| 测试通过率 | 100% | ✅ 100% |
| 安全漏洞 | 0 | ✅ 0 |
| 任务成功率 | >95% | ✅ 100% |

---

## 🎓 学习路径

### 新手入门
1. 阅读 `docs/USER_GUIDE.md`
2. 运行快速开始示例
3. 使用 `/help` 查看命令

### 开发者
1. 阅读 `docs/ARCHITECTURE.md`
2. 查看 `src/agents/base_agent.py`
3. 参考 `docs/FLOWCHARTS.md`

### 维护者
1. 查看 `docs/QUICK_REFERENCE.md`
2. 监控 CI/CD 状态
3. 定期更新 OWASP 规则

---

## 📚 相关资源

- **AgentScope 文档**: https://agentscope.io/
- **GitHub API**: https://docs.github.com/en/rest
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **项目仓库**: https://github.com/Lisa0926/github-insight-agent

---

*架构梳理完成 by Hermes Agent*
