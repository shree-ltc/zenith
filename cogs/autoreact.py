"""
Autoreact System for Zenith.
Automatically adds reactions to messages based on keyword triggers or targeted channel rooms.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Dict, List
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class Autoreact(commands.Cog):
    """Keyword and channel-based automatic reaction system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # RAM Cache: {guild_id: {trigger_lowercase: emoji_str}}
        self._keyword_cache: Dict[int, Dict[str, str]] = {}
        # RAM Cache: {guild_id: {channel_id: [emoji_str, ...]}}
        self._channel_cache: Dict[int, Dict[int, List[str]]] = {}

    async def cog_load(self) -> None:
        """Load autoreact registry into RAM."""
        k_rows = await db.fetch("SELECT guild_id, trigger, emoji FROM autoreacts")
        for r in k_rows:
            gid = r["guild_id"]
            if gid not in self._keyword_cache:
                self._keyword_cache[gid] = {}
            self._keyword_cache[gid][r["trigger"].lower()] = r["emoji"]

        c_rows = await db.fetch("SELECT guild_id, channel_id, emoji FROM channel_autoreacts")
        for r in c_rows:
            gid = r["guild_id"]
            cid = r["channel_id"]
            if gid not in self._channel_cache:
                self._channel_cache[gid] = {}
            if cid not in self._channel_cache[gid]:
                self._channel_cache[gid][cid] = []
            self._channel_cache[gid][cid].append(r["emoji"])

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # 1. Channel-level reactions (e.g., suggestions, media)
        guild_chans = self._channel_cache.get(message.guild.id, {})
        emojis = guild_chans.get(message.channel.id)
        if emojis:
            for em in emojis:
                try:
                    await message.add_reaction(em)
                except Exception:
                    pass

        # 2. Keyword-level reactions
        if message.content:
            guild_kwords = self._keyword_cache.get(message.guild.id, {})
            if guild_kwords:
                content_lower = message.content.lower()
                for trig, em in guild_kwords.items():
                    if trig in content_lower:
                        try:
                            await message.add_reaction(em)
                        except Exception:
                            pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="autoreact", invoke_without_command=True)
    @commands.guild_only()
    async def autoreact_group(self, ctx: commands.Context):
        """Autoreact management and subcommands."""
        embed = discord.Embed(
            title="[AUTOREACT SYSTEM]",
            description="Automatically apply reactions to messages based on keyword triggers or channel rooms.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Keyword Commands",
            value=(
                f"`{ctx.prefix}autoreact add <trigger> <emoji>` - Add keyword reaction\n"
                f"`{ctx.prefix}autoreact remove <trigger>` - Remove keyword reaction\n"
                f"`{ctx.prefix}autoreact list` - List registered keyword reactions\n"
                f"`{ctx.prefix}autoreact reset` - Clear all keyword reactions"
            ),
            inline=False
        )
        embed.add_field(
            name="Channel Room Commands",
            value=(
                f"`{ctx.prefix}autoreact channel add <channel> <emoji>` - Add channel reaction\n"
                f"`{ctx.prefix}autoreact channel remove <channel> <emoji>` - Remove channel reaction\n"
                f"`{ctx.prefix}autoreact channel list` - List active channel rooms\n"
                f"`{ctx.prefix}autoreact channel reset` - Clear channel rooms"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @autoreact_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ar_add(self, ctx: commands.Context, trigger: str, emoji: str):
        """Add a keyword trigger reaction."""
        trigger_clean = trigger.strip().lower()
        await db.execute(
            """
            INSERT INTO autoreacts (guild_id, trigger, emoji) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, trigger) DO UPDATE SET emoji = excluded.emoji
            """,
            ctx.guild.id, trigger_clean, emoji
        )

        if ctx.guild.id not in self._keyword_cache:
            self._keyword_cache[ctx.guild.id] = {}
        self._keyword_cache[ctx.guild.id][trigger_clean] = emoji

        embed = discord.Embed(
            title="[AUTOREACT REGISTERED]",
            description=f"Trigger `{trigger_clean}` will now react with `{emoji}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @autoreact_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ar_remove(self, ctx: commands.Context, trigger: str):
        """Remove a keyword trigger reaction."""
        trigger_clean = trigger.strip().lower()
        await db.execute("DELETE FROM autoreacts WHERE guild_id = ? AND trigger = ?", ctx.guild.id, trigger_clean)

        if ctx.guild.id in self._keyword_cache:
            self._keyword_cache[ctx.guild.id].pop(trigger_clean, None)

        embed = discord.Embed(
            title="[AUTOREACT REMOVED]",
            description=f"Removed trigger `{trigger_clean}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @autoreact_group.command(name="list")
    @commands.guild_only()
    async def ar_list(self, ctx: commands.Context):
        """List registered keyword auto reactions."""
        guild_kwords = self._keyword_cache.get(ctx.guild.id, {})
        if not guild_kwords:
            return await ctx.send(embed=discord.Embed(
                title="[NO KEYWORD REACTIONS]",
                description=f"No triggers registered. Add one using `{ctx.prefix}autoreact add <trigger> <emoji>`.",
                color=ACCENT_COLOR
            ))

        lines = [f"• **{trig}** -> `{em}`" for trig, em in guild_kwords.items()]
        embed = discord.Embed(
            title="[KEYWORD AUTOREACTS]",
            description="\n".join(lines[:25]),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @autoreact_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_reset(self, ctx: commands.Context):
        """Clear all keyword reactions."""
        await db.execute("DELETE FROM autoreacts WHERE guild_id = ?", ctx.guild.id)
        self._keyword_cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[AUTOREACT RESET]",
            description="Cleared all keyword reactions.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # CHANNEL ROOM SUBGROUP
    # ---------------------------------------------------------

    @autoreact_group.group(name="channel", invoke_without_command=True)
    @commands.guild_only()
    async def ar_channel_group(self, ctx: commands.Context):
        """Channel-specific autoreaction rules."""
        await self.autoreact_group(ctx)

    @ar_channel_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def ar_channel_add(self, ctx: commands.Context, channel: discord.TextChannel, emoji: str):
        """Add an automatic reaction to all messages in a channel."""
        await db.execute(
            """
            INSERT INTO channel_autoreacts (guild_id, channel_id, emoji) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, channel_id, emoji) DO NOTHING
            """,
            ctx.guild.id, channel.id, emoji
        )

        if ctx.guild.id not in self._channel_cache:
            self._channel_cache[ctx.guild.id] = {}
        if channel.id not in self._channel_cache[ctx.guild.id]:
            self._channel_cache[ctx.guild.id][channel.id] = []
        if emoji not in self._channel_cache[ctx.guild.id][channel.id]:
            self._channel_cache[ctx.guild.id][channel.id].append(emoji)

        embed = discord.Embed(
            title="[CHANNEL AUTOREACT REGISTERED]",
            description=f"Messages in {channel.mention} will automatically receive reaction `{emoji}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_channel_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def ar_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel, emoji: str):
        """Remove a channel automatic reaction."""
        await db.execute(
            "DELETE FROM channel_autoreacts WHERE guild_id = ? AND channel_id = ? AND emoji = ?",
            ctx.guild.id, channel.id, emoji
        )

        if ctx.guild.id in self._channel_cache and channel.id in self._channel_cache[ctx.guild.id]:
            try:
                self._channel_cache[ctx.guild.id][channel.id].remove(emoji)
            except ValueError:
                pass

        embed = discord.Embed(
            title="[CHANNEL AUTOREACT REMOVED]",
            description=f"Removed reaction `{emoji}` from {channel.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_channel_group.command(name="list")
    @commands.guild_only()
    async def ar_channel_list(self, ctx: commands.Context):
        """List active channel automatic reaction rooms."""
        guild_chans = self._channel_cache.get(ctx.guild.id, {})
        if not guild_chans:
            return await ctx.send(embed=discord.Embed(
                title="[NO CHANNEL AUTOREACTS]",
                description=f"No channel rooms configured. Add one using `{ctx.prefix}autoreact channel add #channel <emoji>`.",
                color=ACCENT_COLOR
            ))

        lines = []
        for cid, em_list in guild_chans.items():
            ch = ctx.guild.get_channel(cid)
            ch_str = ch.mention if ch else f"`{cid}`"
            lines.append(f"• {ch_str}: " + " ".join(f"`{e}`" for e in em_list))

        embed = discord.Embed(
            title="[CHANNEL AUTOREACT ROOMS]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_channel_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_channel_reset(self, ctx: commands.Context):
        """Clear all channel reaction rooms."""
        await db.execute("DELETE FROM channel_autoreacts WHERE guild_id = ?", ctx.guild.id)
        self._channel_cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[CHANNEL AUTOREACTS RESET]",
            description="Cleared all channel reaction rooms.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Autoreact(bot))
