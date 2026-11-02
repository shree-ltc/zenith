"""
cogs/moderation.py - Professional Server Moderation & Governance Engine for Zenith

Provides extensive moderation controls: bans, softbans, timeouts, warnings, channel locks,
comprehensive multi-filter purges, and bulk role automation with strict hierarchy checks.
"""

import re
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List

import discord
from discord.ext import commands

from core.database import db
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
        if moderator.guild.owner_id == moderator.id:
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

        # Attempt to notify victim via DM
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
    async def kick_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided."):
        """Ejects a member from the guild."""
        if not self._check_hierarchy(ctx.author, member) or not self._check_hierarchy(ctx.guild.me, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Cannot kick this user due to role positioning."), mention_author=False)

        try:
            await member.send(embed=ZenithEmbed.warning(f"Kicked from {ctx.guild.name}", f"**Reason:** {reason}"))
        except Exception:
            pass

        await member.kick(reason=f"Zenith Kick [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Kicked", f"Successfully kicked **{member}**.\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="timeout", aliases=["mute", "shutup"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout_command(self, ctx: commands.Context, member: discord.Member, duration: str = "10m", *, reason: Optional[str] = "No reason provided."):
        """Applies a Discord timeout mute (e.g., 5m, 1h, 1d). Max 28 days."""
        delta = parse_duration(duration)
        if not delta:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Duration", "Please provide a valid time format like `10m`, `2h`, or `1d`."), mention_author=False)

        if not self._check_hierarchy(ctx.author, member) or not self._check_hierarchy(ctx.guild.me, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Cannot timeout this user due to role hierarchy."), mention_author=False)

        until = datetime.now(timezone.utc) + delta
        await member.timeout(until, reason=f"Zenith Timeout [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Member Timed Out", f"Applied timeout to **{member}** for **{duration}**.\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="untimeout", aliases=["unmute"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout_command(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = "No reason provided."):
        """Lifts an active timeout from a member."""
        await member.timeout(None, reason=f"Zenith Untimeout [{ctx.author}]: {reason}")
        embed = ZenithEmbed.success("Timeout Lifted", f"Removed timeout from **{member}**.")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  WARNING SUBSYSTEM
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="warn")
    @commands.has_permissions(moderate_members=True)
    async def warn_command(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """Records an official warning against a member."""
        if not self._check_hierarchy(ctx.author, member):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "You cannot warn a member above your rank."), mention_author=False)

        query = "INSERT INTO user_warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)"
        await db.execute(query, ctx.guild.id, member.id, ctx.author.id, reason)

        # Count total warnings
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as total FROM user_warnings WHERE guild_id = ? AND user_id = ?",
            ctx.guild.id, member.id
        )
        total = count_row["total"] if count_row else 1

        try:
            await member.send(embed=ZenithEmbed.warning(f"Warned in {ctx.guild.name}", f"**Reason:** {reason}\n**Total Infractions:** {total}"))
        except Exception:
            pass

        embed = ZenithEmbed.success("Warning Issued", f"Logged warning for {member.mention} (Infraction #{total}).\n**Reason:** {reason}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="warnings", aliases=["warns"])
    @commands.has_permissions(moderate_members=True)
    async def warnings_command(self, ctx: commands.Context, member: discord.Member):
        """Retrieves a member's warning history."""
        rows = await db.fetch(
            "SELECT id, moderator_id, reason, created_at FROM user_warnings WHERE guild_id = ? AND user_id = ? ORDER BY id DESC",
            ctx.guild.id, member.id
        )
        if not rows:
            return await ctx.reply(embed=ZenithEmbed.info("Clean Record", f"{member.mention} has no recorded warnings in this server."), mention_author=False)

        desc = "\n".join(f"• **#{r['id']}** | Mod: <@{r['moderator_id']}> | Reason: `{r['reason']}`" for r in rows)
        embed = ZenithEmbed(
            title=f"Warnings for {member}",
            description=desc,
            color=Color.WARNING
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="clearwarnings", aliases=["clearwarns"])
    @commands.has_permissions(administrator=True)
    async def clearwarnings_command(self, ctx: commands.Context, member: discord.Member):
        """Erases all warning records for a user."""
        await db.execute("DELETE FROM user_warnings WHERE guild_id = ? AND user_id = ?", ctx.guild.id, member.id)
        embed = ZenithEmbed.success("Record Cleared", f"Erased all warnings for {member.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  CHANNEL RESTRICTION TOOLS (LOCK, HIDE, SLOWMODE)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None, *, reason: Optional[str] = "Channel Lockdown"):
        """Locks a channel, preventing @everyone from sending messages."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Lock [{ctx.author}]: {reason}")
        await ctx.reply(embed=ZenithEmbed.success("Channel Locked", f"Secured {ch.mention}. Members cannot send messages."), mention_author=False)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Unlocks a previously locked channel."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unlock [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Unlocked", f"Restored default permissions for {ch.mention}."), mention_author=False)

    @commands.command(name="hide")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def hide_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Hides a channel from regular members by disabling view_channel."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = False
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Hide [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Hidden", f"Hidden {ch.mention} from @everyone."), mention_author=False)

    @commands.command(name="unhide")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unhide_command(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Makes a hidden channel visible to members again."""
        ch = channel or ctx.channel
        overwrite = ch.overwrites_for(ctx.guild.default_role)
        overwrite.view_channel = None
        await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Zenith Unhide [{ctx.author}]")
        await ctx.reply(embed=ZenithEmbed.success("Channel Visible", f"Restored visibility for {ch.mention}."), mention_author=False)

    @commands.command(name="slowmode", aliases=["sm"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode_command(self, ctx: commands.Context, seconds: int):
        """Sets message rate delay in seconds for the current channel (0 to disable)."""
        if seconds < 0 or seconds > 21600:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Limit", "Slowmode must be between 0 seconds and 6 hours (21600s)."), mention_author=False)

        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            embed = ZenithEmbed.success("Slowmode Disabled", "Rate limit removed from this channel.")
        else:
            embed = ZenithEmbed.success("Slowmode Configured", f"Set channel delay to **{seconds}s** per message.")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  ADVANCED PURGE SUBSYSTEM
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="purge", aliases=["clear", "c"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_group(self, ctx: commands.Context, amount: int):
        """Deletes a specified number of recent messages in the channel."""
        if amount <= 0 or amount > config.MAX_PURGE_LIMIT:
            return await ctx.reply(embed=ZenithEmbed.error("Limit Exceeded", f"Amount must be between 1 and {config.MAX_PURGE_LIMIT}."), mention_author=False)

        deleted = await ctx.channel.purge(limit=amount + 1)
        msg = await ctx.send(embed=ZenithEmbed.success("Messages Purged", f"Deleted **{len(deleted) - 1}** messages."))
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    @purge_group.command(name="bots")
    @commands.has_permissions(manage_messages=True)
    async def purge_bots(self, ctx: commands.Context, amount: int = 50):
        """Cleans up messages sent by bots."""
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author.bot)
        msg = await ctx.send(embed=ZenithEmbed.success("Bot Messages Purged", f"Deleted **{len(deleted)}** bot messages."))
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    @purge_group.command(name="links")
    @commands.has_permissions(manage_messages=True)
    async def purge_links(self, ctx: commands.Context, amount: int = 50):
        """Removes messages containing URLs."""
        url_regex = re.compile(r"https?://\S+")
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: bool(url_regex.search(m.content)))
        msg = await ctx.send(embed=ZenithEmbed.success("Links Purged", f"Deleted **{len(deleted)}** link messages."))
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    @purge_group.command(name="user")
    @commands.has_permissions(manage_messages=True)
    async def purge_user(self, ctx: commands.Context, target: discord.Member, amount: int = 50):
        """Deletes messages sent exclusively by a specific user."""
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author.id == target.id)
        msg = await ctx.send(embed=ZenithEmbed.success("User Messages Purged", f"Removed **{len(deleted)}** messages from {target.mention}."))
        await asyncio.sleep(4)
        try:
            await msg.delete()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  ROLE MANAGEMENT TOOLS
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="role", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_group(self, ctx: commands.Context, target: discord.Member, role: discord.Role):
        """Toggles a role on a user (assigns if missing, strips if present)."""
        if not self._check_hierarchy(ctx.author, target):
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "Target user has equal or higher roles than you."), mention_author=False)
        if role >= ctx.guild.me.top_role:
            return await ctx.reply(embed=ZenithEmbed.error("Bot Hierarchy Error", "This role is higher than or equal to my highest role."), mention_author=False)

        if role in target.roles:
            await target.remove_roles(role, reason=f"Zenith Role Toggle [{ctx.author}]")
            await ctx.reply(embed=ZenithEmbed.success("Role Removed", f"Removed {role.mention} from {target.mention}."), mention_author=False)
        else:
            await target.add_roles(role, reason=f"Zenith Role Toggle [{ctx.author}]")
            await ctx.reply(embed=ZenithEmbed.success("Role Granted", f"Assigned {role.mention} to {target.mention}."), mention_author=False)

    @role_group.command(name="humans")
    @commands.has_permissions(administrator=True)
    async def role_humans(self, ctx: commands.Context, role: discord.Role):
        """Assigns a role in bulk to all human members."""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "I cannot assign a role above my highest role."), mention_author=False)

        status_msg = await ctx.reply(embed=ZenithEmbed.info("Processing", f"Assigning {role.mention} to all human members..."), mention_author=False)
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Zenith Mass Role Humans [{ctx.author}]")
                    count += 1
                except Exception:
                    pass
        await status_msg.edit(embed=ZenithEmbed.success("Bulk Role Complete", f"Granted {role.mention} to **{count}** human members."))

    @role_group.command(name="bots")
    @commands.has_permissions(administrator=True)
    async def role_bots(self, ctx: commands.Context, role: discord.Role):
        """Assigns a role in bulk to all bot accounts."""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "I cannot assign a role above my highest role."), mention_author=False)

        status_msg = await ctx.reply(embed=ZenithEmbed.info("Processing", f"Assigning {role.mention} to all bot accounts..."), mention_author=False)
        count = 0
        for member in ctx.guild.members:
            if member.bot and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Zenith Mass Role Bots [{ctx.author}]")
                    count += 1
                except Exception:
                    pass
        await status_msg.edit(embed=ZenithEmbed.success("Bulk Role Complete", f"Granted {role.mention} to **{count}** bot accounts."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
