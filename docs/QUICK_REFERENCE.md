# GitHub Insight Agent - 快速参考卡片

**打印版本** | 最后更新：2026-04-24

---

## 🚀 常用命令

```bash
# 启动交互模式
gia

# 分析项目
gia /analyze owner/repo

# 搜索项目
gia /search "关键词"

# 生成报告
gia /report "关键词"

# PR 审查
gia /pr

# 安全扫描
gia /scan <file>
```

---

## 📁 目录结构

```
github-insight-agent/
├── src/
│   ├── agents/         # 智能体
│   ├── core/           # 核心模块
│   ├── tools/          # 工具集
│   ├── workflows/      # 工作流
│   └── cli/            # 命令行
├── docs/               # 文档
├── tests/              # 测试
├── data/               # 数据
├── logs/               # 日志
└── configs/            # 配置
```

---

## 🔑 配置位置

| 配置项 | 位置 |
|--------|------|
| API Keys | `~/.env` |
| 模型配置 | `configs/model_configs.json` |
| 任务历史 | `.hermes/tasks/{project}/INDEX.md` |
| 日志 | `logs/` |
| 数据库 | `data/app.db` |

---

## 🎯 自然语言示例

```
✅ "最近三天内 star 最高的 Python 项目前 3 个"
✅ "按 fork 数排序找 AI 相关项目"
✅ "本周最活跃的 Rust Web 框架"
✅ "分析 microsoft/typescript 并生成报告"
```

---

## 🛠️ 故障排除

| 问题 | 解决方案 |
|------|----------|
| API Key 错误 | 检查 `~/.env` |
| GitHub 限流 | 配置 Token 或等待 1h |
| SQLite 锁定 | `rm data/app.db` |
| CI 失败 | 查看 GitHub Actions 日志 |

---

## 📊 核心模块

```
User → CLI → ReportGenerator → Agents → Tools → APIs
                     ↓
                PersistentMemory (SQLite)
                     ↓
                Logs + Reports
```

---

## 🔒 安全规则

- **53 条 OWASP Top 10 规则**
- **PR 自动审查**
- **CI/CD 集成**
- **敏感信息集中管理**

---

## 📚 文档链接

- [架构文档](ARCHITECTURE.md)
- [用户手册](USER_GUIDE.md)
- [流程图](FLOWCHARTS.md)
- [CHANGELOG](../CHANGELOG.md)

---

## ⏰ 定时任务

GIA 项目每日自动执行：

| 任务 | 时间 | 内容 |
|------|------|------|
| Part 1: 技术迭代 | 21:00 | 架构审查、安全修复、测试补充 |
| Part 2: 产品迭代 | 21:00 | 竞品分析、待办列表、迭代计划 |

**推送渠道:** 微信 + 飞书

---

## 📝 开发 checklist

- [ ] 代码通过 flake8
- [ ] 测试通过 pytest
- [ ] 无安全漏洞 (pip-audit)
- [ ] 更新 CHANGELOG
- [ ] 提交 Git

---

**完整版文档:** `<项目根目录>/docs/`
