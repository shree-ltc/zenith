"""
Anti-Betray System for Zenith.
Detects compromised staff accounts or rogue administrators executing rapid destructive actions.
Bypasses whitelists and immediately neutralizes rogue actors based on sliding time window thresholds.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
import logging
from collections import defaultdict
from typing import Optional, Dict, List, Any
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin, DANGEROUS_PERMISSIONS
from core.config import config

logger = logging.getLogger("zenith.antibetray")

ACCENT_COLOR = 0x0F0F13
DEFAULT_THRESHOLD = 3
DEFAULT_WINDOW = 5  # seconds

COUNTER_ACTIONS = {
    discord.AuditLogAction.channel_create,
    discord.AuditLogAction.channel_delete,
    discord.AuditLogAction.channel_update,
    discord.AuditLogAction.overwrite_create,
    discord.AuditLogAction.overwrite_delete,
    discord.AuditLogAction.overwrite_update,
    discord.AuditLogAction.role_create,
    discord.AuditLogAction.role_delete,
    discord.AuditLogAction.role_update,
    discord.AuditLogAction.member_role_update,
    discord.AuditLogAction.ban,
    discord.AuditLogAction.kick,
    discord.AuditLogAction.webhook_create,
    discord.AuditLogAction.webhook_delete,
    discord.AuditLogAction.webhook_update,
    discord.AuditLogAction.bot_add,
    discord.AuditLogAction.emoji_create,
    discord.AuditLogAction.emoji_delete,
    discord.AuditLogAction.emoji_update,
    discord.AuditLogAction.guild_update,
    discord.AuditLogAction.integration_create,
    discord.AuditLogAction.integration_delete,
}


class AntiBetray(commands.Cog):
    """Mitigates rogue moderator abuse and hijacked staff accounts."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory config cache: {guild_id: {"enabled": bool, "threshold": int, "window_sec": int, "action": str, "channel_id": Optional[int]}}
        self._config_cache: Dict[int, Dict[str, Any]] = {}
        # Sliding action tracker: {guild_id: {user_id: [timestamp1, timestamp2, ...]}}
        self._tracker: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))

    async def cog_load(self) -> None:
        """Preload anti-betray configurations into RAM."""
        rows = await db.fetch("SELECT * FROM antibetray_config")
        for r in rows:
            self._config_cache[r["guild_id"]] = {
                "enabled": bool(r["enabled"]),
                "threshold": int(r["threshold"]),
                "window_sec": int(r["window_sec"]),
                "action": r.get("action", "ban"),
                "channel_id": r.get("channel_id")
            }

    async def _get_config(self, guild_id: int) -> Dict[str, Any]:
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]
        row = await db.fetchrow("SELECT * FROM antibetray_config WHERE guild_id = ?", guild_id)
        if row:
            cfg = {
                "enabled": bool(row["enabled"]),
                "threshold": int(row["threshold"]),
                "window_sec": int(row["window_sec"]),
                "action": row.get("action", "ban"),
                "channel_id": row.get("channel_id")
            }
            self._config_cache[guild_id] = cfg
            return cfg

        default_cfg = {
            "enabled": False,
            "threshold": DEFAULT_THRESHOLD,
            "window_sec": DEFAULT_WINDOW,
            "action": "ban",
            "channel_id": None
        }
        self._config_cache[guild_id] = default_cfg
        return default_cfg

    async def _update_config(self, guild_id: int, **kwargs) -> None:
        cfg = await self._get_config(guild_id)
        cfg.update(kwargs)
        await db.execute(
            """
            INSERT INTO antibetray_config (guild_id, enabled, threshold, window_sec, action, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                enabled = excluded.enabled,
                threshold = excluded.threshold,
                window_sec = excluded.window_sec,
                action = excluded.action,
                channel_id = excluded.channel_id
            """,
            guild_id, cfg["enabled"], cfg["threshold"], cfg["window_sec"], cfg["action"], cfg["channel_id"]
        )
        self._config_cache[guild_id] = cfg

    async def _log_incident(self, guild_id: int, user_id: int, user_name: str, action: str, details: str) -> None:
        await db.execute(
            "INSERT INTO antibetray_logs (guild_id, user_id, user_name, action, details) VALUES (?, ?, ?, ?, ?)",
            guild_id, user_id, user_name, action, details
        )

    async def _send_alert(self, guild: discord.Guild, embed: discord.Embed) -> None:
        cfg = await self._get_config(guild.id)
        target_ch = None
        if cfg["channel_id"]:
            target_ch = guild.get_channel(cfg["channel_id"])
        if not target_ch:
            # Fallback to general antinuke logs
            sec_row = await db.fetchrow("SELECT log_channel FROM antinuke_config WHERE guild_id = ?", guild.id)
            if sec_row and sec_row["log_channel"]:
                target_ch = guild.get_channel(sec_row["log_channel"])

        if target_ch and target_ch.permissions_for(guild.me).send_messages:
            try:
                await target_ch.send(embed=embed)
            except Exception:
                pass

    # ---------------------------------------------------------
    # AUDIT LOG LISTENER & BETRAYAL DETECTOR
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        """Intercept gateway audit log events and evaluate execution velocity."""
        if entry.action not in COUNTER_ACTIONS:
            return

        guild = entry.guild
        if not guild:
            return

        actor = entry.user
        if not actor or actor.bot or actor.id == self.bot.user.id:
            return

        # Server Owner and Bot Owners (Shree) are immune to anti-betray
        if actor.id == guild.owner_id or actor.id in config.OWNER_IDS:
            return

        cfg = await self._get_config(guild.id)
        if not cfg["enabled"]:
            return

        now = time.monotonic()
        uid = actor.id
        timestamps = self._tracker[guild.id][uid]
        timestamps.append(now)

        cutoff = now - cfg["window_sec"]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        # Check threshold
        if len(timestamps) > cfg["threshold"]:
            self._tracker[guild.id][uid] = []  # Reset counter
            action_type = cfg["action"]
            reason = f"[Zenith AntiBetray] Exceeded {cfg['threshold']} critical audit actions in {cfg['window_sec']}s."

            punished = False
            punish_label = "Failed"

            # Execute configured punishment
            if action_type == "ban":
                try:
                    await guild.ban(actor, reason=reason, delete_message_days=0)
                    punished = True
                    punish_label = "Banned"
                except Exception as e:
                    logger.error(f"[AntiBetray Ban Failed] {actor} ({actor.id}): {e}")
            elif action_type == "kick":
                try:
                    await guild.kick(actor, reason=reason)
                    punished = True
                    punish_label = "Kicked"
                except Exception as e:
                    logger.error(f"[AntiBetray Kick Failed] {actor} ({actor.id}): {e}")
            else:  # "stripstaff"
                member = guild.get_member(actor.id)
                if member and guild.me.guild_permissions.manage_roles:
                    dangerous_roles = [
                        r for r in member.roles
                        if r < guild.me.top_role and not r.is_default() and any(
                            getattr(r.permissions, p, False) for p in DANGEROUS_PERMISSIONS
                        )
                    ]
                    if dangerous_roles:
                        try:
                            await member.remove_roles(*dangerous_roles, reason=reason)
                            punished = True
                            punish_label = f"Stripped {len(dangerous_roles)} staff role(s)"
                        except Exception as e:
                            logger.error(f"[AntiBetray Strip Failed] {actor} ({actor.id}): {e}")

            # Record incident in database
            details = f"Action: {punish_label} | Reason: {reason}"
            await self._log_incident(guild.id, uid, str(actor), action_type.upper(), details)

            # Dispatch security alert embed
            embed = discord.Embed(
                title="[CRITICAL ALERT] Rogue Action Detected (Anti-Betray)",
                description=(
                    f"**Suspect Actor:** {actor.mention} (`{actor.id}`)\n"
                    f"**Velocity:** `{len(timestamps)}` actions in `{cfg['window_sec']}` seconds\n"
                    f"**Action Executed:** `{punish_label}`\n"
                    f"**Reason:** Rapid administrative actions exceeded betrayal threshold."
                ),
                color=0xFF0000
            )
            embed.set_footer(text="Zenith Anti-Betray Protocol | Developed by Shree")
            await self._send_alert(guild, embed)
            logger.warning(f"[AntiBetray Neutralized] Actor {actor} in guild {guild.id} - {punish_label}")

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="antibetray", aliases=["abetray"], invoke_without_command=True)
    @commands.guild_only()
    async def antibetray_group(self, ctx: commands.Context):
        """Anti-Betray protection overview and controls."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Anti-Betray management is strictly restricted to the Server Owner.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        cfg = await self._get_config(ctx.guild.id)
        status = "Active" if cfg["enabled"] else "Disabled"
        log_ch = ctx.guild.get_channel(cfg["channel_id"]) if cfg["channel_id"] else None
        log_mention = log_ch.mention if log_ch else "Default Antinuke Channel"

        embed = discord.Embed(
            title="[ANTI-BETRAY PROTOCOL]",
            description=(
                "Anti-Betray detects when a trusted administrator or whitelisted moderator suddenly "
                "goes rogue (e.g., account compromised, mass deleting channels or banning members). "
                "It immediately neutralizes them based on velocity thresholds, bypassing whitelists."
            ),
            color=ACCENT_COLOR
        )
        embed.add_field(name="Status", value=f"`[{status}]`", inline=True)
        embed.add_field(name="Threshold", value=f"`{cfg['threshold']}` actions in `{cfg['window_sec']}s`", inline=True)
        embed.add_field(name="Punishment", value=f"`{cfg['action'].upper()}`", inline=True)
        embed.add_field(name="Alert Channel", value=log_mention, inline=False)
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}antibetray enable` - Arm anti-betray protection\n"
                f"`{ctx.prefix}antibetray disable` - Disarm anti-betray protection\n"
                f"`{ctx.prefix}antibetray set <threshold> <seconds>` - Configure limits\n"
                f"`{ctx.prefix}antibetray punishment <ban/stripstaff/kick>` - Set penalty\n"
                f"`{ctx.prefix}antibetray logs <channel>` - Set alert channel\n"
                f"`{ctx.prefix}antibetray show` - Show active configuration"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="enable", aliases=["on", "arm"])
    @commands.guild_only()
    async def antibetray_enable(self, ctx: commands.Context):
        """Enable anti-betray monitoring."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await self._update_config(ctx.guild.id, enabled=True)
        embed = discord.Embed(
            title="[ANTI-BETRAY ARMED]",
            description="Anti-Betray protection is now actively monitoring administrative velocities.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="disable", aliases=["off", "disarm"])
    @commands.guild_only()
    async def antibetray_disable(self, ctx: commands.Context):
        """Disable anti-betray monitoring."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await self._update_config(ctx.guild.id, enabled=False)
        embed = discord.Embed(
            title="[ANTI-BETRAY DISARMED]",
            description="Anti-Betray protection has been disabled.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="set")
    @commands.guild_only()
    async def antibetray_set(self, ctx: commands.Context, threshold: int, window_sec: int):
        """Set the action count threshold and time window in seconds."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        if threshold < 1 or threshold > 20:
            return await ctx.send(embed=discord.Embed(title="[INVALID VALUE]", description="Threshold must be between 1 and 20.", color=ACCENT_COLOR))

        if window_sec < 1 or window_sec > 60:
            return await ctx.send(embed=discord.Embed(title="[INVALID VALUE]", description="Window must be between 1 and 60 seconds.", color=ACCENT_COLOR))

        await self._update_config(ctx.guild.id, threshold=threshold, window_sec=window_sec)
        embed = discord.Embed(
            title="[ANTI-BETRAY THRESHOLD UPDATED]",
            description=f"Trigger set to **{threshold}** critical actions within **{window_sec}** seconds.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="punishment", aliases=["action"])
    @commands.guild_only()
    async def antibetray_punishment(self, ctx: commands.Context, action: str):
        """Set the penalty when anti-betray triggers: ban, stripstaff, or kick."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        action = action.lower()
        if action not in ["ban", "stripstaff", "kick"]:
            return await ctx.send(embed=discord.Embed(
                title="[INVALID ACTION]",
                description="Valid actions: `ban`, `stripstaff`, `kick`.",
                color=ACCENT_COLOR
            ))

        await self._update_config(ctx.guild.id, action=action)
        embed = discord.Embed(
            title="[ANTI-BETRAY PUNISHMENT UPDATED]",
            description=f"Configured penalty set to **{action.upper()}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="logs", aliases=["log"])
    @commands.guild_only()
    async def antibetray_logs(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the audit alert channel for anti-betray."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        if channel is None:
            cfg = await self._get_config(ctx.guild.id)
            ch = ctx.guild.get_channel(cfg["channel_id"]) if cfg["channel_id"] else None
            mention = ch.mention if ch else "None configured"
            return await ctx.send(embed=discord.Embed(
                title="[ANTI-BETRAY LOGS]",
                description=f"Current alert channel: {mention}\nUse `{ctx.prefix}antibetray logs #channel` to update.",
                color=ACCENT_COLOR
            ))

        await self._update_config(ctx.guild.id, channel_id=channel.id)
        embed = discord.Embed(
            title="[ANTI-BETRAY LOGS UPDATED]",
            description=f"Anti-Betray alerts will now be dispatched to {channel.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @antibetray_group.command(name="show", aliases=["status"])
    @commands.guild_only()
    async def antibetray_show(self, ctx: commands.Context):
        """Display active anti-betray parameters."""
        await self.antibetray_group(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiBetray(bot))
