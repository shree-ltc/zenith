"""
Community giveaway system with duration parsing and random winner selection.
"""

import time
import random
import asyncio
from typing import Optional
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import ui

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color
from cogs.moderation import parse_duration


class GiveawayView(ui.View):
    """Interactive button allowing community members to enter the drawing."""

    def __init__(self, message_id: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.entrants: set[int] = set()

    @ui.button(label="Enter (0)", style=discord.ButtonStyle.primary, custom_id="zenith:giveaway:enter")
    async def enter_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        if user_id in self.entrants:
            self.entrants.remove(user_id)
            button.label = f"Enter ({len(self.entrants)})"
            await interaction.response.edit_message(view=self)
            return await interaction.followup.send(
                embed=ZenithEmbed.info("Entry Withdrawn", "You have stepped out of this giveaway."),
                ephemeral=True
            )

        self.entrants.add(user_id)
        button.label = f"Enter ({len(self.entrants)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            embed=ZenithEmbed.success("Entered Successfully", "You are now in the running to win!"),
            ephemeral=True
        )


class Giveaways(commands.Cog):
    """Community rewards and giveaway lifecycle management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_views: dict[int, GiveawayView] = {}

    async def _conclude_giveaway(self, message: discord.Message, prize: str, winners_count: int, view: GiveawayView):
        """Selects random winners and updates embed state."""
        # Disable entry button
        for child in view.children:
            child.disabled = True
        try:
            await message.edit(view=view)
        except Exception:
            pass

        if not view.entrants:
            embed = ZenithEmbed(
                title=f"Giveaway Concluded — {prize}",
                description="The drawing ended with no participants.",
                color=Color.MUTED
            )
            return await message.reply(embed=embed)

        winners_pool = list(view.entrants)
        actual_winners = random.sample(winners_pool, k=min(winners_count, len(winners_pool)))
        winner_mentions = ", ".join(f"<@{uid}>" for uid in actual_winners)

        embed = ZenithEmbed(
            title=f"Giveaway Concluded — {prize}",
            description=f"Winner(s): {winner_mentions}\nHosted by: Zenith",
            color=Color.SUCCESS
        )
        await message.reply(content=f"Congratulations {winner_mentions}! You won **{prize}**.", embed=embed)
        await db.execute("UPDATE giveaways SET ended = TRUE WHERE message_id = ?", message.id)

    @commands.group(name="giveaway", aliases=["g", "gstart"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def giveaway_group(self, ctx: commands.Context):
        """Displays giveaway commands manual."""
        embed = ZenithEmbed(
            title="Zenith Giveaway System",
            description=(
                f"• `{ctx.prefix}giveaway start <time> <winners> <prize>` — Launches giveaway\n"
                f"• `{ctx.prefix}giveaway end <message_id>` — Closes giveaway early\n"
                f"• `{ctx.prefix}giveaway reroll <message_id>` — Picks new winner"
            ),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @giveaway_group.command(name="start")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_start(self, ctx: commands.Context, duration: str, winners: int, *, prize: str):
        """Launches a new interactive giveaway with timer."""
        delta = parse_duration(duration)
        if not delta:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Duration", "Use formats like `10m`, `2h`, or `1d`."), mention_author=False)

        if winners < 1:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Winners", "Winners must be at least 1."), mention_author=False)

        end_ts = int(time.time() + delta.total_seconds())
        embed = ZenithEmbed(
            title=f"Giveaway: {prize}",
            description=(
                f"Click the button below to enter.\n\n"
                f"Winners: **{winners}**\n"
                f"Ends: <t:{end_ts}:R> (<t:{end_ts}:f>)\n"
                f"Hosted by: {ctx.author.mention}"
            ),
            color=Color.PRIMARY
        )

        view = GiveawayView(0)
        msg = await ctx.send(embed=embed, view=view)
        view.message_id = msg.id
        self._active_views[msg.id] = view

        # Save in database
        await db.execute(
            "INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners, end_time) VALUES (?, ?, ?, ?, ?, ?)",
            msg.id, ctx.guild.id, ctx.channel.id, prize, winners, end_ts
        )

        # Asynchronous sleep until conclusion
        await asyncio.sleep(delta.total_seconds())
        await self._conclude_giveaway(msg, prize, winners, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
