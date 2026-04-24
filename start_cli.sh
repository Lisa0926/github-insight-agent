#!/bin/bash
# GitHub Insight Agent CLI 启动脚本
# 用法：./start_cli.sh

cd /home/lisa/claude_apps/github-insight-agent
source venv/bin/activate
python run_cli.py
