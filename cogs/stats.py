"""
Server Statistics Counter Channels for Zenith.
Dynamically displays live server population counters using locked voice channels.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import asyncio
from typing import Optional, Dict
import discord
from discord.ext import commands, tasks

from core.database import db

ACCENT_COLOR = 0x0F0F13


class ServerStats(commands.Cog):
    """Dynamic voice channel server statistics counters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.update_stats_loop.is_running():
            self.update_stats_loop.start()

    def cog_unload(self):
        self.update_stats_loop.cancel()

    async def _update_guild_stats(self, guild: discord.Guild, cfg: dict) -> None:
        """Update locked voice channel titles to reflect live counts."""
        total = guild.member_count or len(guild.members)
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        roles_count = len(guild.roles)

        channel_updates = [
            (cfg.get("members_ch"), f"Total Members: {total:,}"),
            (cfg.get("humans_ch"), f"Humans: {humans:,}"),
            (cfg.get("bots_ch"), f"Bots: {bots:,}"),
            (cfg.get("roles_ch"), f"Roles: {roles_count:,}"),
        ]

        for cid, title in channel_updates:
            if not cid:
                continue
            ch = guild.get_channel(cid)
            if ch and ch.name != title:
                try:
                    await ch.edit(name=title, reason="Zenith Live Server Stats Sync")
                    await asyncio.sleep(1.0)
                except Exception:
                    pass

    @tasks.loop(minutes=10)
    async def update_stats_loop(self):
        """Periodic background refresh loop."""
        await self.bot.wait_until_ready()
        rows = await db.fetch("SELECT * FROM stats_config")
        for r in rows:
            guild = self.bot.get_guild(r["guild_id"])
            if guild:
                await self._update_guild_stats(guild, r)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        row = await db.fetchrow("SELECT * FROM stats_config WHERE guild_id = ?", member.guild.id)
        if row:
            await self._update_guild_stats(member.guild, row)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        row = await db.fetchrow("SELECT * FROM stats_config WHERE guild_id = ?", member.guild.id)
        if row:
            await self._update_guild_stats(member.guild, row)

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="serverstats", aliases=["statschannels", "counters"], invoke_without_command=True)
    @commands.guild_only()
    async def stats_group(self, ctx: commands.Context):
        """Server statistics counters overview."""
        embed = discord.Embed(
            title="[SERVER STATS COUNTERS]",
            description="Display live server population counters in locked voice channels.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}serverstats setup` - Spawn counter category & channels\n"
                f"`{ctx.prefix}serverstats update` - Force immediate counter refresh\n"
                f"`{ctx.prefix}serverstats delete` - Remove all counter channels"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @stats_group.command(name="setup")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def stats_setup(self, ctx: commands.Context):
        """Create the Server Statistics category and counter voice channels."""
        status_msg = await ctx.send(embed=discord.Embed(title="[CREATING COUNTERS]", description="Building statistics category...", color=ACCENT_COLOR))

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=False)
        }

        category = await ctx.guild.create_category("Server Statistics", overwrites=overwrites, reason="Zenith Server Stats Setup")

        total = ctx.guild.member_count or len(ctx.guild.members)
        humans = sum(1 for m in ctx.guild.members if not m.bot)
        bots = sum(1 for m in ctx.guild.members if m.bot)
        roles_count = len(ctx.guild.roles)

        ch_mem = await ctx.guild.create_voice_channel(f"Total Members: {total:,}", category=category, reason="Zenith Stats Setup")
        ch_hum = await ctx.guild.create_voice_channel(f"Humans: {humans:,}", category=category, reason="Zenith Stats Setup")
        ch_bot = await ctx.guild.create_voice_channel(f"Bots: {bots:,}", category=category, reason="Zenith Stats Setup")
        ch_rol = await ctx.guild.create_voice_channel(f"Roles: {roles_count:,}", category=category, reason="Zenith Stats Setup")

        await db.execute(
            """
            INSERT INTO stats_config (guild_id, category_id, members_ch, humans_ch, bots_ch, roles_ch)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                category_id = excluded.category_id,
                members_ch = excluded.members_ch,
                humans_ch = excluded.humans_ch,
                bots_ch = excluded.bots_ch,
                roles_ch = excluded.roles_ch
            """,
            ctx.guild.id, category.id, ch_mem.id, ch_hum.id, ch_bot.id, ch_rol.id
        )

        embed = discord.Embed(
            title="[SERVER COUNTERS CREATED]",
            description=f"Created counter category {category.name} with 4 live voice channels.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await status_msg.edit(embed=embed)

    @stats_group.command(name="update")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def stats_update(self, ctx: commands.Context):
        """Force manual refresh of all counter channels."""
        row = await db.fetchrow("SELECT * FROM stats_config WHERE guild_id = ?", ctx.guild.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT CONFIGURED]", description=f"Run `{ctx.prefix}serverstats setup` first.", color=ACCENT_COLOR))

        await self._update_guild_stats(ctx.guild, row)
        embed = discord.Embed(title="[COUNTERS UPDATED]", description="Refreshed live server counter names.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @stats_group.command(name="delete", aliases=["reset"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def stats_delete(self, ctx: commands.Context):
        """Delete all statistics counter channels."""
        row = await db.fetchrow("SELECT * FROM stats_config WHERE guild_id = ?", ctx.guild.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT CONFIGURED]", description="No counter channels found.", color=ACCENT_COLOR))

        channel_ids = [row.get("category_id"), row.get("members_ch"), row.get("humans_ch"), row.get("bots_ch"), row.get("roles_ch")]
        for cid in channel_ids:
            if cid:
                ch = ctx.guild.get_channel(cid)
                if ch:
                    try:
                        await ch.delete(reason="Zenith Server Stats Teardown")
                    except Exception:
                        pass

        await db.execute("DELETE FROM stats_config WHERE guild_id = ?", ctx.guild.id)
        embed = discord.Embed(title="[COUNTERS DELETED]", description="Removed statistics category and channels.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerStats(bot))
