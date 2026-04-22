#!/bin/bash
# Git Hooks 安装脚本
# 用法：./install-hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GIT_HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "=============================================="
echo "  Git Hooks 安装"
echo "=============================================="
echo ""

# 检查 .git 目录是否存在
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "错误：未在 $PROJECT_ROOT 找到 .git 目录"
    echo "请确保在项目根目录下运行此脚本"
    exit 1
fi

# 创建 hooks 目录（如果不存在）
mkdir -p "$GIT_HOOKS_DIR"

# 安装 commit-msg hook
echo "安装 commit-msg hook..."
cp "$SCRIPT_DIR/commit-msg" "$GIT_HOOKS_DIR/commit-msg"
chmod +x "$GIT_HOOKS_DIR/commit-msg"
echo "  ✅ commit-msg 已安装"

# 安装 pre-commit-security hook
echo "安装 pre-commit-security hook..."
cp "$SCRIPT_DIR/pre-commit-security" "$GIT_HOOKS_DIR/pre-commit"
chmod +x "$GIT_HOOKS_DIR/pre-commit"
echo "  ✅ pre-commit-security 已安装"

# 安装 post-commit hook（如果存在）
if [ -f "$SCRIPT_DIR/post-commit" ]; then
    echo "安装 post-commit hook..."
    cp "$SCRIPT_DIR/post-commit" "$GIT_HOOKS_DIR/post-commit"
    chmod +x "$GIT_HOOKS_DIR/post-commit"
    echo "  ✅ post-commit 已安装"
fi

echo ""
echo "=============================================="
echo "  安装完成"
echo "=============================================="
echo ""
echo "已安装的 hooks:"
echo "  - commit-msg: 验证提交信息格式（英文 + Conventional Commits）"
echo "  - pre-commit: 提交前安全扫描（检测硬编码敏感信息）"
echo "  - post-commit: 提交后自动同步到远程"
echo ""
echo "运行以下命令验证安装:"
echo "  git hook list"
echo ""
