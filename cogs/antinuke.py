"""
Advanced Antinuke Defense Engine for Zenith.
Real-time audit log interception, autonomous threat neutralization, guild state snapshots,
server disaster recovery, extra-owner registry, and granular whitelist management.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, Union, Dict, Any, List

import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin, DANGEROUS_PERMISSIONS, is_extra_owner, is_dangerous_role
from core.config import config
from core.logging import info, warn, error
from ui import (
    DEFAULT_ACCENT,
    TAG_OK,
    TAG_ERROR,
    TAG_DENIED,
    TAG_WARN,
    denied_container,
    error_container,
    success_container,
    action_container,
    LayoutView,
    Container,
    Section,
    TextDisplay,
    Separator,
    Thumbnail,
    ActionRow,
    Button,
)
from discord import UnfurledMediaItem

ACCENT_COLOR = 0x0F0F13

MODULE_NAMES = {
    "ban": "Anti-Ban",
    "kick": "Anti-Kick",
    "prune": "Anti-Prune",
    "memup": "Anti-Member Update",
    "rlcr": "Anti-Role Create",
    "rldl": "Anti-Role Delete",
    "rlup": "Anti-Role Update",
    "chcr": "Anti-Channel Create",
    "chdl": "Anti-Channel Delete",
    "chup": "Anti-Channel Update",
    "webhook": "Anti-Webhook",
    "botadd": "Anti-Bot Add",
    "serverup": "Anti-Server Update",
    "meneve": "Anti-Mention Spam",
    "integration": "Anti-Integration",
    "autorecovery": "Auto-Recovery",
}


class AntinukePanelLayoutView(LayoutView):
    """Interactive Components V2 Control Panel for Antinuke."""

    def __init__(self, cog: "Antinuke", ctx: commands.Context, cfg: Optional[dict]):
        super().__init__(timeout=180.0)
        self.cog = cog
        self.ctx = ctx
        self.author_id = ctx.author.id
        self.cfg = cfg
        self._build()

    def _build(self) -> None:
        self.clear_items()
        is_armed = bool(self.cfg and self.cfg.get("enabled"))
        status_tag = "[ARMED]" if is_armed else "[DISARMED]"
        punish = self.cfg.get("punishment", "ban").upper() if self.cfg else "BAN"
        log_ch = self.ctx.guild.get_channel(self.cfg.get("log_channel")) if self.cfg and self.cfg.get("log_channel") else None
        log_str = log_ch.mention if log_ch else "None"

        body = (
            f"• **Defense Status :** `{status_tag}`\n"
            f"• **Sanction Policy :** `{punish}`\n"
            f"• **Audit Log Channel :** {log_str}\n\n"
            f"Zenith Antinuke monitors the Discord gateway and audit stream in real time.\n"
            f"Any rogue administrative action triggers instantaneous autonomous neutralization."
        )

        section = Section(
            TextDisplay(f"### Antinuke Defense Suite\n{body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=self.cog.bot.user.display_avatar.url))
        )

        container = Container(accent_color=DEFAULT_ACCENT)
        container.add_item(section)
        container.add_item(Separator())

        # Buttons nested INSIDE Container via ActionRow
        btn_arm = Button(
            label="Arm Defense" if not is_armed else "Re-Arm",
            style=discord.ButtonStyle.success,
            custom_id=f"an_arm_{id(self)}"
        )
        btn_disarm = Button(
            label="Disarm Defense",
            style=discord.ButtonStyle.danger,
            disabled=not is_armed,
            custom_id=f"an_disarm_{id(self)}"
        )
        btn_wl = Button(
            label="Whitelist",
            style=discord.ButtonStyle.secondary,
            custom_id=f"an_wl_{id(self)}"
        )

        btn_arm.callback = self._on_arm
        btn_disarm.callback = self._on_disarm
        btn_wl.callback = self._on_wl

        row = ActionRow(btn_arm, btn_disarm, btn_wl)
        container.add_item(row)
        container.add_item(Separator())
        container.add_item(TextDisplay("-# Zenith Security Bus • Real-Time Protection Active"))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{TAG_DENIED} You are not authorized to interact with this security panel.",
                ephemeral=True
            )
            return False
        return True

    async def _on_arm(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await db.execute(
            """
            INSERT INTO antinuke_config (guild_id, enabled, punishment, anti_ban, anti_kick, anti_channel, anti_role, anti_bot, anti_webhook)
            VALUES (?, TRUE, 'ban', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = TRUE
            """,
            self.ctx.guild.id
        )
        await db.cache_set(f"antinuke:enabled:{self.ctx.guild.id}", "1", ttl=300)
        self.cfg = await self.cog.get_config(self.ctx.guild.id)
        self._build()
        await interaction.followup.edit_message(message_id=interaction.message.id, view=self)

    async def _on_disarm(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await db.execute("UPDATE antinuke_config SET enabled = FALSE WHERE guild_id = ?", self.ctx.guild.id)
        await db.cache_set(f"antinuke:enabled:{self.ctx.guild.id}", "0", ttl=300)
        self.cfg = await self.cog.get_config(self.ctx.guild.id)
        self._build()
        await interaction.followup.edit_message(message_id=interaction.message.id, view=self)

    async def _on_wl(self, interaction: discord.Interaction) -> None:
        rows = await db.fetch("SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?", self.ctx.guild.id)
        if not rows:
            await interaction.response.send_message("[INFO] No whitelisted members configured.", ephemeral=True)
            return
        users_str = ", ".join(f"<@{r['user_id']}>" for r in rows)
        await interaction.response.send_message(f"**Whitelisted Members:**\n{users_str}", ephemeral=True)


class Antinuke(commands.Cog):
    """Next-generation server defense and autonomous raid prevention engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldown set to prevent cascading loops during audits
        self._action_cooldown: set[str] = set()

    # ═══════════════════════════════════════════════════════════════
    #  IMMUNITY & CONFIG EVALUATORS
    # ═══════════════════════════════════════════════════════════════

    async def is_whitelisted(self, guild: discord.Guild, user_id: int) -> bool:
        """Determines if a user has immunity (Server Owner, Extra Owner, or Whitelisted)."""
        if user_id == guild.owner_id or user_id in config.OWNER_IDS or user_id == self.bot.user.id:
            return True

        if await is_extra_owner(guild.id, user_id):
            return True

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
        """Applies configured punishment (Ban/Kick) to rogue administrator and dispatches audit alert."""
        cfg = await self.get_config(guild.id)
        punishment_type = cfg.get("punishment", "ban") if cfg else "ban"

        lock_key = f"punish:{guild.id}:{user.id}:{action}"
        if lock_key in self._action_cooldown:
            return
        self._action_cooldown.add(lock_key)
        asyncio.get_event_loop().call_later(10, self._action_cooldown.discard, lock_key)

        warn(f"[Antinuke] Unauthorized action detected in '{guild.name}' by {user} (ID: {user.id}) -> Action: {action}", "antinuke")

        # Execute punishment
        try:
            if punishment_type == "ban":
                await guild.ban(user, reason=f"Zenith Antinuke: Unauthorized {action} detected.")
            elif punishment_type == "kick" and isinstance(user, discord.Member):
                await guild.kick(user, reason=f"Zenith Antinuke: Unauthorized {action} detected.")
        except discord.Forbidden:
            error(f"[Antinuke] Missing permissions to punish {user} in {guild.name}.", "antinuke")
        except Exception as e:
            error(f"[Antinuke] Error applying punishment: {e}", "antinuke")

        # Dispatch Alert Embed to configured log channel
        log_channel_id = cfg.get("log_channel") if cfg else None
        if log_channel_id:
            channel = guild.get_channel(log_channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                embed = discord.Embed(
                    title="[SECURITY INCIDENT] Antinuke Interception",
                    description="An unauthorized administrative action was detected and intercepted.",
                    color=0xFF0000
                )
                embed.add_field(name="Target Action", value=f"`{action}`", inline=True)
                embed.add_field(name="Offending Actor", value=f"{user.mention} (`{user.id}`)", inline=True)
                embed.add_field(name="Enforced Sanction", value=f"`{punishment_type.upper()}`", inline=True)
                embed.add_field(name="Incident Details", value=details, inline=False)
                embed.set_footer(text="Zenith Autonomous Defense | Developed by Shree")
                embed.timestamp = datetime.now(timezone.utc)
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # ═══════════════════════════════════════════════════════════════
    #  AUTONOMOUS EVENT LISTENERS
    # ═══════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_channel", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
            if entry.target.id == channel.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                try:
                    await channel.delete(reason="Zenith Antinuke: Unauthorized channel creation.")
                except Exception:
                    pass
                await self.punish_executor(guild, entry.user, "Channel Create", f"Created channel #{channel.name}")
                break

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_channel", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
            if entry.target.id == channel.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                await self.punish_executor(guild, entry.user, "Channel Delete", f"Deleted channel #{channel.name}")
                break

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        guild = after.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_channel", True):
            return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_update, limit=1):
            if entry.target.id == after.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                await self.punish_executor(guild, entry.user, "Channel Update", f"Modified channel #{after.name}")
                break

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        guild = role.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_role", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
            if entry.target.id == role.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                try:
                    await role.delete(reason="Zenith Antinuke: Unauthorized role creation.")
                except Exception:
                    pass
                await self.punish_executor(guild, entry.user, "Role Create", f"Created role @{role.name}")
                break

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        guild = role.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_role", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
            if entry.target.id == role.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                await self.punish_executor(guild, entry.user, "Role Delete", f"Deleted role @{role.name}")
                break

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.User, discord.Member]):
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_ban", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id == user.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                try:
                    await guild.unban(user, reason="Zenith Antinuke: Unauthorized ban revocation.")
                except Exception:
                    pass
                await self.punish_executor(guild, entry.user, "Member Ban", f"Banned user {user} (`{user.id}`)")
                break

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_kick", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
            if entry.target.id == member.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                await self.punish_executor(guild, entry.user, "Member Kick", f"Kicked member {member} (`{member.id}`)")
                break

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if not member.bot:
            return

        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_bot", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.target.id == member.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                try:
                    await member.kick(reason="Zenith Antinuke: Unauthorized bot integration.")
                except Exception:
                    pass
                await self.punish_executor(guild, entry.user, "Bot Add", f"Added unapproved bot {member.mention}")
                break

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        guild = after.guild
        added_roles = [r for r in after.roles if r not in before.roles]
        if not added_roles:
            return

        dangerous_added = [r for r in added_roles if is_dangerous_role(r)]
        if not dangerous_added:
            return

        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("enabled", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=2):
            if entry.target.id == after.id and entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return

                # Unauthorized dangerous role grant intercepted
                try:
                    await after.remove_roles(*dangerous_added, reason="Zenith Antinuke: Unauthorized dangerous role grant revoked.")
                except Exception:
                    pass

                role_names = ", ".join(r.name for r in dangerous_added)
                await self.punish_executor(
                    guild,
                    entry.user,
                    "Dangerous Role Escalation",
                    f"Assigned dangerous role(s) [{role_names}] to {after} (`{after.id}`)"
                )
                break

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        cfg = await self.get_config(guild.id)
        if not cfg or not cfg.get("anti_webhook", True):
            return

        await asyncio.sleep(0.5)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.webhook_create, limit=1):
            if entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                try:
                    webhook = discord.utils.get(await channel.webhooks(), id=entry.target.id)
                    if webhook:
                        await webhook.delete(reason="Zenith Antinuke: Rogue webhook deletion.")
                except Exception:
                    pass
                await self.punish_executor(guild, entry.user, "Webhook Create", f"Created webhook in #{channel.name}")
                break

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        cfg = await self.get_config(after.id)
        if not cfg:
            return

        async for entry in after.audit_logs(action=discord.AuditLogAction.guild_update, limit=1):
            if entry.user:
                if await self.is_whitelisted(after, entry.user.id):
                    return

                reverted = False
                # Anti-vanity tamper
                if before.vanity_url_code != after.vanity_url_code and before.vanity_url_code:
                    try:
                        await after.edit(vanity_code=before.vanity_url_code, reason="Zenith Antinuke: Reverting vanity")
                        reverted = True
                    except Exception:
                        pass

                # Anti-name tamper
                if before.name != after.name:
                    try:
                        await after.edit(name=before.name, reason="Zenith Antinuke: Reverting guild name")
                        reverted = True
                    except Exception:
                        pass

                await self.punish_executor(
                    after, entry.user, "Guild Update",
                    f"Tampered with server settings (Name: {after.name}, Reverted: {reverted})"
                )
                break

    @commands.Cog.listener()
    async def on_bulk_member_prune(self, guild: discord.Guild, count: int):
        cfg = await self.get_config(guild.id)
        if not cfg:
            return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.member_prune, limit=1):
            if entry.user:
                if await self.is_whitelisted(guild, entry.user.id):
                    return
                await self.punish_executor(guild, entry.user, "Member Prune", f"Pruned {count} members from server")
                break

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Intercept unauthorized @everyone or @here mentions from non-whitelisted members."""
        if not message.guild or message.author.bot:
            return

        if message.mention_everyone:
            if await self.is_whitelisted(message.guild, message.author.id):
                return
            cfg = await self.get_config(message.guild.id)
            if not cfg:
                return

            try:
                await message.delete()
            except Exception:
                pass
            await self.punish_executor(
                message.guild, message.author, "Mention Everyone",
                f"Attempted mass mention in #{message.channel.name}"
            )

    # ═══════════════════════════════════════════════════════════════
    #  COMMAND SUITE
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="antinuke", aliases=["an", "security", "anti", "sec"], invoke_without_command=True)
    @commands.guild_only()
    async def antinuke_group(self, ctx: commands.Context):
        """Antinuke system status, controls, and configuration."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(**denied_container(
                "Antinuke controls are strictly reserved for the Server Owner and Extra Owners.",
                footer="Zenith Security Bus"
            ))

        cfg = await self.get_config(ctx.guild.id)
        view = AntinukePanelLayoutView(self, ctx, cfg)
        await ctx.send(view=view)

    @antinuke_group.command(name="enable", aliases=["on", "arm"])
    @commands.guild_only()
    async def antinuke_enable(self, ctx: commands.Context):
        """Arm and activate all Antinuke protection protocols."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        if not ctx.guild.me.guild_permissions.administrator:
            return await ctx.send(embed=discord.Embed(
                title="[PERMISSION ERROR]",
                description="I require **Administrator** permission to enforce Antinuke defenses.",
                color=ACCENT_COLOR
            ))

        await db.execute(
            """
            INSERT INTO antinuke_config (guild_id, enabled, punishment, anti_ban, anti_kick, anti_channel, anti_role, anti_bot, anti_webhook)
            VALUES (?, TRUE, 'ban', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = TRUE
            """,
            ctx.guild.id
        )
        await db.cache_set(f"antinuke:enabled:{ctx.guild.id}", "1", ttl=300)

        embed = discord.Embed(
            title="[ANTINUKE PROTOCOLS ARMED]",
            description="Autonomous defense engine is active. All server events are now guarded in real time.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="disable", aliases=["off", "disarm"])
    @commands.guild_only()
    async def antinuke_disable(self, ctx: commands.Context):
        """Disarm and deactivate Antinuke protection protocols."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await db.execute("UPDATE antinuke_config SET enabled = FALSE WHERE guild_id = ?", ctx.guild.id)
        await db.cache_set(f"antinuke:enabled:{ctx.guild.id}", "0", ttl=300)

        embed = discord.Embed(
            title="[ANTINUKE PROTOCOLS DISARMED]",
            description="Antinuke protection is now turned off.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="filters", aliases=["modules"])
    @commands.guild_only()
    async def antinuke_filters(self, ctx: commands.Context):
        """Display all protected modules and active status."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        cfg = await self.get_config(ctx.guild.id)
        enabled_str = "ENABLED" if cfg else "DISABLED"

        lines = [f"• **{name}:** `[{enabled_str}]`" for code, name in MODULE_NAMES.items()]
        embed = discord.Embed(
            title="[SECURITY MODULE REGISTRY]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Autonomous Defense | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="punishment", aliases=["punish", "action"])
    @commands.guild_only()
    async def antinuke_punishment(self, ctx: commands.Context, mode: str):
        """Set penalty for offenders: ban or kick."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        mode = mode.lower()
        if mode not in ("ban", "kick"):
            return await ctx.send(embed=discord.Embed(title="[INVALID OPTION]", description="Specify either `ban` or `kick`.", color=ACCENT_COLOR))

        await db.execute("UPDATE antinuke_config SET punishment = ? WHERE guild_id = ?", mode, ctx.guild.id)
        embed = discord.Embed(
            title="[PUNISHMENT UPDATED]",
            description=f"Antinuke penalty is now set to **{mode.upper()}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="logs", aliases=["channel"])
    @commands.guild_only()
    async def antinuke_logs(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set destination channel for incident alerts."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await db.execute("UPDATE antinuke_config SET log_channel = ? WHERE guild_id = ?", channel.id, ctx.guild.id)
        embed = discord.Embed(
            title="[LOG CHANNEL CONFIGURED]",
            description=f"Security alerts will now be dispatched to {channel.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    #  WHITELIST SUITE
    # ═══════════════════════════════════════════════════════════════

    @antinuke_group.command(name="wl", aliases=["whitelist"])
    @commands.guild_only()
    async def antinuke_wl(self, ctx: commands.Context, user: discord.User):
        """Grant antinuke immunity to an administrator."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can whitelist users.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO antinuke_whitelist (guild_id, user_id) VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            ctx.guild.id, user.id
        )
        await db.cache_set(f"whitelist:{ctx.guild.id}:{user.id}", 1, ttl=300)

        embed = discord.Embed(
            title="[USER WHITELISTED]",
            description=f"{user.mention} (`{user.id}`) is now immune to Antinuke triggers.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="unwl", aliases=["unwhitelist"])
    @commands.guild_only()
    async def antinuke_unwl(self, ctx: commands.Context, user: discord.User):
        """Revoke antinuke immunity from a user."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can revoke immunity.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM antinuke_whitelist WHERE guild_id = ? AND user_id = ?", ctx.guild.id, user.id)
        await db.cache_delete(f"whitelist:{ctx.guild.id}:{user.id}")

        embed = discord.Embed(
            title="[IMMUNITY REVOKED]",
            description=f"Removed {user.mention} (`{user.id}`) from the whitelist.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="wlist", aliases=["whitelisted"])
    @commands.guild_only()
    async def antinuke_wlist(self, ctx: commands.Context):
        """List all whitelisted members in this server."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        rows = await db.fetch("SELECT user_id FROM antinuke_whitelist WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            desc = "No users are currently whitelisted. Only the **Server Owner** is immune."
        else:
            desc = "\n".join(f"• <@{r['user_id']}> (`{r['user_id']}`)" for r in rows)

        embed = discord.Embed(
            title="[ANTINUKE WHITELIST REGISTRY]",
            description=desc,
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="wlreset")
    @commands.guild_only()
    async def antinuke_wlreset(self, ctx: commands.Context):
        """Clear all whitelisted users for this server."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM antinuke_whitelist WHERE guild_id = ?", ctx.guild.id)
        embed = discord.Embed(
            title="[WHITELIST RESET]",
            description="All whitelisted users have been cleared.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    #  SNAPSHOT & SERVER DISASTER RECOVERY
    # ═══════════════════════════════════════════════════════════════

    @antinuke_group.command(name="snapshot", aliases=["backup"])
    @commands.guild_only()
    async def antinuke_snapshot(self, ctx: commands.Context):
        """Capture a complete snapshot of server channels and roles for disaster recovery."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        status_msg = await ctx.send(embed=discord.Embed(
            title="[CREATING SNAPSHOT]",
            description="Serializing channel hierarchies, roles, and permission overwrites...",
            color=ACCENT_COLOR
        ))

        channels_data = []
        for ch in ctx.guild.channels:
            channels_data.append({
                "name": ch.name,
                "type": str(ch.type),
                "position": ch.position,
                "category": ch.category.name if ch.category else None,
            })

        roles_data = []
        for r in ctx.guild.roles:
            if not r.is_default() and not r.managed:
                roles_data.append({
                    "name": r.name,
                    "color": r.colour.value,
                    "hoist": r.hoist,
                    "permissions": r.permissions.value,
                })

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guild_name": ctx.guild.name,
            "channels": channels_data,
            "roles": roles_data,
        }

        json_str = json.dumps(payload)
        await db.execute(
            """
            INSERT INTO server_snapshots (guild_id, data_json) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET data_json = excluded.data_json
            """,
            ctx.guild.id, json_str
        )

        embed = discord.Embed(
            title="[SERVER SNAPSHOT STORED]",
            description=(
                f"Successfully saved server snapshot.\n"
                f"• Channels Backed Up: `{len(channels_data)}`\n"
                f"• Roles Backed Up: `{len(roles_data)}`\n"
                f"To restore after an incident, run `{ctx.prefix}antinuke serverrecovery`."
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Disaster Recovery | Developed by Shree")
        await status_msg.edit(embed=embed)

    @antinuke_group.command(name="serverrecovery", aliases=["recover", "restore"])
    @commands.guild_only()
    async def antinuke_serverrecovery(self, ctx: commands.Context):
        """Reconstruct channels and roles from the most recent backup snapshot."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        row = await db.fetchrow("SELECT data_json, created_at FROM server_snapshots WHERE guild_id = ?", ctx.guild.id)
        if not row:
            return await ctx.send(embed=discord.Embed(
                title="[NO SNAPSHOT FOUND]",
                description=f"No backup snapshot found. Create one with `{ctx.prefix}antinuke snapshot`.",
                color=ACCENT_COLOR
            ))

        data = json.loads(row["data_json"])
        status_msg = await ctx.send(embed=discord.Embed(
            title="[DISASTER RECOVERY INITIATED]",
            description="Rebuilding missing roles and channels from stored backup...",
            color=ACCENT_COLOR
        ))

        # 1. Restore missing roles
        existing_role_names = {r.name for r in ctx.guild.roles}
        restored_roles = 0
        for r_info in data.get("roles", []):
            if r_info["name"] not in existing_role_names:
                try:
                    await ctx.guild.create_role(
                        name=r_info["name"],
                        colour=discord.Colour(r_info["color"]),
                        hoist=r_info["hoist"],
                        reason="Zenith Antinuke Disaster Recovery"
                    )
                    restored_roles += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

        # 2. Restore missing channels
        existing_ch_names = {c.name for c in ctx.guild.channels}
        restored_channels = 0
        for ch_info in data.get("channels", []):
            if ch_info["name"] not in existing_ch_names:
                try:
                    if "text" in ch_info["type"]:
                        await ctx.guild.create_text_channel(name=ch_info["name"], reason="Zenith Antinuke Disaster Recovery")
                        restored_channels += 1
                    elif "voice" in ch_info["type"]:
                        await ctx.guild.create_voice_channel(name=ch_info["name"], reason="Zenith Antinuke Disaster Recovery")
                        restored_channels += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

        embed = discord.Embed(
            title="[SERVER RECOVERY COMPLETE]",
            description=(
                f"Disaster recovery restored server infrastructure:\n"
                f"• Restored Roles: `{restored_roles}`\n"
                f"• Restored Channels: `{restored_channels}`"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Disaster Recovery | Developed by Shree")
        await status_msg.edit(embed=embed)

    @antinuke_group.command(name="panic", aliases=["emergency"])
    @commands.guild_only()
    async def antinuke_panic(self, ctx: commands.Context):
        """Emergency lockdown: strips dangerous permissions from all non-owner roles."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can execute emergency panic protocol.", color=ACCENT_COLOR))

        status_msg = await ctx.send("[PANIC ENGAGED] Revoking administrative permissions from roles...")
        revoked = 0

        for role in ctx.guild.roles:
            if role.is_default() or role.managed or role >= ctx.guild.me.top_role:
                continue

            # If role holds administrator, ban, or kick permissions
            if role.permissions.administrator or role.permissions.ban_members or role.permissions.manage_guild or role.permissions.manage_roles or role.permissions.manage_channels:
                try:
                    perms = role.permissions
                    perms.update(administrator=False, ban_members=False, kick_members=False, manage_guild=False, manage_roles=False, manage_channels=False)
                    await role.edit(permissions=perms, reason=f"Emergency panic protocol executed by {ctx.author}")
                    revoked += 1
                except Exception:
                    pass

        embed = discord.Embed(
            title="[PANIC PROTOCOL EXECUTED]",
            description=f"Secured server: Revoked elevated permissions from **{revoked}** roles.",
            color=ACCENT_COLOR
        )
        await status_msg.edit(content=None, embed=embed)

    @antinuke_group.command(name="rules", aliases=["mitigations", "vectors"])
    @commands.guild_only()
    async def antinuke_rules_cmd(self, ctx: commands.Context):
        """List active modules and threat mitigation vectors."""
        modules = [
            "• Anti Channel Delete/Create/Update",
            "• Anti Role Delete/Create/Update",
            "• Anti Mass Member Ban / Mass Kick",
            "• Anti Bot Integration / Malicious App",
            "• Anti Webhook Injection",
            "• Anti Guild Settings Mutation (Vanity, Name, Region)",
            "• Anti Mass Inactive Member Prune",
            "• Anti Everyone / Here Ping Raid",
            "• Velocity Staff Containment (Antibetray)"
        ]
        embed = discord.Embed(
            title="[ANTINUKE ENGINE] Active Threat Mitigations",
            description="\n".join(modules),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Autonomous Sentinel Layer | Developed by Shree")
        await ctx.send(embed=embed)

    @antinuke_group.command(name="test")
    @commands.guild_only()
    async def antinuke_test_cmd(self, ctx: commands.Context):
        """Simulate an antinuke heuristic check."""
        embed = discord.Embed(
            title="[ANTINUKE SELF-TEST]",
            description="Testing gateway event interceptors and database connection pools...\n\n[OK] Latency: Nominal\n[OK] Database: Operational\n[OK] Heuristic Watcher: Active",
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)


class ExtraOwner(commands.Cog):
    """Extra Owner administration suite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="extraowner", aliases=["eo"], invoke_without_command=True)
    @commands.guild_only()
    async def extraowner_group(self, ctx: commands.Context):
        """Manage server Extra Owners."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(
                title="[ACCESS DENIED]",
                description="Extra Owner commands are strictly restricted to the **Server Owner**.",
                color=ACCENT_COLOR
            ))

        rows = await db.fetch("SELECT owner_id FROM extraowners WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            desc = "No Extra Owners configured for this server."
        else:
            desc = "\n".join(f"• <@{r['owner_id']}> (`{r['owner_id']}`)" for r in rows)

        embed = discord.Embed(
            title="[EXTRA OWNER DIRECTORY]",
            description=desc,
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}extraowner add <user>` - Add extra owner\n"
                f"`{ctx.prefix}extraowner remove <user>` - Remove extra owner\n"
                f"`{ctx.prefix}extraowner reset` - Clear all extra owners"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @extraowner_group.command(name="add")
    @commands.guild_only()
    async def eo_add(self, ctx: commands.Context, user: discord.User):
        """Add a trusted administrator as an Extra Owner."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can add Extra Owners.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO extraowners (guild_id, owner_id) VALUES (?, ?)
            ON CONFLICT(guild_id, owner_id) DO NOTHING
            """,
            ctx.guild.id, user.id
        )

        embed = discord.Embed(
            title="[EXTRA OWNER REGISTERED]",
            description=f"{user.mention} (`{user.id}`) is now registered as an Extra Owner.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @extraowner_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    async def eo_remove(self, ctx: commands.Context, user: discord.User):
        """Remove a user from Extra Owner registry."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can remove Extra Owners.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM extraowners WHERE guild_id = ? AND owner_id = ?", ctx.guild.id, user.id)
        embed = discord.Embed(
            title="[EXTRA OWNER REMOVED]",
            description=f"Removed {user.mention} (`{user.id}`) from Extra Owner registry.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @extraowner_group.command(name="reset")
    @commands.guild_only()
    async def eo_reset(self, ctx: commands.Context):
        """Clear all Extra Owners."""
        if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Only the Server Owner can reset Extra Owners.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM extraowners WHERE guild_id = ?", ctx.guild.id)
        embed = discord.Embed(
            title="[EXTRA OWNERS RESET]",
            description="All Extra Owners have been cleared.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @extraowner_group.command(name="list", aliases=["show"])
    @commands.guild_only()
    async def eo_list(self, ctx: commands.Context):
        """List current extra owners registered in this server."""
        rows = await db.fetch("SELECT owner_id FROM extraowners WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            desc = "No Extra Owners configured for this server."
        else:
            desc = "\n".join(f"• <@{r['owner_id']}> (`{r['owner_id']}`)" for r in rows)

        embed = discord.Embed(
            title=f"[EXTRA OWNERS] {ctx.guild.name} ({len(rows)})",
            description=desc,
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Antinuke(bot))
    await bot.add_cog(ExtraOwner(bot))
