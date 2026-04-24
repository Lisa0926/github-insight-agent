# github-insight-agent Mission

Project directory: `/home/lisa/claude_apps/github-insight-agent`

---

## Part 1: Architecture + Development + Testing

### Goals
- Self-test and validate current functionality
- Identify and fix security vulnerabilities
- Add missing test cases
- Execute full test suite

### Tasks

#### 1.1 Architecture Review
- Review project structure and dependencies
- Check for outdated packages (pip audit)
- Verify configuration loading
- Identify any architectural debt or TODOs

#### 1.2 Development & Bug Fixes
- Review open issues in project backlog
- Fix any identified security vulnerabilities
- Address code quality warnings (lint, type errors)
- Refactor any problematic code patterns

#### 1.3 Test Coverage
- Run existing test suite: `python tests/test_integration.py`
- Identify untested code paths
- Add unit tests for critical functions
- Add integration tests for API endpoints

#### 1.4 AgentScope Memory 一致性检查（本项目特有）
- [ ] PersistentMemory 初始化正确（db_path 指向有效 SQLite 文件）
- [ ] conversation_history 表结构完整（id, role, content, timestamp）
- [ ] memory_index 表支持向量/关键词检索
- [ ] 写入后立即可读（无 SQLite 锁竞争）
- [ ] 长时间运行无内存泄漏（monitor gc 警告）
- [ ] 断连后可恢复（SQLite 文件未损坏）

#### 1.5 MCP 连接验证（本项目特有）
- [ ] MCP Client 初始化成功（从配置加载 server_url）
- [ ] 与 MCP Server 握手成功（/health 检查通过）
- [ ] 工具注册完整（list_tools 返回预期工具列表）
- [ ] 消息路由正确（send_message 无 404）
- [ ] 断线自动重连（max_retries=3, backoff=5s）

#### 1.6 Test Execution
```bash
cd /home/lisa/claude_apps/github-insight-agent
source venv/bin/activate
python tests/test_integration.py
```

### Deliverables
- [ ] Test results summary (pass/fail count)
- [ ] List of vulnerabilities fixed
- [ ] New test cases added (file paths + descriptions)
- [ ] Any blocking issues discovered

---

## Part 2: Product Manager

### Goals
- Analyze competitor products
- Maintain product backlog
- Create iteration plan for next cycle

### Tasks

#### 2.1 Competitive Analysis
Research competing GitHub analytics tools:
- What features do they offer?
- What are their pricing models?
- What do users praise/complain about?

Sources to check:
- GitHub Marketplace alternatives
- Product Hunt similar products
- Reddit r/github, r/devtools discussions
- Twitter/X developer feedback

#### 2.2 Product Backlog
Review and prioritize:
- User-requested features (from issues/feedback)
- Technical debt items
- Feature improvements
- Bug fixes

Format:
| Priority | Item | Type | Effort | Notes |
|----------|------|------|--------|-------|
| P0 | ... | feature/bug/debt | S/M/L | ... |

#### 2.3 Iteration Plan
Based on backlog, propose next iteration:
- Sprint duration (1 week / 2 weeks)
- Top 3-5 items to tackle
- Expected outcomes
- Dependencies/risks

Format:
## Next Iteration (YYYY-MM-DD to YYYY-MM-DD)

### Goals
1. ...
2. ...

### Tasks
- [ ] Task 1 (owner, estimate)
- [ ] Task 2 (owner, estimate)

### Deliverables
- [ ] Competitive analysis summary (max 500 words)
- [ ] Updated product backlog (prioritized table)
- [ ] Next iteration plan

---

## Output Format

### 详细报告保存位置
- 目录：`/home/lisa/claude_apps/github-insight-agent/.hermes/mission-results/`
- 文件名：`mission-YYYYMMDD-HHMMSS-{part1|part2}.md`

### 微信推送格式 (手机端优化)

**要求:**
1. 使用 emoji 增强可读性
2. 简短摘要 (不超过 20 行)
3. 关键数据用表格展示
4. 包含详细报告的引用链接

**模板:**
```
📊 GitHub Insight Agent - 任务执行报告

✅ Part 1: 测试任务 - 4/4 通过
✅ Part 2: 产品报告 - 已完成

详细报告：
📁 .hermes/mission-results/mission-YYYYMMDD-HHMMSS.md
```

---

## Notification Settings

**多渠道推送:** 启用
- 渠道：微信 (openclaw-weixin) + 飞书 (feishu)
- **两条消息内容完全统一**，仅 channel 不同
- 接收人：当前会话用户

**推送语气:** 工程师风格 + 温暖结尾
- 称呼：「Lisa」
- 风格：专业、清晰、工程师视角
- 结尾：「祝您今天心情美美的～」💖

**格式:** 手机端优化 (emoji + 简短摘要 + 报告链接)

---

## 🔒 安全规则 - 敏感信息管理

**所有敏感信息必须存放在全局 `/home/lisa/.env` 中，禁止在项目目录中存储:**

❌ **禁止在项目中的内容:**
- API Keys (DASHSCOPE_API_KEY, ANTHROPIC_AUTH_TOKEN, etc.)
- GitHub Tokens
- 微信 Channel ID
- 飞书 Group ID / User ID
- 任何密码或密钥

✅ **全局配置位置:** `/home/lisa/.env`

**项目配置方式:**
```python
from dotenv import load_dotenv
load_dotenv('/home/lisa/.env')  # 加载全局配置
import os
api_key = os.getenv('DASHSCOPE_API_KEY')
```

---

## 📌 版本管理

**自动化 changelog 生成**: `git-cliff`

**配置位置**: `cliff.toml` (项目根目录)

**发布流程:**
```bash
# 1. 生成 CHANGELOG
git-cliff -o CHANGELOG.md

# 2. 查看待发布的 commits
git-cliff --unreleased

# 3. 语义化版本号
git tag v1.2.0
```

**Mission 执行后自动记录**:
- 执行日期
- 版本号（从 git tag 获取）
- 关键变更摘要

---

## Execution Notes

- Use `hermes` CLI for all agent operations
- Run code changes in Docker sandbox if needed
- Commit results to git after review
- **任务完成后必须通过微信推送结果**
