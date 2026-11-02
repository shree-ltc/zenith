"""
Productivity, reminder alerts, and temporal utilities for Zenith.
Includes asynchronous background task queue for user reminders and timestamp formatting.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from core.database import db
from cogs.moderation import parse_duration

THEME_COLOR = 0x0F0F13


class General(commands.Cog):
    """Productivity alerts, reminders, and temporal utilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(seconds=15)
    async def reminder_loop(self):
        """Asynchronous poller delivering reminders whose schedule has elapsed."""
        now = time.time()
        try:
            due = await db.fetch("SELECT id, user_id, channel_id, text FROM reminders WHERE remind_at <= ?", now)
            for row in due:
                user = self.bot.get_user(row["user_id"])
                channel = self.bot.get_channel(row["channel_id"])
                alert_text = row["text"]

                embed = discord.Embed(
                    title="[REMINDER ALERT]",
                    description=f"{user.mention if user else ''} Here is your scheduled reminder:\n\n**{alert_text}**",
                    color=THEME_COLOR
                )

                delivered = False
                if channel:
                    try:
                        await channel.send(embed=embed)
                        delivered = True
                    except Exception:
                        pass

                if not delivered and user:
                    try:
                        await user.send(embed=embed)
                    except Exception:
                        pass

                await db.execute("DELETE FROM reminders WHERE id = ?", row["id"])
        except Exception:
            pass



    @commands.group(name="remind", aliases=["remindme", "reminder"], invoke_without_command=True)
    async def remind_group(self, ctx: commands.Context, duration: Optional[str] = None, *, reminder_text: Optional[str] = None):
        """Set a scheduled personal reminder or inspect reminder commands."""
        if not duration or not reminder_text:
            embed = discord.Embed(
                title="[REMINDERS] Schedule Alerts",
                description=(
                    f"• `{ctx.prefix}remind <duration> <message>` - Create reminder\n"
                    f"• `{ctx.prefix}remind list` - View your active reminders\n"
                    f"• `{ctx.prefix}remind cancel <id>` - Abort scheduled reminder"
                ),
                color=THEME_COLOR
            )
            return await ctx.reply(embed=embed, mention_author=False)

        delta = parse_duration(duration)
        if not delta:
            return await ctx.reply("[ERROR] Invalid duration. Use formats like `10m`, `2h`, or `1d`.", mention_author=False)

        remind_at = time.time() + delta.total_seconds()
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, remind_at, text) VALUES (?, ?, ?, ?)",
            ctx.author.id, ctx.channel.id, remind_at, reminder_text
        )

        embed = discord.Embed(
            title="[OK] Reminder Stored",
            description=f"Alert scheduled for <t:{int(remind_at)}:F> (<t:{int(remind_at)}:R>).\n\n**Message:** {reminder_text}",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @remind_group.command(name="list")
    async def remind_list(self, ctx: commands.Context):
        """List all active reminders you have scheduled."""
        rows = await db.fetch("SELECT id, remind_at, text FROM reminders WHERE user_id = ? ORDER BY remind_at ASC", ctx.author.id)
        if not rows:
            return await ctx.reply("[INFO] You have no active reminders scheduled.", mention_author=False)

        desc = []
        for r in rows:
            desc.append(f"• ID: `{r['id']}` | Due: <t:{int(r['remind_at'])}:R> — **{r['text'][:50]}**")

        embed = discord.Embed(
            title=f"[YOUR REMINDERS] ({len(rows)})",
            description="\n".join(desc),
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @remind_group.command(name="cancel", aliases=["delete", "del"])
    async def remind_cancel(self, ctx: commands.Context, reminder_id: int):
        """Cancel a scheduled reminder by ID."""
        row = await db.fetchrow("SELECT id FROM reminders WHERE id = ? AND user_id = ?", reminder_id, ctx.author.id)
        if not row:
            return await ctx.reply(f"[ERROR] Reminder `{reminder_id}` was not found in your schedule.", mention_author=False)

        await db.execute("DELETE FROM reminders WHERE id = ?", reminder_id)
        await ctx.reply(f"[OK] Reminder `{reminder_id}` was successfully cancelled.", mention_author=False)

    @commands.command(name="timestamp", aliases=["timeformat", "ts"])
    async def format_timestamp(self, ctx: commands.Context, seconds_offset: Optional[int] = 0):
        """Generate copy-pasteable Discord dynamic timestamp tags."""
        target_ts = int(time.time() + seconds_offset)
        embed = discord.Embed(
            title=f"[TIMESTAMPS] Target: {target_ts}",
            color=THEME_COLOR
        )
        embed.add_field(name="Relative", value=f"`<t:{target_ts}:R>` -> <t:{target_ts}:R>", inline=False)
        embed.add_field(name="Short Time", value=f"`<t:{target_ts}:t>` -> <t:{target_ts}:t>", inline=True)
        embed.add_field(name="Long Time", value=f"`<t:{target_ts}:T>` -> <t:{target_ts}:T>", inline=True)
        embed.add_field(name="Short Date", value=f"`<t:{target_ts}:d>` -> <t:{target_ts}:d>", inline=True)
        embed.add_field(name="Long Date", value=f"`<t:{target_ts}:D>` -> <t:{target_ts}:D>", inline=True)
        embed.add_field(name="Long Date w/ Short Time", value=f"`<t:{target_ts}:f>` -> <t:{target_ts}:f>", inline=True)
        embed.add_field(name="Full Long", value=f"`<t:{target_ts}:F>` -> <t:{target_ts}:F>", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="worldclock", aliases=["clock", "timezones"])
    async def worldclock_cmd(self, ctx: commands.Context):
        """Display current wall-clock times across global financial and technical hubs."""
        now_utc = datetime.now(timezone.utc)

        # Standard offsets
        hubs = [
            ("UTC / London (GMT)", 0),
            ("New York (EST/EDT)", -5),
            ("Los Angeles (PST/PDT)", -8),
            ("Tokyo (JST)", 9),
            ("Singapore (SGT)", 8),
            ("Sydney (AEST)", 10),
            ("Berlin / Paris (CET)", 1),
            ("New Delhi (IST)", 5.5)
        ]

        desc = []
        for name, offset in hubs:
            from datetime import timedelta
            t = now_utc + timedelta(hours=offset)
            desc.append(f"• **{name}**: `{t.strftime('%Y-%m-%d %H:%M:%S')}`")

        embed = discord.Embed(
            title="[WORLD CLOCK] Global Standard Time",
            description="\n".join(desc),
            color=THEME_COLOR
        )
        embed.set_footer(text=f"UTC Anchor: {now_utc.strftime('%H:%M:%S UTC')}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="uptime", aliases=["up"])
    async def uptime_cmd(self, ctx: commands.Context):
        """Check bot runtime uptime."""
        delta = int(time.time() - self.bot.launch_time)
        days, rem = divmod(delta, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        await ctx.reply(f"[UPTIME] Online for **{days}d {hours}h {minutes}m {seconds}s** (Since <t:{int(self.bot.launch_time)}:R>).", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
