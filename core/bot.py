"""
Core bot class for Zenith.
Handles extension discovery, prefixes, and gateway events.
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Union, Any, List

import aiohttp
import discord
from discord.ext import commands
from discord import ui

# Jishaku configuration flags
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

from core.config import config
from core.database import db
from core.logging import info, warn, error, success, logger
from ui.components import embed_to_container


class ZenithContext(commands.Context):
    """
    Zenith Custom Execution Context.
    Adapts embeds seamlessly into Discord Components V2 Containers,
    housing interactive controls inside the Container via ActionRow.
    """

    def _convert_kwargs(self, kwargs: dict) -> dict:
        embed = kwargs.get("embed")
        embeds = kwargs.get("embeds")
        view = kwargs.get("view")

        if embed is not None or embeds:
            selects = []
            buttons = []
            if isinstance(view, discord.ui.View) and not isinstance(view, ui.LayoutView):
                for item in view.children:
                    if isinstance(item, (discord.ui.Select, discord.ui.ChannelSelect, discord.ui.RoleSelect, discord.ui.MentionableSelect, discord.ui.UserSelect)):
                        selects.append(item)
                    elif isinstance(item, discord.ui.Button):
                        buttons.append(item)

            containers: List[ui.Container] = []
            if embed is not None:
                c = embed_to_container(embed)
                for sel in selects:
                    c.add_item(ui.Separator())
                    c.add_item(ui.ActionRow(sel))
                if buttons:
                    c.add_item(ui.Separator())
                    for i in range(0, len(buttons), 5):
                        c.add_item(ui.ActionRow(*buttons[i:i+5]))
                containers.append(c)

            if embeds:
                for idx, emb in enumerate(embeds):
                    c = embed_to_container(emb)
                    if idx == len(embeds) - 1:
                        for sel in selects:
                            c.add_item(ui.Separator())
                            c.add_item(ui.ActionRow(sel))
                        if buttons:
                            c.add_item(ui.Separator())
                            for i in range(0, len(buttons), 5):
                                c.add_item(ui.ActionRow(*buttons[i:i+5]))
                    containers.append(c)

            if isinstance(view, ui.LayoutView):
                for c in containers:
                    view.add_item(c)
                layout_view = view
            else:
                layout_view = ui.LayoutView(timeout=getattr(view, "timeout", 180.0) if view else None)
                for c in containers:
                    layout_view.add_item(c)

            kwargs["embed"] = None
            kwargs["embeds"] = None
            kwargs["view"] = layout_view

        return kwargs

    async def send(self, content=None, **kwargs):
        kwargs = self._convert_kwargs(kwargs)
        return await super().send(content, **kwargs)

    async def reply(self, content=None, **kwargs):
        kwargs = self._convert_kwargs(kwargs)
        return await super().reply(content, **kwargs)


async def determine_prefix(bot: "ZenithBot", message: discord.Message) -> list[str]:
    """Retrieves custom guild prefix from database or falls back to default prefix."""
    user_id = message.author.id if message.author else 0
    is_np = getattr(bot, "is_noprefix", None)
    if is_np and is_np(user_id):
        if not message.guild:
            return commands.when_mentioned_or(config.DEFAULT_PREFIX, "z!", "&", "")(bot, message)
        prefix = await db.get_prefix(message.guild.id)
        return commands.when_mentioned_or(prefix, "z!", "&", "")(bot, message)

    if not message.guild:
        return commands.when_mentioned_or(config.DEFAULT_PREFIX, "z!", "&")(bot, message)

    prefix = await db.get_prefix(message.guild.id)
    return commands.when_mentioned_or(prefix, "z!", "&")(bot, message)


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

        # Developer & Security State
        self.maintenance_mode: bool = False
        self.maintenance_reason: str = "Scheduled system maintenance in progress."
        self.blacklisted_users: set[int] = set()
        self.blacklisted_guilds: set[int] = set()
        self.global_bans: set[int] = set()

        # Global command security gate
        @self.check
        async def global_security_filter(ctx: commands.Context) -> bool:
            # 1. Ignore blacklisted users
            if ctx.author.id in self.blacklisted_users:
                return False
            # 2. Ignore blacklisted guilds
            if ctx.guild and ctx.guild.id in self.blacklisted_guilds:
                return False
            # 3. Enforce maintenance mode for non-owners
            if self.maintenance_mode and ctx.author.id not in config.OWNER_IDS:
                embed = discord.Embed(
                    title="[MAINTENANCE MODE ACTIVE]",
                    description=(
                        "Zenith is currently undergoing developer maintenance.\n\n"
                        f"• **Reason:** {self.maintenance_reason}\n"
                        "• **Status:** Operations in progress\n\n"
                        "Command execution is temporarily restricted to bot developers."
                    ),
                    color=0x0F0F13
                )
                embed.set_footer(text="Zenith Suite | Developed by Shree")
                await ctx.reply(embed=embed, mention_author=False)
                return False
            return True

    def is_noprefix(self, user_id: int) -> bool:
        return user_id in self.noprefix_users or user_id in config.OWNER_IDS

    async def get_context(self, origin: Union[discord.Message, discord.Interaction], /, *, cls=ZenithContext) -> Any:
        return await super().get_context(origin, cls=cls)

    async def setup_hook(self) -> None:
        """Executes asynchronous setup before the bot connects to Discord gateway."""
        info("Initializing system dependencies...", "core")

        # 1. Start HTTP Client session
        self.session = aiohttp.ClientSession()

        # 2. Initialize Database & Cache pools
        await self.db.initialize()

        # 2b. Load System Security States (Maintenance, Blacklists, Global Bans)
        try:
            maint_row = await self.db.fetchrow("SELECT value FROM system_settings WHERE key = 'maintenance'")
            if maint_row:
                self.maintenance_mode = True
                self.maintenance_reason = maint_row["value"]
                warn(f"Maintenance mode active on boot: {self.maintenance_reason}", "core")

            bl_rows = await self.db.fetch("SELECT target_id, target_type FROM blacklists")
            for r in bl_rows:
                if r["target_type"] == "user":
                    self.blacklisted_users.add(r["target_id"])
                elif r["target_type"] == "guild":
                    self.blacklisted_guilds.add(r["target_id"])

            gban_rows = await self.db.fetch("SELECT user_id FROM global_bans")
            for r in gban_rows:
                self.global_bans.add(r["user_id"])

            success(
                f"Security state initialized: {len(self.blacklisted_users)} user(s), "
                f"{len(self.blacklisted_guilds)} guild(s) blacklisted, "
                f"{len(self.global_bans)} global ban(s)",
                "core"
            )
        except Exception as e:
            warn(f"Failed to load system security states from DB: {e}", "core")

        # 3. Load Global Error Handler
        try:
            await self.load_extension("core.errors")
            success("Loaded core error handling subsystem", "core")
        except Exception as e:
            error(f"Failed to load core error handler: {e}", "core", exc_info=True)

        # 3b. Load Jishaku (jsk) Diagnostic Engine
        try:
            await self.load_extension("jishaku")
            success("Loaded Jishaku (jsk) diagnostic suite", "core")
        except Exception as e:
            warn(f"Failed to load Jishaku: {e}", "core")

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

    async def on_member_join(self, member: discord.Member) -> None:
        """Enforces global bans on joining accounts."""
        if member.id in self.global_bans:
            if member.guild.me.guild_permissions.ban_members and member.guild.me.top_role > member.top_role:
                try:
                    await member.ban(reason="[ZENITH GBAN] Globally banned account from bot network.")
                    info(f"Enforced global ban on {member} (ID: {member.id}) in guild '{member.guild.name}'", "core")
                except Exception:
                    pass

    async def close(self) -> None:
        """Gracefully terminates open sockets and connection pools."""
        warn("Initiating graceful shutdown sequence...", "core")
        if self.session and not self.session.closed:
            await self.session.close()
        await self.db.close()
        await super().close()
        info("Zenith shut down cleanly.", "core")
