"""
Antinuke system monitoring audit logs for unauthorized guild changes.
Intercepts mass bans, kicks, channel purges, role tampering, and rogue bots.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Union

import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color
from core.logging import info, warn, error


class Antinuke(commands.Cog):
    """Real-time server shield and anti-raid defense engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldown set to prevent cascading loops during audits
        self._action_cooldown: set[str] = set()

    # ═══════════════════════════════════════════════════════════════
    #  INTERNAL DEFENSE LOGIC
    # ═══════════════════════════════════════════════════════════════

    async def is_whitelisted(self, guild: discord.Guild, user_id: int) -> bool:
        """Determines if a user has immunity (Server Owner or Whitelisted Admin)."""
        # 1. Server Owner is always completely immune
        if guild.owner_id == user_id:
            return True

        # 2. The bot itself is immune
        if user_id == self.bot.user.id:
            return True

        # 3. Check database whitelist
        cached = await db.cache_get(f"whitelist:{guild.id}:{user_id}")
        if cached is not None:
            return bool(int(cached))

        row = await db.fetchrow(
            "SELECT 1 FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?",
            guild.id, user_id
        )
        is_wl = row is not None
        await db.cache_set(f"whitelist:{guild.id}:{user_id}", 1 if is_wl else 0, ttl=300)
        return is_wl

    async def get_config(self, guild_id: int) -> Optional[dict]:
        """Fetches guild antinuke rules with cache validation."""
        cached_enabled = await db.cache_get(f"antinuke:enabled:{guild_id}")
        if cached_enabled == "0":
            return None

        row = await db.fetchrow("SELECT * FROM antinuke_config WHERE guild_id = ?", guild_id)
        if not row or not row.get("enabled"):
            await db.cache_set(f"antinuke:enabled:{guild_id}", "0", ttl=300)
            return None

        await db.cache_set(f"antinuke:enabled:{guild_id}", "1", ttl=300)
        return row

    async def punish_executor(self, guild: discord.Guild, user: Union[discord.User, discord.Member], action: str, details: str):
        """Applies configured punishment (Ban/Kick) to rogue administrator and dispatches audit log."""
        cfg = await self.get_config(guild.id)
        punishment_type = cfg.get("punishment", "ban") if cfg else "ban"

        # Unique key to ensure we don't punish the same trigger multiple times in concurrency
        lock_key = f"punish:{guild.id}:{user.id}:{action}"
        if lock_key in self._action_cooldown:
            return
        self._action_cooldown.add(lock_key)

        # Remove from cooldown after 10 seconds
        asyncio.get_event_loop().call_later(10, self._action_cooldown.discard, lock_key)

        warn(f"[Antinuke] Unauthorized action detected in '{guild.name}' by {user} (ID: {user.id}) -> Action: {action}", "antinuke")

        # Execute punishment
        try:
            if punishment_type == "ban":
                await guild.ban(user, reason=f"Zenith Antinuke: Unauthorized {action} detected.")
            elif punishment_type == "kick" and isinstance(user, discord.Member):
                await guild.kick(user, reason=f"Zenith Antinuke: Unauthorized {action} detected.")
        except discord.Forbidden:
            error(f"[Antinuke] Failed to punish {user} in {guild.name} (Missing Permissions or Role Hierarchy).", "antinuke")
        except Exception as e:
            error(f"[Antinuke] Unexpected error applying punishment: {e}", "antinuke")

        # Dispatch Alert Embed to configured log channel
        log_channel_id = cfg.get("log_channel") if cfg else None
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = ZenithEmbed(
                    title="Antinuke Security Alert",
                    description="An unauthorized action was detected and intercepted.",
                    color=Color.ERROR
                )
                embed.add_field(name="Target Action", value=f"`{action}`", inline=True)
                embed.add_field(name="Offending Actor", value=f"{user.mention} (`{user.id}`)", inline=True)
                embed.add_field(name="Punishment Enforced", value=f"`{punishment_type.upper()}`", inline=True)
                embed.add_field(name="Details", value=details, inline=False)
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════
    #  SECURITY EVENT LISTENERS
    # ═══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Detects unauthorized channel generation."""
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_channel", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Channel Create", f"Created channel: `#{channel.name}`")
                        await channel.delete(reason="Zenith Antinuke: Reverting unauthorized channel creation.")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Detects unauthorized channel deletion."""
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_channel", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Channel Delete", f"Deleted channel: `#{channel.name}`")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Detects unauthorized role creation."""
        guild = role.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_role", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Role Create", f"Created role: `@{role.name}`")
                        await role.delete(reason="Zenith Antinuke: Reverting unauthorized role creation.")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Detects unauthorized role deletion."""
        guild = role.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_role", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Role Delete", f"Deleted role: `@{role.name}`")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        """Detects mass/unauthorized bans."""
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_ban", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
                if entry.target.id == user.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Member Ban", f"Banned member: {user.mention} (`{user.id}`)")
                        # Auto unban the victim
                        try:
                            await guild.unban(user, reason="Zenith Antinuke: Restoring unlawfully banned member.")
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Detects unauthorized kicks."""
        guild = member.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_kick", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                if entry.target.id == member.id:
                    if not await self.is_whitelisted(guild, entry.user.id):
                        await self.punish_executor(guild, entry.user, "Member Kick", f"Kicked member: {member.mention} (`{member.id}`)")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Prevents unauthorized bot invitations (anti-rogue bot)."""
        if not member.bot:
            return

        guild = member.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_bot", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                if entry.target.id == member.id:
                    # Check who invited this bot
                    inviter = entry.user
                    if not await self.is_whitelisted(guild, inviter.id):
                        # Ban the unauthorized bot immediately
                        await member.ban(reason="Zenith Antinuke: Unauthorized bot addition.")
                        # Punish the admin who added it
                        await self.punish_executor(guild, inviter, "Bot Addition", f"Added rogue bot: {member.mention}")
                    break
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        """Detects webhook creation or modification attacks."""
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_webhook", True):
            return

        try:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
                if not await self.is_whitelisted(guild, entry.user.id):
                    await self.punish_executor(guild, entry.user, "Webhook Create", f"Spawned webhook in `#{channel.name}`")
                    # Delete the rogue webhook
                    try:
                        wh = entry.target
                        await wh.delete(reason="Zenith Antinuke: Deleting unauthorized webhook.")
                    except Exception:
                        pass
                break
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  ANTINUKE COMMAND MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="antinuke", aliases=["an", "security"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke_group(self, ctx: commands.Context):
        """Accesses the Zenith Antinuke dashboard and configuration suite."""
        row = await db.fetchrow("SELECT * FROM antinuke_config WHERE guild_id = ?", ctx.guild.id)
        status_text = "ENABLED" if (row and row.get("enabled")) else "DISABLED"
        punishment = row.get("punishment", "ban").upper() if row else "BAN"
        log_ch = f"<#{row.get('log_channel')}>" if (row and row.get("log_channel")) else "`None`"

        embed = ZenithEmbed(
            title="Zenith Antinuke Dashboard",
            description=f"Server defense system is currently **{status_text}**.",
            color=Color.SUCCESS if status_text == "ENABLED" else Color.MUTED
        )
        embed.add_field(name="Punishment Mode", value=f"`{punishment}`", inline=True)
        embed.add_field(name="Security Log Channel", value=log_ch, inline=True)
        embed.add_field(
            name="Available Commands",
            value=(
                f"• `{ctx.prefix}antinuke enable` — Arm server protection\n"
                f"• `{ctx.prefix}antinuke disable` — Disarm server protection\n"
                f"• `{ctx.prefix}antinuke punishment <ban|kick>` — Set consequence\n"
                f"• `{ctx.prefix}antinuke logs <#channel>` — Set security alerts channel\n"
                f"• `{ctx.prefix}antinuke whitelist <add|remove|list>` — Manage immune admins"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_group.command(name="enable", aliases=["on", "arm"])
    @commands.has_permissions(administrator=True)
    async def antinuke_enable(self, ctx: commands.Context):
        """Arms all antinuke protection modules."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in self.bot.owner_ids:
            return await ctx.reply(
                embed=ZenithEmbed.error("Owner Restricted", "Only the Server Owner can arm or disarm Antinuke."),
                mention_author=False
            )

        if db.is_postgres:
            query = """
            INSERT INTO antinuke_config (guild_id, enabled) VALUES (?, TRUE)
            ON CONFLICT (guild_id) DO UPDATE SET enabled = TRUE;
            """
        else:
            query = """
            INSERT INTO antinuke_config (guild_id, enabled) VALUES (?, TRUE)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = TRUE;
            """
        await db.execute(query, ctx.guild.id)
        await db.cache_set(f"antinuke:enabled:{ctx.guild.id}", "1", ttl=300)

        embed = ZenithEmbed.success(
            "Antinuke Armed",
            "Zenith is now actively monitoring server audit logs for malicious activity."
        )
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_group.command(name="disable", aliases=["off", "disarm"])
    @commands.has_permissions(administrator=True)
    async def antinuke_disable(self, ctx: commands.Context):
        """Disarms antinuke protection modules."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in self.bot.owner_ids:
            return await ctx.reply(
                embed=ZenithEmbed.error("Owner Restricted", "Only the Server Owner can arm or disarm Antinuke."),
                mention_author=False
            )

        await db.execute("UPDATE antinuke_config SET enabled = FALSE WHERE guild_id = ?", ctx.guild.id)
        await db.cache_set(f"antinuke:enabled:{ctx.guild.id}", "0", ttl=300)

        embed = ZenithEmbed.warning(
            "Antinuke Disarmed",
            "Server protection has been turned off. Be careful when granting administrator roles."
        )
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_group.command(name="punishment", aliases=["punish", "action"])
    @commands.has_permissions(administrator=True)
    async def antinuke_punishment(self, ctx: commands.Context, mode: str):
        """Sets the penalty applied to offenders (ban or kick)."""
        mode = mode.lower()
        if mode not in ("ban", "kick"):
            return await ctx.reply(
                embed=ZenithEmbed.error("Invalid Option", "Punishment must be either `ban` or `kick`."),
                mention_author=False
            )

        await db.execute("UPDATE antinuke_config SET punishment = ? WHERE guild_id = ?", mode, ctx.guild.id)
        embed = ZenithEmbed.success("Punishment Updated", f"Antinuke penalty is now set to **{mode.upper()}**.")
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_group.command(name="logs", aliases=["channel"])
    @commands.has_permissions(administrator=True)
    async def antinuke_logs(self, ctx: commands.Context, channel: discord.TextChannel):
        """Sets the destination channel for antinuke incident alerts."""
        await db.execute("UPDATE antinuke_config SET log_channel = ? WHERE guild_id = ?", channel.id, ctx.guild.id)
        embed = ZenithEmbed.success("Alert Channel Configured", f"Security logs will now be broadcast to {channel.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    @antinuke_group.group(name="whitelist", aliases=["wl"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def whitelist_group(self, ctx: commands.Context):
        """Manages the list of trusted administrators immune to antinuke triggers."""
        rows = await db.fetch("SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            desc = "No extra users are currently whitelisted. Only the **Server Owner** is immune."
        else:
            desc = "\n".join(f"• <@{r['user_id']}> (`{r['user_id']}`)" for r in rows)

        embed = ZenithEmbed(
            title="Antinuke Whitelist Directory",
            description=desc,
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @whitelist_group.command(name="add")
    @commands.has_permissions(administrator=True)
    async def whitelist_add(self, ctx: commands.Context, user: discord.User):
        """Grants antinuke immunity to a trusted administrator."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in self.bot.owner_ids:
            return await ctx.reply(
                embed=ZenithEmbed.error("Owner Restricted", "Only the Server Owner can grant whitelist immunity."),
                mention_author=False
            )

        if db.is_postgres:
            query = """
            INSERT INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)
            ON CONFLICT (guild_id, user_id) DO NOTHING;
            """
        else:
            query = """
            INSERT INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING;
            """
        await db.execute(query, ctx.guild.id, user.id)
        await db.cache_set(f"whitelist:{ctx.guild.id}:{user.id}", 1, ttl=300)

        embed = ZenithEmbed.success("User Whitelisted", f"{user.mention} is now immune to Antinuke triggers.")
        await ctx.reply(embed=embed, mention_author=False)

    @whitelist_group.command(name="remove", aliases=["del"])
    @commands.has_permissions(administrator=True)
    async def whitelist_remove(self, ctx: commands.Context, user: discord.User):
        """Revokes antinuke immunity from an administrator."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in self.bot.owner_ids:
            return await ctx.reply(
                embed=ZenithEmbed.error("Owner Restricted", "Only the Server Owner can revoke whitelist immunity."),
                mention_author=False
            )

        await db.execute("DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", ctx.guild.id, user.id)
        await db.cache_delete(f"whitelist:{ctx.guild.id}:{user.id}")

        embed = ZenithEmbed.success("Immunity Revoked", f"{user.mention} has been removed from the whitelist.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))
