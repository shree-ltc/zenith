"""
Sticky Messages Subsystem for Zenith.
Keeps an essential announcement or instruction pinned to the very bottom of active text channels.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import asyncio
from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class StickyMessage(commands.Cog):
    """Pins vital information to the latest position in designated channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # RAM Cache: {channel_id: {"content": str, "last_id": Optional[int]}}
        self._cache: Dict[int, Dict[str, Optional[int]]] = {}

    async def cog_load(self) -> None:
        """Load sticky message configurations into RAM."""
        rows = await db.fetch("SELECT channel_id, content, last_message_id FROM sticky_messages")
        for r in rows:
            self._cache[r["channel_id"]] = {
                "content": r["content"],
                "last_id": r["last_message_id"]
            }

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        sticky_data = self._cache.get(message.channel.id)
        if not sticky_data:
            return

        # Delete previous sticky message
        last_id = sticky_data.get("last_id")
        if last_id:
            try:
                old_msg = await message.channel.fetch_message(last_id)
                await old_msg.delete()
            except Exception:
                pass

        embed = discord.Embed(
            title="[NOTICE]",
            description=sticky_data["content"],
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Sticky Message | Zenith")

        try:
            new_msg = await message.channel.send(embed=embed)
            sticky_data["last_id"] = new_msg.id
            await db.execute("UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?", new_msg.id, message.channel.id)
        except Exception:
            pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="sticky", invoke_without_command=True)
    @commands.guild_only()
    async def sticky_group(self, ctx: commands.Context):
        """Sticky messages configuration overview."""
        embed = discord.Embed(
            title="[STICKY MESSAGES SYSTEM]",
            description="Keep vital instructions permanently visible at the bottom of active chat rooms.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}sticky add <#channel> <message>` - Create a sticky message\n"
                f"`{ctx.prefix}sticky remove <#channel>` - Remove a sticky message\n"
                f"`{ctx.prefix}sticky list` - List active sticky channels\n"
                f"`{ctx.prefix}sticky clear` - Clear all sticky messages"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @sticky_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def sticky_add(self, ctx: commands.Context, channel: discord.TextChannel, *, content: str):
        """Create or update a sticky message for a channel."""
        await db.execute(
            """
            INSERT INTO sticky_messages (guild_id, channel_id, content, last_message_id) VALUES (?, ?, ?, NULL)
            ON CONFLICT(channel_id) DO UPDATE SET content = excluded.content
            """,
            ctx.guild.id, channel.id, content
        )

        self._cache[channel.id] = {"content": content, "last_id": None}

        # Send initial sticky message
        embed = discord.Embed(title="[NOTICE]", description=content, color=ACCENT_COLOR)
        embed.set_footer(text="Sticky Message | Zenith")
        msg = await channel.send(embed=embed)
        self._cache[channel.id]["last_id"] = msg.id
        await db.execute("UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?", msg.id, channel.id)

        await ctx.send(embed=discord.Embed(title="[STICKY MESSAGE CONFIGURED]", description=f"Active in {channel.mention}.", color=ACCENT_COLOR))

    @sticky_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def sticky_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a sticky message from a channel."""
        sticky_data = self._cache.pop(channel.id, None)
        if sticky_data and sticky_data.get("last_id"):
            try:
                old_msg = await channel.fetch_message(sticky_data["last_id"])
                await old_msg.delete()
            except Exception:
                pass

        await db.execute("DELETE FROM sticky_messages WHERE channel_id = ?", channel.id)
        embed = discord.Embed(title="[STICKY REMOVED]", description=f"Removed sticky message from {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @sticky_group.command(name="list")
    @commands.guild_only()
    async def sticky_list(self, ctx: commands.Context):
        """List active sticky messages in this server."""
        rows = await db.fetch("SELECT channel_id, content FROM sticky_messages WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO STICKY MESSAGES]", description="Zero sticky messages configured.", color=ACCENT_COLOR))

        lines = [f"• <#{r['channel_id']}>: `{r['content'][:45]}...`" for r in rows]
        embed = discord.Embed(title="[ACTIVE STICKY CHANNELS]", description="\n".join(lines), color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @sticky_group.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sticky_clear(self, ctx: commands.Context):
        """Clear all sticky messages across the server."""
        await db.execute("DELETE FROM sticky_messages WHERE guild_id = ?", ctx.guild.id)
        self._cache.clear()
        embed = discord.Embed(title="[STICKY MESSAGES CLEARED]", description="All sticky messages have been deleted.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @sticky_group.command(name="view", aliases=["show"])
    @commands.guild_only()
    async def sticky_view(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Inspect the current sticky text for a channel."""
        target = channel or ctx.channel
        row = await db.fetchrow("SELECT content FROM sticky_messages WHERE guild_id = ? AND channel_id = ?", ctx.guild.id, target.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NO STICKY MESSAGE]", description=f"No sticky message configured for {target.mention}.", color=ACCENT_COLOR))

        embed = discord.Embed(
            title=f"[STICKY MESSAGE] #{target.name}",
            description=row["content"],
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @sticky_group.command(name="edit")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def sticky_edit(self, ctx: commands.Context, channel: discord.TextChannel, *, new_content: str):
        """Edit the sticky message text for a channel."""
        row = await db.fetchrow("SELECT channel_id FROM sticky_messages WHERE guild_id = ? AND channel_id = ?", ctx.guild.id, channel.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT CONFIGURED]", description=f"No sticky message found for {channel.mention}. Use `sticky add` first.", color=ACCENT_COLOR))

        await db.execute("UPDATE sticky_messages SET content = ? WHERE guild_id = ? AND channel_id = ?", new_content, ctx.guild.id, channel.id)
        self._cache[channel.id] = (new_content, None)
        await ctx.send(embed=discord.Embed(title="[OK] Sticky Message Updated", description=f"Updated text for {channel.mention}.", color=ACCENT_COLOR))

    @sticky_group.command(name="count")
    @commands.guild_only()
    async def sticky_count(self, ctx: commands.Context):
        """Display the total number of channels with sticky messages."""
        row = await db.fetchrow("SELECT COUNT(*) as c FROM sticky_messages WHERE guild_id = ?", ctx.guild.id)
        count = row["c"] if row else 0
        await ctx.send(embed=discord.Embed(title="[STICKY COUNT]", description=f"Active sticky channels: **{count}**", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(StickyMessage(bot))
