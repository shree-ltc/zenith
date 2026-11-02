"""
Fake Permission (Virtual Authorization) System for Zenith.
Allows staff members to execute Zenith moderation commands without granting native Discord permissions.
Includes daily quotas and rate limiting to prevent staff abuse.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import datetime
from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin
from core.config import config

ACCENT_COLOR = 0x0F0F13

FP_ACTIONS = [
    "ban",
    "kick",
    "timeout",
    "warn",
    "unwarn",
    "lock",
    "unlock",
    "hide",
    "unhide",
    "purge",
]


class FakePermission(commands.Cog):
    """Virtual permissions and quota management for moderator roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cache for fast lookup: {guild_id: role_id}
        self._fp_role_cache: Dict[int, Optional[int]] = {}

    async def cog_load(self) -> None:
        """Preload fake permission role mappings."""
        rows = await db.fetch("SELECT guild_id, role_id FROM fp_config")
        for r in rows:
            self._fp_role_cache[r["guild_id"]] = r["role_id"]

    async def _get_fp_role_id(self, guild_id: int) -> Optional[int]:
        if guild_id in self._fp_role_cache:
            return self._fp_role_cache[guild_id]
        row = await db.fetchrow("SELECT role_id FROM fp_config WHERE guild_id = ?", guild_id)
        rid = row["role_id"] if row else None
        self._fp_role_cache[guild_id] = rid
        return rid

    async def _get_limit(self, guild_id: int, action: str) -> int:
        row = await db.fetchrow(
            "SELECT action_limit FROM fp_limits WHERE guild_id = ? AND action = ?",
            guild_id, action
        )
        return row["action_limit"] if row else 0  # 0 = unlimited

    async def _get_usage(self, guild_id: int, user_id: int, action: str) -> int:
        today_str = datetime.date.today().isoformat()
        row = await db.fetchrow(
            "SELECT usage_count FROM fp_usage WHERE guild_id = ? AND user_id = ? AND action = ? AND date_str = ?",
            guild_id, user_id, action, today_str
        )
        return row["usage_count"] if row else 0

    async def _increment_usage(self, guild_id: int, user_id: int, action: str) -> None:
        today_str = datetime.date.today().isoformat()
        await db.execute(
            """
            INSERT INTO fp_usage (guild_id, user_id, action, usage_count, date_str)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(guild_id, user_id, action, date_str)
            DO UPDATE SET usage_count = fp_usage.usage_count + 1
            """,
            guild_id, user_id, action, today_str
        )

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="fakepermission", aliases=["fp"], invoke_without_command=True)
    @commands.guild_only()
    async def fp_group(self, ctx: commands.Context):
        """Fake Permission configuration overview."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Fake Permission management is restricted to the Server Owner.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        rid = await self._get_fp_role_id(ctx.guild.id)
        role = ctx.guild.get_role(rid) if rid else None
        role_status = role.mention if role else "None configured"

        embed = discord.Embed(
            title="[FAKE PERMISSION SYSTEM]",
            description=(
                "Fake Permission lets you designate a moderator role that can run Zenith commands "
                "(ban, kick, mute, warn, lock, hide, purge) WITHOUT giving that role native Discord "
                "permissions. This prevents rogue mods from destroying channels or abusing Discord perms."
            ),
            color=ACCENT_COLOR
        )
        embed.add_field(name="Authorized Role", value=role_status, inline=True)
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}fp set <role>` - Assign the authorized moderator role\n"
                f"`{ctx.prefix}fp remove` - Clear the authorized role\n"
                f"`{ctx.prefix}fp limit <action> <count>` - Set daily limit for an action\n"
                f"`{ctx.prefix}fp limits` - View configured daily limits\n"
                f"`{ctx.prefix}fp usage [user]` - View daily action usage for a user\n"
                f"`{ctx.prefix}fp reset <user>` - Reset daily action usage for a user"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="set")
    @commands.guild_only()
    async def fp_set(self, ctx: commands.Context, role: discord.Role):
        """Set the role that receives fake permissions."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=discord.Embed(
                title="[HIERARCHY ERROR]",
                description="Cannot assign a role that is higher than or equal to my highest role.",
                color=ACCENT_COLOR
            ))

        await db.execute(
            """
            INSERT INTO fp_config (guild_id, role_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
            """,
            ctx.guild.id, role.id
        )
        self._fp_role_cache[ctx.guild.id] = role.id

        embed = discord.Embed(
            title="[FAKE PERMISSION ROLE ASSIGNED]",
            description=f"Members possessing {role.mention} can now execute Zenith moderation commands under daily quotas.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="remove")
    @commands.guild_only()
    async def fp_remove(self, ctx: commands.Context):
        """Remove fake permission role configuration."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await db.execute("UPDATE fp_config SET role_id = NULL WHERE guild_id = ?", ctx.guild.id)
        self._fp_role_cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[FAKE PERMISSION CONFIG REMOVED]",
            description="Cleared fake permission role configuration.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="limit")
    @commands.guild_only()
    async def fp_limit(self, ctx: commands.Context, action: str, count: int):
        """Set daily execution quota for a moderation action (0 for unlimited)."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        action = action.lower()
        if action not in FP_ACTIONS:
            return await ctx.send(embed=discord.Embed(
                title="[INVALID ACTION]",
                description=f"Supported actions: `{'`, `'.join(FP_ACTIONS)}`.",
                color=ACCENT_COLOR
            ))

        if count < 0 or count > 500:
            return await ctx.send(embed=discord.Embed(
                title="[INVALID COUNT]",
                description="Limit must be between 0 (unlimited) and 500.",
                color=ACCENT_COLOR
            ))

        await db.execute(
            """
            INSERT INTO fp_limits (guild_id, action, action_limit) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, action) DO UPDATE SET action_limit = excluded.action_limit
            """,
            ctx.guild.id, action, count
        )

        limit_str = f"**{count} actions / day**" if count > 0 else "**Unlimited**"
        embed = discord.Embed(
            title="[QUOTA UPDATED]",
            description=f"Daily limit for `{action}` set to {limit_str}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="limits")
    @commands.guild_only()
    async def fp_limits(self, ctx: commands.Context):
        """Display daily execution quotas across all moderation actions."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        lines = []
        for a in FP_ACTIONS:
            limit = await self._get_limit(ctx.guild.id, a)
            limit_str = f"`{limit} / day`" if limit > 0 else "`Unlimited`"
            lines.append(f"• **{a.capitalize()}:** {limit_str}")

        embed = discord.Embed(
            title="[DAILY MODERATION QUOTAS]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="usage")
    @commands.guild_only()
    async def fp_usage(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display a staff member's daily command execution usage."""
        target = member or ctx.author
        lines = []
        for a in FP_ACTIONS:
            used = await self._get_usage(ctx.guild.id, target.id, a)
            limit = await self._get_limit(ctx.guild.id, a)
            limit_str = str(limit) if limit > 0 else "∞"
            lines.append(f"• **{a.capitalize()}:** `{used} / {limit_str}`")

        embed = discord.Embed(
            title=f"[DAILY USAGE - {target.display_name}]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="reset")
    @commands.guild_only()
    async def fp_reset(self, ctx: commands.Context, member: discord.Member):
        """Reset daily execution counters for a user."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        today_str = datetime.date.today().isoformat()
        await db.execute(
            "DELETE FROM fp_usage WHERE guild_id = ? AND user_id = ? AND date_str = ?",
            ctx.guild.id, member.id, today_str
        )

        embed = discord.Embed(
            title="[USAGE RESET]",
            description=f"Reset today's moderation command counters for {member.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Security | Developed by Shree")
        await ctx.send(embed=embed)

    @fp_group.command(name="actions", aliases=["listactions"])
    @commands.guild_only()
    async def fp_actions(self, ctx: commands.Context):
        """List all actions configurable under the fake permission matrix."""
        lines = [f"• `{a}`" for a in ALLOWED_ACTIONS]
        embed = discord.Embed(
            title="[FP ACTIONS MATRIX]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @fp_group.command(name="resetall")
    @commands.guild_only()
    async def fp_resetall(self, ctx: commands.Context):
        """Purge all daily usage records across the entire server."""
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Server Owner.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM fp_usage WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Usage Purged", description="Reset all moderation quota counters for all members.", color=ACCENT_COLOR))

    @fp_group.command(name="test")
    @commands.guild_only()
    async def fp_test_cmd(self, ctx: commands.Context, member: discord.Member, action: str):
        """Test whether a member has authorization to execute an action."""
        action_clean = action.lower().strip()
        role_id = await self._get_fp_role_id(ctx.guild.id)
        role = ctx.guild.get_role(role_id) if role_id else None

        has_role = role in member.roles if role else False
        used = await self._get_usage(ctx.guild.id, member.id, action_clean)
        limit = await self._get_limit(ctx.guild.id, action_clean)
        can_exec = has_role and (limit == 0 or used < limit)

        embed = discord.Embed(
            title=f"[FP AUDIT] {member.display_name} -> {action_clean}",
            description=f"Authorized: **{'YES' if can_exec else 'NO'}**\n• Holds FP Role: `{'Yes' if has_role else 'No'}`\n• Quota Used: `{used} / {limit or '∞'}`",
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FakePermission(bot))
