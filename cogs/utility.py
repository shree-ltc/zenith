"""
Utility, diagnostic, and information gathering suite for Zenith.
Includes user profiles, server analytics, high-res avatar/banner extraction,
message recovery (snipe/editsnipe), color analysis, math calculation, polling, and telemetry.
"""

from __future__ import annotations

import io
import math
import random
import re
import time
from datetime import datetime, timezone
from typing import Optional, Union
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
import psutil

from core.config import config
from ui.components import ping_container, stats_paged_container

THEME_COLOR = 0x0F0F13
CUSTOM_EMOJI_REGEX = re.compile(r"<(a)?:([a-zA-Z0-9_]+):([0-9]+)>")


class Utility(commands.Cog):
    """Server diagnostics, user lookups, and operational utilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._snipe_cache: dict[int, tuple[discord.Message, datetime]] = {}
        self._editsnipe_cache: dict[int, tuple[discord.Message, discord.Message, datetime]] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return
        self._snipe_cache[message.channel.id] = (message, datetime.now(timezone.utc))

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        self._editsnipe_cache[before.channel.id] = (before, after, datetime.now(timezone.utc))

    # ═══════════════════════════════════════════════════════════════
    #  INSPECTION COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="userinfo", aliases=["ui", "whois", "user"])
    async def userinfo_command(self, ctx: commands.Context, *, target: Optional[Union[discord.Member, discord.User]] = None):
        """Provide identity profile on a guild member or Discord user."""
        user = target or ctx.author

        embed = discord.Embed(
            title=f"[IDENTITY] {user.name}",
            color=THEME_COLOR
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        created_ts = int(user.created_at.timestamp())
        embed.add_field(name="Account Created", value=f"<t:{created_ts}:F>\n(<t:{created_ts}:R>)", inline=True)

        if isinstance(user, discord.Member):
            if user.joined_at:
                joined_ts = int(user.joined_at.timestamp())
                embed.add_field(name="Joined Server", value=f"<t:{joined_ts}:F>\n(<t:{joined_ts}:R>)", inline=True)

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

        embed.add_field(name="User ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="Bot Account", value="Yes" if user.bot else "No", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverinfo", aliases=["si", "guildinfo", "guild"])
    async def serverinfo_command(self, ctx: commands.Context):
        """Summarize guild metrics, member breakdown, channels, and security tiers."""
        guild = ctx.guild
        owner = guild.owner or await self.bot.fetch_user(guild.owner_id)

        embed = discord.Embed(title=f"[SERVER METRICS] {guild.name}", color=THEME_COLOR)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        created_ts = int(guild.created_at.timestamp())
        embed.add_field(name="Server Owner", value=f"{owner.mention} (`{owner.id}`)", inline=True)
        embed.add_field(name="Created On", value=f"<t:{created_ts}:D>\n(<t:{created_ts}:R>)", inline=True)
        embed.add_field(name="Boost Level", value=f"Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)

        total_members = guild.member_count or len(guild.members)
        humans = sum(1 for m in guild.members if not m.bot)
        bots = total_members - humans
        embed.add_field(name="Population", value=f"Total: **{total_members:,}**\nHumans: **{humans:,}** | Bots: **{bots:,}**", inline=True)

        text_count = len(guild.text_channels)
        voice_count = len(guild.voice_channels)
        cat_count = len(guild.categories)
        embed.add_field(name="Channels", value=f"Text: **{text_count}** | Voice: **{voice_count}** | Cat: **{cat_count}**", inline=True)

        embed.add_field(name="Role Count", value=f"**{len(guild.roles)}** roles", inline=True)
        embed.add_field(name="Verification", value=f"`{str(guild.verification_level).title()}`", inline=True)
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar_command(self, ctx: commands.Context, *, user: Optional[Union[discord.Member, discord.User]] = None):
        """Display full-resolution Discord profile avatar."""
        target = user or ctx.author
        avatar_url = target.display_avatar.url

        embed = discord.Embed(title=f"[AVATAR] {target.name}", color=THEME_COLOR)
        embed.set_image(url=avatar_url)
        embed.add_field(
            name="Asset Links",
            value=f"[PNG]({target.display_avatar.replace(format='png').url}) | [JPG]({target.display_avatar.replace(format='jpg').url}) | [WEBP]({target.display_avatar.replace(format='webp').url})"
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="userbanner", aliases=["ubanner", "banner"])
    async def banner_command(self, ctx: commands.Context, *, user: Optional[Union[discord.Member, discord.User]] = None):
        """Display user's profile banner asset."""
        target = user or ctx.author
        fetched = await self.bot.fetch_user(target.id)
        if not fetched.banner:
            return await ctx.reply(f"[INFO] {target.name} does not have a profile banner set.", mention_author=False)

        embed = discord.Embed(title=f"[USER BANNER] {target.name}", color=THEME_COLOR)
        embed.set_image(url=fetched.banner.url)
        embed.add_field(name="Asset Link", value=f"[Direct Image Link]({fetched.banner.url})")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="snipe")
    async def snipe_command(self, ctx: commands.Context):
        """Recover the most recently deleted message in this channel."""
        data = self._snipe_cache.get(ctx.channel.id)
        if not data:
            return await ctx.reply("[INFO] No recently deleted messages cached in this channel.", mention_author=False)

        msg, deleted_at = data
        embed = discord.Embed(
            title=f"[SNIPE] Message from {msg.author}",
            description=msg.content or "*[Message had no text content]*",
            color=THEME_COLOR,
            timestamp=deleted_at
        )
        embed.set_thumbnail(url=msg.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="editsnipe", aliases=["esnipe"])
    async def editsnipe_command(self, ctx: commands.Context):
        """Display before and after text of the last edited message."""
        data = self._editsnipe_cache.get(ctx.channel.id)
        if not data:
            return await ctx.reply("[INFO] No recently edited messages cached in this channel.", mention_author=False)

        before, after, edited_at = data
        embed = discord.Embed(
            title=f"[EDITSNIPE] Edited by {before.author}",
            color=THEME_COLOR,
            timestamp=edited_at
        )
        embed.add_field(name="Before", value=before.content or "*[Empty]*", inline=False)
        embed.add_field(name="After", value=after.content or "*[Empty]*", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="enlarge", aliases=["jumbo", "bigemoji"])
    async def enlarge_cmd(self, ctx: commands.Context, emoji: str):
        """Enlarge a custom emoji to full resolution."""
        match = CUSTOM_EMOJI_REGEX.search(emoji)
        if match:
            animated, name, emoji_id = match.groups()
            ext = "gif" if animated else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?size=512"
            embed = discord.Embed(
                title=f"[EMOJI ENLARGED] :{name}:",
                description=f"[Direct Asset Link]({url})",
                color=THEME_COLOR
            )
            embed.set_image(url=url)
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(f"[INFO] Showing unicode character: `{emoji}`", mention_author=False)

    @commands.command(name="color", aliases=["colour", "hexcolor", "colorinfo"])
    async def color_cmd(self, ctx: commands.Context, hex_code: str):
        """Inspect a hex color with preview, RGB, and integer values."""
        clean_hex = hex_code.strip("#").upper()
        if len(clean_hex) != 6:
            return await ctx.reply("[ERROR] Invalid hex color code. Provide 6 hex characters (e.g. `5865F2`).", mention_author=False)

        try:
            r = int(clean_hex[0:2], 16)
            g = int(clean_hex[2:4], 16)
            b = int(clean_hex[4:6], 16)
            int_val = int(clean_hex, 16)
        except ValueError:
            return await ctx.reply("[ERROR] Invalid hexadecimal characters.", mention_author=False)

        embed = discord.Embed(
            title=f"[COLOR] #{clean_hex}",
            color=int_val
        )
        embed.add_field(name="Hexadecimal", value=f"`#{clean_hex}`", inline=True)
        embed.add_field(name="RGB", value=f"`rgb({r}, {g}, {b})`", inline=True)
        embed.add_field(name="Integer Value", value=f"`{int_val}`", inline=True)
        preview_url = f"https://singlecolorimage.com/get/{clean_hex}/200x80"
        embed.set_thumbnail(url=preview_url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="inviteinfo", aliases=["ii", "fetchinvite"])
    async def inviteinfo_cmd(self, ctx: commands.Context, invite_code: str):
        """Fetch details about a Discord invite code without joining."""
        code = invite_code.split("/")[-1]
        try:
            inv = await self.bot.fetch_invite(code, with_counts=True)
        except Exception:
            return await ctx.reply(f"[ERROR] Could not resolve invite `{code}`.", mention_author=False)

        embed = discord.Embed(
            title=f"[INVITE INFO] {inv.guild.name if inv.guild else 'Group DM'}",
            color=THEME_COLOR
        )
        if inv.guild and inv.guild.icon:
            embed.set_thumbnail(url=inv.guild.icon.url)

        embed.add_field(name="Code", value=f"`{inv.code}`", inline=True)
        if inv.inviter:
            embed.add_field(name="Inviter", value=f"{inv.inviter} (`{inv.inviter.id}`)", inline=True)
        if inv.channel:
            embed.add_field(name="Destination", value=f"#{inv.channel.name}", inline=True)
        if inv.approximate_member_count:
            embed.add_field(name="Members", value=f"{inv.approximate_member_count:,} total ({inv.approximate_presence_count:,} online)", inline=True)
        if inv.guild:
            embed.add_field(name="Guild ID", value=f"`{inv.guild.id}`", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rawmessage", aliases=["rawmsg"])
    @commands.has_permissions(manage_messages=True)
    async def rawmessage_cmd(self, ctx: commands.Context, message_id: int):
        """Inspect the raw unparsed content and markdown of a message."""
        try:
            msg = await ctx.channel.fetch_message(message_id)
        except Exception:
            return await ctx.reply(f"[ERROR] Message `{message_id}` was not found in this channel.", mention_author=False)

        raw = msg.content or "[Empty Content]"
        if len(raw) > 1900:
            raw = raw[:1900] + "..."
        await ctx.reply(f"```{discord.utils.escape_markdown(raw)}```", mention_author=False)

    @commands.command(name="calc", aliases=["calculator", "math"])
    async def calc_cmd(self, ctx: commands.Context, *, expression: str):
        """Safely evaluate mathematical expressions."""
        # Sanitize expression: allow only numbers, math operators, parens, dots
        clean = expression.replace(" ", "")
        allowed = set("0123456789+-*/().,%^")
        if not all(c in allowed for c in clean):
            return await ctx.reply("[ERROR] Invalid characters in mathematical expression.", mention_author=False)

        try:
            safe_expr = clean.replace("^", "**")
            result = eval(safe_expr, {"__builtins__": None}, {})
            embed = discord.Embed(
                title="[CALCULATOR]",
                color=THEME_COLOR
            )
            embed.add_field(name="Expression", value=f"`{expression}`", inline=False)
            embed.add_field(name="Result", value=f"`{result}`", inline=False)
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Math evaluation error: {e}", mention_author=False)

    @commands.command(name="randomnumber", aliases=["randint", "rand"])
    async def randint_cmd(self, ctx: commands.Context, min_val: int = 1, max_val: int = 100):
        """Generate a random integer between min and max."""
        if min_val >= max_val:
            return await ctx.reply("[ERROR] Minimum value must be less than maximum value.", mention_author=False)

        val = random.randint(min_val, max_val)
        await ctx.reply(f"[RANDOM NUMBER] Generated: **{val}** (Range: {min_val} - {max_val})", mention_author=False)



    @commands.command(name="poll")
    async def poll_cmd(self, ctx: commands.Context, question: str, *options: str):
        """Create a community reaction poll."""
        if len(options) == 0:
            embed = discord.Embed(
                title=f"[POLL] {question}",
                description="Vote below with standard reaction indicators:\n• ▲ (Yes / Agree)\n• ▼ (No / Disagree)",
                color=THEME_COLOR
            )
            embed.set_footer(text=f"Initiated by {ctx.author.name}")
            msg = await ctx.send(embed=embed)
            await msg.add_reaction("▲")
            await msg.add_reaction("▼")
        elif len(options) > 10:
            return await ctx.reply("[ERROR] Polls support a maximum of 10 options.", mention_author=False)
        else:
            body = "\n".join(f"**[{i+1}]** {opt}" for i, opt in enumerate(options))
            embed = discord.Embed(
                title=f"[POLL] {question}",
                description=body,
                color=THEME_COLOR
            )
            embed.set_footer(text=f"Initiated by {ctx.author.name}")
            await ctx.send(embed=embed)

    @commands.command(name="firstmessage", aliases=["firstmsg"])
    async def firstmessage_cmd(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Fetch the very first message sent in a channel."""
        target = channel or ctx.channel
        try:
            async for m in target.history(limit=1, oldest_first=True):
                first_msg = m
                break
            else:
                return await ctx.reply("[INFO] No messages found in channel.", mention_author=False)

            embed = discord.Embed(
                title=f"[FIRST MESSAGE] #{target.name}",
                description=first_msg.content or "*[No text]*",
                color=THEME_COLOR,
                timestamp=first_msg.created_at
            )
            embed.set_author(name=str(first_msg.author), icon_url=first_msg.author.display_avatar.url)
            embed.add_field(name="Jump Link", value=f"[Go to Message]({first_msg.jump_url})")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Could not fetch first message: {e}", mention_author=False)

    @commands.command(name="ping", aliases=["latency"])
    async def ping_command(self, ctx: commands.Context):
        """Measure WebSocket gateway heartbeat and REST API roundtrip."""
        start_time = time.monotonic()
        msg = await ctx.reply("[INFO] Measuring gateway telemetry...", mention_author=False)
        end_time = time.monotonic()

        api_latency = round((end_time - start_time) * 1000)
        ws_latency = round(self.bot.latency * 1000)
        msg_latency = round((time.time() - ctx.message.created_at.timestamp()) * 1000)

        container_data = ping_container(
            ws_ms=ws_latency,
            msg_ms=abs(msg_latency),
            api_ms=api_latency,
            bot_avatar=self.bot.user.display_avatar.url
        )
        await msg.edit(content=None, view=container_data["view"])

    @commands.command(name="botinfo", aliases=["stats", "about", "info"])
    async def botinfo_command(self, ctx: commands.Context):
        """Display runtime architecture, memory utilization, and node stats."""
        uptime_seconds = int(time.time() - self.bot.launch_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        process = psutil.Process()
        memory_usage = process.memory_info().rss / (1024 * 1024)
        cpu_usage = psutil.cpu_percent()

        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count or 0 for g in self.bot.guilds)
        total_shards = self.bot.shard_count or 1

        body = (
            f"• **Guilds :** `{total_guilds:,}` servers\n"
            f"• **Users :** `{total_users:,}` cached accounts\n"
            f"• **Shards :** `{total_shards}` active shards\n"
            f"• **Memory :** `{memory_usage:.1f} MB` (RSS)\n"
            f"• **CPU Load :** `{cpu_usage}%`\n"
            f"• **System Uptime :** `{uptime_str}`\n"
            f"• **Discord.py :** `v{discord.__version__}` (Components V2)\n"
            f"• **Platform :** Linux / Python 3.12"
        )

        team_data = {
            "Architect": [("Shree", "shree.ltc", 1465912900710305822)],
            "Developer": [("Shree", "shree.ltc", 1465912900710305822)],
        }

        cluster_data = [
            ("Master Gateway", "Connected (0.0.0.0:8080)"),
            ("PostgreSQL Cluster", "Pool Active (asyncpg)"),
            ("Redis Cache", "Sub-millisecond L1 Memory"),
            ("Components V2 UI", "Active (Obsidian Theme)"),
        ]

        invite_url = getattr(config, "INVITE_URL", None) or "https://discord.com/oauth2/authorize?client_id=1298918870039527435&permissions=8&integration_type=0&scope=bot+applications.commands"
        support_url = getattr(config, "SUPPORT_SERVER", None) or "https://discord.gg/zenith"

        paged_view = stats_paged_container(
            author_id=ctx.author.id,
            bot_name=self.bot.user.name,
            bot_avatar=self.bot.user.display_avatar.url,
            invite_url=invite_url,
            support_url=support_url,
            bot_info_body=body,
            team_data=team_data,
            cluster_data=cluster_data,
        )
        await ctx.send(view=paged_view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
