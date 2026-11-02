"""
ui/embeds.py - Standardized Zenith Embed Factory

Provides a uniform, sleek interface for all responses, alerts, and notifications.
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from ui.colors import Color


class ZenithEmbed(discord.Embed):
    """Base embed for Zenith enforcing consistent branding, footers, and timestamps."""

    def __init__(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[discord.Colour] = None,
        timestamp: Optional[datetime] = None,
    ):
        super().__init__(
            title=title,
            description=description,
            color=color or Color.PRIMARY,
            timestamp=timestamp or datetime.now(timezone.utc)
        )
        self.set_footer(text="Zenith • Security & Infrastructure")

    @classmethod
    def success(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        """Generates a positive confirmation embed."""
        embed = cls(
            title=f"✓  {title}",
            description=description,
            color=Color.SUCCESS
        )
        return embed

    @classmethod
    def error(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        """Generates an error or rejection embed."""
        embed = cls(
            title=f"✕  {title}",
            description=description,
            color=Color.ERROR
        )
        return embed

    @classmethod
    def warning(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        """Generates an alert or warning embed."""
        embed = cls(
            title=f"⚠  {title}",
            description=description,
            color=Color.WARNING
        )
        return embed

    @classmethod
    def info(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        """Generates a general informational embed."""
        embed = cls(
            title=title,
            description=description,
            color=Color.PRIMARY
        )
        return embed
