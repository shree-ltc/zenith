"""
cogs/owner.py - Comprehensive Developer Operations Suite for Zenith.
Engineered by Shree (Discord ID: 1465912900710305822)
GitHub: https://github.com/shree-ltc/zenith

Features:
- Process management (restart, shutdown)
- Maintenance mode toggle (system-wide non-owner command gating)
- Server operations (paginated serverlist, leaveserver, devguild, createinvite)
- Security sanctions (user/guild blacklist, cross-server global ban & unban)
- Diagnostic inspection (mutual servers, developer telemetry, raw SQL executor)
- Code execution & extension lifecycle (eval, sync, reload, load, unload, reloadall)
- Guild prefix configuration
Strictly zero decorative emojis.
"""

from __future__ import annotations

import io
import os
import sys
import time
import psutil
import asyncio
import textwrap
import traceback
from pathlib import Path
from contextlib import redirect_stdout
from typing import Optional, List, Union

import discord
from discord.ext import commands
from discord import ui

from core.config import config
from core.database import db
from core.logging import info, warn, error, success
from ui.embeds import ZenithEmbed
from ui.colors import Color

ACCENT_COLOR = 0x0F0F13


# ═══════════════════════════════════════════════════════════════
#  INTERACTIVE PAGINATED VIEWS
# ═══════════════════════════════════════════════════════════════

