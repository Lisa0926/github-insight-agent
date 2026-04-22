# Git Hooks 自动更新 Changelog

## 已安装的 Hooks

### 1. post-commit (提交后自动更新 Changelog)

**位置**: `.git/hooks/post-commit`  
**来源**: `.githooks/post-commit`

**功能**:
- 每次 commit 后自动运行 `git cliff --unreleased`
- 更新 `CHANGELOG.md` 文件
- 如果 git-cliff 未安装，自动跳过

**安装状态**: ✅ 已安装

---

### 2. commit-msg (提交信息验证)

**位置**: `.git/hooks/commit-msg`  
**来源**: `.githooks/commit-msg`

**功能**:
- 验证 commit message 是否符合 Conventional Commits 规范
- 不符合规范的提交会被拒绝

**格式要求**:
```
<type>(<scope>): <description>
```

**可用的 type**:
| Type | 说明 | Changelog 分类 |
|------|------|---------------|
| `feat` | 新功能 | Added |
| `fix` | Bug 修复 | Fixed |
| `docs` | 文档更新 | Documentation |
| `style` | 代码格式 | Changed |
| `refactor` | 重构 | Changed |
| `perf` | 性能优化 | Performance |
| `test` | 测试 | Testing |
| `build` | 构建系统 | Build |
| `ci` | CI/CD | CI/CD |
| `chore` | 其他变更 | Chore |
| `revert` | 回滚 | Reverted |
| `security` | 安全修复 | Security |
| `deprecate` | 弃用功能 | Deprecated |

**示例**:
```bash
✅ 正确
git commit -m "feat(llm): add OpenAI provider support"
git commit -m "fix(mcp): resolve connection leak"
git commit -m "docs: update README"

❌ 错误
git commit -m "added new feature"
git commit -m "fix bug"
git commit -m "update"
```

**安装状态**: ✅ 已安装

---

## 使用方法

### 安装 Hooks

```bash
# 方式 1: 手动复制
cp .githooks/post-commit .git/hooks/post-commit
cp .githooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/*

# 方式 2: 使用 git-cliff
git cliff --init
```

### 测试 Hook

```bash
# 测试 commit-msg hook
echo "invalid message" | .git/hooks/commit-msg /dev/stdin

# 测试 post-commit hook
git commit --allow-empty -m "test: test hook"
```

### 卸载 Hooks

```bash
rm .git/hooks/post-commit
rm .git/hooks/commit-msg
```

---

## GitHub Actions 自动发布

推送 tag 时自动生成 GitHub Release：

```bash
# 创建并推送 tag
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0
```

GitHub Actions 会：
1. 检出代码
2. 运行 git-cliff 生成 Changelog
3. 创建 GitHub Release

---

## 故障排除

### Hook 未执行

检查权限：
```bash
ls -la .git/hooks/
```

确保文件有执行权限：
```bash
chmod +x .git/hooks/post-commit
chmod +x .git/hooks/commit-msg
```

### git-cliff 未找到

安装 git-cliff：
```bash
pip install git-cliff
```

### Changelog 格式不正确

检查 `cliff.toml` 配置，确保 commit 类型映射正确。

---

*文档最后更新：2026-04-22*
