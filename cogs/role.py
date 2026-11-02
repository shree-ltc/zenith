"""
Comprehensive Role Management System for Zenith.
Includes individual role toggling, role editing, and safe rate-limited mass role utilities.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import asyncio
from typing import Optional, Callable
import discord
from discord.ext import commands

from core.security import is_authorized_admin, is_dangerous_role, validate_role_hierarchy
from core.config import config

ACCENT_COLOR = 0x0F0F13


class Role(commands.Cog):
    """Complete role administration and mass assignment suite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _check_role_manageable(
        self,
        ctx: commands.Context,
        role: discord.Role,
        is_removal: bool = False
    ) -> tuple[bool, str]:
        """Validates role hierarchy against actor and bot."""
        return validate_role_hierarchy(ctx.author, role, is_removal=is_removal)

    async def _safe_mass_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
        filter_fn: Callable[[discord.Member], bool],
        action: str,  # "add" or "remove"
        target_label: str
    ) -> None:
        """Executes a mass role assignment/removal safely with rate limiting and progress updates."""
        # 1. Permission check: Mass operations strictly limited to Server Owner / Extra Owner
        if not await is_authorized_admin(ctx.author.id, ctx.guild, self.bot):
            embed = discord.Embed(
                title="[ACCESS DENIED]",
                description="Mass role actions are strictly restricted to the Server Owner and Extra Owners.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        # 2. Safety check: Never mass assign roles with dangerous administrative permissions
        if action == "add" and is_dangerous_role(role):
            embed = discord.Embed(
                title="[SECURITY VIOLATION]",
                description="Roles with administrative or dangerous permissions cannot be mass assigned.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        # 3. Role hierarchy check
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            embed = discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR)
            return await ctx.send(embed=embed)

        # 4. Target compilation
        if action == "add":
            targets = [m for m in ctx.guild.members if filter_fn(m) and role not in m.roles]
            verb = "Assigning"
            done_verb = "Assigned"
        else:
            targets = [m for m in ctx.guild.members if filter_fn(m) and role in m.roles]
            verb = "Removing"
            done_verb = "Removed"

        if not targets:
            embed = discord.Embed(
                title="[NO TARGETS]",
                description=f"No members found matching the criteria for {target_label}.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        status_embed = discord.Embed(
            title=f"[MASS ROLE] {verb} Role...",
            description=(
                f"**Role:** {role.mention}\n"
                f"**Target Scope:** {target_label}\n"
                f"**Total Targets:** `{len(targets)}` members\n"
                f"Processing with safe rate limits..."
            ),
            color=ACCENT_COLOR
        )
        status_embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        msg = await ctx.send(embed=status_embed)

        success_count = 0
        failed_count = 0

        for member in targets:
            try:
                if action == "add":
                    await member.add_roles(role, reason=f"Zenith Mass Role ({target_label}) [{ctx.author}]")
                else:
                    await member.remove_roles(role, reason=f"Zenith Mass Remove ({target_label}) [{ctx.author}]")
                success_count += 1
            except (discord.Forbidden, discord.HTTPException):
                failed_count += 1

            # Prevent Discord rate limit spikes
            await asyncio.sleep(0.35)

        done_embed = discord.Embed(
            title=f"[MASS ROLE COMPLETE] {done_verb} Role",
            description=(
                f"**Role:** {role.mention}\n"
                f"**Target Scope:** {target_label}\n"
                f"**Successfully Updated:** `{success_count}` members\n"
                f"**Failed / Skipped:** `{failed_count}` members\n"
                f"**Moderator:** {ctx.author}"
            ),
            color=ACCENT_COLOR
        )
        done_embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        try:
            await msg.edit(embed=done_embed)
        except Exception:
            await ctx.send(embed=done_embed)

    # ---------------------------------------------------------
    # MAIN ROLE GROUP & SUBCOMMANDS
    # ---------------------------------------------------------

    @commands.group(name="role", aliases=["r"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_group(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None
    ):
        """Toggle a role on a user, or view role module commands."""
        # Case 1: No arguments provided -> show role suite help
        if member is None:
            embed = discord.Embed(
                title="[ROLE MANAGEMENT MODULE]",
                description="Manage server roles, toggle assignments, or execute mass role operations.",
                color=ACCENT_COLOR
            )
            embed.add_field(
                name="Single User Commands",
                value=(
                    f"`{ctx.prefix}role <user> <role>` - Toggle role on a user\n"
                    f"`{ctx.prefix}role add <user> <role>` - Add role to user\n"
                    f"`{ctx.prefix}role remove <user> <role>` - Remove role from user\n"
                    f"`{ctx.prefix}role create <name> [hex]` - Create a new role\n"
                    f"`{ctx.prefix}role delete <role>` - Delete a role\n"
                    f"`{ctx.prefix}role rename <role> <name>` - Rename a role\n"
                    f"`{ctx.prefix}role color <role> <hex>` - Change role color\n"
                    f"`{ctx.prefix}role hoist <role> [true/false]` - Toggle hoist display"
                ),
                inline=False
            )
            embed.add_field(
                name="Mass Role Commands (Owner Only)",
                value=(
                    f"`{ctx.prefix}role all <role>` - Assign role to all members\n"
                    f"`{ctx.prefix}role humans <role>` - Assign role to all humans\n"
                    f"`{ctx.prefix}role bots <role>` - Assign role to all bots\n"
                    f"`{ctx.prefix}rrole <role>` / `{ctx.prefix}rroleall <role>` - Remove from all members\n"
                    f"`{ctx.prefix}rrolehumans <role>` - Remove from all humans\n"
                    f"`{ctx.prefix}rrolebots <role>` - Remove from all bots"
                ),
                inline=False
            )
            embed.set_footer(text="Zenith Role Suite | Developed by Shree")
            return await ctx.send(embed=embed)

        # Case 2: Member provided without role
        if role is None:
            embed = discord.Embed(
                title="[INVALID SYNTAX]",
                description=f"Usage: `{ctx.prefix}role <@user> <@role>` to toggle, or `{ctx.prefix}role help`.",
                color=ACCENT_COLOR
            )
            return await ctx.send(embed=embed)

        # Case 3: Both provided -> Toggle role
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            embed = discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR)
            return await ctx.send(embed=embed)

        if role in member.roles:
            await member.remove_roles(role, reason=f"Zenith Role Toggle [{ctx.author}]")
            action = "Removed"
        else:
            await member.add_roles(role, reason=f"Zenith Role Toggle [{ctx.author}]")
            action = "Added"

        embed = discord.Embed(
            title=f"[ROLE {action.upper()}]",
            description=f"{action} {role.mention} for {member.mention}.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_add(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        """Add a role to a specific member."""
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        if role in member.roles:
            return await ctx.send(embed=discord.Embed(
                title="[ROLE ALREADY ASSIGNED]",
                description=f"{member.mention} already possesses the role {role.mention}.",
                color=ACCENT_COLOR
            ))

        await member.add_roles(role, reason=f"Zenith Role Add [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE ADDED]",
            description=f"Added {role.mention} to {member.mention}.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="remove", aliases=["rm"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_remove(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        """Remove a role from a specific member."""
        ok, err = self._check_role_manageable(ctx, role, is_removal=True)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        if role not in member.roles:
            return await ctx.send(embed=discord.Embed(
                title="[ROLE NOT ASSIGNED]",
                description=f"{member.mention} does not have the role {role.mention}.",
                color=ACCENT_COLOR
            ))

        await member.remove_roles(role, reason=f"Zenith Role Remove [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE REMOVED]",
            description=f"Removed {role.mention} from {member.mention}.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="create")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_create(self, ctx: commands.Context, name: str, color_hex: Optional[str] = None):
        """Create a new role with an optional hex color."""
        colour = discord.Colour.default()
        if color_hex:
            try:
                colour = discord.Colour(int(color_hex.lstrip("#"), 16))
            except ValueError:
                return await ctx.send(embed=discord.Embed(
                    title="[INVALID COLOR]",
                    description="Please provide a valid hex color code (e.g. `#5865F2`).",
                    color=ACCENT_COLOR
                ))

        role = await ctx.guild.create_role(name=name, colour=colour, reason=f"Zenith Role Create [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE CREATED]",
            description=f"Successfully created role {role.mention} (`{role.id}`).\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="delete")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_delete(self, ctx: commands.Context, role: discord.Role):
        """Delete an existing role."""
        ok, err = self._check_role_manageable(ctx, role, is_removal=True)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        role_name = role.name
        await role.delete(reason=f"Zenith Role Delete [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE DELETED]",
            description=f"Deleted role `{role_name}`.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="rename")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_rename(self, ctx: commands.Context, role: discord.Role, *, new_name: str):
        """Rename an existing role."""
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        old_name = role.name
        await role.edit(name=new_name, reason=f"Zenith Role Rename [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE RENAMED]",
            description=f"Renamed role from `{old_name}` to {role.mention}.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="color", aliases=["colour"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_color(self, ctx: commands.Context, role: discord.Role, color_hex: str):
        """Change the color of an existing role."""
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        try:
            colour = discord.Colour(int(color_hex.lstrip("#"), 16))
        except ValueError:
            return await ctx.send(embed=discord.Embed(
                title="[INVALID COLOR]",
                description="Please provide a valid hex color code (e.g. `#FF0000`).",
                color=ACCENT_COLOR
            ))

        await role.edit(colour=colour, reason=f"Zenith Role Color Change [{ctx.author}]")
        embed = discord.Embed(
            title="[ROLE COLOR UPDATED]",
            description=f"Updated color for {role.mention} to `#{color_hex.lstrip('#').upper()}`.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @role_group.command(name="hoist")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_hoist(self, ctx: commands.Context, role: discord.Role, hoist: Optional[bool] = None):
        """Toggle or set whether a role is hoisted separately in member list."""
        ok, err = self._check_role_manageable(ctx, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        new_hoist = not role.hoist if hoist is None else hoist
        await role.edit(hoist=new_hoist, reason=f"Zenith Role Hoist Change [{ctx.author}]")
        status = "enabled (hoisted)" if new_hoist else "disabled (unhoisted)"
        embed = discord.Embed(
            title="[ROLE HOIST UPDATED]",
            description=f"Hoist display for {role.mention} is now {status}.\n**Moderator:** {ctx.author}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Role Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # MASS ROLE ASSIGNMENT (ALL / HUMANS / BOTS)
    # ---------------------------------------------------------

    @role_group.command(name="all")
    @commands.guild_only()
    async def role_all(self, ctx: commands.Context, role: discord.Role):
        """Assign a role to all members in the server."""
        await self._safe_mass_role(ctx, role, lambda m: True, "add", "All Members")

    @role_group.command(name="humans")
    @commands.guild_only()
    async def role_humans(self, ctx: commands.Context, role: discord.Role):
        """Assign a role to all human members in the server."""
        await self._safe_mass_role(ctx, role, lambda m: not m.bot, "add", "Human Members")

    @role_group.command(name="bots")
    @commands.guild_only()
    async def role_bots(self, ctx: commands.Context, role: discord.Role):
        """Assign a role to all bot accounts in the server."""
        await self._safe_mass_role(ctx, role, lambda m: m.bot, "add", "Bot Accounts")

    @role_group.command(name="mentionable", aliases=["mention"])
    @commands.guild_only()
    async def role_mentionable(self, ctx: commands.Context, role: discord.Role, mentionable: Optional[bool] = None):
        """Toggle or set whether a role is mentionable by everyone."""
        if not await self._validate_role_hierarchy(ctx, role):
            return

        new_val = not role.mentionable if mentionable is None else mentionable
        try:
            await role.edit(mentionable=new_val, reason=f"Modified by {ctx.author}")
            state_str = "mentionable" if new_val else "not mentionable"
            await ctx.send(embed=discord.Embed(
                title="[OK] Role Updated",
                description=f"Role {role.mention} is now `{state_str}`.",
                color=ACCENT_COLOR
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[ERROR]", description=f"Failed to update role: {e}", color=ACCENT_COLOR))

    @role_group.command(name="duplicate", aliases=["clone"])
    @commands.guild_only()
    async def role_duplicate(self, ctx: commands.Context, role: discord.Role, *, new_name: Optional[str] = None):
        """Clone an existing role's permissions and color."""
        name = new_name or f"{role.name} Copy"
        try:
            new_role = await ctx.guild.create_role(
                name=name,
                permissions=role.permissions,
                colour=role.colour,
                hoist=role.hoist,
                mentionable=role.mentionable,
                reason=f"Cloned from {role.name} by {ctx.author}"
            )
            await ctx.send(embed=discord.Embed(
                title="[OK] Role Cloned",
                description=f"Created {new_role.mention} copied from {role.mention}.",
                color=ACCENT_COLOR
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[ERROR]", description=f"Failed to clone role: {e}", color=ACCENT_COLOR))

    @role_group.command(name="strip", aliases=["clearroles"])
    @commands.guild_only()
    async def role_strip(self, ctx: commands.Context, member: discord.Member):
        """Remove all non-default roles from a member."""
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description="Cannot strip roles from members with equal or higher roles.", color=ACCENT_COLOR))

        roles_to_remove = [r for r in member.roles if not r.is_default() and r < ctx.guild.me.top_role]
        if not roles_to_remove:
            return await ctx.send(embed=discord.Embed(title="[INFO]", description="No removable roles found on member.", color=ACCENT_COLOR))

        try:
            await member.remove_roles(*roles_to_remove, reason=f"Roles stripped by {ctx.author}")
            await ctx.send(embed=discord.Embed(
                title="[OK] Roles Stripped",
                description=f"Removed **{len(roles_to_remove)}** roles from {member.mention}.",
                color=ACCENT_COLOR
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[ERROR]", description=f"Failed to strip roles: {e}", color=ACCENT_COLOR))

    @role_group.command(name="members", aliases=["inrole"])
    @commands.guild_only()
    async def role_members(self, ctx: commands.Context, role: discord.Role):
        """List members who have this role."""
        members = role.members
        if not members:
            return await ctx.send(embed=discord.Embed(title="[INFO]", description=f"No members possess {role.mention}.", color=ACCENT_COLOR))

        desc = ", ".join(m.mention for m in members[:40])
        if len(members) > 40:
            desc += f" *(+{len(members) - 40} more)*"

        embed = discord.Embed(
            title=f"[ROLE MEMBERS] @{role.name} ({len(members)})",
            description=desc,
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @role_group.command(name="permissions", aliases=["perms"])
    @commands.guild_only()
    async def role_permissions(self, ctx: commands.Context, role: discord.Role):
        """Audit granted permissions on a role."""
        granted = [name.replace("_", " ").title() for name, value in role.permissions if value]
        desc = ", ".join(granted) if granted else "No permissions granted"

        embed = discord.Embed(
            title=f"[ROLE PERMISSIONS] @{role.name} ({len(granted)})",
            description=desc,
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @role_group.command(name="position", aliases=["pos"])
    @commands.guild_only()
    async def role_position(self, ctx: commands.Context, role: discord.Role, new_position: int):
        """Move a role to a specific hierarchy index."""
        if not await self._validate_role_hierarchy(ctx, role):
            return

        try:
            await role.edit(position=new_position, reason=f"Moved by {ctx.author}")
            await ctx.send(embed=discord.Embed(
                title="[OK] Role Moved",
                description=f"Role {role.mention} position changed to `{new_position}`.",
                color=ACCENT_COLOR
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[ERROR]", description=f"Failed to move role: {e}", color=ACCENT_COLOR))

    @role_group.command(name="info")
    @commands.guild_only()
    async def role_info_cmd(self, ctx: commands.Context, role: discord.Role):
        """View metadata and settings for a role."""
        embed = discord.Embed(
            title=f"[ROLE INFO] @{role.name}",
            color=role.colour if role.colour.value != 0 else ACCENT_COLOR
        )
        embed.add_field(name="Role ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Color", value=f"`{str(role.colour).upper()}`", inline=True)
        embed.add_field(name="Members", value=f"`{len(role.members)}`", inline=True)
        embed.add_field(name="Position", value=f"`{role.position}`", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # MASS ROLE REMOVAL (RROLE / RROLEALL / RROLEHUMANS / RROLEBOTS)
    # ---------------------------------------------------------

    @commands.command(name="rrole", aliases=["rroleall"])
    @commands.guild_only()
    async def rrole_all(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from all members in the server."""
        await self._safe_mass_role(ctx, role, lambda m: True, "remove", "All Members")

    @commands.command(name="rrolehumans", aliases=["rrolehuman"])
    @commands.guild_only()
    async def rrole_humans(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from all human members in the server."""
        await self._safe_mass_role(ctx, role, lambda m: not m.bot, "remove", "Human Members")

    @commands.command(name="rrolebots", aliases=["rrolebot"])
    @commands.guild_only()
    async def rrole_bots(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from all bot accounts in the server."""
        await self._safe_mass_role(ctx, role, lambda m: m.bot, "remove", "Bot Accounts")


async def setup(bot: commands.Bot):
    await bot.add_cog(Role(bot))
