"""
Logging Setup - Centralized logging configuration

Provides logging configuration for the entire Irene system.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from ..config.models import LogLevel


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    log_file: Optional[Path] = None,
    enable_console: bool = True
) -> None:
    """
    Set up logging for the Irene system.
    
    Args:
        level: Logging level
        log_file: Optional log file path
        enable_console: Whether to enable console logging
    """
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(level.value)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name) 