"""
Utility commands: userinfo, serverinfo, avatar, botinfo, ping, and snipe.
"""

import time
import psutil
from datetime import datetime, timezone
from typing import Optional, Union

import discord
from discord.ext import commands

from ui.embeds import ZenithEmbed
from ui.colors import Color
from core.config import config


class Utility(commands.Cog):
    """Server diagnostics, user lookups, and operational utilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Ephemeral snipe caches: dict[channel_id, tuple[Message, timestamp]]
        self._snipe_cache: dict[int, tuple[discord.Message, datetime]] = {}
        self._editsnipe_cache: dict[int, tuple[discord.Message, discord.Message, datetime]] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Caches the most recently deleted message per channel."""
        if message.author.bot or not message.guild or not message.content:
            return
        self._snipe_cache[message.channel.id] = (message, datetime.now(timezone.utc))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Caches the most recently edited message per channel."""
        if before.author.bot or not before.guild or before.content == after.content:
            return
        self._editsnipe_cache[before.channel.id] = (before, after, datetime.now(timezone.utc))

    # ═══════════════════════════════════════════════════════════════
    #  INSPECTION COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="userinfo", aliases=["ui", "whois", "user"])
    async def userinfo_command(self, ctx: commands.Context, *, target: Optional[Union[discord.Member, discord.User]] = None):
        """Provides an exhaustive identity profile on a guild member or Discord user."""
        user = target or ctx.author

        embed = ZenithEmbed(
            title=f"Identity Profile — {user.name}",
            color=user.color if isinstance(user, discord.Member) and user.color.value != 0 else Color.PRIMARY
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Dates
        created_ts = int(user.created_at.timestamp())
        embed.add_field(name="Account Created", value=f"<t:{created_ts}:F>\n(<t:{created_ts}:R>)", inline=True)

        if isinstance(user, discord.Member):
            if user.joined_at:
                joined_ts = int(user.joined_at.timestamp())
                embed.add_field(name="Joined Guild", value=f"<t:{joined_ts}:F>\n(<t:{joined_ts}:R>)", inline=True)

            roles = [r.mention for r in reversed(user.roles) if not r.is_default()]
            role_str = ", ".join(roles[:15]) if roles else "None"
            if len(roles) > 15:
                role_str += f" *(+{len(roles) - 15} more)*"
            embed.add_field(name=f"Roles [{len(roles)}]", value=role_str, inline=False)

            key_perms = []
            if user.guild_permissions.administrator:
                key_perms.append("Administrator")
            if user.guild_permissions.manage_guild:
                key_perms.append("Manage Server")
            if user.guild_permissions.ban_members:
                key_perms.append("Ban Members")
            if user.guild_permissions.kick_members:
                key_perms.append("Kick Members")
            if user.guild_permissions.manage_channels:
                key_perms.append("Manage Channels")

            if key_perms:
                embed.add_field(name="Key Permissions", value=", ".join(key_perms), inline=False)

        embed.add_field(name="Discord User ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Bot Account", value="Yes" if user.bot else "No", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverinfo", aliases=["si", "guildinfo", "guild"])
    async def serverinfo_command(self, ctx: commands.Context):
        """Summarizes guild metrics, member breakdown, channels, and security tiers."""
        guild = ctx.guild
        owner = guild.owner or await self.bot.fetch_user(guild.owner_id)

        embed = ZenithEmbed(title=f"{guild.name} — Server Analytics", color=Color.PRIMARY)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        created_ts = int(guild.created_at.timestamp())
        embed.add_field(name="Server Owner", value=f"{owner.mention}\n(`{owner.id}`)", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_ts}:D>\n(<t:{created_ts}:R>)", inline=True)
        embed.add_field(name="Boost Level", value=f"Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

        # Member counts
        total_members = guild.member_count or len(guild.members)
        humans = sum(1 for m in guild.members if not m.bot)
        bots = total_members - humans
        embed.add_field(name="Member Population", value=f"Total: **{total_members:,}**\nHumans: **{humans:,}** | Bots: **{bots:,}**", inline=True)

        # Channels
        text_count = len(guild.text_channels)
        voice_count = len(guild.voice_channels)
        cat_count = len(guild.categories)
        embed.add_field(name="Channel Counts", value=f"Text: **{text_count}**\nVoice: **{voice_count}** | Categories: **{cat_count}**", inline=True)

        embed.add_field(name="Role Count", value=f"**{len(guild.roles)}** roles", inline=True)
        embed.add_field(name="Verification Level", value=f"`{str(guild.verification_level).title()}`", inline=True)
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar_command(self, ctx: commands.Context, *, user: Optional[Union[discord.Member, discord.User]] = None):
        """Displays full-resolution Discord profile picture."""
        target = user or ctx.author
        avatar_url = target.display_avatar.url

        embed = ZenithEmbed(title=f"{target.name}'s Avatar", color=Color.PRIMARY)
        embed.set_image(url=avatar_url)
        embed.add_field(
            name="Download Links",
            value=f"[PNG]({target.display_avatar.replace(format='png').url}) | [JPG]({target.display_avatar.replace(format='jpg').url}) | [WEBP]({target.display_avatar.replace(format='webp').url})"
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serveravatar", aliases=["sav"])
    async def serveravatar_command(self, ctx: commands.Context):
        """Displays guild icon in full resolution."""
        if not ctx.guild.icon:
            return await ctx.reply(embed=ZenithEmbed.error("No Icon", "This guild does not possess an icon."), mention_author=False)

        embed = ZenithEmbed(title=f"{ctx.guild.name} — Server Icon", color=Color.PRIMARY)
        embed.set_image(url=ctx.guild.icon.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="snipe")
    async def snipe_command(self, ctx: commands.Context):
        """Recovers the most recently deleted message in this channel."""
        data = self._snipe_cache.get(ctx.channel.id)
        if not data:
            return await ctx.reply(embed=ZenithEmbed.info("Snipe Cache Empty", "No recently deleted messages found in this channel."), mention_author=False)

        msg, deleted_at = data
        embed = ZenithEmbed(
            title=f"Sniped Message from {msg.author}",
            description=msg.content or "*[Message had no text content]*",
            color=Color.PRIMARY,
            timestamp=deleted_at
        )
        embed.set_thumbnail(url=msg.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="editsnipe", aliases=["esnipe"])
    async def editsnipe_command(self, ctx: commands.Context):
        """Displays the before and after text of the last edited message."""
        data = self._editsnipe_cache.get(ctx.channel.id)
        if not data:
            return await ctx.reply(embed=ZenithEmbed.info("Snipe Cache Empty", "No recently edited messages found in this channel."), mention_author=False)

        before, after, edited_at = data
        embed = ZenithEmbed(
            title=f"Edited Message by {before.author}",
            color=Color.WARNING,
            timestamp=edited_at
        )
        embed.add_field(name="Before", value=before.content or "*[Empty]*", inline=False)
        embed.add_field(name="After", value=after.content or "*[Empty]*", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  SYSTEM TELEMETRY
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="ping", aliases=["latency"])
    async def ping_command(self, ctx: commands.Context):
        """Measures WebSocket gateway heartbeat and REST API roundtrip."""
        start_time = time.monotonic()
        msg = await ctx.reply(embed=ZenithEmbed.info("Pinging...", "Measuring gateway telemetry..."), mention_author=False)
        end_time = time.monotonic()

        api_latency = round((end_time - start_time) * 1000)
        ws_latency = round(self.bot.latency * 1000)

        embed = ZenithEmbed(title="Zenith Telemetry", color=Color.SUCCESS)
        embed.add_field(name="REST API Roundtrip", value=f"`{api_latency} ms`", inline=True)
        embed.add_field(name="Gateway Latency", value=f"`{ws_latency} ms`", inline=True)
        await msg.edit(embed=embed)

    @commands.command(name="botinfo", aliases=["stats", "about", "info"])
    async def botinfo_command(self, ctx: commands.Context):
        """Displays runtime architecture, memory utilization, and node stats."""
        # Calculate uptime
        uptime_seconds = int(time.time() - self.bot.launch_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        # Host statistics
        process = psutil.Process()
        memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
        cpu_usage = psutil.cpu_percent()

        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count or 0 for g in self.bot.guilds)
        total_shards = self.bot.shard_count or 1

        embed = ZenithEmbed(title="Zenith — Core Telemetry", color=Color.PRIMARY)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        embed.add_field(name="Guild Footprint", value=f"**{total_guilds:,}** servers", inline=True)
        embed.add_field(name="User Audience", value=f"**{total_users:,}** users", inline=True)
        embed.add_field(name="Cluster Shards", value=f"**{total_shards}** active", inline=True)

        embed.add_field(name="Memory (RSS)", value=f"`{memory_usage:.1f} MB`", inline=True)
        embed.add_field(name="CPU Load", value=f"`{cpu_usage}%`", inline=True)
        embed.add_field(name="System Uptime", value=f"`{uptime_str}`", inline=True)

        embed.add_field(name="Discord.py Version", value=f"`v{discord.__version__}`", inline=True)
        embed.add_field(name="Developer", value=f"{config.AUTHOR}", inline=True)
        embed.add_field(name="Repository", value=f"[GitHub]({config.GITHUB_URL})", inline=True)

        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
