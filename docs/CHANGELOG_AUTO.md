# Changelog 自动生成

本项目使用 [git-cliff](https://git-cliff.org/) 自动生成 Changelog，基于 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

## 快速开始

### 1. 安装 git-cliff

```bash
# macOS
brew install git-cliff

# Linux (cargo)
cargo install git-cliff

# Linux (apt)
sudo apt install git-cliff

# Windows (scoop)
scoop install git-cliff

# 或使用 pip
pip install git-cliff
```

### 2. 生成 Changelog

```bash
# 生成完整 Changelog
git cliff --output CHANGELOG.md

# 预览最新版本的变更
git cliff --unreleased

# 生成特定版本的 Changelog
git cliff --tag v1.1.0
```

### 3. 自动更新（推荐）

使用 git hooks 在每次 commit 后自动更新：

```bash
# 设置 git hooks
git cliff --init
```

---

## 提交规范

请遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

### 格式

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### 类型说明

| Type | 说明 | Changelog 分类 |
|------|------|---------------|
| `feat` | 新功能 | Added |
| `fix` | Bug 修复 | Fixed |
| `docs` | 文档更新 | Documentation |
| `style` | 代码格式（不影响功能） | Changed |
| `refactor` | 重构 | Changed |
| `perf` | 性能优化 | Performance |
| `test` | 测试相关 | Testing |
| `build` | 构建系统 | Build |
| `ci` | CI/CD | CI/CD |
| `chore` | 其他变更 | Chore |
| `revert` | 回滚 | Reverted |
| `security` | 安全修复 | Security |
| `deprecate` | 弃用功能 | Deprecated |

### 示例

```bash
# 新功能
git commit -m "feat(llm): add OpenAI provider support"

# Bug 修复
git commit -m "fix(mcp): resolve connection leak in mock client"

# 文档更新
git commit -m "docs: update README with installation guide"

# 重构
git commit -m "refactor(core): extract StudioHelper module"

# 破坏性变更（在 body 中标注）
git commit -m "feat(api): migrate to v2 endpoint

BREAKING CHANGE: API v1 is deprecated
```

---

## 自动化配置

### GitHub Actions 自动发布

创建 `.github/workflows/release.yml`：

```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate Changelog
        uses: orhun/git-cliff-action@v2
        with:
          config: cliff.toml
          args: -vv --latest --strip header

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          body_path: CHANGELOG.md
          token: ${{ secrets.GITHUB_TOKEN }}
```

### Pre-commit Hook

创建 `.git/hooks/commit-msg`：

```bash
#!/bin/sh
# 验证提交信息是否符合 Conventional Commits 规范

commit_msg=$(cat "$1")
if ! echo "$commit_msg" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|security|deprecate)(\(.+\))?: .+"; then
    echo "ERROR: Commit message does not follow Conventional Commits"
    echo "See: https://www.conventionalcommits.org/"
    exit 1
fi
```

---

## 版本发布流程

### 1. 更新版本号

```bash
# 编辑版本号（在合适的地方，如 pyproject.toml 或 __init__.py）
```

### 2. 创建 Git Tag

```bash
git tag -a v1.1.0 -m "Release version 1.1.0"
git push origin v1.1.0
```

### 3. 自动生成 Changelog

```bash
git cliff -o CHANGELOG.md
git add CHANGELOG.md
git commit -m "docs: update changelog for v1.1.0"
git push
```

---

## 故障排除

### 问题：Changelog 为空

**原因**: 没有符合规范的提交

**解决**:
```bash
# 检查提交历史
git log --oneline

# 查看 git-cliff 解析结果
git cliff --debug
```

### 问题：版本号不正确

**原因**: Tag 命名不规范

**解决**: 确保 tag 格式为 `v*.*.*`（如 `v1.1.0`）

### 问题：某些提交未出现在 Changelog

**原因**: 提交信息不符合 Conventional Commits 规范

**解决**: 修改提交信息或调整 `cliff.toml` 中的过滤规则

---

## 配置说明

详细配置选项请参考 [git-cliff 文档](https://git-cliff.org/docs/configuration)。

关键配置在 `cliff.toml`：
- `[git]` - Git 相关配置
- `[commit_parser]` - 提交解析规则
- `[bump]` - 版本号自动升级规则
- `[template]` - Changelog 模板

---

*文档最后更新：2026-04-22*
