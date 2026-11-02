"""
AFK tracking and automatic mention responses.
"""

import time
from typing import Optional
from datetime import datetime, timezone

import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class AFK(commands.Cog):
    """AFK status listener and automatic mention replies."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory fast cache: dict[guild_id, dict[user_id, tuple[reason, float_timestamp]]]
        self._afk_cache: dict[int, dict[int, tuple[str, float]]] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitors chat for mentions of AFK members and handles returning users."""
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        author_id = message.author.id

        # 1. Check if the message author was AFK -> Remove status
        if guild_id in self._afk_cache and author_id in self._afk_cache[guild_id]:
            reason, set_time = self._afk_cache[guild_id].pop(author_id)
            await db.execute("DELETE FROM afk_users WHERE guild_id = ? AND user_id = ?", guild_id, author_id)

            duration = int(time.time() - set_time)
            mins, secs = divmod(duration, 60)
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

            welcome_embed = ZenithEmbed.success(
                "Welcome Back!",
                f"{message.author.mention}, I have removed your AFK status. You were away for **{time_str}**."
            )
            msg = await message.channel.send(embed=welcome_embed)
            await asyncio.sleep(6)
            try:
                await msg.delete()
            except Exception:
                pass

        # 2. Check if any mentioned users are currently AFK
        if message.mentions:
            for mentioned in message.mentions:
                if mentioned.id == author_id:
                    continue

                afk_info = None
                # Check in-memory cache first
                if guild_id in self._afk_cache and mentioned.id in self._afk_cache[guild_id]:
                    afk_info = self._afk_cache[guild_id][mentioned.id]
                else:
                    # Query database
                    row = await db.fetchrow("SELECT message, set_at FROM afk_users WHERE guild_id = ? AND user_id = ?", guild_id, mentioned.id)
                    if row:
                        afk_info = (row["message"], time.time())

                if afk_info:
                    reason, set_time = afk_info
                    since_ts = int(set_time)
                    embed = ZenithEmbed.info(
                        "Member is Away",
                        f"**{mentioned.display_name}** is currently AFK: `{reason}`\n"
                        f"Away since: <t:{since_ts}:R>"
                    )
                    await message.reply(embed=embed, mention_author=False)

    @commands.command(name="afk")
    async def set_afk(self, ctx: commands.Context, *, reason: Optional[str] = "AFK"):
        """Marks your account as away-from-keyboard."""
        guild_id = ctx.guild.id
        author_id = ctx.author.id

        if guild_id not in self._afk_cache:
            self._afk_cache[guild_id] = {}

        now = time.time()
        self._afk_cache[guild_id][author_id] = (reason, now)

        if db.is_postgres:
            query = """
            INSERT INTO afk_users (guild_id, user_id, message) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET message = EXCLUDED.message;
            """
        else:
            query = """
            INSERT INTO afk_users (guild_id, user_id, message) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET message = excluded.message;
            """
        await db.execute(query, guild_id, author_id, reason)

        embed = ZenithEmbed.success("Status Updated", f"I have set your AFK: **{reason}**.\nI'll notify anyone who mentions you.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
