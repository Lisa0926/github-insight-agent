# GitHub Insight Agent - 用户使用手册

**版本:** v2.1.0  
**最后更新:** 2026-04-29

---

## 📖 快速开始

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/Lisa0926/github-insight-agent.git
cd github-insight-agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制环境变量模板
cp .env.sample .env

# 编辑 .env 文件 (或使用全局配置 ~/.env)
```

**必需配置:**
```bash
# 阿里云百炼 API Key
DASHSCOPE_API_KEY=sk-xxx

# GitHub Personal Access Token
GITHUB_TOKEN=ghp_xxx
```

### 3. 运行

#### 方式 A: 使用虚拟环境（推荐）

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行 CLI
python run_cli.py
```

**常见问题:** 如果运行时报 `ModuleNotFoundError: No module named 'aiosqlite'`，请安装缺失的依赖：
```bash
pip install aiosqlite
```

#### 方式 B: 直接运行

```bash
# 方式 1: 使用 CLI 启动脚本
python run_cli.py

# 方式 2: 直接运行 main.py
python main.py
```

#### 方式 C: 安装为全局命令（可选）

```bash
# 安装项目
pip install -e .

# 之后可在任何目录运行
gia
```

**注意:** 如果使用虚拟环境，每次使用前需要先激活：
```bash
cd /path/to/github-insight-agent
source venv/bin/activate
gia
```

---

## 🎯 功能特性

### 核心功能

| 功能 | 命令 | 描述 |
|------|------|------|
| 项目分析 | `/analyze owner/repo` | 分析单个 GitHub 项目 |
| 项目搜索 | `/search <关键词>` | 搜索相关项目 |
| 详细报告 | `/report <关键词>` | 生成深度分析报告 |
| PR 审查 | `/pr` | 审查 Pull Request 代码 |
| 安全扫描 | `/scan <文件>` | OWASP 安全漏洞检测 |

### 自然语言交互 (v2.1 增强)

**无需记忆命令**，直接用自然语言描述需求：

| 自然语言输入 | 处理逻辑 |
|------------|---------|
| `搜索 Python web 框架` | LLM 意图理解 → 执行搜索 |
| `分析 microsoft/TypeScript` | LLM 意图理解 → 获取仓库详情 |
| `找最近一周 star 最高的 3 个项目` | LLM 理解意图 + 参数提取 |
| `前 5 个最活跃的 AI 框架` | LLM 提取关键词 + 搜索 |
| `和第二个对比一下` (追问) | 意图路由 → 自动调用对比工具 |
| `langchain的star数是多少` (追问) | 意图路由 → 获取仓库信息 |

**技术实现 (v2.1)**: 搜索关键词提取由 LLM 驱动（使用 `qwen-max-0428`），支持中文自然语言自动转换为英文技术术语。支持 5 类意图：搜索仓库、获取信息、深度分析、项目对比、纯对话。

---

## 📋 使用示例

### 示例 1: 分析单个项目

**命令方式:**
```bash
$ gia /analyze microsoft/TypeScript
```

**自然语言方式:**
```bash
$ gia
👤 您：分析 microsoft/TypeScript
```

**输出:**
```
📊 正在分析：microsoft/TypeScript
✅ 分析完成！

项目概览:
┌─────────────────────────────────────┐
│ 名称：microsoft/TypeScript          │
│ Stars: 98,234                       │
│ 语言：TypeScript                    │
│ 简介：TypeScript is a superset...   │
└─────────────────────────────────────┘

技术栈分析:
- 主要语言：TypeScript (92.3%)
- 构建工具：npm, Makefile
- 测试框架：Jest

质量评分：
- 代码质量：★★★★☆ (4.2/5)
- 安全性：★★★★★ (4.8/5)
- 文档完整度：★★★★★ (5.0/5)

推荐意见:
⭐⭐⭐⭐⭐ 强烈推荐
```

---

### 示例 2: 搜索项目

**命令方式:**
```bash
$ gia /search "最近三天内 star 最高的 Python AI 项目前 3 个"
```

**自然语言方式:**
```bash
$ gia
👤 您：为我搜索最近一周内 star 最高的 3 个 Python 项目
```

