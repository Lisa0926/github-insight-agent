# Git Hooks for github-insight-agent

## Installation

```bash
# Install all hooks
cp .githooks/* .git/hooks/
chmod +x .git/hooks/*
```

## Available Hooks

### commit-msg

Validates commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) format **in English**.

**Rules:**
- All commit messages MUST be written in English
- Format: `<type>(<scope>): <description>`
- CJK (Chinese/Japanese/Korean) characters are rejected

**Available types:**
| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style (no functional changes) |
| `refactor` | Code refactoring |
| `perf` | Performance improvements |
| `test` | Test-related changes |
| `build` | Build system changes |
| `ci` | CI/CD changes |
| `chore` | Other changes |
| `revert` | Revert previous commits |
| `security` | Security fixes |
| `deprecate` | Deprecate features |

**Examples:**
```
✅ Valid:
- feat(llm): add OpenAI provider support
- fix(mcp): resolve connection leak
- docs: update README
- refactor(cli): extract shared module
- test: add integration tests for MCP

❌ Invalid (contains Chinese):
- feat: 添加新功能
- fix: 修复 bug
- docs: 更新 README
```

**Installation:**
```bash
cp .githooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

### pre-commit-security (推荐安装 | Recommended)

在提交前扫描暂存文件中的硬编码敏感信息 | Scan staged files for hardcoded secrets before commit.

**检测内容 | Detects:**
- GitHub Token (`ghp_...`)
- API Keys (Anthropic, OpenAI, Dashscope)
- 飞书/微信 Channel ID (Feishu/WeChat Channel ID)

**安装 | Installation:**
```bash
cp .githooks/pre-commit-security .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

**示例输出 | Example Output:**
```
❌ 发现硬编码的敏感信息，提交已阻止:
  [HIGH] GitHub Personal Access Token
    文件：src/config.py
    行：15
    内容：GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

**解决方法 | Resolution:**
1. 使用环境变量代替硬编码值 | Use environment variables instead of hardcoded values
   ```python
   # ✅ Correct
   import os
   GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
   ```
2. 将敏感信息添加到全局 `~/.env` 文件 | Add secrets to global `~/.env` file
3. 如果只是测试占位符，使用 `YOUR_TOKEN_HERE` | Use `YOUR_TOKEN_HERE` for placeholders

## Bypassing Hooks (Emergency Only)

If you need to bypass hooks in an emergency:

```bash
git commit --no-verify -m "your message"
```

⚠️ **Note:** Only use `--no-verify` for exceptional circumstances. All commit messages should still follow the English + Conventional Commits rules.
