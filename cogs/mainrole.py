"""
Main Role Protection System for Zenith.
Prevents core member/verified roles and @everyone from receiving dangerous administrative permissions.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
import logging
from typing import Optional, List
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin, DANGEROUS_PERMISSIONS
from core.config import config

logger = logging.getLogger("zenith.mainrole")

ACCENT_COLOR = 0x0F0F13


class Mainrole(commands.Cog):
    """Protects essential member roles from privilege escalation and rogue permission grants."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cache: {guild_id: {role_id, ...}} for sub-millisecond lookup
        self._cache: dict[int, set[int]] = {}
        self._log_cache: dict[int, Optional[int]] = {}

    async def cog_load(self) -> None:
        """Preload protected roles and log channels into memory on startup."""
        rows = await db.fetch("SELECT guild_id, role_id FROM main_roles")
        for r in rows:
            gid = r["guild_id"]
            rid = r["role_id"]
            if gid not in self._cache:
                self._cache[gid] = set()
            self._cache[gid].add(rid)

        log_rows = await db.fetch("SELECT guild_id, channel_id FROM mainrole_config")
        for r in log_rows:
            self._log_cache[r["guild_id"]] = r["channel_id"]

    async def _get_roles(self, guild_id: int) -> set[int]:
        if guild_id in self._cache:
            return self._cache[guild_id]
        rows = await db.fetch("SELECT role_id FROM main_roles WHERE guild_id = ?", guild_id)
        role_ids = {r["role_id"] for r in rows}
        self._cache[guild_id] = role_ids
        return role_ids

    async def _add_role(self, guild_id: int, role_id: int) -> None:
        await db.execute(
            "INSERT INTO main_roles (guild_id, role_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            guild_id, role_id
        )
        if guild_id not in self._cache:
            self._cache[guild_id] = set()
        self._cache[guild_id].add(role_id)

    async def _remove_role(self, guild_id: int, role_id: int) -> None:
        await db.execute(
            "DELETE FROM main_roles WHERE guild_id = ? AND role_id = ?",
            guild_id, role_id
        )
        if guild_id in self._cache:
            self._cache[guild_id].discard(role_id)

    async def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        cid = self._log_cache.get(guild.id)
        if cid:
            return guild.get_channel(cid)
        row = await db.fetchrow("SELECT channel_id FROM mainrole_config WHERE guild_id = ?", guild.id)
        if row and row["channel_id"]:
            self._log_cache[guild.id] = row["channel_id"]
            return guild.get_channel(row["channel_id"])
        # Fallback to antinuke log channel if configured
        sec_row = await db.fetchrow("SELECT log_channel FROM antinuke_config WHERE guild_id = ?", guild.id)
        if sec_row and sec_row["log_channel"]:
            return guild.get_channel(sec_row["log_channel"])
        return None

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        ch = await self._get_log_channel(guild)
        if ch and ch.permissions_for(guild.me).send_messages:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass

    async def _record_incident(self, guild_id: int, action: str, details: str) -> None:
        await db.execute(
            "INSERT INTO mainrole_logs (guild_id, action, details) VALUES (?, ?, ?)",
            guild_id, action, details
        )

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="mainrole", aliases=["mrole", "protectrole"], invoke_without_command=True)
    @commands.guild_only()
    async def mainrole_group(self, ctx: commands.Context):
        """Main role protection overview and commands."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="This system is restricted to the Server Owner and authorized Administrators.",
                color=ACCENT_COLOR
            )
            embed.set_footer(text="Zenith Security | Developed by Shree")
            return await ctx.send(embed=embed)

        roles = await self._get_roles(ctx.guild.id)
        log_ch = await self._get_log_channel(ctx.guild)
        log_status = log_ch.mention if log_ch else "Not Configured"

        embed = discord.Embed(
            title="[MAINROLE PROTECTION SYSTEM]",
            description=(
                "Mainrole protection locks down your default member roles and `@everyone` "
                "from ever receiving dangerous administrative permissions. Any unauthorized "
                "permission updates are intercepted and reverted automatically."
            ),
            color=ACCENT_COLOR
        )
        embed.add_field(name="Protected Roles", value=f"`{len(roles)}` role(s) configured", inline=True)
        embed.add_field(name="Audit Log Channel", value=log_status, inline=True)
        embed.add_field(
            name="Subcommands",
            value=(
                f"`{ctx.prefix}mainrole add <roles>` - Add roles to protection list\n"
                f"`{ctx.prefix}mainrole remove <roles>` - Remove roles from protection\n"
                f"`{ctx.prefix}mainrole scan` - Audit and strip active dangerous perms\n"
                f"`{ctx.prefix}mainrole show` - Display all protected roles & health status\n"
                f"`{ctx.prefix}mainrole logs <channel>` - Set audit alert log channel\n"
                f"`{ctx.prefix}mainrole reset` - Clear all protected roles"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @mainrole_group.command(name="add")
    @commands.guild_only()
    async def mainrole_add(self, ctx: commands.Context, roles: commands.Greedy[discord.Role]):
        """Add one or more roles to the mainrole protection system."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can manage mainroles.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        if not roles:
            embed = discord.Embed(
                title="[INVALID SYNTAX]",
                description=f"Usage: `{ctx.prefix}mainrole add <@role1> [@role2 ...]`",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        current = await self._get_roles(ctx.guild.id)
        added: List[str] = []
        sanitized: List[str] = []

        for role in roles:
            if role.id in current:
                continue

            # Check if role currently has dangerous permissions
            harmful = [p for p in DANGEROUS_PERMISSIONS if getattr(role.permissions, p, False)]
            if harmful:
                if ctx.guild.me.guild_permissions.manage_roles and role < ctx.guild.me.top_role:
                    new_perms = role.permissions
                    for p in harmful:
                        setattr(new_perms, p, False)
                    try:
                        await role.edit(permissions=new_perms, reason="Mainrole add: Auto-sanitized harmful perms")
                        sanitized.append(f"{role.mention} (stripped `{len(harmful)}` dangerous perms)")
                    except Exception:
                        pass

            await self._add_role(ctx.guild.id, role.id)
            added.append(role.mention)

        if not added:
            embed = discord.Embed(
                title="[NO CHANGES]",
                description="All specified roles are already in the mainrole protection registry.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        desc = f"Successfully added **{len(added)}** role(s) to Mainrole Protection:\n" + ", ".join(added)
        if sanitized:
            desc += "\n\n**Sanitized Active Permissions:**\n" + "\n".join(sanitized)

        embed = discord.Embed(
            title="[MAINROLE PROTECTION UPDATED]",
            description=desc,
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)
        await self._record_incident(ctx.guild.id, "ROLE_ADD", f"Added {len(added)} roles by {ctx.author} ({ctx.author.id})")

    @mainrole_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    async def mainrole_remove(self, ctx: commands.Context, roles: commands.Greedy[discord.Role]):
        """Remove one or more roles from mainrole protection."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can manage mainroles.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        if not roles:
            embed = discord.Embed(
                title="[INVALID SYNTAX]",
                description=f"Usage: `{ctx.prefix}mainrole remove <@role1> [@role2 ...]`",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        removed: List[str] = []
        for role in roles:
            await self._remove_role(ctx.guild.id, role.id)
            removed.append(role.mention)

        embed = discord.Embed(
            title="[MAINROLE PROTECTION UPDATED]",
            description=f"Removed **{len(removed)}** role(s) from Mainrole Protection:\n" + ", ".join(removed),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)
        await self._record_incident(ctx.guild.id, "ROLE_REMOVE", f"Removed {len(removed)} roles by {ctx.author}")

    @mainrole_group.command(name="scan", aliases=["audit", "sanitize"])
    @commands.guild_only()
    async def mainrole_scan(self, ctx: commands.Context):
        """Immediately audit all protected roles and strip any active harmful permissions."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can execute a scan.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        role_ids = await self._get_roles(ctx.guild.id)
        if not role_ids:
            embed = discord.Embed(
                title="[NO PROTECTED ROLES]",
                description=f"No roles configured. Use `{ctx.prefix}mainrole add <roles>` first.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        fixed: List[str] = []
        clean: List[str] = []

        for rid in role_ids:
            role = ctx.guild.get_role(rid)
            if not role:
                continue

            harmful = [p for p in DANGEROUS_PERMISSIONS if getattr(role.permissions, p, False)]
            if harmful:
                if ctx.guild.me.guild_permissions.manage_roles and role < ctx.guild.me.top_role:
                    new_perms = role.permissions
                    for p in harmful:
                        setattr(new_perms, p, False)
                    try:
                        await role.edit(permissions=new_perms, reason="Mainrole scan: Stripped dangerous permissions")
                        fixed.append(f"{role.mention} - Stripped: `{', '.join(harmful)}`")
                    except Exception as e:
                        fixed.append(f"{role.mention} - Error sanitizing ({e})")
                else:
                    fixed.append(f"{role.mention} - Detected `{len(harmful)}` harmful perms but role is higher than bot!")
            else:
                clean.append(role.name)

        embed = discord.Embed(
            title="[MAINROLE SECURITY AUDIT COMPLETE]",
            color=ACCENT_COLOR
        )
        if fixed:
            embed.add_field(name="Sanitized Roles", value="\n".join(fixed), inline=False)
        embed.add_field(name="Safe Roles", value=f"`{len(clean)}` role(s) verified safe and clean.", inline=False)
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @mainrole_group.command(name="show", aliases=["list"])
    @commands.guild_only()
    async def mainrole_show(self, ctx: commands.Context):
        """Display all protected roles, member counts, and permission health."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can view mainroles.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        role_ids = await self._get_roles(ctx.guild.id)
        if not role_ids:
            embed = discord.Embed(
                title="[NO MAINROLES CONFIGURED]",
                description=f"No roles are currently protected. Add one using `{ctx.prefix}mainrole add <roles>`.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        lines = []
        for i, rid in enumerate(sorted(role_ids), 1):
            role = ctx.guild.get_role(rid)
            if role:
                harmful = [p for p in DANGEROUS_PERMISSIONS if getattr(role.permissions, p, False)]
                status = f"[DANGER: {len(harmful)} harmful perms]" if harmful else "[CLEAN & PROTECTED]"
                lines.append(f"`{i:02d}.` {role.mention} ({len(role.members)} members) - `{status}`")
            else:
                lines.append(f"`{i:02d}.` `<@&{rid}>` [Role Deleted from Guild]")

        embed = discord.Embed(
            title="[PROTECTED MAINROLES REGISTRY]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @mainrole_group.command(name="logs", aliases=["log"])
    @commands.guild_only()
    async def mainrole_logs(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the audit log channel for mainrole incidents."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can configure logs.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        if channel is None:
            log_ch = await self._get_log_channel(ctx.guild)
            status = log_ch.mention if log_ch else "None"
            embed = discord.Embed(
                title="[MAINROLE LOG CONFIGURATION]",
                description=f"Current Mainrole Log Channel: {status}\nUse `{ctx.prefix}mainrole logs #channel` to update.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        await db.execute(
            "INSERT INTO mainrole_config (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id",
            ctx.guild.id, channel.id
        )
        self._log_cache[ctx.guild.id] = channel.id

        embed = discord.Embed(
            title="[MAINROLE LOG CONFIGURED]",
            description=f"Mainrole security alerts will now be dispatched to {channel.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @mainrole_group.command(name="reset")
    @commands.guild_only()
    async def mainrole_reset(self, ctx: commands.Context):
        """Reset and remove all mainrole configurations for this server."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Only the Server Owner or authorized Extra Owners can reset mainroles.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        await db.execute("DELETE FROM main_roles WHERE guild_id = ?", ctx.guild.id)
        self._cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[MAINROLE CONFIGURATION CLEARED]",
            description="All protected roles have been removed from the protection registry.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)
        await self._record_incident(ctx.guild.id, "RESET", f"Reset all protected roles by {ctx.author}")

    # ---------------------------------------------------------
    # LISTENERS
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Instantly strip dangerous permissions if assigned to any protected mainrole."""
        guild = after.guild
        role_ids = self._cache.get(guild.id)
        if role_ids is None:
            role_ids = await self._get_roles(guild.id)

        if after.id not in role_ids:
            return

        harmful_found = [
            perm for perm in DANGEROUS_PERMISSIONS
            if getattr(after.permissions, perm, False)
        ]

        if not harmful_found:
            return

        # Instantly revoke harmful permissions
        new_perms = after.permissions
        for perm in harmful_found:
            setattr(new_perms, perm, False)

        try:
            await after.edit(
                permissions=new_perms,
                reason=f"Mainrole Security: Revoked dangerous permissions ({', '.join(harmful_found)})"
            )

            # Audit log executor lookup
            executor_str = "Unknown Executor"
            if guild.me.guild_permissions.view_audit_log:
                try:
                    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_update, limit=3):
                        if entry.target.id == after.id:
                            executor_str = f"{entry.user} (`{entry.user.id}`)"
                            break
                except Exception:
                    pass

            embed = discord.Embed(
                title="[SECURITY ALERT] Mainrole Permissions Intercepted",
                description=(
                    f"**Protected Role:** {after.mention} (`{after.id}`)\n"
                    f"**Attempted Permissions:** `{', '.join(harmful_found)}`\n"
                    f"**Action Taken:** Instantly stripped dangerous permissions back to safe state.\n"
                    f"**Executor:** {executor_str}"
                ),
                color=0xFF0000
            )
            embed.set_footer(text="Zenith Security Shield | Developed by Shree")
            await self._send_log(guild, embed)
            await self._record_incident(
                guild.id,
                "REVOKE",
                f"Revoked {', '.join(harmful_found)} from {after.name} ({after.id}) by {executor_str}"
            )
            logger.warning(f"[Mainrole Shield] Revoked dangerous perms on {after.name} in guild {guild.id}")
        except Exception as e:
            logger.error(f"[Mainrole Shield Error] Could not revoke perms for {after.name}: {e}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Clean up deleted roles from cache and registry."""
        guild = role.guild
        role_ids = self._cache.get(guild.id)
        if role_ids is None:
            role_ids = await self._get_roles(guild.id)

        if role.id in role_ids:
            await self._remove_role(guild.id, role.id)
            await self._record_incident(guild.id, "ROLE_DELETED", f"Protected role {role.name} ({role.id}) was deleted.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Mainrole(bot))
