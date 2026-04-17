# -*- coding: utf-8 -*-
"""
日志封装模块 - 基于 loguru 的全局 Logger

功能:
- 统一的日志格式 (时间、文件名、行号、日志级别、消息)
- 同时输出到控制台和文件
- 支持日志轮转和清理

使用示例:
    from src.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("这是一条信息日志")
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as loguru_logger


def get_logger(
    name: str,
    log_file: Optional[str] = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
    level: str = "INFO",
) -> loguru_logger:
    """
    获取配置好的 logger 实例

    Args:
        name: 模块名称 (通常传入 __name__)
        log_file: 日志文件路径，默认 logs/app.log
        rotation: 日志轮转大小，默认 10MB
        retention: 日志保留时间，默认 7 天
        level: 日志级别，默认 INFO

    Returns:
        配置好的 loguru logger 实例
    """
    # 移除默认的 handler
    loguru_logger.remove()

    # 确定日志目录
    base_dir = Path(__file__).parent.parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 日志文件路径
    if log_file is None:
        log_file = str(logs_dir / "app.log")
    else:
        log_file = str(logs_dir / log_file)

    # 控制台输出格式 (带颜色)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # 文件输出格式 (无颜色)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # 添加控制台 handler
    loguru_logger.add(
        sys.stderr,
        format=console_format,
        level=level,
        colorize=True,
    )

    # 添加文件 handler (支持轮转)
    loguru_logger.add(
        log_file,
        format=file_format,
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    return loguru_logger


# 全局默认 logger
default_logger = get_logger("github_insight_agent")
