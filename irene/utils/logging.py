"""
Logging Setup - Centralized logging configuration

Provides logging configuration for the entire Irene system.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..config.models import LogLevel


def _rotate_log_file(log_file: Path) -> None:
    """
    Rotate existing log file by adding timestamp to filename.
    
    Args:
        log_file: Path to the log file to rotate
    """
    if log_file.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create new filename with timestamp: irene_20241220_143025.log
        stem = log_file.stem  # 'irene'
        suffix = log_file.suffix  # '.log'
        rotated_name = f"{stem}_{timestamp}{suffix}"
        rotated_path = log_file.parent / rotated_name
        
        try:
            log_file.rename(rotated_path)
            # Log the rotation to console since file logging isn't set up yet
            print(f"Rotated existing log file to: {rotated_path}")
        except OSError as e:
            # If rotation fails, just warn and continue
            print(f"Warning: Could not rotate log file {log_file}: {e}")


class UTF8StreamHandler(logging.StreamHandler):
    """
    StreamHandler that ensures UTF-8 encoding for stdout/stderr.
    
    Addresses Windows terminal encoding issues by explicitly writing
    UTF-8 encoded bytes to the stream buffer when available.
    """

    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # If stream supports buffer (like sys.stdout), write UTF-8 encoded bytes
            if hasattr(stream, 'buffer'):
                stream.buffer.write(msg.encode('utf-8'))
                stream.buffer.write(self.terminator.encode('utf-8'))
                stream.buffer.flush()
            else:
                stream.write(msg + self.terminator)
                stream.flush()
        except Exception:
            self.handleError(record)


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
    
    # Console handler with UTF-8 support
    if enable_console:
        console_handler = UTF8StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler (already uses UTF-8 by default in Python 3)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Rotate existing log file before creating new one
        _rotate_log_file(log_file)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name) 