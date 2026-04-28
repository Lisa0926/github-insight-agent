#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security scan utility for CI pipeline.

Scans all tracked files (or staged files in pre-commit mode) for hardcoded
secrets, API keys, tokens, and local path exposure.

Usage:
    # CI mode - scan all files
    python .github/scripts/secret_scan.py --ci-mode --path .

    # Pre-commit mode - scan only staged files
    python .github/scripts/secret_scan.py --staged
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Secret patterns to detect
SECRET_PATTERNS = {
    "github_token": {
        "re": r"ghp_[a-zA-Z0-9]{20,}",
        "severity": "HIGH",
        "msg": "GitHub Personal Access Token",
    },
    "github_oauth": {
        "re": r"gho_[a-zA-Z0-9]{20,}",
        "severity": "HIGH",
        "msg": "GitHub OAuth Token",
    },
    "anthropic_key": {
        "re": r"sk-ant-[a-zA-Z0-9_-]{20,}",
        "severity": "HIGH",
        "msg": "Anthropic API Key",
    },
    "openai_key": {
        "re": r"sk-proj-[a-zA-Z0-9_-]{20,}|sk-[a-zA-Z0-9]{48}",
        "severity": "HIGH",
        "msg": "OpenAI API Key",
    },
    "dashscope_key": {
        "re": r"sk-[a-zA-Z0-9]{20,}",
        "severity": "HIGH",
        "msg": "DashScope API Key",
    },
    "generic_secret": {
        "re": r"(?:api[_-]?key|secret|token|password)\s*[=:]\s*['\"](?:ghp_|sk-ant-|sk-proj-|sk-[a-zA-Z0-9]{20,})",
        "severity": "HIGH",
        "msg": "Generic secret assignment",
    },
    "feishu_channel": {
        "re": r"ou_[a-zA-Z0-9_-]{10,}",
        "severity": "MEDIUM",
        "msg": "Feishu/Lark Channel ID",
    },
    "local_path_linux": {
        "re": r"/home/[a-zA-Z0-9_-]+/",
        "severity": "HIGH",
        "msg": "Linux local path exposure (may leak username)",
    },
    "local_path_macos": {
        "re": r"/Users/[a-zA-Z0-9_-]+/",
        "severity": "HIGH",
        "msg": "macOS local path exposure (may leak username)",
    },
    "local_path_windows": {
        "re": r"C:\\Users\\[a-zA-Z0-9_-]+\\",
        "severity": "HIGH",
        "msg": "Windows local path exposure (may leak username)",
    },
}

# Directories to skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", "env", ".env",
    "dist", "build", "*.egg-info", ".mypy_cache", ".pytest_cache",
}

# File extensions to skip (binary files)
SKIP_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".whl", ".egg", ".so", ".dylib", ".dll", ".exe",
    ".db", ".sqlite", ".sqlite3",
    ".pyc", ".pyo",
}

# Allowed placeholder patterns (lines containing these are not flagged)
ALLOWED_PLACEHOLDERS = [
    r"YOUR[_\w]*_HERE",
    r"PLACEHOLDER",
    r"xxx",
    r"example\.com",
    r"/home/(user|username|<[^>]+>)/",
    r"<project_root>",
    r"<[A-Z_]+>",
]


def should_skip_file(filepath: str) -> bool:
    """Check if file should be skipped from scanning"""
    path = Path(filepath)

    # Skip directories
    for part in path.parts:
        if part in SKIP_DIRS:
            return True

    # Skip binary extensions
    if path.suffix.lower() in SKIP_EXTS:
        return True

    return False


def is_allowed_placeholder(line: str) -> bool:
    """Check if line contains an allowed placeholder pattern"""
    for pattern in ALLOWED_PLACEHOLDERS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def is_comment(line: str) -> bool:
    """Check if line is a comment"""
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*")


def scan_content(content: str, filepath: str) -> list:
    """Scan file content for secrets"""
    findings = []
    for line_num, line in enumerate(content.split("\n"), 1):
        # Skip comments and blank lines
        if not line.strip() or is_comment(line):
            continue

        # Skip allowed placeholders
        if is_allowed_placeholder(line):
            continue

        # Skip lines that read from environment variables
        if "os.getenv" in line or "os.environ" in line:
            continue

        for name, config in SECRET_PATTERNS.items():
            if re.search(config["re"], line):
                findings.append({
                    "file": filepath,
                    "line": line_num,
                    "pattern": name,
                    "severity": config["severity"],
                    "msg": config["msg"],
                    "content": line.strip()[:120],
                })

    return findings


def scan_all_files(root: str) -> list:
    """Scan all files tracked by git in the project"""
    all_findings = []
    root_path = Path(root).resolve()

    # Get list of files tracked by git
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, cwd=root_path,
    )
    tracked_files = [f for f in result.stdout.strip().split("\n") if f]

    for rel_path in tracked_files:
        if should_skip_file(rel_path):
            continue

        filepath = root_path / rel_path
        if not filepath.exists():
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = scan_content(content, rel_path)
            all_findings.extend(findings)
        except (PermissionError, OSError):
            continue

    return all_findings


def scan_staged_files() -> list:
    """Scan only staged (cached) git files"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    staged = [f for f in result.stdout.strip().split("\n") if f]

    all_findings = []
    for filepath in staged:
        if should_skip_file(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            findings = scan_content(content, filepath)
            all_findings.extend(findings)
        except (PermissionError, OSError):
            continue

    return all_findings


def main() -> int:
    """Main entry point"""
    ci_mode = "--ci-mode" in sys.argv
    staged_mode = "--staged" in sys.argv

    print("=" * 60)
    print("  Secret & Sensitive Data Scan")
    print("=" * 60)
    print()

    if staged_mode:
        print("Mode: scanning staged files...")
        findings = scan_staged_files()
    elif ci_mode:
        root = "."
        for i, arg in enumerate(sys.argv):
            if arg == "--path" and i + 1 < len(sys.argv):
                root = sys.argv[i + 1]
        print(f"Mode: scanning all files in '{root}'...")
        findings = scan_all_files(root)
    else:
        print("Usage: secret_scan.py --ci-mode --path <dir>  OR  secret_scan.py --staged")
        return 0

    if not findings:
        print("PASS - No hardcoded secrets found")
        print("=" * 60)
        return 0

    high_count = sum(1 for f in findings if f["severity"] == "HIGH")

    print(f"FAIL - Found {len(findings)} issue(s) (HIGH={high_count}):")
    print("-" * 60)
    for f in findings:
        print(f"  [{f['severity']}] {f['msg']}")
        print(f"    File: {f['file']}")
        print(f"    Line: {f['line']}")
        print(f"    Content: {f['content']}")
        print()

    print("-" * 60)
    print("Remediation:")
    print("  1. Use environment variables: os.getenv('MY_KEY')")
    print("  2. Store secrets in ~/.env (never commit .env)")
    print("  3. Use placeholders: YOUR_KEY_HERE")
    print("  4. Use ~/.env instead of absolute paths like /home/user/.env")
    print("=" * 60)

    return 1 if high_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
