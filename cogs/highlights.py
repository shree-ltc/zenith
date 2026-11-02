"""
Keyword highlight notification engine for Zenith.
Alerts users via direct message when configured keywords are mentioned in channels they have access to.
"""

from __future__ import annotations

import discord
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13


class Highlights(commands.Cog):
    """Personal keyword alert notifications system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory keyword lookup: guild_id -> dict[user_id, set[keyword]]
        self._highlights: dict[int, dict[int, set[str]]] = {}
        self._loaded_guilds: set[int] = set()

    async def _load_guild_highlights(self, guild_id: int):
        rows = await db.fetch(
            "SELECT user_id, keyword FROM user_highlights WHERE guild_id = ?",
            guild_id
        )
        mapping: dict[int, set[str]] = {}
        for r in rows:
            uid = r["user_id"]
            kw = r["keyword"].lower()
            if uid not in mapping:
                mapping[uid] = set()
            mapping[uid].add(kw)
        self._highlights[guild_id] = mapping
        self._loaded_guilds.add(guild_id)

    @commands.group(name="highlight", aliases=["hl"], invoke_without_command=True)
    async def highlight_group(self, ctx: commands.Context):
        """Manage keyword highlight notifications."""
        embed = discord.Embed(
            title="[HIGHLIGHTS] Keyword Notification Engine",
            description="Receive direct messages whenever specified keywords or topics are mentioned in the server.",
            color=THEME_COLOR
        )
        embed.add_field(
            name="Commands",
            value=(
                "`highlight add <keyword>` - Register a keyword for DM alerts\n"
                "`highlight remove <keyword>` - Remove a registered keyword\n"
                "`highlight list` - View your active monitored keywords\n"
                "`highlight clear` - Delete all monitored keywords in this server"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    @highlight_group.command(name="add")
    async def hl_add(self, ctx: commands.Context, *, keyword: str):
        """Register a keyword or phrase to receive DM alerts."""
        clean_kw = keyword.strip().lower()
        if len(clean_kw) < 2 or len(clean_kw) > 50:
            await ctx.reply("[ERROR] Keyword must be between 2 and 50 characters in length.", mention_author=False)
            return

        # Check existing count
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as c FROM user_highlights WHERE guild_id = ? AND user_id = ?",
            ctx.guild.id, ctx.author.id
        )
        if count_row and count_row["c"] >= 20:
            await ctx.reply("[ERROR] Maximum limit of 20 highlight keywords reached per server.", mention_author=False)
            return

        existing = await db.fetchrow(
            "SELECT keyword FROM user_highlights WHERE guild_id = ? AND user_id = ? AND keyword = ?",
            ctx.guild.id, ctx.author.id, clean_kw
        )
        if existing:
            await ctx.reply(f"[ERROR] You already have keyword '{clean_kw}' registered.", mention_author=False)
            return

        await db.execute(
            "INSERT INTO user_highlights (guild_id, user_id, keyword) VALUES (?, ?, ?)",
            ctx.guild.id, ctx.author.id, clean_kw
        )

        if ctx.guild.id not in self._highlights:
            self._highlights[ctx.guild.id] = {}
        if ctx.author.id not in self._highlights[ctx.guild.id]:
            self._highlights[ctx.guild.id][ctx.author.id] = set()
        self._highlights[ctx.guild.id][ctx.author.id].add(clean_kw)

        embed = discord.Embed(
            title="[OK] Highlight Added",
            description=f"You will be alerted when `{clean_kw}` is mentioned in {ctx.guild.name}.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @highlight_group.command(name="remove", aliases=["del", "delete"])
    async def hl_remove(self, ctx: commands.Context, *, keyword: str):
        """Remove a monitored keyword."""
        clean_kw = keyword.strip().lower()
        row = await db.fetchrow(
            "SELECT keyword FROM user_highlights WHERE guild_id = ? AND user_id = ? AND keyword = ?",
            ctx.guild.id, ctx.author.id, clean_kw
        )
        if not row:
            await ctx.reply(f"[ERROR] Keyword '{clean_kw}' is not in your highlight registry.", mention_author=False)
            return

        await db.execute(
            "DELETE FROM user_highlights WHERE guild_id = ? AND user_id = ? AND keyword = ?",
            ctx.guild.id, ctx.author.id, clean_kw
        )

        if ctx.guild.id in self._highlights and ctx.author.id in self._highlights[ctx.guild.id]:
            self._highlights[ctx.guild.id][ctx.author.id].discard(clean_kw)

        embed = discord.Embed(
            title="[OK] Highlight Removed",
            description=f"Keyword `{clean_kw}` was removed from your alerts.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @highlight_group.command(name="list")
    async def hl_list(self, ctx: commands.Context):
        """List all keywords you currently monitor in this server."""
        rows = await db.fetch(
            "SELECT keyword FROM user_highlights WHERE guild_id = ? AND user_id = ?",
            ctx.guild.id, ctx.author.id
        )
        if not rows:
            await ctx.reply("[INFO] You have no active highlight keywords in this server.", mention_author=False)
            return

        kw_list = "\n".join(f"• `{r['keyword']}`" for r in rows)
        embed = discord.Embed(
            title=f"[HIGHLIGHTS] Your Active Triggers ({len(rows)}/20)",
            description=kw_list,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @highlight_group.command(name="clear")
    async def hl_clear(self, ctx: commands.Context):
        """Clear all monitored keywords for this server."""
        await db.execute(
            "DELETE FROM user_highlights WHERE guild_id = ? AND user_id = ?",
            ctx.guild.id, ctx.author.id
        )
        if ctx.guild.id in self._highlights and ctx.author.id in self._highlights[ctx.guild.id]:
            self._highlights[ctx.guild.id].pop(ctx.author.id, None)

        embed = discord.Embed(
            title="[OK] Highlights Cleared",
            description=f"All of your keyword alerts for {ctx.guild.name} have been purged.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        guild_id = message.guild.id
        if guild_id not in self._loaded_guilds:
            await self._load_guild_highlights(guild_id)

        guild_data = self._highlights.get(guild_id, {})
        if not guild_data:
            return

        content_lower = message.content.lower()
        if not content_lower:
            return

        for user_id, keywords in list(guild_data.items()):
            if user_id == message.author.id:
                continue

            member = message.guild.get_member(user_id)
            if not member:
                continue

            # Verify permissions
            perms = message.channel.permissions_for(member)
            if not (perms.view_channel and perms.read_message_history):
                continue

            matched = [kw for kw in keywords if kw in content_lower]
            if matched:
                try:
                    embed = discord.Embed(
                        title=f"[HIGHLIGHT ALERT] {message.guild.name}",
                        description=f"Keyword `{matched[0]}` matched in {message.channel.mention}",
                        color=THEME_COLOR
                    )
                    clean_content = message.content[:500] if len(message.content) > 500 else message.content
                    embed.add_field(name="Sender", value=f"{message.author} (`{message.author.id}`)", inline=True)
                    embed.add_field(name="Message", value=f"{clean_content}\n\n[Jump to Message]({message.jump_url})", inline=False)
                    await member.send(embed=embed)
                except Exception:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Highlights(bot))
