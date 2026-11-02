"""
core/errors.py - Bulletproof Global Error Handling System for Zenith

Intercepts and handles every command failure gracefully, translating cryptic
exceptions into polished, helpful interface embeds while logging full tracebacks.
"""

import sys
import uuid
import traceback
import discord
from discord.ext import commands
from discord import app_commands

from ui.embeds import ZenithEmbed
from core.logging import error, warn


class ErrorHandler(commands.Cog):
    """Listens for global command errors across prefixes and slash interactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exc: commands.CommandError):
        """Dispatches user-friendly responses for standard prefix command failures."""
        # Unwrap invoke errors
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original

        # 1. Silently ignore command not found to prevent spam
        if isinstance(exc, commands.CommandNotFound):
            return

        # 2. Cooldown timer exceeded
        if isinstance(exc, commands.CommandOnCooldown):
            retry_after = f"{exc.retry_after:.1f}s" if exc.retry_after < 60 else f"{int(exc.retry_after // 60)}m {int(exc.retry_after % 60)}s"
            embed = ZenithEmbed.warning(
                "Slow Down",
                f"You are invoking this command too quickly. Please retry in **{retry_after}**."
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 3. User is missing required Discord permissions
        if isinstance(exc, commands.MissingPermissions):
            missing = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in exc.missing_permissions)
            embed = ZenithEmbed.error(
                "Missing Permissions",
                f"You do not possess the necessary permissions to execute this command:\n{missing}"
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 4. Bot is missing required Discord permissions
        if isinstance(exc, commands.BotMissingPermissions):
            missing = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in exc.missing_permissions)
            embed = ZenithEmbed.error(
                "Bot Missing Permissions",
                f"I require the following guild permissions to perform this action:\n{missing}"
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 5. Missing required command arguments
        if isinstance(exc, commands.MissingRequiredArgument):
            param = exc.param.name
            embed = ZenithEmbed.error(
                "Missing Argument",
                f"Required parameter `{param}` was omitted.\n"
                f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 6. Invalid argument type (e.g., string passed where member expected)
        if isinstance(exc, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound, commands.RoleNotFound, commands.ChannelNotFound)):
            embed = ZenithEmbed.error(
                "Invalid Parameter",
                f"{str(exc)}\n"
                f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`"
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 7. Bot owner restricted
        if isinstance(exc, commands.NotOwner):
            embed = ZenithEmbed.error(
                "Developer Only",
                "This administrative tool is reserved exclusively for the bot developer."
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # 8. Unhandled Internal System Exceptions
        incident_id = str(uuid.uuid4())[:8].upper()
        error(f"[Incident {incident_id}] Unhandled error in command '{ctx.command}': {exc}", "errors")
        traceback_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        error(f"[Incident {incident_id}] Traceback:\n{traceback_str}", "errors")

        embed = ZenithEmbed.error(
            "Internal System Error",
            f"An unexpected problem occurred while processing this command.\n"
            f"Reference code: **`ERR-{incident_id}`** (logged for review)."
        )
        try:
            await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
