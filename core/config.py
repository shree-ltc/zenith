"""
Configuration loader for Zenith.
Reads environment variables with sensible defaults for local development.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


@dataclass(frozen=True)
class Config:
    # Bot credentials
    TOKEN: str = os.getenv("BOT_TOKEN", "")
    DEFAULT_PREFIX: str = os.getenv("BOT_PREFIX", "z!")
    BOT_NAME: str = "Zenith"
    AUTHOR: str = "Shree"

    # Developer user IDs (1465912900710305822 = Shree)
    OWNER_IDS: set[int] = field(default_factory=lambda: {
        int(uid.strip()) 
        for uid in os.getenv("OWNER_IDS", "1465912900710305822").split(",") 
        if uid.strip().isdigit()
    })

    # Links
    SUPPORT_URL: str = os.getenv("SUPPORT_URL", "https://discord.com/users/1465912900710305822")
    GITHUB_URL: str = "https://github.com/shree-ltc/zenith"

    # Database and cache connections
    POSTGRES_URL: str | None = os.getenv("POSTGRES_URL", None)
    REDIS_URL: str | None = os.getenv("REDIS_URL", None)
    SQLITE_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "zenith.db"

    # Lavalink audio node
    LAVALINK_URI: str = os.getenv("LAVALINK_URI", "https://lava-v4.ajieblogs.eu.org:443")
    LAVALINK_PASSWORD: str = os.getenv("LAVALINK_PASSWORD", "https://dsc.gg/ajidevserver")

    # Color scheme
    COLOR_PRIMARY: int = int(os.getenv("COLOR_PRIMARY", "5865F2"), 16)
    COLOR_SUCCESS: int = int(os.getenv("COLOR_SUCCESS", "57F287"), 16)
    COLOR_WARNING: int = int(os.getenv("COLOR_WARNING", "FEE75C"), 16)
    COLOR_ERROR: int = int(os.getenv("COLOR_ERROR", "ED4245"), 16)
    COLOR_NEUTRAL: int = int(os.getenv("COLOR_NEUTRAL", "2B2D31"), 16)

    # Dashboard & Web Server
    DASHBOARD_ENABLED: bool = os.getenv("DASHBOARD_ENABLED", "true").lower() in ("true", "1", "yes")
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8080"))

    # Defaults
    ANTINUKE_PUNISHMENT: str = os.getenv("ANTINUKE_PUNISHMENT", "ban")
    MAX_PURGE_LIMIT: int = int(os.getenv("MAX_PURGE_LIMIT", "500"))


config = Config()