**输出:**
```
🔍 搜索：最近三天内 star 最高的 Python AI 项目前 3 个

找到 3 个项目:
┌───┬──────────────────────────┬───────────┬─────────┬─────────────────┐
│ # │ 项目                     │ Stars     │ 语言    │ 简介            │
├───┼──────────────────────────┼───────────┼─────────┼─────────────────┤
│ 1 │ openai/whisper           │ ⭐ 15,234  │ Python  │ Robust Speech.. │
│ 2 │ huggingface/transformers │ ⭐ 12,456  │ Python  │ State-of-art..  │
│ 3 │ antora/claude-code       │ ⭐ 8,901   │ Python  │ AI assistant... │
└───┴──────────────────────────┴───────────┴─────────┴─────────────────┘
```

---

### 示例 3: 生成详细报告

**命令方式:**
```bash
$ gia /report "Rust web framework"
```

**自然语言方式:**
```bash
$ gia
👤 您：生成一份 Rust web framework 的详细报告
```

**输出:**
```
📄 正在生成详细报告...

# Rust Web Framework 分析报告

**生成时间**: 2026-04-24 15:30
**搜索关键词**: Rust web framework
**分析项目数**: 5

## 执行摘要
本次分析对比了 5 个主流的 Rust Web 框架，
其中 Axum 表现最佳...

## 综合评估
最佳选择：Axum
次优选择：Actix-web
```

---

### 示例 4: PR 审查

```bash
$ gia /pr
# 粘贴 git diff 内容

diff --git a/src/app.py b/src/app.py
index 1234567..abcdefg 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,7 @@ def login(request):
-    password = request.args['password']
+    password = hash_password(request.args['password'])

🔍 正在审查代码变更...

## PR 审查报告

### 发现的问题

🔴 [严重] A03 注入风险
- 文件：src/app.py, 第 12 行
- 问题：直接使用用户输入作为密码
- 建议：使用 hash_password() 加密

### 修复建议
```python
# 修改前
password = request.args['password']

# 修改后
password = hash_password(request.args['password'])
```

---

### 示例 5: 安全扫描

```bash
$ gia /scan src/handlers/auth.py

🔒 正在扫描：src/handlers/auth.py

## 安全扫描报告

### 发现的问题

🔴 [严重] A02 加密失败
- 第 23 行：使用 MD5 哈希密码
- 建议：使用 bcrypt 或 argon2

🟠 [高危] A07 认证缺陷
- 第 45 行：缺少会话超时机制
- 建议：添加会话过期时间

### 扫描统计
- 扫描行数：234
- 发现问题：3
- 安全评级：⚠️  需要改进
```

---

### 示例 6: 自然语言多轮对话 (新增)

**使用虚拟环境:**
```bash
# 1. 激活虚拟环境
source venv/bin/activate

# 2. 启动 GIA
python run_cli.py

# 或直接运行
python run_cli.py
```

**交互示例:**
```bash
$ python run_cli.py

👤 您：搜索 Python AI 框架

🔍 搜索：Python AI 框架
找到 5 个项目:
┌───┬──────────────────────────┬───────────┬─────────┬─────────────────┐
│ # │ 项目                     │ Stars     │ 语言    │ 简介            │
├───┼──────────────────────────┼───────────┼─────────┼─────────────────┤
│ 1 │ huggingface/transformers │ ⭐ 90,123  │ Python  │ State-of-art.. │
│ 2 │ langchain-ai/langchain   │ ⭐ 45,678  │ Python  │ Building apps.. │
└───┴──────────────────────────┴───────────┴─────────┴─────────────────┘

👤 您：分析第一个

📊 正在分析：huggingface/transformers
✅ 分析完成！
核心功能：自然语言处理模型库
技术栈：Python
推荐意见：强烈推荐

👤 您：和第二个对比一下

🤖 Agent: transformers vs langchain 对比分析...
1. 定位差异：transformers 专注模型推理，langchain 专注应用编排
2. 社区规模：transformers 更大，langchain 增长更快
3. 适用场景：...
```

---

## 🎨 自然语言语法详解

### 支持的查询模式

| 类型 | 示例 | 识别结果 |
|------|------|---------|
| **数量** | `前 3 个 `、`5 个项目` | num_results=3 或 5 |
| **排序** | `star 最高 `、`fork 最多 `、`最新` | sort=stars/forks/updated |
| **时间** | `最近一周 `、` 过去 3 天`、`本月` | time_range=对应日期范围 |
| **项目名** | `microsoft/TypeScript` | 自动识别为 analyze |

### 意图识别 (LLM 驱动 v2.1)

系统使用 LLM 理解用户意图，支持 5 类工具调用：

| 工具 | 说明 | 示例 |
|------|------|------|
| `search_repositories` | 搜索 GitHub 仓库 | "找最火的 AI 框架" |
| `get_repo_info` | 获取单个仓库详情 | "langchain 的 star 数是多少" |
| `analyze_project` | 深度分析项目 | "分析一下这个 Rust 框架" |
| `compare_repositories` | 比较多个项目 | "对比一下 langchain 和 autogen" |
| `chat` | 纯对话（无需查 GitHub） | "你好"、"什么是 AI" |

### 高级示例

```bash
# 组合查询
👤 您：最近 7 天内 star 最高的 5 个 Python 机器学习项目
   → 搜索：Python 机器学习，时间=7 天，排序=stars，数量=5

