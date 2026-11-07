"""
No-Prefix Authorization System for Zenith.
Allows authorized users to execute commands without typing any prefix.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional
import discord
from discord.ext import commands

from core.database import db
from core.config import config

ACCENT_COLOR = 0x0F0F13


class NoPrefix(commands.Cog):
    """Manages users authorized to run Zenith commands without a prefix."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self) -> None:
        """Load no-prefix user IDs into bot memory."""
        rows = await db.fetch("SELECT user_id FROM noprefix")
        for r in rows:
            self.bot.noprefix_users.add(r["user_id"])

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="noprefix", aliases=["np", "nopre", "nop"], invoke_without_command=True)
    async def noprefix_group(self, ctx: commands.Context):
        """No-prefix authorization controls."""
        if ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Bot Developers.", color=ACCENT_COLOR))

        embed = discord.Embed(
            title="[NO-PREFIX AUTHORIZATION]",
            description="Authorize VIP accounts to execute commands without prepending a prefix.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}np add <@user>` - Authorize user\n"
                f"`{ctx.prefix}np remove <@user>` - Revoke authorization\n"
                f"`{ctx.prefix}np list` - List authorized users\n"
                f"`{ctx.prefix}np reset` - Clear all authorizations"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @noprefix_group.command(name="add")
    async def np_add(self, ctx: commands.Context, user: discord.User):
        """Authorize a user for no-prefix command execution."""
        if ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Bot Developers.", color=ACCENT_COLOR))

        await db.execute("INSERT INTO noprefix (user_id) VALUES (?) ON CONFLICT DO NOTHING", user.id)
        self.bot.noprefix_users.add(user.id)

        embed = discord.Embed(
            title="[NO-PREFIX AUTHORIZED]",
            description=f"{user.mention} (`{user.id}`) can now execute commands without a prefix.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @noprefix_group.command(name="remove", aliases=["rm", "del"])
    async def np_remove(self, ctx: commands.Context, user: discord.User):
        """Revoke no-prefix command authorization."""
        if ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Bot Developers.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM noprefix WHERE user_id = ?", user.id)
        self.bot.noprefix_users.discard(user.id)

        embed = discord.Embed(
            title="[NO-PREFIX REVOKED]",
            description=f"Revoked no-prefix authorization for {user.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @noprefix_group.command(name="list")
    async def np_list(self, ctx: commands.Context):
        """List all users authorized for no-prefix execution."""
        if ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Bot Developers.", color=ACCENT_COLOR))

        users = self.bot.noprefix_users
        if not users:
            desc = "No users are currently granted no-prefix authorization."
        else:
            desc = "\n".join(f"• <@{uid}> (`{uid}`)" for uid in sorted(users))

        embed = discord.Embed(
            title="[NO-PREFIX DIRECTORY]",
            description=desc,
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @noprefix_group.command(name="reset")
    async def np_reset(self, ctx: commands.Context):
        """Reset all no-prefix authorizations."""
        if ctx.author.id not in config.OWNER_IDS:
            return await ctx.send(embed=discord.Embed(title="[ACCESS DENIED]", description="Restricted to Bot Developers.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM noprefix")
        self.bot.noprefix_users.clear()

        embed = discord.Embed(
            title="[NO-PREFIX RESET]",
            description="All no-prefix authorizations have been cleared.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(NoPrefix(bot))
