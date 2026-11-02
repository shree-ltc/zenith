"""
core/config.py - Centralized Configuration for Zenith

Loads environment variables with type validation and sensible fallbacks
so the bot can boot seamlessly in development or production.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Locate and load .env from project root
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration container."""

    # Core Discord Credentials
    TOKEN: str = os.getenv("BOT_TOKEN", "")
    DEFAULT_PREFIX: str = os.getenv("BOT_PREFIX", "z!")
    BOT_NAME: str = os.getenv("BOT_NAME", "Zenith")

    # Developer & Owner IDs
    OWNER_IDS: set[int] = field(default_factory=lambda: {
        int(uid.strip()) 
        for uid in os.getenv("OWNER_IDS", "").split(",") 
        if uid.strip().isdigit()
    })

    # Links & Support
    SUPPORT_SERVER: str = os.getenv("SUPPORT_SERVER", "https://discord.gg/zenith")
    WEBSITE: str = os.getenv("WEBSITE", "https://github.com/shree-ltc/zenith")
    INVITE_URL: str = os.getenv(
        "INVITE_URL",
        "https://discord.com/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot+applications.commands"
    )

    # Database & Cache Configurations
    POSTGRES_URL: str | None = os.getenv("POSTGRES_URL", None)
    REDIS_URL: str | None = os.getenv("REDIS_URL", None)
    SQLITE_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "zenith.db"

    # UI Theme Palette (Hex code ints)
    COLOR_PRIMARY: int = int(os.getenv("COLOR_PRIMARY", "5865F2"), 16)   # Discord Blurple
    COLOR_SUCCESS: int = int(os.getenv("COLOR_SUCCESS", "57F287"), 16)   # Emerald Green
    COLOR_WARNING: int = int(os.getenv("COLOR_WARNING", "FEE75C"), 16)   # Amber Yellow
    COLOR_ERROR: int = int(os.getenv("COLOR_ERROR", "ED4245"), 16)       # Crimson Red
    COLOR_NEUTRAL: int = int(os.getenv("COLOR_NEUTRAL", "2B2D31"), 16)   # Dark Charcoal

    # Limits & Guards
    ANTINUKE_PUNISHMENT: str = os.getenv("ANTINUKE_PUNISHMENT", "ban")   # ban / kick / strip_roles
    MAX_PURGE_LIMIT: int = int(os.getenv("MAX_PURGE_LIMIT", "500"))


# Global singleton instance
config = Config()