# 模糊查询
👤 您：找一些 Rust web 框架
   → 搜索：Rust web framework

# 对比追问
👤 您：第一个和第三个哪个更好？
   → 基于上下文的对比分析
```

---

## 🔧 高级用法

### 1. 自然语言查询

支持中文自然语言，无需学习复杂语法：

```bash
# 时间范围
"最近 7 天内 star 最高的项目"
"过去一个月最活跃的 Python 项目"
"本周新创建的 Rust 项目"

# 数量限制
"前 5 个项目"
"排名前 10 的 AI 工具"

# 排序偏好
"按 fork 数排序"
"按更新时间排序"
"star 最多的"
```

---

### 2. 多轮对话

支持追问和上下文理解：

```bash
用户：搜索 Python Web 框架
助手：找到 10 个相关项目...

用户：分析第一个
助手：正在分析 Flask...

用户：和第二个对比一下
助手：Flask vs Django 对比分析...
```

---

### 3. 自定义配置

```python
# 在项目中使用
from src.core.config_manager import ConfigManager

config = ConfigManager()

# 获取模型配置
model_config = config.get_model_config("YOUR_MODEL_NAME_HERE")

# 切换 LLM 提供商
config.set_provider("openai")
```

---

## 📊 输出格式

### CLI 输出

- ✅ 成功消息 - 绿色
- ⚠️ 警告消息 - 黄色
- ❌ 错误消息 - 红色
- 📊 数据表格 - 边框美化

### 微信推送

```
📊 GitHub Insight Agent - 任务执行报告

✅ Part 1: 测试任务 - 4/4 通过
✅ Part 2: 产品报告 - 已完成

详细报告：
📁 .hermes/mission-results/mission-20260424-210000.md

祝您今天心情美美的～💖
```

---

## 🛠️ 故障排除

### 问题 1: API Key 错误

```
错误：DASHSCOPE_API_KEY 未配置
```

**解决方案:**
```bash
# 检查全局配置
cat ~/.env | grep DASHSCOPE

# 重新配置
echo "DASHSCOPE_API_KEY=sk-xxx" >> ~/.env
```

---

### 问题 2: GitHub API 限流

```
错误：API rate limit exceeded
```

**解决方案:**
1. 配置 GitHub Token
2. 等待 1 小时自动重置
3. 使用企业账号提高限额

---

### 问题 3: SQLite 锁竞争

```
错误：database is locked
```

**解决方案:**
```bash
# 清理锁定的数据库
rm data/app.db
# 重启应用
gia
```

---

## 📚 API 参考

### ReportGenerator

```python
from src.workflows.report_generator import ReportGenerator

generator = ReportGenerator()

# 搜索并分析
result = generator.researcher.search_and_analyze(
    query="python web framework",
    sort="stars",
    per_page=5
)

# 深度分析
analysis = generator.analyst.analyze_project(
    owner="tokio-rs",
    repo="axum"
)

# 生成报告
report = generator.generate_report(result, analysis)
```

---

### GitHubTool

```python
from src.tools.github_tool import GitHubTool

tool = GitHubTool()

# 搜索仓库
repos = tool.search_repositories(
    query="python",
    sort="stars",
    order="desc",
    per_page=10
)

# 获取 README
readme = tool.get_readme("owner", "repo")

# 获取仓库信息
info = tool.get_repo_info("owner", "repo")
```

---

## 📝 最佳实践

1. **使用全局配置**: 将 API Keys 放在 `~/.env`
2. **定期清理缓存**: `rm -rf data/*.db logs/*.log`
3. **查看执行历史**: `cat .hermes/tasks/github-insight-agent/INDEX.md`
4. **监控 CI 状态**: 关注 GitHub Actions 邮件通知

---

*更多示例请访问：https://github.com/Lisa0926/github-insight-agent*
