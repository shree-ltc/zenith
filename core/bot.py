"""
Core bot class for Zenith.
Handles extension discovery, prefixes, and gateway events.
"""

import time
import asyncio
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from core.config import config
from core.database import db
from core.logging import info, warn, error, success, logger


async def determine_prefix(bot: "ZenithBot", message: discord.Message) -> list[str]:
    """Retrieves custom guild prefix from database or falls back to default prefix."""
    user_id = message.author.id if message.author else 0
    is_np = getattr(bot, "is_noprefix", None)
    if is_np and is_np(user_id):
        if not message.guild:
            return commands.when_mentioned_or(config.DEFAULT_PREFIX, "")(bot, message)
        prefix = await db.get_prefix(message.guild.id)
        return commands.when_mentioned_or(prefix, "")(bot, message)

    if not message.guild:
        return commands.when_mentioned_or(config.DEFAULT_PREFIX)(bot, message)

    prefix = await db.get_prefix(message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


class ZenithBot(commands.AutoShardedBot):
    """The central Zenith Discord client."""

    def __init__(self):
        # Configure Discord Gateway Intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        intents.moderation = True

        super().__init__(
            command_prefix=determine_prefix,
            intents=intents,
            help_command=None,  # Custom paginated help system implemented in cogs/help.py
            owner_ids=config.OWNER_IDS,
            case_insensitive=True,
            strip_after_prefix=True,
            allowed_mentions=discord.AllowedMentions(
                roles=False,
                everyone=False,
                users=True,
                replied_user=False
            )
        )

        self.session: Optional[aiohttp.ClientSession] = None
        self.launch_time: float = time.time()
        self.db = db
        self.noprefix_users: set[int] = set()

    def is_noprefix(self, user_id: int) -> bool:
        return user_id in self.noprefix_users or user_id in config.OWNER_IDS

    async def setup_hook(self) -> None:
        """Executes asynchronous setup before the bot connects to Discord gateway."""
        info("Initializing system dependencies...", "core")

        # 1. Start HTTP Client session
        self.session = aiohttp.ClientSession()

        # 2. Initialize Database & Cache pools
        await self.db.initialize()

        # 3. Load Global Error Handler
        try:
            await self.load_extension("core.errors")
            success("Loaded core error handling subsystem", "core")
        except Exception as e:
            error(f"Failed to load core error handler: {e}", "core", exc_info=True)

        # 4. Discover and load all feature cogs
        cogs_dir = Path(__file__).resolve().parent.parent / "cogs"
        loaded_count = 0

        for file in cogs_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            extension_name = f"cogs.{file.stem}"
            try:
                await self.load_extension(extension_name)
                loaded_count += 1
                logger.debug(f"Loaded extension: {extension_name}")
            except Exception as e:
                error(f"Failed to load extension {extension_name}: {e}", "core", exc_info=True)

        success(f"Successfully loaded {loaded_count} feature cogs", "core")

    async def on_ready(self) -> None:
        """Fires when gateway handshake is complete and cache is populated."""
        guild_count = len(self.guilds)
        user_count = sum(g.member_count or 0 for g in self.guilds)
        shard_count = self.shard_count or 1

        info(f"Connected as {self.user} (ID: {self.user.id})", "core")
        info(f"Serving {guild_count:,} guilds and {user_count:,} members across {shard_count} shard(s)", "core")

        # Set professional activity status
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{config.DEFAULT_PREFIX}help | Zenith Protection"
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

    async def close(self) -> None:
        """Gracefully terminates open sockets and connection pools."""
        warn("Initiating graceful shutdown sequence...", "core")
        if self.session and not self.session.closed:
            await self.session.close()
        await self.db.close()
        await super().close()
        info("Zenith shut down cleanly.", "core")
