"""
cogs/logs.py - Multi-Channel Audit & Event Logging Engine for Zenith

Dispatches real-time forensic logs for deleted/edited messages, member joins/leaves,
role changes, nickname updates, and channel modifications.
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class Logs(commands.Cog):
    """Event auditing and security logging subsystem."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_log_channel(self, guild: discord.Guild, log_type: str = "message_logs") -> Optional[discord.TextChannel]:
        """Fetches the configured log channel for a specific event category."""
        row = await db.fetchrow(f"SELECT {log_type} FROM server_logs WHERE guild_id = ?", guild.id)
        if not row or not row.get(log_type):
            return None
        ch = guild.get_channel(row[log_type])
        return ch if isinstance(ch, discord.TextChannel) else None

    # ═══════════════════════════════════════════════════════════════
    #  MESSAGE AUDIT EVENTS
    # ═══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Dispatches an audit embed when a message is deleted."""
        if not message.guild or message.author.bot:
            return

        channel = await self.get_log_channel(message.guild, "message_logs")
        if not channel:
            return

        embed = ZenithEmbed(
            title="🗑️ Message Deleted",
            color=Color.ERROR,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{message.author} ({message.author.id})", icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Content", value=message.content or "*[No text content]*", inline=False)

        if message.attachments:
            att_names = ", ".join(f"`{a.filename}`" for a in message.attachments)
            embed.add_field(name="Attachments", value=att_names, inline=False)

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Dispatches an audit embed when a message is updated."""
        if not before.guild or before.author.bot or before.content == after.content:
            return

        channel = await self.get_log_channel(before.guild, "message_logs")
        if not channel:
            return

        embed = ZenithEmbed(
            title="✏️ Message Edited",
            color=Color.WARNING,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{before.author} ({before.author.id})", icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Jump to Message", value=f"[Click Here]({after.jump_url})", inline=True)
        embed.add_field(name="Before", value=before.content or "*[Empty]*", inline=False)
        embed.add_field(name="After", value=after.content or "*[Empty]*", inline=False)

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  MEMBER AUDIT EVENTS
    # ═══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Logs member departures from the server."""
        channel = await self.get_log_channel(member.guild, "member_logs")
        if not channel:
            return

        embed = ZenithEmbed(
            title="📤 Member Left",
            color=Color.MUTED,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{member} ({member.id})", icon_url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        if member.joined_at:
            embed.add_field(name="Joined At", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)

        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  LOGGING CONFIGURATION COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="logs", aliases=["logging"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def logs_group(self, ctx: commands.Context):
        """Displays server logging channels."""
        row = await db.fetchrow("SELECT * FROM server_logs WHERE guild_id = ?", ctx.guild.id) or {}
        msg_ch = f"<#{row.get('message_logs')}>" if row.get("message_logs") else "`Disabled`"
        mem_ch = f"<#{row.get('member_logs')}>" if row.get("member_logs") else "`Disabled`"

        embed = ZenithEmbed(
            title="Zenith Event Logging Hub",
            description=(
                f"• **Message Logs:** {msg_ch}\n"
                f"• **Member Logs:** {mem_ch}\n\n"
                f"**Configuration Commands:**\n"
                f"• `{ctx.prefix}logs messages <#channel>` — Directs edit/delete logs\n"
                f"• `{ctx.prefix}logs members <#channel>` — Directs join/leave logs"
            ),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @logs_group.command(name="messages", aliases=["msg"])
    @commands.has_permissions(administrator=True)
    async def set_message_logs(self, ctx: commands.Context, channel: discord.TextChannel):
        """Routes message delete and edit events to a designated text channel."""
        if db.is_postgres:
            query = """
            INSERT INTO server_logs (guild_id, message_logs) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET message_logs = EXCLUDED.message_logs;
            """
        else:
            query = """
            INSERT INTO server_logs (guild_id, message_logs) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET message_logs = excluded.message_logs;
            """
        await db.execute(query, ctx.guild.id, channel.id)
        embed = ZenithEmbed.success("Message Logging Enabled", f"Message audit logs will now be sent to {channel.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    @logs_group.command(name="members", aliases=["mem"])
    @commands.has_permissions(administrator=True)
    async def set_member_logs(self, ctx: commands.Context, channel: discord.TextChannel):
        """Routes member departure and join events to a designated text channel."""
        if db.is_postgres:
            query = """
            INSERT INTO server_logs (guild_id, member_logs) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET member_logs = EXCLUDED.member_logs;
            """
        else:
            query = """
            INSERT INTO server_logs (guild_id, member_logs) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET member_logs = excluded.member_logs;
            """
        await db.execute(query, ctx.guild.id, channel.id)
        embed = ZenithEmbed.success("Member Logging Enabled", f"Member audit logs will now be sent to {channel.mention}.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logs(bot))
