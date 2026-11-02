"""
cogs/automod.py - Real-Time Chat Security & Automod Subsystem for Zenith

Scans incoming message payloads with low latency for spam bursts, unauthorized
invite links, external URLs, excessive capitalization, and mass mentions.
"""

import re
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional, Any

import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class Automod(commands.Cog):
    """Real-time automated content filtering and chat regulation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory rate tracker: dict[guild_id, dict[user_id, list[float]]]
        self._message_times = defaultdict(lambda: defaultdict(list))
        self.INVITE_REGEX = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9]+", re.IGNORECASE)
        self.URL_REGEX = re.compile(r"https?://(?:www\.)?[a-zA-Z0-9.\-_]+(?:\.[a-zA-Z]{2,})+(?:/\S*)?", re.IGNORECASE)

    async def get_automod_config(self, guild_id: int) -> Optional[dict]:
        """Fetches guild automod configuration with caching."""
        cached = await db.cache_get(f"automod:{guild_id}")
        if cached:
            return None if cached == "none" else eval(cached)

        row = await db.fetchrow("SELECT * FROM automod_config WHERE guild_id = ?", guild_id)
        if not row:
            await db.cache_set(f"automod:{guild_id}", "none", ttl=300)
            return None

        cfg = dict(row)
        await db.cache_set(f"automod:{guild_id}", str(cfg), ttl=300)
        return cfg

    async def execute_punishment(self, message: discord.Message, rule_name: str, reason: str):
        """Removes offending message and enforces punishment."""
        # 1. Delete offending message
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except Exception:
            pass

        # 2. Inform the user in channel temporarily
        alert = await message.channel.send(
            embed=ZenithEmbed.warning(
                "Automod Triggered",
                f"{message.author.mention}, your message was filtered for **{rule_name}**.\n{reason}"
            )
        )

        # 3. Apply timeout if punishment is set to timeout
        cfg = await self.get_automod_config(message.guild.id)
        punish_mode = cfg.get("punishment", "delete") if cfg else "delete"

        if punish_mode == "timeout" and isinstance(message.author, discord.Member):
            try:
                until = datetime.now(timezone.utc) + timedelta(minutes=5)
                await message.author.timeout(until, reason=f"Zenith Automod: {rule_name}")
            except Exception:
                pass

        # Self-destruct warning notification after 5 seconds to reduce chat spam
        await asyncio.sleep(5)
        try:
            await alert.delete()
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Scans all non-bot guild messages for automod rule violations."""
        if not message.guild or message.author.bot:
            return

        # Administrators and members with Manage Messages bypass automod
        if message.author.guild_permissions.manage_messages:
            return

        cfg = await self.get_automod_config(message.guild.id)
        if not cfg:
            return

        content = message.content or ""

        # 1. Anti-Invite Check
        if cfg.get("anti_invites") and self.INVITE_REGEX.search(content):
            return await self.execute_punishment(message, "Discord Invite Link", "Discord server invite links are prohibited here.")

        # 2. Anti-Link Check (General URLs)
        if cfg.get("anti_links") and self.URL_REGEX.search(content):
            return await self.execute_punishment(message, "External Link", "Sending external web URLs is disabled in this server.")

        # 3. Anti-Caps Check (Requires minimum 8 characters, > 70% uppercase)
        if cfg.get("anti_caps") and len(content) >= 8:
            letters = [c for c in content if c.isalpha()]
            if letters:
                caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if caps_ratio > 0.70:
                    return await self.execute_punishment(message, "Excessive Caps", "Please refrain from shouting in capital letters.")

        # 4. Anti-Massmention Check
        mention_threshold = cfg.get("mention_threshold", 5)
        if cfg.get("anti_massmention"):
            total_mentions = len(message.mentions) + len(message.role_mentions)
            if total_mentions >= mention_threshold:
                return await self.execute_punishment(message, "Mass Mentions", f"Your message exceeded the mention limit ({mention_threshold}).")

        # 5. Anti-Spam (Burst check: 5 messages in 3 seconds)
        if cfg.get("anti_spam"):
            now = time.monotonic()
            history = self._message_times[message.guild.id][message.author.id]
            # Prune timestamps older than 3 seconds
            history = [t for t in history if now - t < 3.0]
            history.append(now)
            self._message_times[message.guild.id][message.author.id] = history

            if len(history) >= 5:
                return await self.execute_punishment(message, "Rapid Chat Spam", "You are sending messages too quickly.")

    # ═══════════════════════════════════════════════════════════════
    #  AUTOMOD MANAGEMENT COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="automod", aliases=["am"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod_dashboard(self, ctx: commands.Context):
        """Displays current server automod toggles and rules."""
        cfg = await self.get_automod_config(ctx.guild.id) or {}

        def format_state(val: bool) -> str:
            return "🟢 Enabled" if val else "🔴 Disabled"

        embed = ZenithEmbed(
            title="Zenith Automod Configuration",
            description="Automated message filters active on this server:\n",
            color=Color.PRIMARY
        )
        embed.add_field(name="Anti-Spam", value=format_state(cfg.get("anti_spam", False)), inline=True)
        embed.add_field(name="Anti-Links", value=format_state(cfg.get("anti_links", False)), inline=True)
        embed.add_field(name="Anti-Invites", value=format_state(cfg.get("anti_invites", False)), inline=True)
        embed.add_field(name="Anti-Caps", value=format_state(cfg.get("anti_caps", False)), inline=True)
        embed.add_field(name="Anti-Massmention", value=format_state(cfg.get("anti_massmention", False)), inline=True)
        embed.add_field(name="Punishment Action", value=f"`{cfg.get('punishment', 'delete').upper()}`", inline=True)

        embed.add_field(
            name="Configuration Commands",
            value=(
                f"• `{ctx.prefix}automod antispam <on|off>`\n"
                f"• `{ctx.prefix}automod antilinks <on|off>`\n"
                f"• `{ctx.prefix}automod antiinvites <on|off>`\n"
                f"• `{ctx.prefix}automod anticaps <on|off>`\n"
                f"• `{ctx.prefix}automod massmention <threshold>`\n"
                f"• `{ctx.prefix}automod punishment <delete|timeout>`"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    async def _update_rule(self, guild_id: int, column: str, value: Any):
        """Helper to upsert automod parameters."""
        if db.is_postgres:
            query = f"""
            INSERT INTO automod_config (guild_id, {column}) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET {column} = EXCLUDED.{column};
            """
        else:
            query = f"""
            INSERT INTO automod_config (guild_id, {column}) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {column} = excluded.{column};
            """
        await db.execute(query, guild_id, value)
        await db.cache_delete(f"automod:{guild_id}")

    @automod_dashboard.command(name="antispam")
    @commands.has_permissions(manage_guild=True)
    async def toggle_antispam(self, ctx: commands.Context, state: str):
        """Toggles rapid message burst protection (on/off)."""
        val = state.lower() in ("on", "true", "enable", "1")
        await self._update_rule(ctx.guild.id, "anti_spam", val)
        embed = ZenithEmbed.success("Automod Updated", f"Anti-Spam has been {'enabled' if val else 'disabled'}.")
        await ctx.reply(embed=embed, mention_author=False)

    @automod_dashboard.command(name="antilinks")
    @commands.has_permissions(manage_guild=True)
    async def toggle_antilinks(self, ctx: commands.Context, state: str):
        """Toggles external link filtering (on/off)."""
        val = state.lower() in ("on", "true", "enable", "1")
        await self._update_rule(ctx.guild.id, "anti_links", val)
        embed = ZenithEmbed.success("Automod Updated", f"Anti-Links has been {'enabled' if val else 'disabled'}.")
        await ctx.reply(embed=embed, mention_author=False)

    @automod_dashboard.command(name="antiinvites")
    @commands.has_permissions(manage_guild=True)
    async def toggle_antiinvites(self, ctx: commands.Context, state: str):
        """Toggles Discord server invite link blocking (on/off)."""
        val = state.lower() in ("on", "true", "enable", "1")
        await self._update_rule(ctx.guild.id, "anti_invites", val)
        embed = ZenithEmbed.success("Automod Updated", f"Anti-Invites has been {'enabled' if val else 'disabled'}.")
        await ctx.reply(embed=embed, mention_author=False)

    @automod_dashboard.command(name="anticaps")
    @commands.has_permissions(manage_guild=True)
    async def toggle_anticaps(self, ctx: commands.Context, state: str):
        """Toggles excessive capital letters filter (on/off)."""
        val = state.lower() in ("on", "true", "enable", "1")
        await self._update_rule(ctx.guild.id, "anti_caps", val)
        embed = ZenithEmbed.success("Automod Updated", f"Anti-Caps has been {'enabled' if val else 'disabled'}.")
        await ctx.reply(embed=embed, mention_author=False)

    @automod_dashboard.command(name="massmention")
    @commands.has_permissions(manage_guild=True)
    async def set_massmention(self, ctx: commands.Context, threshold: int):
        """Sets the maximum allowed mentions per message (0 to disable)."""
        if threshold < 0:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Number", "Threshold cannot be negative."), mention_author=False)

        await self._update_rule(ctx.guild.id, "anti_massmention", threshold > 0)
        await self._update_rule(ctx.guild.id, "mention_threshold", max(threshold, 3))
        embed = ZenithEmbed.success("Automod Updated", f"Mass mention limit set to **{threshold}** mentions.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Automod(bot))
