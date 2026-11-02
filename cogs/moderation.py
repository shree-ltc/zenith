"""
Server moderation suite for Zenith.
Includes bans, kicks, timeouts, warnings, channel lockdowns, visibility controls,
purges, channel cloning, nuke, snipe, mass unban, and emoji stealing.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import re
import io
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List, Dict, Any

import aiohttp
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin
from ui.embeds import ZenithEmbed
from ui.colors import Color
from core.config import config


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Translates strings like '10m', '2h', '7d', '30s' into python timedeltas."""
    match = re.match(r"^(\d+)([smhd])$", duration_str.lower().strip())
    if not match:
        return None
    val, unit = int(match.group(1)), match.group(2)
    if unit == "s":
        return timedelta(seconds=val)
    if unit == "m":
        return timedelta(minutes=val)
    if unit == "h":
        return timedelta(hours=val)
    if unit == "d":
        return timedelta(days=val)
    return None


class Moderation(commands.Cog):
    """Core enforcement and moderation capabilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _check_hierarchy(self, moderator: discord.Member, target: discord.Member) -> bool:
        """Enforces that the moderator stands higher in the role hierarchy than the target."""
        if moderator.guild.owner_id == moderator.id or moderator.id in config.OWNER_IDS:
            return True
        return moderator.top_role > target.top_role

    # ═══════════════════════════════════════════════════════════════
    #  SANCTION COMMANDS (BAN, KICK, TIMEOUT)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="ban", aliases=["b"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_command(self, ctx: commands.Context, target: Union[discord.Member, discord.User], *, reason: Optional[str] = "No reason provided."):
        """Bans a member from the guild with hierarchy validation."""
        if isinstance(target, discord.Member):
            if not self._check_hierarchy(ctx.author, target):
                return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "You cannot ban a user with equal or higher roles."), mention_author=False)
            if not self._check_hierarchy(ctx.guild.me, target):
                return await ctx.reply(embed=ZenithEmbed.error("Bot Hierarchy Error", "I cannot ban this user because their role is above mine."), mention_author=False)

        try:
            await target.send(embed=ZenithEmbed.error(f"Banned from {ctx.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass

        await ctx.guild.ban(target, reason=f"Zenith Mod [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Banned", f"Successfully banned **{target}** (`{target.id}`).\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban_command(self, ctx: commands.Context, user_id: int, *, reason: Optional[str] = "No reason provided."):
        """Revokes a ban using the target's Discord User ID."""
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"Zenith Unban [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Unbanned", f"Revoked ban for **{user}** (`{user.id}`).")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="softban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def softban_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided."):
        """Bans and instantly unbans a user to purge their recent 7 days of messages."""
        if not self._check_hierarchy(ctx.author, member) or not self._check_hierarchy(ctx.guild.me, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Cannot softban this user due to role positioning."), mention_author=False)

        await ctx.guild.ban(member, delete_message_days=7, reason=f"Zenith Softban [{ctx.author}]: {reason}")
        await ctx.guild.unban(member, reason=f"Zenith Softban Complete [{ctx.author}]")
        embed = ZenithEmbed.success("Member Softbanned", f"Softbanned **{member}** and purged their recent messages.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="kick", aliases=["k"])
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick_command(self, ctx: commands.Context, target: discord.Member, *, reason: Optional[str] = "No reason provided."):
        """Kicks a member from the guild."""
        if not self._check_hierarchy(ctx.author, target):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Target user has equal or higher roles than you."), mention_author=False)
        if not self._check_hierarchy(ctx.guild.me, target):
            return await ctx.reply(embed=ZenithEmbed.error("Bot Hierarchy Error", "Target user has higher roles than the bot."), mention_author=False)

        try:
            await target.send(embed=ZenithEmbed.error(f"Kicked from {ctx.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass

        await target.kick(reason=f"Zenith Mod [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Kicked", f"Successfully kicked **{target}** (`{target.id}`).\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="timeout", aliases=["mute", "shutup"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout_command(self, ctx: commands.Context, member: discord.Member, duration_str: str, *, reason: Optional[str] = "No reason provided."):
        """Places a member in Discord communication timeout."""
        if not self._check_hierarchy(ctx.author, member) or not self._check_hierarchy(ctx.guild.me, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Role positions prevent moderating this user."), mention_author=False)

        delta = parse_duration(duration_str)
        if not delta or delta.total_seconds() > 2419200:  # 28 days max Discord limit
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Duration", "Specify duration like `10m`, `2h`, `7d` (max 28 days)."), mention_author=False)

        until = discord.utils.utcnow() + delta
        await member.timeout(until, reason=f"Zenith Timeout [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Timed Out", f"Applied timeout to **{member}** for **{duration_str}**.\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="untimeout", aliases=["unmute"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "Mute lifted by moderator."):
        """Removes an active timeout from a member."""
        if not self._check_hierarchy(ctx.author, member) or not self._check_hierarchy(ctx.guild.me, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Cannot remove timeout due to role positions."), mention_author=False)

        await member.timeout(None, reason=f"Zenith Untimeout [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Timeout Lifted", f"Removed timeout restriction from **{member}**.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unbanall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unbanall_command(self, ctx: commands.Context):
        """Mass unban all banned members from the server."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.reply(embed=ZenithEmbed.error("Access Denied", "Unbanall is restricted to the Server Owner."), mention_author=False)

        bans = [entry async for entry in ctx.guild.bans(limit=2000)]
        if not bans:
            return await ctx.reply(embed=ZenithEmbed.info("No Bans", "There are no banned users in this server."), mention_author=False)

        status_msg = await ctx.reply(embed=ZenithEmbed.info("Processing Unbanall", f"Unbanning **{len(bans)}** users with safe rate limits..."), mention_author=False)

        count = 0
        failed = 0
        for entry in bans:
            try:
                await ctx.guild.unban(entry.user, reason=f"Zenith Mass Unban [{ctx.author}]")
                count += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.4)

        await status_msg.edit(embed=ZenithEmbed.success(
            "Unbanall Complete",
            f"Successfully unbanned **{count}** users.\nFailed/Skipped: **{failed}**."
        ))

    # ═══════════════════════════════════════════════════════════════
    #  WARNING SYSTEM
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn_command(self, ctx: commands.Context, target: discord.Member, *, reason: Optional[str] = "Rule infraction"):
        """Issues an official moderation warning recorded in database."""
        if not self._check_hierarchy(ctx.author, target):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Cannot warn someone with equal or higher roles."), mention_author=False)

        await db.execute(
            "INSERT INTO user_warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            ctx.guild.id, target.id, ctx.author.id, reason
        )

        rows = await db.fetch("SELECT id FROM user_warnings WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        total_warns = len(rows)

        try:
            await target.send(embed=ZenithEmbed.error(
                f"Warning Issued in {ctx.guild.name}",
                f"**Reason:** {reason}\n**Total Warnings:** {total_warns}"
            ))
        except Exception:
            pass

        embed = ZenithEmbed.success(
            "Warning Logged",
            f"Logged warning for {target.mention} (`{target.id}`).\n**Reason:** {reason}\n**Total Infractions:** {total_warns}"
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unwarn")
    @commands.has_permissions(moderate_members=True)
    async def unwarn_command(self, ctx: commands.Context, target: discord.Member, warn_id: Optional[int] = None):
        """Remove a specific warning by ID, or the most recent warning for a member."""
        if warn_id:
            row = await db.fetchrow(
                "SELECT id FROM user_warnings WHERE guild_id = ? AND user_id = ? AND id = ?",
                ctx.guild.id, target.id, warn_id
            )
            if not row:
                return await ctx.reply(embed=ZenithEmbed.error("Warning Not Found", f"No warning with ID `{warn_id}` found for {target.mention}."), mention_author=False)
            await db.execute("DELETE FROM user_warnings WHERE id = ?", warn_id)
            return await ctx.reply(embed=ZenithEmbed.success("Warning Cleared", f"Removed warning `{warn_id}` from {target.mention}."), mention_author=False)

        # Remove most recent warning
        row = await db.fetchrow(
            "SELECT id FROM user_warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1",
            ctx.guild.id, target.id
        )
        if not row:
            return await ctx.reply(embed=ZenithEmbed.info("No Warnings", f"{target.mention} has zero logged warnings."), mention_author=False)

        await db.execute("DELETE FROM user_warnings WHERE id = ?", row["id"])
        await ctx.reply(embed=ZenithEmbed.success("Warning Cleared", f"Removed recent warning (ID `{row['id']}`) from {target.mention}."), mention_author=False)

    @commands.command(name="delwarn", aliases=["dewarn", "removewarn"])
    @commands.has_permissions(moderate_members=True)
    async def delwarn_command(self, ctx: commands.Context, warn_id: int):
        """Delete a specific warning record by warning ID."""
        row = await db.fetchrow("SELECT id, user_id FROM user_warnings WHERE guild_id = ? AND id = ?", ctx.guild.id, warn_id)
        if not row:
            return await ctx.reply(embed=ZenithEmbed.error("Not Found", f"No warning found with ID `{warn_id}`."), mention_author=False)

        await db.execute("DELETE FROM user_warnings WHERE id = ?", warn_id)
        await ctx.reply(embed=ZenithEmbed.success("Warning Deleted", f"Deleted warning record `{warn_id}`."), mention_author=False)

    @commands.command(name="warnings", aliases=["warns"])
    @commands.has_permissions(moderate_members=True)
    async def warnings_command(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Lists historical warnings and infraction IDs for a user."""
        target = target or ctx.author
        rows = await db.fetch(
            "SELECT id, moderator_id, reason, created_at FROM user_warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 15",
            ctx.guild.id, target.id
        )

        if not rows:
            return await ctx.reply(embed=ZenithEmbed.info("Clean Record", f"{target.mention} has no recorded warnings in this server."), mention_author=False)

        desc = f"Displaying recent infractions for {target.mention}:\n\n"
        for r in rows:
            mod = ctx.guild.get_member(r["moderator_id"])
            mod_tag = mod.mention if mod else f"`{r['moderator_id']}`"
            desc += f"`#{r['id']}` - **Reason:** {r['reason']}\n> Moderator: {mod_tag}\n\n"

        embed = ZenithEmbed.accent(f"Warning Registry ({len(rows)})", desc)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="clearwarnings", aliases=["clearwarns"])
    @commands.has_permissions(administrator=True)
    async def clearwarnings_command(self, ctx: commands.Context, target: discord.Member):
        """Purges all stored warnings for a specified member."""
        await db.execute("DELETE FROM user_warnings WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        embed = ZenithEmbed.success("Warnings Expunged", f"Successfully cleared all warning records for {target.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  CHANNEL ACCESS & LOCKDOWN (LOCK, UNLOCK, HIDE, UNHIDE)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, *, reason: Optional[str] = "Channel lockdown"):
        """Denies send_messages permission for @everyone on the specified channel."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Lock [{ctx.author}]: {reason}")
        await ctx.reply(embed=ZenithEmbed.accent("Channel Locked", f"{ch.mention} has been locked for `@everyone`.\n**Reason:** {reason}"), mention_author=False)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Restores send_messages permission for @everyone on the specified channel."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unlock [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Unlocked", f"{ch.mention} has been unlocked for `@everyone`."), mention_author=False)

    @commands.command(name="lockall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockall_command(self, ctx: commands.Context, *, reason: Optional[str] = "Server emergency lockdown"):
        """Locks all text channels in the server for @everyone."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Locking Channels", "Applying lockdown across text channels..."), mention_author=False)
        count = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                if overwrite.send_messages is not False:
                    overwrite.send_messages = False
                    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Lockall [{ctx.author}]: {reason}")
                    count += 1
            except Exception:
                pass
        await status_msg.edit(embed=ZenithEmbed.success("Lockall Complete", f"Locked **{count}** text channels for `@everyone`.\n**Reason:** {reason}"))

    @commands.command(name="unlockall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockall_command(self, ctx: commands.Context):
        """Unlocks all text channels in the server for @everyone."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Unlocking Channels", "Restoring send message permissions across text channels..."), mention_author=False)
        count = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                if overwrite.send_messages is False:
                    overwrite.send_messages = None
                    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unlockall [{ctx.author}]")
                    count += 1
            except Exception:
                pass
        await status_msg.edit(embed=ZenithEmbed.success("Unlockall Complete", f"Restored access across **{count}** text channels."))

    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def hide_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Hides the channel from @everyone view."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Hide [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.accent("Channel Hidden", f"{ch.mention} is now hidden from `@everyone`."), mention_author=False)

    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unhide_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Restores channel visibility to @everyone."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unhide [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Unhidden", f"{ch.mention} visibility has been restored for `@everyone`."), mention_author=False)

    @commands.command(name="hideall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def hideall_command(self, ctx: commands.Context):
        """Hides all text channels in the server from @everyone."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Hiding Channels", "Hiding channels from `@everyone`..."), mention_author=False)
        count = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                if overwrite.view_channel is not False:
                    overwrite.view_channel = False
                    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Hideall [{ctx.author}]")
                    count += 1
            except Exception:
                pass
        await status_msg.edit(embed=ZenithEmbed.success("Hideall Complete", f"Hidden **{count}** channels from `@everyone`."))

    @commands.command(name="unhideall")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unhideall_command(self, ctx: commands.Context):
        """Restores visibility on all text channels for @everyone."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Unhiding Channels", "Restoring channel visibility..."), mention_author=False)
        count = 0
        for ch in ctx.guild.text_channels:
            try:
                overwrite = ch.overwrites_for(ctx.guild.default_role)
                if overwrite.view_channel is False:
                    overwrite.view_channel = None
                    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unhideall [{ctx.author}]")
                    count += 1
            except Exception:
                pass
        await status_msg.edit(embed=ZenithEmbed.success("Unhideall Complete", f"Restored visibility across **{count}** channels."))

    @commands.command(name="slowmode", aliases=["sm", "slow"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode_command(self, ctx: commands.Context, seconds: int):
        """Sets slowmode delay on current channel (0 to disable, max 21600)."""
        if seconds < 0 or seconds > 21600:
            return await ctx.reply(embed=ZenithEmbed.error("Out of Bounds", "Slowmode must be between 0 and 21600 seconds (6 hours)."), mention_author=False)

        await ctx.channel.edit(slowmode_delay=seconds, reason=f"Zenith Slowmode [{ctx.author}]")
        if seconds == 0:
            return await ctx.reply(embed=ZenithEmbed.success("Slowmode Disabled", "Slowmode restrictions disabled on this channel."), mention_author=False)
        await ctx.reply(embed=ZenithEmbed.accent("Slowmode Applied", f"Rate limit per user set to **{seconds} seconds**."), mention_author=False)

    @commands.command(name="unslowmode", aliases=["unslow"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unslowmode_command(self, ctx: commands.Context):
        """Disables slowmode on the current channel."""
        await ctx.channel.edit(slowmode_delay=0, reason=f"Zenith Unslowmode [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Slowmode Cleared", "Slowmode has been removed from this channel."), mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  CHANNEL ADMINISTRATION (CREATE, DELETE, RENAME, CLONE)
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="channel", aliases=["ch"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def channel_group(self, ctx: commands.Context):
        """Manage server channels."""
        embed = discord.Embed(
            title="[CHANNEL COMMANDS]",
            description=(
                f"`{ctx.prefix}channel create <name> [text/voice/category]` - Create a channel\n"
                f"`{ctx.prefix}channel delete <channel>` - Delete a channel\n"
                f"`{ctx.prefix}channel rename <channel> <new_name>` - Rename a channel\n"
                f"`{ctx.prefix}channel clone <channel>` - Clone an existing channel"
            ),
            color=0x0F0F13
        )
        embed.set_footer(text="Zenith Moderation | Developed by Shree")
        await ctx.send(embed=embed)

    @channel_group.command(name="create")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_create(self, ctx: commands.Context, name: str, ch_type: str = "text"):
        """Create a new channel."""
        ch_type = ch_type.lower()
        if ch_type in ["text", "t"]:
            ch = await ctx.guild.create_text_channel(name=name, reason=f"[{ctx.author}]")
        elif ch_type in ["voice", "vc", "v"]:
            ch = await ctx.guild.create_voice_channel(name=name, reason=f"[{ctx.author}]")
        elif ch_type in ["category", "cat", "c"]:
            ch = await ctx.guild.create_category(name=name, reason=f"[{ctx.author}]")
        else:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Type", "Valid types: `text`, `voice`, `category`."), mention_author=False)

        await ctx.reply(embed=ZenithEmbed.success("Channel Created", f"Created {ch.mention} (`{ch.id}`)."), mention_author=False)

    @channel_group.command(name="delete")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_delete(self, ctx: commands.Context, channel: discord.abc.GuildChannel):
        """Delete an existing channel."""
        ch_name = channel.name
        await channel.delete(reason=f"[{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Deleted", f"Deleted channel `{ch_name}`."), mention_author=False)

    @channel_group.command(name="rename")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_rename(self, ctx: commands.Context, channel: discord.abc.GuildChannel, *, new_name: str):
        """Rename an existing channel."""
        old = channel.name
        await channel.edit(name=new_name, reason=f"[{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Renamed", f"Renamed `{old}` to `{new_name}`."), mention_author=False)

    @channel_group.command(name="clone")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_clone(self, ctx: commands.Context, channel: discord.abc.GuildChannel):
        """Clone an existing channel."""
        new_ch = await channel.clone(reason=f"[{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Cloned", f"Cloned `{channel.name}` into {new_ch.mention}."), mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  EMOJI STEALER
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="steal", aliases=["stealemoji"])
    @commands.guild_only()
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def steal_emoji(self, ctx: commands.Context, emoji: str, *, name: Optional[str] = None):
        """Steal a custom emoji or image url and add it to the server."""
        custom_match = re.search(r"<(a)?:([a-zA-Z0-9_]+):([0-9]+)>", emoji)
        if custom_match:
            is_animated = bool(custom_match.group(1))
            ext = "gif" if is_animated else "png"
            emoji_id = custom_match.group(3)
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
            emoji_name = name or custom_match.group(2)
        elif emoji.startswith("http://") or emoji.startswith("https://"):
            url = emoji
            emoji_name = name or "custom_emoji"
        else:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Emoji", "Please provide a valid custom emoji or direct image URL."), mention_author=False)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return await ctx.reply(embed=ZenithEmbed.error("Download Failed", "Could not fetch emoji asset."), mention_author=False)
                    image_bytes = await resp.read()

            created = await ctx.guild.create_custom_emoji(name=emoji_name, image=image_bytes, reason=f"Zenith Steal [{ctx.author}]")
            await ctx.reply(embed=ZenithEmbed.success("Emoji Added", f"Successfully added emoji {created} (`:{created.name}:`)."), mention_author=False)
        except discord.HTTPException as e:
            await ctx.reply(embed=ZenithEmbed.error("Upload Error", f"Failed to upload emoji: {e}"), mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  NICKNAME & VOICE MODERATION SUITE
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="nick", aliases=["setnick"])
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nick_command(self, ctx: commands.Context, member: discord.Member, *, nickname: Optional[str] = None):
        """Change or reset a member's server nickname."""
        if not await self.can_moderate(ctx, member):
            return await ctx.reply("[ERROR] Hierarchy restriction: Cannot modify this member.", mention_author=False)

        old_nick = member.display_name
        try:
            await member.edit(nick=nickname, reason=f"Moderator: {ctx.author}")
            if nickname:
                await ctx.reply(f"[OK] Changed nickname of {member.mention} to `{nickname}`.", mention_author=False)
            else:
                await ctx.reply(f"[OK] Reset nickname for {member.mention} (was `{old_nick}`).", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to alter nickname: {e}", mention_author=False)

    @commands.command(name="resetnick")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def resetnick_command(self, ctx: commands.Context, member: discord.Member):
        """Reset a member's nickname back to their default username."""
        if not await self.can_moderate(ctx, member):
            return await ctx.reply("[ERROR] Hierarchy restriction: Cannot modify this member.", mention_author=False)

        try:
            await member.edit(nick=None, reason=f"Moderator: {ctx.author}")
            await ctx.reply(f"[OK] Reset nickname for {member.mention}.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to reset nickname: {e}", mention_author=False)

    @commands.command(name="voicekick", aliases=["vkick"])
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def voicekick_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "Voice kick"):
        """Disconnect a member from their current voice channel."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not in any voice channel.", mention_author=False)

        try:
            await member.move_to(None, reason=f"{reason} (by {ctx.author})")
            await ctx.reply(f"[OK] Disconnected {member.mention} from voice.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to disconnect member: {e}", mention_author=False)

    @commands.command(name="voicemute", aliases=["vmute"])
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def voicemute_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "Voice mute"):
        """Server-mute a member in voice channels."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently connected to voice.", mention_author=False)

        try:
            await member.edit(mute=True, reason=f"{reason} (by {ctx.author})")
            await ctx.reply(f"[OK] Server muted {member.mention} in voice.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to voice-mute member: {e}", mention_author=False)

    @commands.command(name="voiceunmute", aliases=["vunmute"])
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def voiceunmute_command(self, ctx: commands.Context, member: discord.Member):
        """Remove server-mute from a member in voice channels."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently connected to voice.", mention_author=False)

        try:
            await member.edit(mute=False, reason=f"Voice unmute by {ctx.author}")
            await ctx.reply(f"[OK] Unmuted {member.mention} in voice.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to unmute member: {e}", mention_author=False)

    @commands.command(name="voicedeafen", aliases=["vdeaf"])
    @commands.has_permissions(deafen_members=True)
    @commands.bot_has_permissions(deafen_members=True)
    async def voicedeafen_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "Voice deafen"):
        """Server-deafen a member in voice channels."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently connected to voice.", mention_author=False)

        try:
            await member.edit(deafen=True, reason=f"{reason} (by {ctx.author})")
            await ctx.reply(f"[OK] Server deafened {member.mention} in voice.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to deafen member: {e}", mention_author=False)

    @commands.command(name="voiceundeafen", aliases=["vundeaf"])
    @commands.has_permissions(deafen_members=True)
    @commands.bot_has_permissions(deafen_members=True)
    async def voiceundeafen_command(self, ctx: commands.Context, member: discord.Member):
        """Remove server-deafen from a member in voice channels."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently connected to voice.", mention_author=False)

        try:
            await member.edit(deafen=False, reason=f"Voice undeafen by {ctx.author}")
            await ctx.reply(f"[OK] Undeafened {member.mention} in voice.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to undeafen member: {e}", mention_author=False)

    @commands.command(name="voicemove", aliases=["vmove"])
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def voicemove_command(self, ctx: commands.Context, member: discord.Member, target_channel: discord.VoiceChannel):
        """Move a member to another voice channel."""
        if not member.voice or not member.voice.channel:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently in a voice channel.", mention_author=False)

        try:
            await member.move_to(target_channel, reason=f"Moved by {ctx.author}")
            await ctx.reply(f"[OK] Moved {member.mention} to {target_channel.name}.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to move member: {e}", mention_author=False)

    @commands.command(name="voicemoveall", aliases=["vmoveall"])
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def voicemoveall_command(self, ctx: commands.Context, source_channel: discord.VoiceChannel, target_channel: discord.VoiceChannel):
        """Move all members from one voice channel to another."""
        members = list(source_channel.members)
        if not members:
            return await ctx.reply(f"[INFO] No members found in {source_channel.name}.", mention_author=False)

        moved = 0
        for m in members:
            try:
                await m.move_to(target_channel, reason=f"Mass voice move by {ctx.author}")
                moved += 1
            except Exception:
                pass

        await ctx.reply(f"[OK] Moved {moved}/{len(members)} members from {source_channel.name} to {target_channel.name}.", mention_author=False)

    @channel_group.command(name="topic")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_topic(self, ctx: commands.Context, channel: discord.TextChannel, *, topic: str):
        """Set the topic of a text channel."""
        try:
            await channel.edit(topic=topic, reason=f"Topic set by {ctx.author}")
            await ctx.reply(f"[OK] Updated topic for {channel.mention}.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to update topic: {e}", mention_author=False)

    @channel_group.command(name="nsfw")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_nsfw(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Toggle NSFW status on a text channel."""
        target = channel or ctx.channel
        new_state = not target.is_nsfw()
        try:
            await target.edit(nsfw=new_state, reason=f"NSFW toggled by {ctx.author}")
            await ctx.reply(f"[OK] Channel {target.mention} is now {'NSFW marked' if new_state else 'SFW'}.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to toggle NSFW: {e}", mention_author=False)

    @channel_group.command(name="sync")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def ch_sync(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Sync channel permissions with its parent category."""
        target = channel or ctx.channel
        if not target.category:
            return await ctx.reply(f"[ERROR] {target.mention} is not inside a category.", mention_author=False)

        try:
            await target.sync_permissions(reason=f"Permissions synced by {ctx.author}")
            await ctx.reply(f"[OK] Permissions for {target.mention} synced with category `{target.category.name}`.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to sync permissions: {e}", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
