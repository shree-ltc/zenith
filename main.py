"""
main.py - Entry Point for Zenith Discord Bot

Bootstraps the asynchronous runtime, enforces environment validation,
and handles operating system termination signals gracefully.
"""

import os
import sys
import asyncio
from core.bot import ZenithBot
from core.config import config
from core.logging import info, error, warn, success


def main():
    """Validates configuration and launches the Discord bot instance."""
    info("=" * 60, "boot")
    info("  ZENITH - Next-Generation Discord Infrastructure & Security", "boot")
    info("=" * 60, "boot")

    if not config.TOKEN:
        error("BOT_TOKEN is missing or blank in .env file! Exiting.", "boot")
        sys.exit(1)

    bot = ZenithBot()

    try:
        bot.run(config.TOKEN, log_handler=None)
    except KeyboardInterrupt:
        warn("Termination signal received via KeyboardInterrupt.", "boot")
    except Exception as e:
        error(f"Fatal exception during runtime: {e}", "boot", exc_info=True)


if __name__ == "__main__":
    main()
