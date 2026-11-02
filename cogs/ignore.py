"""
Ignore & Blacklist Subsystem for Zenith.
Allows servers to mute bot commands in specific channels, block individual commands,
blacklist disruptive users, and configure staff bypass exceptions.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Set, Dict, Union
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin
from core.config import config

ACCENT_COLOR = 0x0F0F13


class Ignore(commands.Cog):
    """Channel, user, and command ignore controls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory sets for fast lookups
        self._channels: Dict[int, Set[int]] = {}
        self._commands: Dict[int, Set[str]] = {}
        self._users: Dict[int, Set[int]] = {}
        self._bypass: Dict[int, Set[int]] = {}

        # Register global check
        self.bot.add_check(self.global_ignore_check)

    def cog_unload(self):
        self.bot.remove_check(self.global_ignore_check)

    async def cog_load(self) -> None:
        """Preload ignore rules into RAM."""
        ch_rows = await db.fetch("SELECT guild_id, channel_id FROM ignored_channels")
        for r in ch_rows:
            gid = r["guild_id"]
            if gid not in self._channels:
                self._channels[gid] = set()
            self._channels[gid].add(r["channel_id"])

        cmd_rows = await db.fetch("SELECT guild_id, command_name FROM ignored_commands")
        for r in cmd_rows:
            gid = r["guild_id"]
            if gid not in self._commands:
                self._commands[gid] = set()
            self._commands[gid].add(r["command_name"].lower())

        u_rows = await db.fetch("SELECT guild_id, user_id FROM ignored_users")
        for r in u_rows:
            gid = r["guild_id"]
            if gid not in self._users:
                self._users[gid] = set()
            self._users[gid].add(r["user_id"])

        bp_rows = await db.fetch("SELECT guild_id, target_id FROM ignore_bypass")
        for r in bp_rows:
            gid = r["guild_id"]
            if gid not in self._bypass:
                self._bypass[gid] = set()
            self._bypass[gid].add(r["target_id"])

    # ---------------------------------------------------------
    # GLOBAL CHECK HOOK
    # ---------------------------------------------------------

    async def global_ignore_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return True

        # Bot owners and Server Owner always bypass ignore restrictions
        if ctx.author.id == ctx.guild.owner_id or ctx.author.id in config.OWNER_IDS:
            return True

        # Check bypass roles and users
        guild_bypass = self._bypass.get(ctx.guild.id, set())
        if ctx.author.id in guild_bypass:
            return True
        if any(r.id in guild_bypass for r in ctx.author.roles):
            return True

        # Check user blacklist
        if ctx.author.id in self._users.get(ctx.guild.id, set()):
            return False

        # Check channel blacklist (exempt ignore management command itself)
        if ctx.command and ctx.command.root_parent and ctx.command.root_parent.name in ("ignore", "unignore"):
            return True
        if ctx.command and ctx.command.name in ("ignore", "unignore"):
            return True

        if ctx.channel.id in self._channels.get(ctx.guild.id, set()):
            return False

        # Check command blacklist
        if ctx.command:
            cmd_name = ctx.command.qualified_name.lower()
            if cmd_name in self._commands.get(ctx.guild.id, set()) or ctx.command.name.lower() in self._commands.get(ctx.guild.id, set()):
                return False

        return True

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="ignore", invoke_without_command=True)
    @commands.guild_only()
    async def ignore_group(self, ctx: commands.Context):
        """Ignore system overview."""
        embed = discord.Embed(
            title="[IGNORE CONTROLS]",
            description="Mute bot commands in specific channels, disable commands, or blacklist disruptive users.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}ignore channel <#channel>` - Mute commands in a channel\n"
                f"`{ctx.prefix}unignore channel <#channel>` - Unmute channel\n"
                f"`{ctx.prefix}ignore command <name>` - Disable a command\n"
                f"`{ctx.prefix}unignore command <name>` - Re-enable command\n"
                f"`{ctx.prefix}ignore user <@user>` - Blacklist a user\n"
                f"`{ctx.prefix}unignore user <@user>` - Unblacklist user\n"
                f"`{ctx.prefix}ignore bypass <add/remove/list>` - Manage bypass exemptions"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # Channel subcommands
    @ignore_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Mute bot commands in a specific text channel."""
        await db.execute("INSERT INTO ignored_channels (guild_id, channel_id) VALUES (?, ?) ON CONFLICT DO NOTHING", ctx.guild.id, channel.id)
        if ctx.guild.id not in self._channels:
            self._channels[ctx.guild.id] = set()
        self._channels[ctx.guild.id].add(channel.id)

        embed = discord.Embed(title="[CHANNEL IGNORED]", description=f"Bot commands will now be ignored in {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="unignore")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def unignore_command(self, ctx: commands.Context, target: Union[discord.TextChannel, discord.Member, str]):
        """Unignore a channel, user, or command."""
        if isinstance(target, discord.TextChannel):
            await db.execute("DELETE FROM ignored_channels WHERE guild_id = ? AND channel_id = ?", ctx.guild.id, target.id)
            if ctx.guild.id in self._channels:
                self._channels[ctx.guild.id].discard(target.id)
            return await ctx.send(embed=discord.Embed(title="[CHANNEL RESTORED]", description=f"Commands unignored in {target.mention}.", color=ACCENT_COLOR))

        if isinstance(target, discord.Member):
            await db.execute("DELETE FROM ignored_users WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
            if ctx.guild.id in self._users:
                self._users[ctx.guild.id].discard(target.id)
            return await ctx.send(embed=discord.Embed(title="[USER RESTORED]", description=f"{target.mention} is no longer blacklisted.", color=ACCENT_COLOR))

        cmd_clean = target.lower().strip()
        await db.execute("DELETE FROM ignored_commands WHERE guild_id = ? AND command_name = ?", ctx.guild.id, cmd_clean)
        if ctx.guild.id in self._commands:
            self._commands[ctx.guild.id].discard(cmd_clean)
        await ctx.send(embed=discord.Embed(title="[COMMAND RESTORED]", description=f"Command `{cmd_clean}` is now re-enabled.", color=ACCENT_COLOR))

    # Command ignore
    @ignore_group.command(name="command", aliases=["cmd"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_cmd(self, ctx: commands.Context, command_name: str):
        """Disable a specific command in this server."""
        cmd_clean = command_name.lower().strip()
        if cmd_clean in ("ignore", "unignore", "help"):
            return await ctx.send(embed=discord.Embed(title="[RESTRICTED]", description="Core system commands cannot be ignored.", color=ACCENT_COLOR))

        await db.execute("INSERT INTO ignored_commands (guild_id, command_name) VALUES (?, ?) ON CONFLICT DO NOTHING", ctx.guild.id, cmd_clean)
        if ctx.guild.id not in self._commands:
            self._commands[ctx.guild.id] = set()
        self._commands[ctx.guild.id].add(cmd_clean)

        embed = discord.Embed(title="[COMMAND DISABLED]", description=f"Command `{cmd_clean}` has been disabled.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # User blacklist
    @ignore_group.command(name="user")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ignore_usr(self, ctx: commands.Context, user: discord.Member):
        """Blacklist a user from executing any bot commands."""
        if user.id == ctx.guild.owner_id or user.id in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[RESTRICTED]", description="Owners cannot be blacklisted.", color=ACCENT_COLOR))

        await db.execute("INSERT INTO ignored_users (guild_id, user_id) VALUES (?, ?) ON CONFLICT DO NOTHING", ctx.guild.id, user.id)
        if ctx.guild.id not in self._users:
            self._users[ctx.guild.id] = set()
        self._users[ctx.guild.id].add(user.id)

        embed = discord.Embed(title="[USER BLACKLISTED]", description=f"{user.mention} is now blocked from executing bot commands.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # Bypass
    @ignore_group.group(name="bypass", invoke_without_command=True)
    @commands.guild_only()
    async def bypass_group(self, ctx: commands.Context):
        """Manage ignore bypass roles and users."""
        bypass_ids = self._bypass.get(ctx.guild.id, set())
        if not bypass_ids:
            desc = "No bypass exemptions configured."
        else:
            desc = "\n".join(f"• <@&{i}> / <@{i}> (`{i}`)" for i in bypass_ids)

        embed = discord.Embed(title="[IGNORE BYPASS DIRECTORY]", description=desc, color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bypass_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_add(self, ctx: commands.Context, target: Union[discord.Role, discord.Member]):
        """Grant a role or user immunity from ignore restrictions."""
        target_type = "role" if isinstance(target, discord.Role) else "user"
        await db.execute("INSERT INTO ignore_bypass (guild_id, target_id, target_type) VALUES (?, ?, ?) ON CONFLICT DO NOTHING", ctx.guild.id, target.id, target_type)

        if ctx.guild.id not in self._bypass:
            self._bypass[ctx.guild.id] = set()
        self._bypass[ctx.guild.id].add(target.id)

        embed = discord.Embed(title="[BYPASS EXEMPTION GRANTED]", description=f"{target.mention} now bypasses all ignore rules.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bypass_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_remove(self, ctx: commands.Context, target: Union[discord.Role, discord.Member]):
        """Revoke ignore bypass immunity."""
        await db.execute("DELETE FROM ignore_bypass WHERE guild_id = ? AND target_id = ?", ctx.guild.id, target.id)
        if ctx.guild.id in self._bypass:
            self._bypass[ctx.guild.id].discard(target.id)

        embed = discord.Embed(title="[BYPASS EXEMPTION REVOKED]", description=f"Removed bypass exemption for {target.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bypass_group.command(name="list")
    @commands.guild_only()
    async def bypass_list(self, ctx: commands.Context):
        """List roles and users exempt from ignore rules."""
        exempt = self._bypass.get(ctx.guild.id, set())
        if not exempt:
            return await ctx.send(embed=discord.Embed(title="[BYPASS DIRECTORY]", description="No bypass exemptions configured.", color=ACCENT_COLOR))

        lines = [f"• <@{eid}> / <@&{eid}> (`{eid}`)" for eid in exempt]
        embed = discord.Embed(title=f"[BYPASS EXEMPTIONS] ({len(exempt)})", description="\n".join(lines), color=ACCENT_COLOR)
        await ctx.send(embed=embed)

    @bypass_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bypass_reset(self, ctx: commands.Context):
        """Clear all bypass exemptions."""
        await db.execute("DELETE FROM ignore_bypass WHERE guild_id = ?", ctx.guild.id)
        if ctx.guild.id in self._bypass:
            self._bypass[ctx.guild.id].clear()
        await ctx.send(embed=discord.Embed(title="[OK] Bypass Reset", description="Cleared all bypass rules.", color=ACCENT_COLOR))

    @ignore_group.command(name="list", aliases=["show"])
    @commands.guild_only()
    async def ignore_list(self, ctx: commands.Context):
        """List all channels, commands, and users ignored by Zenith."""
        chans = self._ignored_channels.get(ctx.guild.id, set())
        cmds = self._ignored_commands.get(ctx.guild.id, set())
        usrs = self._ignored_users.get(ctx.guild.id, set())

        embed = discord.Embed(
            title=f"[IGNORE MATRIX] {ctx.guild.name}",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Ignored Channels", value=", ".join(f"<#{c}>" for c in chans) if chans else "None", inline=False)
        embed.add_field(name="Ignored Commands", value=", ".join(f"`{c}`" for c in cmds) if cmds else "None", inline=False)
        embed.add_field(name="Ignored Users", value=", ".join(f"<@{u}>" for u in usrs) if usrs else "None", inline=False)
        await ctx.send(embed=embed)

    @ignore_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ignore_reset(self, ctx: commands.Context):
        """Purge all channel, user, and command ignores."""
        await db.execute("DELETE FROM ignored_channels WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM ignored_commands WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM ignored_users WHERE guild_id = ?", ctx.guild.id)
        self._ignored_channels.pop(ctx.guild.id, None)
        self._ignored_commands.pop(ctx.guild.id, None)
        self._ignored_users.pop(ctx.guild.id, None)
        await ctx.send(embed=discord.Embed(title="[OK] Ignores Reset", description="Purged all active ignores for this server.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Ignore(bot))
