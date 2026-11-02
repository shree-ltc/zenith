"""
cogs/owner.py - Developer Operations & Runtime Diagnostics for Zenith

Reserved exclusively for bot developers to hot-reload extensions, synchronize
slash command trees, evaluate live expressions, and manage deployments.
"""

import io
import sys
import time
import textwrap
import traceback
from pathlib import Path
from contextlib import redirect_stdout
from typing import Optional

import discord
from discord.ext import commands

from core.config import config
from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color
from core.logging import info, warn, error, success


class Owner(commands.Cog):
    """Developer operations and maintenance command suite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Enforces that only verified owner IDs can execute commands in this cog."""
        return ctx.author.id in self.bot.owner_ids

    # ═══════════════════════════════════════════════════════════════
    #  HOT-RELOAD SYSTEM
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="reload")
    async def reload_extension(self, ctx: commands.Context, extension: str):
        """Hot-reloads a single extension (e.g. `z!reload cogs.moderation`)."""
        target = f"cogs.{extension}" if not extension.startswith("cogs.") else extension
        try:
            await self.bot.reload_extension(target)
            success(f"Hot-reloaded extension: {target}", "dev")
            embed = ZenithEmbed.success("Extension Reloaded", f"Successfully reloaded `{target}`.")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            error(f"Failed to reload {target}: {e}", "dev")
            embed = ZenithEmbed.error("Reload Failed", f"```{e}```")
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

        desc = f"✓ Reloaded **{len(reloaded)}** modules: " + ", ".join(f"`{m}`" for m in reloaded)
        if failures:
            desc += "\n\n✕ **Failures:**\n" + "\n".join(f"• `{f}`" for f in failures)

        embed = ZenithEmbed(
            title="System Hot-Reload",
            description=desc,
            color=Color.SUCCESS if not failures else Color.WARNING
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  SLASH COMMAND TREE SYNCHRONIZATION
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

    # ═══════════════════════════════════════════════════════════════
    #  REMOTE CODE EVALUATION
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="eval", aliases=["e"])
    async def eval_command(self, ctx: commands.Context, *, code: str):
        """Evaluates asynchronous Python statements in the running bot context."""
        # Strip markdown fences if present
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
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  GUILD PREFIX ADJUSTMENT
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
