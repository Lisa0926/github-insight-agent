# GitHub Insight Agent - CLI 使用指南

## 启动 CLI

```bash
cd /home/lisa/claude_apps/github-insight-agent
source venv/bin/activate
python run_cli.py
```

## 可用命令

### 项目分析命令

| 命令 | 描述 | 示例 |
|------|------|------|
| `/analyze <owner/repo>` | 分析指定 GitHub 项目 | `/analyze Lisa0926/github-insight-agent` |
| `/search <关键词>` | 搜索 GitHub 项目 | `/search large language model language:python` |
| `/report <关键词>` | 生成详细分析报告 | `/report agent framework` |

### 代码审查命令

| 命令 | 描述 | 示例 |
|------|------|------|
| `/pr` | 审查 Pull Request | `/pr` 然后粘贴 diff |
| `/scan <文件>` | 安全扫描代码 | `/scan src/main.py` |

### 辅助命令

| 命令 | 描述 |
|------|------|
| `/history` | 显示对话历史 |
| `/clear` | 清空对话 |
| `/export <路径>` | 导出对话记录 |
| `/help` | 显示帮助 |
| `/quit` | 退出程序 |

## 功能特性

### 1. 彩色输出
使用 rich 库实现彩色友好的终端输出

### 2. 命令自动补全
使用 prompt_toolkit 实现 Tab 补全和历史记录

### 3. 进度条显示
长时间任务显示进度条

### 4. 结构化报告
生成的报告以结构化格式展示

## 使用示例

### 分析 GitHub 项目

```
👤 您：/analyze Lisa0926/github-insight-agent

🤖 Researcher: 正在分析项目...
   - 获取 README
   - 获取项目统计信息
   - 分析代码结构

🤖 Analyst: 生成分析报告...
   - 代码质量评分：8.5/10
   - 活跃度：高
   - 推荐指数：★★★★☆
```

### 搜索项目

```
👤 您：/search large language model language:python

🤖 搜索结果:
   1. langchain-ai/langchain ⭐ 45k
   2. huggingface/transformers ⭐ 90k
   3. ...
```

### 代码安全扫描

```
👤 您：/scan src/tools/pr_review_tool.py

🔒 安全扫描结果:
   ✅ 未发现已知安全漏洞
   ℹ️  建议：添加输入验证
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Q` | 快速退出 |
| `↑/↓` | 浏览历史命令 |
| `Tab` | 命令自动补全 |
| `Ctrl+C` | 中断当前操作 |

## 环境要求

- Python 3.9+
- 可选依赖：
  - rich>=13.0.0 (彩色输出)
  - prompt_toolkit>=3.0.0 (交互体验)

安装可选依赖：
```bash
pip install rich prompt_toolkit
```

## 配置文件

CLI 从以下配置加载设置：
- `.env` 或 `/home/lisa/.env` (中央配置)
- `configs/config.yaml` (应用配置)

必要的环境变量：
```bash
DASHSCOPE_API_KEY=your_api_key
GITHUB_TOKEN=your_github_token
```

## 输出目录

- 日志：`logs/`
- 报告：`.hermes/mission-results/`
- 对话导出：指定路径

---

**启动命令**:
```bash
cd /home/lisa/claude_apps/github-insight-agent && python run_cli.py
```
