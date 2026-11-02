"""
Enterprise giveaway lifecycle management for Zenith.
Includes scheduled drawings, reaction/button entry pools, rerolling, cancellations,
real-time drops, and prize/timer editing.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional, Union

import discord
from discord.ext import commands
from discord import ui

from core.database import db
from cogs.moderation import parse_duration

THEME_COLOR = 0x0F0F13


class GiveawayView(ui.View):
    """Button interface for entrants."""

    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.entrants: set[int] = set()

    @ui.button(label="Enter (0)", style=discord.ButtonStyle.secondary, custom_id="zenith:giveaway:enter")
    async def enter_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id in self.entrants:
            self.entrants.remove(user_id)
            button.label = f"Enter ({len(self.entrants)})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("[INFO] Withdrawn from giveaway entry.", ephemeral=True)
            return

        self.entrants.add(user_id)
        button.label = f"Enter ({len(self.entrants)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("[OK] You are registered in the drawing.", ephemeral=True)


class DropButton(ui.View):
    """First-click-wins instant reward button."""

    def __init__(self, prize: str, host: discord.Member):
        super().__init__(timeout=120)
        self.prize = prize
        self.host = host
        self.winner: Optional[discord.Member] = None

    @ui.button(label="Claim Drop", style=discord.ButtonStyle.primary, custom_id="zenith:giveaway:drop")
    async def claim_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.winner:
            await interaction.response.send_message("[INFO] This drop has already been claimed.", ephemeral=True)
            return

        self.winner = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.name}"
        button.style = discord.ButtonStyle.success

        embed = discord.Embed(
            title="[GIVEAWAY DROP CLAIMED]",
            description=f"Winner: {interaction.user.mention}\nPrize: **{self.prize}**\nHost: {self.host.mention}",
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.channel.send(f"[CONGRATULATIONS] {interaction.user.mention} claimed the drop: **{self.prize}**.")


class Giveaways(commands.Cog):
    """Community rewards, drawings, and instant drops."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_views: dict[int, GiveawayView] = {}
        self._tasks: dict[int, asyncio.Task] = {}

    async def _conclude_giveaway(self, message: discord.Message, prize: str, winners_count: int, view: GiveawayView):
        for child in view.children:
            child.disabled = True
        try:
            await message.edit(view=view)
        except Exception:
            pass

        if not view.entrants:
            embed = discord.Embed(
                title=f"[GIVEAWAY CONCLUDED] {prize}",
                description="The drawing ended with zero participants.",
                color=THEME_COLOR
            )
            await message.reply(embed=embed)
            await db.execute("UPDATE giveaways SET ended = TRUE WHERE message_id = ?", message.id)
            return

        pool = list(view.entrants)
        actual_winners = random.sample(pool, k=min(winners_count, len(pool)))
        mentions = ", ".join(f"<@{uid}>" for uid in actual_winners)

        embed = discord.Embed(
            title=f"[GIVEAWAY CONCLUDED] {prize}",
            description=f"Winner(s): {mentions}\nTotal Entries: {len(pool)}",
            color=THEME_COLOR
        )
        await message.reply(content=f"[WINNER] Congratulations {mentions}! You won **{prize}**.", embed=embed)
        await db.execute("UPDATE giveaways SET ended = TRUE WHERE message_id = ?", message.id)

    @commands.group(name="giveaway", aliases=["g"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def giveaway_group(self, ctx: commands.Context):
        """Giveaway management dashboard and commands."""
        embed = discord.Embed(
            title="[GIVEAWAY SYSTEM] Zenith Draw Engine",
            description="Autonomous lifecycle management for server prizes and events.",
            color=THEME_COLOR
        )
        embed.add_field(
            name="Drawing Management",
            value=(
                "`giveaway start <channel> <duration> <winners> <prize>` - Launch scheduled drawing\n"
                "`giveaway end <message_id>` - Conclude drawing immediately\n"
                "`giveaway reroll <message_id> [winners]` - Pick new random winners\n"
                "`giveaway cancel <message_id>` - Abort drawing without selecting winners\n"
                "`giveaway drop <prize>` - Send instant first-click claim drop"
            ),
            inline=False
        )
        embed.add_field(
            name="Editing & Telemetry",
            value=(
                "`giveaway edit prize <message_id> <prize>` - Change drawing prize\n"
                "`giveaway edit winners <message_id> <count>` - Update winner count\n"
                "`giveaway list` - View active server giveaways"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    @giveaway_group.command(name="start")
    @commands.has_permissions(manage_guild=True)
    async def g_start(self, ctx: commands.Context, channel: discord.TextChannel, duration: str, winners: int, *, prize: str):
        """Launch a scheduled giveaway in the specified channel."""
        delta = parse_duration(duration)
        if not delta:
            return await ctx.reply("[ERROR] Invalid duration. Use formats like `10m`, `2h`, or `1d`.", mention_author=False)

        if winners < 1 or winners > 20:
            return await ctx.reply("[ERROR] Winners must be between 1 and 20.", mention_author=False)

        end_ts = int(time.time() + delta.total_seconds())
        embed = discord.Embed(
            title=f"[GIVEAWAY] {prize}",
            description=(
                f"Click the button below to register entry.\n\n"
                f"• Winners: **{winners}**\n"
                f"• Ends: <t:{end_ts}:R> (<t:{end_ts}:f>)\n"
                f"• Hosted by: {ctx.author.mention}"
            ),
            color=THEME_COLOR
        )

        view = GiveawayView(0)
        msg = await channel.send(embed=embed, view=view)
        view.message_id = msg.id
        self._active_views[msg.id] = view

        await db.execute(
            "INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            msg.id, ctx.guild.id, channel.id, prize, winners, end_ts
        )

        if channel.id != ctx.channel.id:
            await ctx.reply(f"[OK] Giveaway initiated in {channel.mention}: [Jump to Message]({msg.jump_url})", mention_author=False)

        async def _timer_sleep():
            await asyncio.sleep(delta.total_seconds())
            await self._conclude_giveaway(msg, prize, winners, view)
            self._tasks.pop(msg.id, None)

        task = asyncio.create_task(_timer_sleep())
        self._tasks[msg.id] = task

    @giveaway_group.command(name="end")
    @commands.has_permissions(manage_guild=True)
    async def g_end(self, ctx: commands.Context, message_id: int):
        """Conclude an active drawing immediately and roll winners."""
        row = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ?", message_id, ctx.guild.id)
        if not row:
            return await ctx.reply(f"[ERROR] Giveaway `{message_id}` was not found.", mention_author=False)

        if row["ended"]:
            return await ctx.reply(f"[INFO] Giveaway `{message_id}` has already ended.", mention_author=False)

        # Cancel sleeping task if active
        if message_id in self._tasks:
            self._tasks[message_id].cancel()
            self._tasks.pop(message_id, None)

        channel = ctx.guild.get_channel(row["channel_id"])
        if not channel:
            return await ctx.reply("[ERROR] Giveaway channel no longer exists.", mention_author=False)

        try:
            msg = await channel.fetch_message(message_id)
        except Exception:
            return await ctx.reply("[ERROR] Giveaway message could not be fetched.", mention_author=False)

        view = self._active_views.get(message_id, GiveawayView(message_id))
        await self._conclude_giveaway(msg, row["prize"], row["winners"], view)
        await ctx.reply(f"[OK] Giveaway `{message_id}` ended.", mention_author=False)

    @giveaway_group.command(name="reroll")
    @commands.has_permissions(manage_guild=True)
    async def g_reroll(self, ctx: commands.Context, message_id: int, winners: Optional[int] = None):
        """Reroll new random winners from the entry pool."""
        row = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ?", message_id, ctx.guild.id)
        if not row:
            return await ctx.reply(f"[ERROR] Giveaway `{message_id}` was not found.", mention_author=False)

        view = self._active_views.get(message_id)
        if not view or not view.entrants:
            return await ctx.reply("[ERROR] No entrants pool found in memory to reroll from.", mention_author=False)

        winner_count = winners or row["winners"]
        pool = list(view.entrants)
        new_winners = random.sample(pool, k=min(winner_count, len(pool)))
        mentions = ", ".join(f"<@{uid}>" for uid in new_winners)

        embed = discord.Embed(
            title=f"[GIVEAWAY REROLL] {row['prize']}",
            description=f"New Winner(s): {mentions}",
            color=THEME_COLOR
        )
        channel = ctx.guild.get_channel(row["channel_id"])
        if channel:
            await channel.send(content=f"[REROLL WINNER] {mentions}! You won **{row['prize']}**.", embed=embed)
        await ctx.reply(f"[OK] Rerolled {len(new_winners)} winner(s).", mention_author=False)

    @giveaway_group.command(name="cancel")
    @commands.has_permissions(manage_guild=True)
    async def g_cancel(self, ctx: commands.Context, message_id: int):
        """Cancel a giveaway without drawing any winners."""
        row = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ?", message_id, ctx.guild.id)
        if not row:
            return await ctx.reply(f"[ERROR] Giveaway `{message_id}` was not found.", mention_author=False)

        if message_id in self._tasks:
            self._tasks[message_id].cancel()
            self._tasks.pop(message_id, None)

        await db.execute("UPDATE giveaways SET ended = TRUE WHERE message_id = ?", message_id)

        channel = ctx.guild.get_channel(row["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(message_id)
                embed = discord.Embed(
                    title=f"[GIVEAWAY CANCELLED] {row['prize']}",
                    description="This drawing has been cancelled by server staff.",
                    color=THEME_COLOR
                )
                await msg.edit(embed=embed, view=None)
            except Exception:
                pass

        await ctx.reply(f"[OK] Giveaway `{message_id}` has been cancelled.", mention_author=False)

    @giveaway_group.command(name="drop")
    @commands.has_permissions(manage_guild=True)
    async def g_drop(self, ctx: commands.Context, *, prize: str):
        """Send an instant drop where the first person to click wins."""
        view = DropButton(prize, ctx.author)
        embed = discord.Embed(
            title="[GIVEAWAY DROP] First Click Wins!",
            description=f"Prize: **{prize}**\nHost: {ctx.author.mention}\n\nClick the button below to claim the drop immediately.",
            color=THEME_COLOR
        )
        await ctx.send(embed=embed, view=view)

    @giveaway_group.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def g_list(self, ctx: commands.Context):
        """List active giveaways running on this server."""
        rows = await db.fetch("SELECT * FROM giveaways WHERE guild_id = ? AND ended = FALSE ORDER BY end_time ASC", ctx.guild.id)
        if not rows:
            return await ctx.reply("[INFO] No active giveaways currently running in this server.", mention_author=False)

        entries = []
        for r in rows:
            entries.append(
                f"• ID: `{r['message_id']}` | Prize: **{r['prize']}** | Channel: <#{r['channel_id']}> | Ends: <t:{int(r['end_time'])}:R>"
            )

        embed = discord.Embed(
            title=f"[ACTIVE GIVEAWAYS] {ctx.guild.name} ({len(rows)})",
            description="\n".join(entries),
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @giveaway_group.group(name="edit", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def g_edit_group(self, ctx: commands.Context):
        """Edit active giveaway parameters."""
        await ctx.send_help(ctx.command)

    @g_edit_group.command(name="prize")
    @commands.has_permissions(manage_guild=True)
    async def g_edit_prize(self, ctx: commands.Context, message_id: int, *, new_prize: str):
        """Edit the prize for an ongoing giveaway."""
        row = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = FALSE", message_id, ctx.guild.id)
        if not row:
            return await ctx.reply(f"[ERROR] Active giveaway `{message_id}` not found.", mention_author=False)

        await db.execute("UPDATE giveaways SET prize = ? WHERE message_id = ?", new_prize, message_id)
        channel = ctx.guild.get_channel(row["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(message_id)
                if msg.embeds:
                    emb = msg.embeds[0]
                    emb.title = f"[GIVEAWAY] {new_prize}"
                    await msg.edit(embed=emb)
            except Exception:
                pass
        await ctx.reply(f"[OK] Prize updated to **{new_prize}**.", mention_author=False)

    @g_edit_group.command(name="winners")
    @commands.has_permissions(manage_guild=True)
    async def g_edit_winners(self, ctx: commands.Context, message_id: int, winner_count: int):
        """Edit the number of winners for an ongoing giveaway."""
        if winner_count < 1 or winner_count > 20:
            return await ctx.reply("[ERROR] Winners must be between 1 and 20.", mention_author=False)

        row = await db.fetchrow("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = FALSE", message_id, ctx.guild.id)
        if not row:
            return await ctx.reply(f"[ERROR] Active giveaway `{message_id}` not found.", mention_author=False)

        await db.execute("UPDATE giveaways SET winners = ? WHERE message_id = ?", winner_count, message_id)
        await ctx.reply(f"[OK] Winner count set to **{winner_count}** for giveaway `{message_id}`.", mention_author=False)

    # Standalone shortcut commands
    @commands.command(name="gstart")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_gstart(self, ctx: commands.Context, channel: discord.TextChannel, duration: str, winners: int, *, prize: str):
        """Shortcut to start a giveaway."""
        await self.g_start(ctx, channel, duration, winners, prize=prize)

    @commands.command(name="gend")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_gend(self, ctx: commands.Context, message_id: int):
        """Shortcut to end a giveaway."""
        await self.g_end(ctx, message_id)

    @commands.command(name="greroll")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_greroll(self, ctx: commands.Context, message_id: int, winners: Optional[int] = None):
        """Shortcut to reroll a giveaway."""
        await self.g_reroll(ctx, message_id, winners)

    @commands.command(name="gcancel")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_gcancel(self, ctx: commands.Context, message_id: int):
        """Shortcut to cancel a giveaway."""
        await self.g_cancel(ctx, message_id)

    @commands.command(name="gdrop")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_gdrop(self, ctx: commands.Context, *, prize: str):
        """Shortcut to launch a first-click drop."""
        await self.g_drop(ctx, prize=prize)

    @commands.command(name="glist")
    @commands.has_permissions(manage_guild=True)
    async def shortcut_glist(self, ctx: commands.Context):
        """Shortcut to list server giveaways."""
        await self.g_list(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
