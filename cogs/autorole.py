"""
Advanced Autorole Suite for Zenith.
Supports multi-role automatic assignment on member and bot joins with hierarchy validation.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Dict, Set
import discord
from discord.ext import commands

from core.database import db
from core.security import is_dangerous_role, validate_role_hierarchy

ACCENT_COLOR = 0x0F0F13


class Autorole(commands.Cog):
    """Automatic role assignment engine on member and bot joins."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # RAM Cache: {guild_id: {"humans": {role_id, ...}, "bots": {role_id, ...}}}
        self._cache: Dict[int, Dict[str, Set[int]]] = {}

    async def cog_load(self) -> None:
        """Preload all autoroles into memory."""
        rows = await db.fetch("SELECT guild_id, role_id, role_type FROM autoroles")
        for r in rows:
            gid = r["guild_id"]
            rtype = r["role_type"]
            rid = r["role_id"]
            if gid not in self._cache:
                self._cache[gid] = {"humans": set(), "bots": set()}
            if rtype in self._cache[gid]:
                self._cache[gid][rtype].add(rid)

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        guild_cfg = self._cache.get(guild.id)
        if not guild_cfg or not guild.me.guild_permissions.manage_roles:
            return

        role_ids = guild_cfg["bots"] if member.bot else guild_cfg["humans"]
        if not role_ids:
            return

        roles_to_assign = [
            guild.get_role(rid) for rid in role_ids
            if guild.get_role(rid) and guild.get_role(rid) < guild.me.top_role
        ]

        if roles_to_assign:
            try:
                await member.add_roles(*roles_to_assign, reason="Zenith Autorole Onboarding")
            except Exception:
                pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="autorole", invoke_without_command=True)
    @commands.guild_only()
    async def autorole_group(self, ctx: commands.Context):
        """Autorole management overview."""
        embed = discord.Embed(
            title="[AUTOROLE SYSTEM]",
            description="Automatically grant roles to newly joined humans or automated bot accounts.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Human Role Commands",
            value=(
                f"`{ctx.prefix}autorole humans add <role>` - Add human autorole\n"
                f"`{ctx.prefix}autorole humans remove <role>` - Remove human autorole\n"
                f"`{ctx.prefix}autorole humans list` - View active human autoroles"
            ),
            inline=False
        )
        embed.add_field(
            name="Bot Role Commands",
            value=(
                f"`{ctx.prefix}autorole bots add <role>` - Add bot autorole\n"
                f"`{ctx.prefix}autorole bots remove <role>` - Remove bot autorole\n"
                f"`{ctx.prefix}autorole bots list` - View active bot autoroles"
            ),
            inline=False
        )
        embed.add_field(
            name="Maintenance",
            value=f"`{ctx.prefix}autorole show` - Overview | `{ctx.prefix}autorole reset` - Clear all",
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # HUMANS SUBGROUP
    # ---------------------------------------------------------

    @autorole_group.group(name="humans", invoke_without_command=True)
    @commands.guild_only()
    async def ar_humans(self, ctx: commands.Context):
        """Human autorole settings."""
        await self.autorole_group(ctx)

    @ar_humans.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def ar_humans_add(self, ctx: commands.Context, role: discord.Role):
        """Add a role to be granted to new human members."""
        ok, err = validate_role_hierarchy(ctx.author, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        if is_dangerous_role(role):
            return await ctx.send(embed=discord.Embed(
                title="[SECURITY RESTRICTION]",
                description="Roles with administrative or dangerous permissions cannot be assigned as autoroles.",
                color=ACCENT_COLOR
            ))

        await db.execute(
            """
            INSERT INTO autoroles (guild_id, role_id, role_type) VALUES (?, ?, 'humans')
            ON CONFLICT(guild_id, role_id) DO NOTHING
            """,
            ctx.guild.id, role.id
        )

        if ctx.guild.id not in self._cache:
            self._cache[ctx.guild.id] = {"humans": set(), "bots": set()}
        self._cache[ctx.guild.id]["humans"].add(role.id)

        embed = discord.Embed(
            title="[HUMAN AUTOROLE ADDED]",
            description=f"New human members will automatically receive {role.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_humans.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def ar_humans_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from human autoroles."""
        await db.execute(
            "DELETE FROM autoroles WHERE guild_id = ? AND role_id = ? AND role_type = 'humans'",
            ctx.guild.id, role.id
        )

        if ctx.guild.id in self._cache:
            self._cache[ctx.guild.id]["humans"].discard(role.id)

        embed = discord.Embed(
            title="[HUMAN AUTOROLE REMOVED]",
            description=f"Removed {role.mention} from human autoroles.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_humans.command(name="list")
    @commands.guild_only()
    async def ar_humans_list(self, ctx: commands.Context):
        """List active human autoroles."""
        cfg = self._cache.get(ctx.guild.id, {}).get("humans", set())
        if not cfg:
            return await ctx.send(embed=discord.Embed(title="[NO HUMAN AUTOROLES]", description="Zero roles configured.", color=ACCENT_COLOR))

        lines = [f"• <@&{rid}> (`{rid}`)" for rid in cfg]
        embed = discord.Embed(title="[ACTIVE HUMAN AUTOROLES]", description="\n".join(lines), color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_humans.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_humans_clear(self, ctx: commands.Context):
        """Clear all human autoroles."""
        await db.execute("DELETE FROM autoroles WHERE guild_id = ? AND role_type = 'humans'", ctx.guild.id)
        if ctx.guild.id in self._cache:
            self._cache[ctx.guild.id]["humans"].clear()
        await ctx.send(embed=discord.Embed(title="[OK] Human Autoroles Cleared", description="Removed all human autoroles.", color=ACCENT_COLOR))

    @ar_humans.command(name="test")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def ar_humans_test(self, ctx: commands.Context, member: discord.Member):
        """Simulate human autorole application on a member."""
        cfg = self._cache.get(ctx.guild.id, {}).get("humans", set())
        roles = [ctx.guild.get_role(r) for r in cfg if ctx.guild.get_role(r)]
        if not roles:
            return await ctx.send("[INFO] No human autoroles configured.")
        await member.add_roles(*roles, reason="Autorole Test")
        await ctx.send(f"[OK] Applied {len(roles)} human autoroles to {member.mention}.")

    # ---------------------------------------------------------
    # BOTS SUBGROUP
    # ---------------------------------------------------------

    @autorole_group.group(name="bots", invoke_without_command=True)
    @commands.guild_only()
    async def ar_bots(self, ctx: commands.Context):
        """Bot autorole settings."""
        await self.autorole_group(ctx)

    @ar_bots.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def ar_bots_add(self, ctx: commands.Context, role: discord.Role):
        """Add a role to be granted to new bot accounts."""
        ok, err = validate_role_hierarchy(ctx.author, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        if is_dangerous_role(role):
            return await ctx.send(embed=discord.Embed(
                title="[SECURITY RESTRICTION]",
                description="Roles with administrative or dangerous permissions cannot be assigned as autoroles.",
                color=ACCENT_COLOR
            ))

        await db.execute(
            """
            INSERT INTO autoroles (guild_id, role_id, role_type) VALUES (?, ?, 'bots')
            ON CONFLICT(guild_id, role_id) DO NOTHING
            """,
            ctx.guild.id, role.id
        )

        if ctx.guild.id not in self._cache:
            self._cache[ctx.guild.id] = {"humans": set(), "bots": set()}
        self._cache[ctx.guild.id]["bots"].add(role.id)

        embed = discord.Embed(
            title="[BOT AUTOROLE ADDED]",
            description=f"New bot accounts will automatically receive {role.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_bots.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def ar_bots_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from bot autoroles."""
        await db.execute(
            "DELETE FROM autoroles WHERE guild_id = ? AND role_id = ? AND role_type = 'bots'",
            ctx.guild.id, role.id
        )

        if ctx.guild.id in self._cache:
            self._cache[ctx.guild.id]["bots"].discard(role.id)

        embed = discord.Embed(
            title="[BOT AUTOROLE REMOVED]",
            description=f"Removed {role.mention} from bot autoroles.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_bots.command(name="list")
    @commands.guild_only()
    async def ar_bots_list(self, ctx: commands.Context):
        """List active bot autoroles."""
        cfg = self._cache.get(ctx.guild.id, {}).get("bots", set())
        if not cfg:
            return await ctx.send(embed=discord.Embed(title="[NO BOT AUTOROLES]", description="Zero roles configured.", color=ACCENT_COLOR))

        lines = [f"• <@&{rid}> (`{rid}`)" for rid in cfg]
        embed = discord.Embed(title="[ACTIVE BOT AUTOROLES]", description="\n".join(lines), color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_bots.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_bots_clear(self, ctx: commands.Context):
        """Clear all bot autoroles."""
        await db.execute("DELETE FROM autoroles WHERE guild_id = ? AND role_type = 'bots'", ctx.guild.id)
        if ctx.guild.id in self._cache:
            self._cache[ctx.guild.id]["bots"].clear()
        await ctx.send(embed=discord.Embed(title="[OK] Bot Autoroles Cleared", description="Removed all bot autoroles.", color=ACCENT_COLOR))

    @ar_bots.command(name="test")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def ar_bots_test(self, ctx: commands.Context, member: discord.Member):
        """Simulate bot autorole application on a bot account."""
        if not member.bot:
            return await ctx.send("[ERROR] Target member must be a bot account.")
        cfg = self._cache.get(ctx.guild.id, {}).get("bots", set())
        roles = [ctx.guild.get_role(r) for r in cfg if ctx.guild.get_role(r)]
        if not roles:
            return await ctx.send("[INFO] No bot autoroles configured.")
        await member.add_roles(*roles, reason="Autorole Test")
        await ctx.send(f"[OK] Applied {len(roles)} bot autoroles to {member.mention}.")

    @autorole_group.command(name="show", aliases=["config"])
    @commands.guild_only()
    async def ar_show(self, ctx: commands.Context):
        """Display overall autorole configuration."""
        humans = self._cache.get(ctx.guild.id, {}).get("humans", set())
        bots = self._cache.get(ctx.guild.id, {}).get("bots", set())

        h_str = ", ".join(f"<@&{r}>" for r in humans) if humans else "None configured"
        b_str = ", ".join(f"<@&{r}>" for r in bots) if bots else "None configured"

        embed = discord.Embed(
            title="[AUTOROLE CONFIGURATION]",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Human Autoroles", value=h_str, inline=False)
        embed.add_field(name="Bot Autoroles", value=b_str, inline=False)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @autorole_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_reset(self, ctx: commands.Context):
        """Clear all autoroles for this server."""
        await db.execute("DELETE FROM autoroles WHERE guild_id = ?", ctx.guild.id)
        self._cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[AUTOROLE RESET]",
            description="Cleared all human and bot autoroles.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Autorole(bot))
