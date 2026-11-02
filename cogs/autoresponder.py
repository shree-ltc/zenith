"""
Custom Autoresponder System for Zenith.
Supports dynamic message triggers with contextual placeholder variables and channel burst protection.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db
from core.security import is_authorized_admin

ACCENT_COLOR = 0x0F0F13


class Autoresponder(commands.Cog):
    """Dynamic custom automated responses based on message keywords."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # RAM Cache: {guild_id: {trigger_lowercase: response_text}}
        self._cache: Dict[int, Dict[str, str]] = {}
        self._last_trigger: Dict[int, float] = {}

    async def cog_load(self) -> None:
        """Load all guild autoresponses into RAM."""
        rows = await db.fetch("SELECT guild_id, trigger, response FROM autoresponses")
        for r in rows:
            gid = r["guild_id"]
            if gid not in self._cache:
                self._cache[gid] = {}
            self._cache[gid][r["trigger"].lower()] = r["response"]

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.content:
            return

        guild_responses = self._cache.get(message.guild.id)
        if not guild_responses:
            return

        # Cooldown per channel (1.5 seconds) to prevent infinite message loops
        now = time.monotonic()
        if now - self._last_trigger.get(message.channel.id, 0.0) < 1.5:
            return

        content_lower = message.content.strip().lower()
        response = guild_responses.get(content_lower)

        # Check if full word matches if exact match isn't present
        if not response:
            words = content_lower.split()
            for word in words:
                if word in guild_responses:
                    response = guild_responses[word]
                    break

        if not response:
            return

        self._last_trigger[message.channel.id] = now

        # Placeholder substitutions
        formatted = response.replace("{user}", str(message.author))
        formatted = formatted.replace("{user.mention}", message.author.mention)
        formatted = formatted.replace("{user.name}", message.author.name)
        formatted = formatted.replace("{guild}", message.guild.name)
        formatted = formatted.replace("{guild.name}", message.guild.name)
        formatted = formatted.replace("{members}", str(message.guild.member_count))

        try:
            await message.channel.send(formatted)
        except Exception:
            pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="autoresponder", aliases=["ar"], invoke_without_command=True)
    @commands.guild_only()
    async def ar_group(self, ctx: commands.Context):
        """Autoresponder system overview and commands."""
        embed = discord.Embed(
            title="[AUTORESPONDER SYSTEM]",
            description="Automate text replies based on incoming message triggers.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}ar add <trigger> <response>` - Register a trigger\n"
                f"`{ctx.prefix}ar remove <trigger>` - Delete a trigger\n"
                f"`{ctx.prefix}ar list` - Display registered responses\n"
                f"`{ctx.prefix}ar reset` - Clear all server autoresponses"
            ),
            inline=False
        )
        embed.add_field(
            name="Supported Variables",
            value="`{user}`, `{user.mention}`, `{user.name}`, `{guild}`, `{members}`",
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ar_add(self, ctx: commands.Context, trigger: str, *, response: str):
        """Add a custom autoresponse keyword."""
        trigger_clean = trigger.strip().lower()
        if len(trigger_clean) > 100:
            return await ctx.send(embed=discord.Embed(title="[INVALID LENGTH]", description="Trigger text must be under 100 characters.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO autoresponses (guild_id, trigger, response) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, trigger) DO UPDATE SET response = excluded.response
            """,
            ctx.guild.id, trigger_clean, response
        )

        if ctx.guild.id not in self._cache:
            self._cache[ctx.guild.id] = {}
        self._cache[ctx.guild.id][trigger_clean] = response

        embed = discord.Embed(
            title="[AUTORESPONSE REGISTERED]",
            description=f"**Trigger:** `{trigger_clean}`\n**Response:** {response}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ar_remove(self, ctx: commands.Context, *, trigger: str):
        """Remove a custom autoresponse keyword."""
        trigger_clean = trigger.strip().lower()
        await db.execute("DELETE FROM autoresponses WHERE guild_id = ? AND trigger = ?", ctx.guild.id, trigger_clean)

        if ctx.guild.id in self._cache:
            self._cache[ctx.guild.id].pop(trigger_clean, None)

        embed = discord.Embed(
            title="[AUTORESPONSE REMOVED]",
            description=f"Deleted trigger `{trigger_clean}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_group.command(name="list")
    @commands.guild_only()
    async def ar_list(self, ctx: commands.Context):
        """List all autoresponses registered in this server."""
        guild_responses = self._cache.get(ctx.guild.id, {})
        if not guild_responses:
            return await ctx.send(embed=discord.Embed(
                title="[NO AUTORESPONSES]",
                description=f"Zero triggers configured. Add one with `{ctx.prefix}ar add <trigger> <response>`.",
                color=ACCENT_COLOR
            ))

        lines = []
        for i, (trig, resp) in enumerate(sorted(guild_responses.items()), 1):
            short_resp = resp if len(resp) <= 40 else f"{resp[:37]}..."
            lines.append(f"`{i:02d}.` **{trig}** -> `{short_resp}`")

        embed = discord.Embed(
            title=f"[REGISTERED AUTORESPONSES - {len(lines)}]",
            description="\n".join(lines[:25]),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def ar_reset(self, ctx: commands.Context):
        """Clear all autoresponses for this server."""
        await db.execute("DELETE FROM autoresponses WHERE guild_id = ?", ctx.guild.id)
        self._cache.pop(ctx.guild.id, None)

        embed = discord.Embed(
            title="[AUTORESPONDER RESET]",
            description="All custom autoresponses have been deleted.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @ar_group.command(name="raw")
    @commands.guild_only()
    async def ar_raw(self, ctx: commands.Context, *, trigger: str):
        """View raw unformatted text of an autoresponse."""
        t_clean = trigger.lower().strip()
        resp = self._cache.get(ctx.guild.id, {}).get(t_clean)
        if not resp:
            return await ctx.send(f"[ERROR] Trigger `{t_clean}` was not found.")
        await ctx.send(f"```{discord.utils.escape_markdown(resp)}```")

    @ar_group.command(name="edit")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def ar_edit(self, ctx: commands.Context, trigger: str, *, new_response: str):
        """Update an existing autoresponse message."""
        t_clean = trigger.lower().strip()
        if t_clean not in self._cache.get(ctx.guild.id, {}):
            return await ctx.send(f"[ERROR] Trigger `{t_clean}` does not exist. Use `ar add` first.")

        await db.execute("UPDATE autoresponses SET response = ? WHERE guild_id = ? AND trigger = ?", new_response, ctx.guild.id, t_clean)
        self._cache[ctx.guild.id][t_clean] = new_response
        await ctx.send(embed=discord.Embed(title="[OK] Autoresponse Updated", description=f"Updated response for `{t_clean}`.", color=ACCENT_COLOR))

    @ar_group.command(name="test")
    @commands.guild_only()
    async def ar_test(self, ctx: commands.Context, *, trigger: str):
        """Simulate an autoresponse trigger and display output."""
        t_clean = trigger.lower().strip()
        resp = self._cache.get(ctx.guild.id, {}).get(t_clean)
        if not resp:
            return await ctx.send(f"[ERROR] Trigger `{t_clean}` was not found.")

        output = self._format_response(resp, ctx.author, ctx.guild, ctx.channel)
        await ctx.send(f"[SIMULATED OUTPUT]\n{output}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Autoresponder(bot))