class ServerListView(ui.View):
    """Interactive paginated view for browsing connected Discord servers."""

    def __init__(self, guilds: List[discord.Guild], author_id: int):
        super().__init__(timeout=120.0)
        self.guilds = guilds
        self.author_id = author_id
        self.page = 0
        self.per_page = 10
        self.max_page = max(0, (len(guilds) - 1) // self.per_page)
        self._update_buttons()

    def _update_buttons(self):
        self.btn_first.disabled = self.page == 0
        self.btn_prev.disabled = self.page == 0
        self.btn_next.disabled = self.page >= self.max_page
        self.btn_last.disabled = self.page >= self.max_page

    def get_embed(self) -> discord.Embed:
        start = self.page * self.per_page
        current_chunk = self.guilds[start:start + self.per_page]

        lines = []
        for idx, g in enumerate(current_chunk, start=start + 1):
            owner_str = f"{g.owner} (ID: {g.owner_id})" if g.owner else f"Owner ID: {g.owner_id}"
            lines.append(
                f"`[{idx:03d}]` **{g.name}**\n"
                f"      ID: `{g.id}` • Members: `{g.member_count:,}`\n"
                f"      Owner: {owner_str}"
            )

        total_members = sum(g.member_count or 0 for g in self.guilds)
        embed = discord.Embed(
            title="[CONNECTED SERVERS DIRECTORY]",
            description="\n".join(lines) if lines else "No guilds connected.",
            color=ACCENT_COLOR
        )
        embed.set_footer(
            text=f"Page {self.page + 1}/{self.max_page + 1} • Total Servers: {len(self.guilds)} • Total Members: {total_members:,}"
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("[ACCESS DENIED] You cannot interact with this control session.", ephemeral=True)
            return False
        return True

    @ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def btn_first(self, interaction: discord.Interaction, button: ui.Button):
        self.page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="< Prev", style=discord.ButtonStyle.primary)
    async def btn_prev(self, interaction: discord.Interaction, button: ui.Button):
        if self.page > 0:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Next >", style=discord.ButtonStyle.primary)
    async def btn_next(self, interaction: discord.Interaction, button: ui.Button):
        if self.page < self.max_page:
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def btn_last(self, interaction: discord.Interaction, button: ui.Button):
        self.page = self.max_page
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class PaginatedTextView(ui.View):
    """Generic text paginator for long outputs (GBan list, blacklists, mutuals)."""

    def __init__(self, title: str, entries: List[str], author_id: int, per_page: int = 15):
        super().__init__(timeout=120.0)
        self.title = title
        self.entries = entries
        self.author_id = author_id
        self.per_page = per_page
        self.page = 0
        self.max_page = max(0, (len(entries) - 1) // per_page)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.max_page

    def get_embed(self) -> discord.Embed:
        start = self.page * self.per_page
        chunk = self.entries[start:start + self.per_page]
        desc = "\n".join(chunk) if chunk else "No records found."
        embed = discord.Embed(
            title=f"[{self.title.upper()}]",
            description=desc,
            color=ACCENT_COLOR
        )
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_page + 1} • Total Entries: {len(self.entries)}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("[ACCESS DENIED] You cannot control this session.", ephemeral=True)
            return False
        return True

    @ui.button(label="< Prev", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.page > 0:
            self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Next >", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.page < self.max_page:
            self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


# ═══════════════════════════════════════════════════════════════
#  DEVELOPER SUITE COG
# ═══════════════════════════════════════════════════════════════

class Owner(commands.Cog):
    """Developer operations, system security, and bot administration suite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Enforces that only verified owner IDs can execute commands in this cog."""
        return ctx.author.id in self.bot.owner_ids

    # ═══════════════════════════════════════════════════════════════
    #  1. PROCESS MANAGEMENT (Restart & Shutdown)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="restart", aliases=["reboot"])
    async def restart_command(self, ctx: commands.Context):
        """Gracefully restarts the Zenith bot process."""
        embed = discord.Embed(
            title="[RESTART INITIATED]",
            description="Closing active connections, flushing caches, and respawning process...",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

        info(f"Restart initiated by developer {ctx.author} (ID: {ctx.author.id})", "dev")
        await self.bot.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @commands.command(name="shutdown", aliases=["poweroff", "kill"])
    async def shutdown_command(self, ctx: commands.Context):
        """Cleanly disconnects gateway and terminates the bot process."""
        embed = discord.Embed(
            title="[SYSTEM SHUTDOWN]",
            description="Terminating HTTP session, closing database pool, and disconnecting gateway...",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

        warn(f"Shutdown ordered by developer {ctx.author} (ID: {ctx.author.id})", "dev")
        await self.bot.close()

    # ═══════════════════════════════════════════════════════════════
    #  2. MAINTENANCE MODE CONTROLS
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="maintenance", aliases=["maint", "maintenancemode"])
    async def maintenance_command(
        self,
        ctx: commands.Context,
        action: Optional[str] = None,
        *,
        reason: Optional[str] = "Scheduled developer maintenance in progress."
    ):
        """
        Toggles or checks system-wide maintenance mode.
        Usage:
          z!maintenance on [reason]
          z!maintenance off
          z!maintenance status
        """
        action_clean = (action or "status").lower()

        if action_clean in ("on", "enable", "true", "start"):
            self.bot.maintenance_mode = True
            self.bot.maintenance_reason = reason
            await db.execute(
                """
                INSERT INTO system_settings (key, value) VALUES ('maintenance', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
                """,
                reason
            )
            embed = discord.Embed(
                title="[MAINTENANCE MODE: ENABLED]",
                description=(
                    "Maintenance mode is now active across all connected guilds.\n\n"
                    f"• **Reason:** {reason}\n"
                    "• **Restriction:** Non-developer command invocation is blocked."
                ),
                color=Color.WARNING
            )
            embed.set_footer(text="Zenith Developer Core | Developed by Shree")
            await ctx.reply(embed=embed, mention_author=False)
            warn(f"Maintenance mode enabled by {ctx.author}: {reason}", "dev")

        elif action_clean in ("off", "disable", "false", "stop"):
            self.bot.maintenance_mode = False
            await db.execute("DELETE FROM system_settings WHERE key = 'maintenance'")
            embed = discord.Embed(
                title="[MAINTENANCE MODE: DISABLED]",
                description="Maintenance mode has been deactivated. Normal command execution restored across all guilds.",
                color=Color.SUCCESS
            )
            embed.set_footer(text="Zenith Developer Core | Developed by Shree")
            await ctx.reply(embed=embed, mention_author=False)
            info(f"Maintenance mode deactivated by {ctx.author}", "dev")

        else:
            status_str = "[ACTIVE - NON-DEVELOPERS BLOCKED]" if self.bot.maintenance_mode else "[INACTIVE - NORMAL EXECUTION]"
            embed = discord.Embed(
                title="[MAINTENANCE STATUS]",
                description=(
                    f"• **Status:** `{status_str}`\n"
                    f"• **Reason:** {self.bot.maintenance_reason if self.bot.maintenance_mode else 'N/A'}\n\n"
                    "**Commands:**\n"
                    f"• `{ctx.prefix}maintenance on [reason]` - Activate maintenance\n"
                    f"• `{ctx.prefix}maintenance off` - Restore normal operations\n"
                    f"• `{ctx.prefix}maintenance status` - View current status"
                ),
                color=ACCENT_COLOR
            )
            embed.set_footer(text="Zenith Developer Core | Developed by Shree")
            await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  3. SERVER & GUILD DIRECTORY (serverlist, leaveserver, devguild, createinvite)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="serverlist", aliases=["servers", "guildlist", "slist", "guilds"])
    async def serverlist_command(self, ctx: commands.Context):
        """Displays an interactive, paginated directory of all connected servers."""
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        if not guilds:
            return await ctx.reply("[INFO] The bot is not connected to any servers.", mention_author=False)

        view = ServerListView(guilds, ctx.author.id)
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)

    @commands.command(name="leaveserver", aliases=["leaveguild", "leavesrv", "gleave"])
    async def leaveserver_command(self, ctx: commands.Context, guild_id: int, *, reason: Optional[str] = "Developer administrative departure."):
        """Forces the bot to leave a specified server by ID."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.reply(f"[ERROR] Could not locate guild with ID `{guild_id}`.", mention_author=False)

        guild_name = guild.name
        member_cnt = guild.member_count
        owner_name = str(guild.owner) if guild.owner else f"ID: {guild.owner_id}"

        try:
            await guild.leave()
            embed = discord.Embed(
                title="[SERVER DEPARTURE COMPLETED]",
                description=(
                    f"Zenith has successfully left the target guild.\n\n"
                    f"• **Guild Name:** {guild_name}\n"
                    f"• **Guild ID:** `{guild_id}`\n"
                    f"• **Members:** `{member_cnt:,}`\n"
                    f"• **Owner:** {owner_name}\n"
                    f"• **Departure Reason:** {reason}"
                ),
                color=Color.SUCCESS
            )
            embed.set_footer(text="Zenith Developer Core | Developed by Shree")
            await ctx.reply(embed=embed, mention_author=False)
            warn(f"Left guild '{guild_name}' ({guild_id}) on order from {ctx.author}", "dev")
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to leave guild `{guild_id}`: {e}", mention_author=False)

    @commands.command(name="devguild", aliases=["inspectguild", "gdev", "dginfo"])
    async def devguild_command(self, ctx: commands.Context, guild_id: int):
        """Remotely inspects full telemetry of any connected guild by ID."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.reply(f"[ERROR] Guild `{guild_id}` not found on this bot instance.", mention_author=False)

        embed = discord.Embed(
            title=f"[GUILD TELEMETRY: {guild.name}]",
            description=f"Administrative inspection of guild ID `{guild.id}`.",
            color=ACCENT_COLOR
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        owner_str = f"{guild.owner} (`{guild.owner_id}`)" if guild.owner else f"ID: `{guild.owner_id}`"
        embed.add_field(name="Owner", value=owner_str, inline=True)
        embed.add_field(name="Total Members", value=f"`{guild.member_count:,}`", inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Text Channels", value=f"`{len(guild.text_channels)}`", inline=True)
        embed.add_field(name="Voice Channels", value=f"`{len(guild.voice_channels)}`", inline=True)
        embed.add_field(name="Roles Count", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Bot Perms", value=f"`{guild.me.guild_permissions.value}`", inline=True)
        embed.add_field(name="Verification", value=f"`{str(guild.verification_level).upper()}`", inline=True)
        embed.add_field(name="Vanity URL", value=f"`{guild.vanity_url_code or 'None'}`", inline=True)

        features = ", ".join(guild.features) if guild.features else "None"
        embed.add_field(name="Guild Features", value=f"`{features[:1000]}`", inline=False)
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="createinvite", aliases=["ginvite", "invlink"])
    async def create_invite_command(self, ctx: commands.Context, guild_id: int):
        """Generates an instant invite link for any connected guild."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.reply(f"[ERROR] Guild `{guild_id}` not found on this bot instance.", mention_author=False)

        invite_url = None
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).create_instant_invites:
                try:
                    inv = await ch.create_invite(max_age=3600, max_uses=5, reason="Developer inspection request")
                    invite_url = inv.url
                    break
                except Exception:
                    continue

        if invite_url:
            embed = discord.Embed(
                title=f"[INVITE GENERATED: {guild.name}]",
                description=f"• **URL:** {invite_url}\n• **Expiration:** 1 Hour (Max 5 uses)\n• **Guild ID:** `{guild.id}`",
                color=Color.SUCCESS
            )
            embed.set_footer(text="Zenith Developer Core | Developed by Shree")
            await ctx.reply(embed=embed, mention_author=False)
        else:
            await ctx.reply(f"[ERROR] Missing `create_instant_invites` permission in text channels of '{guild.name}'.", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  4. SECURITY SANCTIONS (Blacklist user/guild, Global Ban)
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="blacklist", aliases=["bl", "botban"], invoke_without_command=True)
    async def blacklist_group(self, ctx: commands.Context):
        """Manage system-wide blacklists for malicious users or guilds."""
        embed = discord.Embed(
            title="[SYSTEM BLACKLIST CONTROLS]",
            description=(
                "Commands to bar abusive accounts and malicious guilds from invoking Zenith:\n\n"
                f"• `{ctx.prefix}bl user <id/mention> [reason]` - Blacklist a user\n"
                f"• `{ctx.prefix}bl unuser <id/mention>` - Remove user from blacklist\n"
                f"• `{ctx.prefix}bl guild <id> [reason]` - Blacklist a server\n"
                f"• `{ctx.prefix}bl unguild <id>` - Remove server from blacklist\n"
                f"• `{ctx.prefix}bl list` - View all blacklisted entities"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @blacklist_group.command(name="user")
    async def bl_user(self, ctx: commands.Context, target: Union[discord.User, int], *, reason: str = "Developer security sanction"):
        """Blacklists a user from executing any bot commands."""
        user_id = target.id if isinstance(target, discord.User) else target
        if user_id in config.OWNER_IDS:
            return await ctx.reply("[DENIED] Cannot blacklist a verified bot developer.", mention_author=False)

        await db.execute(
            """
            INSERT INTO blacklists (target_id, target_type, reason, author_id)
            VALUES (?, 'user', ?, ?)
            ON CONFLICT(target_id) DO UPDATE SET reason = excluded.reason, author_id = excluded.author_id;
            """,
            user_id, reason, ctx.author.id
        )
        self.bot.blacklisted_users.add(user_id)

        embed = discord.Embed(
            title="[USER BLACKLISTED]",
            description=(
                f"User ID `{user_id}` has been barred from invoking Zenith commands.\n\n"
                f"• **Target ID:** `{user_id}`\n"
                f"• **Reason:** {reason}\n"
                f"• **Enforced By:** {ctx.author.mention}"
            ),
            color=Color.ERROR
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)
        warn(f"User {user_id} blacklisted by {ctx.author}: {reason}", "dev")

    @blacklist_group.command(name="unuser")
    async def bl_unuser(self, ctx: commands.Context, target: Union[discord.User, int]):
        """Removes a user from the global blacklist."""
        user_id = target.id if isinstance(target, discord.User) else target
        await db.execute("DELETE FROM blacklists WHERE target_id = ? AND target_type = 'user'", user_id)
        self.bot.blacklisted_users.discard(user_id)

        embed = discord.Embed(
            title="[USER UNBLACKLISTED]",
            description=f"User ID `{user_id}` has been restored to standard access.",
            color=Color.SUCCESS
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)
        info(f"User {user_id} unblacklisted by {ctx.author}", "dev")

    @blacklist_group.command(name="guild", aliases=["server"])
    async def bl_guild(self, ctx: commands.Context, guild_id: int, *, reason: str = "Developer server sanction"):
        """Blacklists a guild from executing any bot commands."""
        await db.execute(
            """
            INSERT INTO blacklists (target_id, target_type, reason, author_id)
            VALUES (?, 'guild', ?, ?)
            ON CONFLICT(target_id) DO UPDATE SET reason = excluded.reason, author_id = excluded.author_id;
            """,
            guild_id, reason, ctx.author.id
        )
        self.bot.blacklisted_guilds.add(guild_id)

        embed = discord.Embed(
            title="[GUILD BLACKLISTED]",
            description=(
                f"Guild ID `{guild_id}` is now ignored across all command triggers.\n\n"
                f"• **Guild ID:** `{guild_id}`\n"
                f"• **Reason:** {reason}\n"
                f"• **Enforced By:** {ctx.author.mention}"
            ),
            color=Color.ERROR
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)
        warn(f"Guild {guild_id} blacklisted by {ctx.author}: {reason}", "dev")

    @blacklist_group.command(name="unguild", aliases=["unserver"])
    async def bl_unguild(self, ctx: commands.Context, guild_id: int):
        """Removes a guild from the global blacklist."""
        await db.execute("DELETE FROM blacklists WHERE target_id = ? AND target_type = 'guild'", guild_id)
        self.bot.blacklisted_guilds.discard(guild_id)

        embed = discord.Embed(
            title="[GUILD UNBLACKLISTED]",
            description=f"Guild ID `{guild_id}` has been restored to standard access.",
            color=Color.SUCCESS
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)
        info(f"Guild {guild_id} unblacklisted by {ctx.author}", "dev")

    @blacklist_group.command(name="list")
    async def bl_list(self, ctx: commands.Context):
        """Displays all blacklisted users and servers."""
        rows = await db.fetch("SELECT target_id, target_type, reason FROM blacklists ORDER BY created_at DESC")
        if not rows:
            return await ctx.reply("[INFO] No users or servers are currently blacklisted.", mention_author=False)

        entries = []
        for r in rows:
            t_type = r["target_type"].upper()
            tid = r["target_id"]
            reason = r["reason"] or "No reason provided"
            entries.append(f"• `[{t_type}]` ID: `{tid}` — {reason}")

        view = PaginatedTextView("System Blacklist Directory", entries, ctx.author.id)
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  5. CROSS-SERVER GLOBAL BAN (gban, gunban, gbanlist)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="globalban", aliases=["gban"])
    async def global_ban_command(self, ctx: commands.Context, target: Union[discord.User, int], *, reason: str = "Network security threat"):
        """Bans a malicious person or rogue bot across ALL servers where Zenith has permission."""
        user_id = target.id if isinstance(target, discord.User) else target
        if user_id in config.OWNER_IDS:
            return await ctx.reply("[DENIED] Cannot issue a global ban against a bot developer.", mention_author=False)
        if user_id == self.bot.user.id:
            return await ctx.reply("[DENIED] Cannot global ban the bot itself.", mention_author=False)

        # Store in DB and in-memory set
        await db.execute(
            """
            INSERT INTO global_bans (user_id, reason, author_id)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason, author_id = excluded.author_id;
            """,
            user_id, reason, ctx.author.id
        )
        self.bot.global_bans.add(user_id)

        msg = await ctx.reply(
            embed=discord.Embed(
                title="[EXECUTING GLOBAL BAN...]",
                description=f"Propagating network-wide security sanction for user ID `{user_id}`...",
                color=Color.WARNING
            ),
            mention_author=False
        )

        success_count = 0
        failed_count = 0
        audit_reason = f"[ZENITH GBAN] {reason} | Sanctioned by {ctx.author}"

        for g in self.bot.guilds:
            if not g.me.guild_permissions.ban_members:
                continue

            member = g.get_member(user_id)
            if member:
                if g.me.top_role <= member.top_role or member.id == g.owner_id:
                    failed_count += 1
                    continue

            try:
                await g.ban(discord.Object(id=user_id), reason=audit_reason, delete_message_days=1)
                success_count += 1
            except Exception:
                failed_count += 1

        embed = discord.Embed(
            title="[GLOBAL BAN EXECUTED]",
            description=(
                f"Global ban deployed for account ID `{user_id}`.\n\n"
                f"• **Target ID:** `{user_id}`\n"
                f"• **Reason:** {reason}\n"
                f"• **Enforced By:** {ctx.author.mention}\n"
                f"• **Sanction Result:** Successfully banned in `{success_count}` guild(s) • `{failed_count}` failed/skipped\n"
                "• **Auto-Enforcement:** Account will be automatically neutralized upon joining any guild protected by Zenith."
            ),
            color=Color.ERROR
        )
        embed.set_footer(text="Zenith Network Defense | Developed by Shree")
        await msg.edit(embed=embed)
        warn(f"GBAN issued for {user_id} by {ctx.author}: {reason} ({success_count} guilds banned)", "dev")

    @commands.command(name="globalunban", aliases=["gunban"])
    async def global_unban_command(self, ctx: commands.Context, target: Union[discord.User, int], *, reason: str = "Sanction revoked by developer"):
        """Revokes a global ban and unbans the user across connected servers."""
        user_id = target.id if isinstance(target, discord.User) else target

        await db.execute("DELETE FROM global_bans WHERE user_id = ?", user_id)
        self.bot.global_bans.discard(user_id)

        msg = await ctx.reply(
            embed=discord.Embed(
                title="[REVOKING GLOBAL BAN...]",
                description=f"Lifting network sanctions for ID `{user_id}`...",
                color=Color.WARNING
            ),
            mention_author=False
        )

        unban_count = 0
        for g in self.bot.guilds:
            if not g.me.guild_permissions.ban_members:
                continue
            try:
                await g.unban(discord.Object(id=user_id), reason=f"[ZENITH GUNBAN] {reason}")
                unban_count += 1
            except Exception:
                pass

        embed = discord.Embed(
            title="[GLOBAL BAN REVOKED]",
            description=(
                f"Global ban revoked for ID `{user_id}`.\n\n"
                f"• **Unbanned in:** `{unban_count}` guilds\n"
                f"• **Reason:** {reason}\n"
                f"• **Revoked By:** {ctx.author.mention}"
            ),
            color=Color.SUCCESS
        )
        embed.set_footer(text="Zenith Network Defense | Developed by Shree")
        await msg.edit(embed=embed)
        info(f"GUNBAN executed for {user_id} by {ctx.author}", "dev")

    @commands.command(name="globalbanlist", aliases=["gbanlist", "gbans"])
    async def global_ban_list_command(self, ctx: commands.Context):
        """Displays all accounts currently registered in the global ban network."""
        rows = await db.fetch("SELECT user_id, reason, banned_at FROM global_bans ORDER BY banned_at DESC")
        if not rows:
            return await ctx.reply("[INFO] No accounts are currently under a network global ban.", mention_author=False)

        entries = []
        for r in rows:
            entries.append(f"• User ID: `{r['user_id']}` — Reason: {r['reason']}")

        view = PaginatedTextView("Global Ban Registry", entries, ctx.author.id)
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  6. MUTUAL SERVERS INSPECTOR
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="mutuals", aliases=["mutualservers", "sharedservers", "sharedguilds"])
    async def mutual_servers_command(self, ctx: commands.Context, target: Union[discord.User, int]):
        """Finds all mutual servers shared between Zenith and a specified user or bot."""
        user_id = target.id if isinstance(target, discord.User) else target
        resolved_user = self.bot.get_user(user_id)
        if not resolved_user:
            try:
                resolved_user = await self.bot.fetch_user(user_id)
            except Exception:
                resolved_user = None

        mutual_guilds = [g for g in self.bot.guilds if g.get_member(user_id) is not None]
        user_tag = f"{resolved_user} (`{user_id}`)" if resolved_user else f"User ID `{user_id}`"

        if not mutual_guilds:
            return await ctx.reply(f"[INFO] Zenith shares zero mutual servers with {user_tag}.", mention_author=False)

        entries = []
        for idx, g in enumerate(mutual_guilds, start=1):
            mem = g.get_member(user_id)
            top_role = mem.top_role.name if mem else "Unknown"
            entries.append(
                f"`[{idx:02d}]` **{g.name}** (ID: `{g.id}`)\n"
                f"      Members: `{g.member_count:,}` • Top Role: `@{top_role}`"
            )

        view = PaginatedTextView(f"Mutual Servers: {user_tag}", entries, ctx.author.id, per_page=10)
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  7. HOT-RELOAD & EXTENSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="reload")
    async def reload_extension(self, ctx: commands.Context, extension: str):
        """Hot-reloads a single extension (e.g. `z!reload moderation`)."""
        target = f"cogs.{extension}" if not extension.startswith("cogs.") and not extension.startswith("core.") else extension
        try:
            await self.bot.reload_extension(target)
            success(f"Hot-reloaded extension: {target}", "dev")
            embed = ZenithEmbed.success("Extension Reloaded", f"Successfully reloaded `{target}`.")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            error(f"Failed to reload {target}: {e}", "dev")
            embed = ZenithEmbed.error("Reload Failed", f"```{e}```")
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="load")
    async def load_extension_cmd(self, ctx: commands.Context, extension: str):
        """Loads a new or unloaded extension into runtime."""
        target = f"cogs.{extension}" if not extension.startswith("cogs.") and not extension.startswith("core.") else extension
        try:
            await self.bot.load_extension(target)
            success(f"Loaded extension: {target}", "dev")
            embed = ZenithEmbed.success("Extension Loaded", f"Successfully loaded `{target}` into runtime.")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            error(f"Failed to load {target}: {e}", "dev")
            embed = ZenithEmbed.error("Load Failed", f"```{e}```")
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="unload")
    async def unload_extension_cmd(self, ctx: commands.Context, extension: str):
        """Unloads an extension from runtime."""
        target = f"cogs.{extension}" if not extension.startswith("cogs.") and not extension.startswith("core.") else extension
        try:
            await self.bot.unload_extension(target)
            warn(f"Unloaded extension: {target}", "dev")
            embed = ZenithEmbed.success("Extension Unloaded", f"Successfully unloaded `{target}` from runtime.")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            error(f"Failed to unload {target}: {e}", "dev")
            embed = ZenithEmbed.error("Unload Failed", f"```{e}```")
            await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="reloadall", aliases=["ra"])
    async def reload_all_extensions(self, ctx: commands.Context):
        """Hot-reloads all registered feature cogs simultaneously."""
        cogs_dir = Path(__file__).resolve().parent
        reloaded = []
        failures = []

        for file in cogs_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            ext_name = f"cogs.{file.stem}"
            try:
                await self.bot.reload_extension(ext_name)
                reloaded.append(file.stem)
            except Exception as e:
                failures.append(f"{file.stem} ({e})")

        desc = f"Reloaded {len(reloaded)} modules: " + ", ".join(f"`{m}`" for m in reloaded)
        if failures:
            desc += "\n\nFailures:\n" + "\n".join(f"• `{f}`" for f in failures)

        embed = ZenithEmbed(
            title="System Hot-Reload",
            description=desc,
            color=Color.SUCCESS if not failures else Color.WARNING
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  9. SLASH TREE SYNC & ASYNC CODE EVAL
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="sync")
    async def sync_slash_commands(self, ctx: commands.Context, scope: Optional[str] = None):
        """Synchronizes application commands (Pass `guild` for instant local testing)."""
        msg = await ctx.reply(embed=ZenithEmbed.info("Syncing...", "Pushing command definitions to Discord API..."), mention_author=False)

        if scope == "guild":
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            embed = ZenithEmbed.success("Guild Tree Synced", f"Synchronized **{len(synced)}** slash commands to this server.")
        else:
            synced = await self.bot.tree.sync()
            embed = ZenithEmbed.success("Global Tree Synced", f"Synchronized **{len(synced)}** slash commands globally.")

        await msg.edit(embed=embed)

    @commands.command(name="eval", aliases=["e"])
    async def eval_command(self, ctx: commands.Context, *, code: str):
        """Evaluates asynchronous Python statements in the running bot context."""
        clean_code = code.strip("`")
        if clean_code.startswith("py\n"):
            clean_code = clean_code[3:]

        env = {
            "bot": self.bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message,
            "db": db,
            "discord": discord,
            "asyncio": asyncio,
        }

        stdout = io.StringIO()
        to_compile = f"async def func():\n{textwrap.indent(clean_code, '  ')}"

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.reply(embed=ZenithEmbed.error("Syntax Error", f"```{e}```"), mention_author=False)

        func = env["func"]
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            return await ctx.reply(embed=ZenithEmbed.error("Execution Exception", f"```{value}{traceback.format_exc()}```"), mention_author=False)

        value = stdout.getvalue()
        result = ret if ret is not None else value
        result_str = str(result) if result else "None"

        if len(result_str) > 1900:
            result_str = result_str[:1900] + "\n... [Truncated]"

        embed = ZenithEmbed(
            title="Evaluation Output",
            description=f"```py\n{result_str}\n```",
            color=Color.SUCCESS
        )
        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  10. DEVELOPER TELEMETRY & SYSTEM INSPECTION (devstats, sql, dm)
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="devstats", aliases=["systeminfo", "devinfo", "hostinfo"])
    async def devstats_command(self, ctx: commands.Context):
        """Displays host performance metrics, memory utilization, and system telemetry."""
        proc = psutil.Process()
        mem_info = proc.memory_info()
        rss_mb = mem_info.rss / (1024 * 1024)
        cpu_pct = proc.cpu_percent(interval=0.1)
        threads = proc.num_threads()

        uptime_sec = int(time.time() - getattr(self.bot, "launch_time", time.time()))
        d, rem = divmod(uptime_sec, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        uptime_fmt = f"{d}d {h}h {m}m {s}s"

        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)
        ping_ms = round(self.bot.latency * 1000, 1)

        embed = discord.Embed(
            title="[ZENITH HOST TELEMETRY]",
            description="Real-time internal diagnostics across operating system and bot container.",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Process RAM (RSS)", value=f"`{rss_mb:.2f} MB`", inline=True)
        embed.add_field(name="Process CPU", value=f"`{cpu_pct:.1f}%`", inline=True)
        embed.add_field(name="Active Threads", value=f"`{threads}`", inline=True)
        embed.add_field(name="Gateway Latency", value=f"`{ping_ms} ms`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime_fmt}`", inline=True)
        embed.add_field(name="Shards", value=f"`{self.bot.shard_count or 1}`", inline=True)
        embed.add_field(name="Guilds", value=f"`{len(self.bot.guilds):,}`", inline=True)
        embed.add_field(name="Cached Members", value=f"`{total_members:,}`", inline=True)
        embed.add_field(name="Cached Channels", value=f"`{total_channels:,}`", inline=True)
        embed.add_field(name="Python Runtime", value=f"`{sys.version.split()[0]}`", inline=True)
        embed.add_field(name="discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.add_field(name="Loaded Cogs", value=f"`{len(self.bot.cogs)}`", inline=True)

        embed.set_footer(text="Zenith Developer Core | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="sql", aliases=["dbquery", "query"])
    async def sql_command(self, ctx: commands.Context, *, query: str):
        """Executes a direct raw SQL query against the database engine."""
        clean_q = query.strip("`")
        if clean_q.startswith("sql\n"):
            clean_q = clean_q[4:]

        start_t = time.perf_counter()
        is_select = clean_q.strip().lower().startswith("select")

        try:
            if is_select:
                rows = await db.fetch(clean_q)
                elapsed = (time.perf_counter() - start_t) * 1000
                if not rows:
                    return await ctx.reply(f"```[0 rows returned in {elapsed:.2f}ms]```", mention_author=False)

                headers = list(rows[0].keys())
                formatted_lines = [" | ".join(headers), "-+-".join("-" * len(h) for h in headers)]
                for r in rows[:25]:
                    formatted_lines.append(" | ".join(str(r[h]) for h in headers))

                if len(rows) > 25:
                    formatted_lines.append(f"... [{len(rows) - 25} more rows]")

                output_str = "\n".join(formatted_lines)
                if len(output_str) > 1900:
                    output_str = output_str[:1900] + "\n... [Truncated]"

                await ctx.reply(f"```{output_str}```\n*Executed in {elapsed:.2f}ms ({len(rows)} row(s))*", mention_author=False)
            else:
                affected = await db.execute(clean_q)
                elapsed = (time.perf_counter() - start_t) * 1000
                await ctx.reply(f"```[OK] Statement executed in {elapsed:.2f}ms. Status: {affected}```", mention_author=False)
        except Exception as e:
            elapsed = (time.perf_counter() - start_t) * 1000
            await ctx.reply(f"```[SQL ERROR in {elapsed:.2f}ms]\n{e}```", mention_author=False)

    @commands.command(name="dm")
    async def dm_command(self, ctx: commands.Context, target: Union[discord.User, int], *, message: str):
        """Sends an administrative direct message to a user from Zenith."""
        user = target if isinstance(target, discord.User) else self.bot.get_user(target)
        if not user:
            try:
                user = await self.bot.fetch_user(target)
            except Exception:
                return await ctx.reply(f"[ERROR] Could not locate or fetch user with ID `{target}`.", mention_author=False)

        embed = discord.Embed(
            title="[OFFICIAL ZENITH COMMUNICATION]",
            description=message,
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Official Developer Dispatch | Zenith Network")

        try:
            await user.send(embed=embed)
            await ctx.reply(f"[OK] Administrative message successfully delivered to {user.mention} (`{user.id}`).", mention_author=False)
        except discord.Forbidden:
            await ctx.reply(f"[ERROR] Cannot send DM to {user.mention}: User has direct messages closed or blocked.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to send DM: {e}", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  11. GUILD PREFIX ADJUSTMENT
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="prefix", aliases=["setprefix"])
    @commands.has_permissions(manage_guild=True)
    async def set_prefix_command(self, ctx: commands.Context, new_prefix: str):
        """Changes the trigger prefix for this guild."""
        clean_prefix = new_prefix.strip()
        if len(clean_prefix) > 10:
            return await ctx.reply(embed=ZenithEmbed.error("Prefix Too Long", "Prefix cannot exceed 10 characters."), mention_author=False)

        await db.set_prefix(ctx.guild.id, clean_prefix)
        embed = ZenithEmbed.success("Prefix Updated", f"Zenith's command prefix in this server is now `{clean_prefix}`.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
