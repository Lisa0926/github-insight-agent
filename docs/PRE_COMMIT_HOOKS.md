# Pre-commit Hooks 使用指南

**最后更新:** 2026-04-24

---

## 📋 功能概述

Pre-commit hook 会在每次 `git commit` 时自动运行安全扫描，防止敏感信息被提交到仓库。

---

## 🔒 检测项目

### 1. API Keys 和 Tokens

| 类型 | 检测模式 | 严重程度 |
|------|---------|---------|
| GitHub Token | `ghp_[a-zA-Z0-9]{20,}` | HIGH |
| Anthropic Key | `sk-ant-[a-zA-Z0-9_-]{20,}` | HIGH |
| OpenAI Key | `sk-proj-*` / `sk-[48 字符]` | HIGH |
| Dashscope Key | `dashscope[a-zA-Z0-9_-]{20,}` | HIGH |
| Feishu Channel | `ou_*` / `chan_*` | MEDIUM |

### 2. 本地路径暴露 (新增)

| 类型 | 检测模式 | 严重程度 |
|------|---------|---------|
| Linux 路径 | `/home/用户名/` | MEDIUM |
| macOS 路径 | `/Users/用户名/` | MEDIUM |
| Windows 路径 | `C:\Users\用户名\` | MEDIUM |

### 3. 文档文件额外检查

仅针对 `.md`, `.rst`, `.txt` 文件：

| 检测项 | 说明 |
|--------|------|
| .env 文件路径 | 应使用 `~/.env` 而非绝对路径 |
| 项目绝对路径 | 应使用 `<项目根目录>` 占位符 |

---

## ✅ 允许的形式

以下形式**不会**被阻止：

```bash
# 正确的 .env 引用
~/.env
.env  # 在代码注释中

# 占位符
YOUR_TOKEN_HERE
your_api_key_here
sk-xxx
ghp_your

# 环境变量读取
os.getenv('GITHUB_TOKEN')
os.environ.get('API_KEY')
config.get_api_key()
```

---

## ❌ 被阻止的形式

以下形式**会**被阻止提交：

```python
# 硬编码 Token
GITHUB_TOKEN = "ghp_abc123def456..."

# 绝对路径 (文档中)
配置文件位于：/home/username/.env
项目路径：/home/username/projects/github-insight-agent
```

---

## 🛠️ 解决方法

### 问题 1: API Key 硬编码

```python
# ❌ 错误
API_KEY = "sk-xxx123456"

# ✅ 正确
import os
API_KEY = os.getenv('DASHSCOPE_API_KEY')
```

### 问题 2: 本地路径暴露

```markdown
# ❌ 错误
配置文件位于 `/home/username/.env`

# ✅ 正确
配置文件位于 `~/.env`
项目根目录为 `<项目根目录>/`
```

---

## 📁 安装/更新 Hook

```bash
# 安装 hook
cp .githooks/pre-commit-security .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 或重新安装
bash .githooks/install-hooks.sh
```

---

## 🧪 测试

```bash
# 测试 Token 检测
echo 'TOKEN = "ghp_YOUR_TOKEN_HERE_FOR_TESTING"' > test.py
git add test.py
git commit -m "test"
# 预期：提交被阻止

# 测试路径检测
echo 'Path: /home/username/project' >> docs/README.md
git add docs/README.md
git commit -m "test"
# 预期：警告但允许提交 (MEDIUM)

# 测试正确形式
echo 'Config: ~/.env' >> docs/README.md
git add docs/README.md
git commit -m "test"
# 预期：通过
```

---

## 📝 错误输出示例

```
============================================================
  Git Pre-commit 安全扫描
============================================================
扫描 1 个暂存文件...

❌ 发现硬编码的敏感信息，提交已阻止:
------------------------------------------------------------
  [HIGH] GitHub Personal Access Token
    文件：src/config.py
    行：10
    内容：TOKEN = "ghp_abc123def456..."

------------------------------------------------------------
发现 1 个问题 (HIGH=1)

解决方法:
  1. 使用环境变量代替硬编码值
     例如：os.getenv('GITHUB_TOKEN')

  2. 将敏感信息添加到 ~/.env 文件 (不要使用绝对路径)

  3. 如果只是测试占位符，使用：YOUR_TOKEN_HERE
  
  4. 文档中使用 ~/ 或 <项目根目录> 代替绝对路径
     错误：/home/user/project
     正确：~/.env 或 <项目根目录>/configs/

============================================================

❌ 提交被阻止 - 请修复 HIGH 级别安全问题
```

---

## 🔧 绕过 Hook (不推荐)

仅在特殊情况下使用：

```bash
git commit --no-verify -m "your message"
```

**注意:** 这会跳过所有检查，仅在你确定没有敏感信息时使用。

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `.githooks/pre-commit-security` | Hook 源文件 |
| `.git/hooks/pre-commit` | 实际运行的 Hook |
| `.githooks/install-hooks.sh` | 安装脚本 |

---

*安全是每个人的责任*
