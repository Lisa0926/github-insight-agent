# -*- coding: utf-8 -*-
"""
Logger wrapper module - Global Logger based on loguru

Features:
- Unified log format (time, filename, line number, log level, message)
- Output to both console and file
- Support log rotation and cleanup

Usage example:
    from src.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("This is an info log")
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
    Get a configured logger instance

    Args:
        name: Module name (usually pass __name__)
        log_file: Log file path, defaults to logs/app.log
        rotation: Log rotation size, defaults to 10MB
        retention: Log retention time, defaults to 7 days
        level: Log level, defaults to INFO

    Returns:
        Configured loguru logger instance
    """
    # Remove default handler
    loguru_logger.remove()

    # Determine log directory
    base_dir = Path(__file__).parent.parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Log file path
    if log_file is None:
        log_file = str(logs_dir / "app.log")
    else:
        log_file = str(logs_dir / log_file)

    # Console output format (with colors)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # File output format (without colors)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # Add console handler
    loguru_logger.add(
        sys.stderr,
        format=console_format,
        level=level,
        colorize=True,
    )

    # Add file handler (with rotation support)
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


# Global default logger
default_logger = get_logger("github_insight_agent")
