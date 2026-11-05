"""
Global command error handler.
Translates exceptions into user-friendly responses and logs unexpected errors.
"""

import sys
import uuid
import traceback
import discord
from discord.ext import commands
from discord import app_commands

from ui import error_container, warning_container, denied_container
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
            return await ctx.reply(**warning_container(
                "Rate Limit Enforced",
                f"You are invoking this command too quickly. Please retry in **{retry_after}**.",
                footer="Zenith Rate Regulation"
            ), mention_author=False)

        # 3. User is missing required Discord permissions
        if isinstance(exc, commands.MissingPermissions):
            missing = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in exc.missing_permissions)
            return await ctx.reply(**denied_container(
                f"You lack the required guild permissions to execute this command:\n{missing}",
                footer="Zenith Security Bus"
            ), mention_author=False)

        # 4. Bot is missing required Discord permissions
        if isinstance(exc, commands.BotMissingPermissions):
            missing = ", ".join(f"`{p.replace('_', ' ').title()}`" for p in exc.missing_permissions)
            return await ctx.reply(**error_container(
                "Bot Missing Permissions",
                f"I require the following guild permissions to perform this action:\n{missing}",
                footer="Ensure bot role has required permissions"
            ), mention_author=False)

        # 5. Missing required command arguments
        if isinstance(exc, commands.MissingRequiredArgument):
            param = exc.param.name
            return await ctx.reply(**error_container(
                "Missing Parameter",
                f"Required argument `{param}` was omitted.\n**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                footer="Run 'help <command>' for syntax details"
            ), mention_author=False)

        # 6. Invalid argument type
        if isinstance(exc, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound, commands.RoleNotFound, commands.ChannelNotFound)):
            return await ctx.reply(**error_container(
                "Invalid Parameter",
                f"{str(exc)}\n**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                footer="Check parameter type and spelling"
            ), mention_author=False)

        # 7. Bot owner restricted
        if isinstance(exc, commands.NotOwner):
            return await ctx.reply(**denied_container(
                "This administrative tool is reserved exclusively for the bot developer.",
                footer="Access Violation Logged"
            ), mention_author=False)

        # 8. Unhandled Internal System Exceptions
        incident_id = str(uuid.uuid4())[:8].upper()
        error(f"[Incident {incident_id}] Unhandled error in command '{ctx.command}': {exc}", "errors")
        traceback_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        error(f"[Incident {incident_id}] Traceback:\n{traceback_str}", "errors")

        try:
            await ctx.reply(**error_container(
                "Internal System Error",
                f"An unexpected problem occurred while processing this command.\nReference code: **`ERR-{incident_id}`** (logged for review).",
                footer="Zenith Diagnostic Engine"
            ), mention_author=False)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
