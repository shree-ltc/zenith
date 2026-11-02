"""
Custom embed helper ensuring uniform formatting across all bot responses.
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from ui.colors import Color


class ZenithEmbed(discord.Embed):
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
        self.set_footer(text="Zenith")

    @classmethod
    def success(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        return cls(title=title, description=description, color=Color.SUCCESS)

    @classmethod
    def error(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        return cls(title=title, description=description, color=Color.ERROR)

    @classmethod
    def warning(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        return cls(title=title, description=description, color=Color.WARNING)

    @classmethod
    def info(cls, title: str, description: Optional[str] = None) -> "ZenithEmbed":
        return cls(title=title, description=description, color=Color.PRIMARY)
