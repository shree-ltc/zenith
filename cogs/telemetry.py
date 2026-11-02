"""
System Telemetry, Latency Benchmarking & Resource Monitor for Zenith.
Measures Discord gateway heartbeats, REST round-trip, database query speed, and process memory.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import os
import time
import psutil
from typing import Optional
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class Telemetry(commands.Cog):
    """Real-time performance diagnostics and system benchmarking."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.process = psutil.Process(os.getpid())

    @commands.group(name="telemetry", aliases=["sysinfo", "botstatus"], invoke_without_command=True)
    async def telemetry_group(self, ctx: commands.Context):
        """System performance and resource overview."""
        # 1. Heartbeat latency
        ws_ping = round(self.bot.latency * 1000)

        # 2. Database latency
        t0 = time.perf_counter()
        await db.fetchrow("SELECT 1")
        db_latency = round((time.perf_counter() - t0) * 1000, 2)

        # 3. Process memory
        mem_info = self.process.memory_info()
        ram_mb = round(mem_info.rss / (1024 * 1024), 1)

        # 4. Total commands
        total_commands = len(self.bot.commands)

        embed = discord.Embed(
            title="[SYSTEM TELEMETRY]",
            description="Live performance benchmarks and hardware utilization statistics.",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Gateway Latency", value=f"`{ws_ping} ms`", inline=True)
        embed.add_field(name="Database Query", value=f"`{db_latency} ms`", inline=True)
        embed.add_field(name="Process Memory", value=f"`{ram_mb} MB` RSS", inline=True)
        embed.add_field(name="Active Cogs", value=f"`{len(self.bot.cogs)}` loaded", inline=True)
        embed.add_field(name="Top Commands", value=f"`{total_commands}` commands", inline=True)
        embed.add_field(name="Guilds Served", value=f"`{len(self.bot.guilds):,}` guilds", inline=True)

        embed.add_field(
            name="Subcommands",
            value=(
                f"`{ctx.prefix}telemetry ping` - Detailed multi-point latency\n"
                f"`{ctx.prefix}telemetry shards` - Shard distribution grid\n"
                f"`{ctx.prefix}telemetry database` - Table record inventory\n"
                f"`{ctx.prefix}telemetry cogs` - Registered extension directory"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Autonomous Engine | Developed by Shree")
        await ctx.send(embed=embed)

    @telemetry_group.command(name="ping")
    async def telemetry_ping(self, ctx: commands.Context):
        """Benchmark websocket, REST round-trip, and database response times."""
        # Gateway
        ws = round(self.bot.latency * 1000)

        # REST round-trip
        t0 = time.perf_counter()
        msg = await ctx.send(embed=discord.Embed(title="[PROBING LATENCY]", description="Measuring REST socket round-trip...", color=ACCENT_COLOR))
        rest = round((time.perf_counter() - t0) * 1000)

        # Database latency
        t1 = time.perf_counter()
        await db.fetchrow("SELECT 1")
        db_time = round((time.perf_counter() - t1) * 1000, 2)

        embed = discord.Embed(
            title="[MULTI-TIER LATENCY BENCHMARK]",
            description=(
                f"• **Gateway WebSocket:** `{ws} ms`\n"
                f"• **REST HTTP Round-Trip:** `{rest} ms`\n"
                f"• **Database Query Engine:** `{db_time} ms`"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await msg.edit(embed=embed)

    @telemetry_group.command(name="shards")
    async def telemetry_shards(self, ctx: commands.Context):
        """Display live shard status grid."""
        shards_info = []
        for shard_id, shard in self.bot.shards.items():
            latency = round(shard.latency * 1000) if shard.latency else "N/A"
            guilds_on_shard = sum(1 for g in self.bot.guilds if g.shard_id == shard_id)
            shards_info.append(f"Shard `#{shard_id:02d}`: `{latency} ms` latency | `{guilds_on_shard}` guilds")

        embed = discord.Embed(
            title=f"[SHARD DISTRIBUTION - {len(self.bot.shards)} TOTAL]",
            description="\n".join(shards_info) or "Operating in un-sharded single instance.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @telemetry_group.command(name="cogs")
    async def telemetry_cogs(self, ctx: commands.Context):
        """Directory of loaded extensions and command counts."""
        lines = []
        for name, cog in sorted(self.bot.cogs.items()):
            cmds = cog.get_commands()
            lines.append(f"• **{name}**: `{len(cmds)}` commands")

        embed = discord.Embed(
            title=f"[LOADED EXTENSIONS - {len(lines)} TOTAL]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Telemetry(bot))
