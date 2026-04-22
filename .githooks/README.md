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

## Bypassing Hooks (Emergency Only)

If you need to bypass hooks in an emergency:

```bash
git commit --no-verify -m "your message"
```

⚠️ **Note:** Only use `--no-verify` for exceptional circumstances. All commit messages should still follow the English + Conventional Commits rules.
