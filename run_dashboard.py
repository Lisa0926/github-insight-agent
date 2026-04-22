#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web 可视化仪表盘启动脚本

用法:
    python run_dashboard.py [--host 0.0.0.0] [--port 8000]
"""

import argparse
from src.web.dashboard_api import run_dashboard


def main():
    parser = argparse.ArgumentParser(description="GitHub Insight Agent Dashboard")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="端口号")
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 GitHub Insight Agent Dashboard")
    print("=" * 60)
    print(f"访问地址：http://localhost:{args.port}")
    print("=" * 60)

    run_dashboard(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
