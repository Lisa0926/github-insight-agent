#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - 交互式 CLI 启动脚本

用法:
    python run_cli.py

功能:
    - 彩色友好输出
    - 命令自动补全
    - 进度条显示
    - 结构化报告展示
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 检查并安装依赖
def check_dependencies():
    """检查并提示安装依赖"""
    missing = []

    try:
        import rich
    except ImportError:
        missing.append("rich")

    try:
        import prompt_toolkit
    except ImportError:
        missing.append("prompt_toolkit")

    if missing:
        print("⚠️  缺少可选依赖，影响 CLI 体验:")
        for pkg in missing:
            print(f"   - {pkg}")
        print()
        print("安装命令:")
        print(f"   pip install {' '.join(missing)}")
        print()
        print("继续启动 (基础模式)...")
        print()

check_dependencies()

from src.cli.app import main

if __name__ == "__main__":
    main()
