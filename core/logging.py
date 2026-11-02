"""
Logging setup for Zenith.
Handles stdout formatting and file logging with rotation.
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "zenith.log"

RESET   = "\033[0m"
BOLD    = "\033[1m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
GRAY    = "\033[90m"


class ColoredFormatter(logging.Formatter):
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
        level = f"{color}[{record.levelname:<7}]{RESET}"
        name = f"{MAGENTA}{record.name:<16}{RESET}"
        message = record.getMessage()

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            message = f"{message}\n{RED}{exc_text}{RESET}"

        return f"{GRAY}{timestamp}{RESET} {level} {name} {message}"


def setup_logger(name: str = "zenith") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    # Console output
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColoredFormatter())
    logger.addHandler(console)

    # 10MB rotating file
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    return logger


logger = setup_logger("zenith")

def info(msg: str, component: str = "zenith"):
    setup_logger(component).info(msg)

def warn(msg: str, component: str = "zenith"):
    setup_logger(component).warning(msg)

def error(msg: str, component: str = "zenith", exc_info: bool = False):
    setup_logger(component).error(msg, exc_info=exc_info)

def success(msg: str, component: str = "zenith"):
    setup_logger(component).info(f"[OK] {msg}")

def debug(msg: str, component: str = "zenith"):
    setup_logger(component).debug(msg)
