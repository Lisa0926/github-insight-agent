#!/bin/bash
# GitHub Insight Agent CLI startup script
# Usage: ./start_cli.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
python run_cli.py
