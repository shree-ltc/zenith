"""
core/logging.py - Professional Logging System for Zenith

Provides clean ANSI-colored console logs with timestamps, component tags,
and structured file logging with automatic rotation in logs/zenith.log.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Log output directory
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "zenith.log"

# ANSI Color Codes for terminal output
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
BLUE    = "\033[34m"
GRAY    = "\033[90m"

class ColoredFormatter(logging.Formatter):
    """Custom formatter to render clean, readable terminal logs with distinct colors."""

    LEVEL_COLORS = {
        logging.DEBUG:    GRAY,
        logging.INFO:     CYAN,
        logging.WARNING:  YELLOW,
        logging.ERROR:    RED,
        logging.CRITICAL: BOLD + RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, RESET)
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = f"{color}{BOLD}[{record.levelname:<7}]{RESET}"
        name = f"{MAGENTA}{record.name:<16}{RESET}"
        message = record.getMessage()

        if record.exc_info:
            # Include traceback if an exception was passed
            exc_text = self.formatException(record.exc_info)
            message = f"{message}\n{RED}{exc_text}{RESET}"

        return f"{GRAY}{timestamp}{RESET} {level} {name} {message}"


def setup_logger(name: str = "zenith") -> logging.Logger:
    """Configures both console and rotating file handlers for a logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Console Handler (Colorized)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # Rotating File Handler (Max 10MB per file, 5 backups preserved)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger

# Primary logger instance
logger = setup_logger("zenith")

# Quick helper functions
def info(msg: str, component: str = "zenith"):
    setup_logger(component).info(msg)

def warn(msg: str, component: str = "zenith"):
    setup_logger(component).warning(msg)

def error(msg: str, component: str = "zenith", exc_info: bool = False):
    setup_logger(component).error(msg, exc_info=exc_info)

def success(msg: str, component: str = "zenith"):
    setup_logger(component).info(f"{GREEN}{BOLD}✓{RESET} {msg}")

def debug(msg: str, component: str = "zenith"):
    setup_logger(component).debug(msg)
