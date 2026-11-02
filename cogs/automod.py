"""
Enterprise-grade automated chat regulation and content moderation engine for Zenith.
Supports multi-filter threat detection: anti-spam, invites, links, caps, zalgo, attachments,
newlines, mass mentions, and dynamic keyword blacklists with whitelist bypasses.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional, Union

import discord
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13

INVITE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9]+",
    re.IGNORECASE
)
URL_REGEX = re.compile(
    r"https?://(?:www\.)?[a-zA-Z0-9.\-_]+(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?",
    re.IGNORECASE
)
ZALGO_REGEX = re.compile(r"[\u0300-\u036f\u0483-\u0489\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]{3,}")
EMOJI_REGEX = re.compile(r"<a?:[a-zA-Z0-9_]+:[0-9]+>|[\U00010000-\U0010ffff]")


class Automod(commands.Cog):
    """Real-time automated content filtering and server protection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory message velocity tracker: (guild_id, user_id) -> list[float]
        self._message_times = defaultdict(list)
        # Guild cache: guild_id -> dict
        self._filter_cache: dict[int, dict] = {}
        self._word_cache: dict[int, set[str]] = {}
        self._whitelist_cache: dict[int, set[int]] = {}

    async def _get_guild_filters(self, guild_id: int) -> dict:
        if guild_id in self._filter_cache:
            return self._filter_cache[guild_id]

        rows = await db.fetch("SELECT filter_name, enabled, action, threshold FROM automod_filters WHERE guild_id = ?", guild_id)
        filters = {r["filter_name"]: {"enabled": bool(r["enabled"]), "action": r["action"], "threshold": r["threshold"]} for r in rows}
        self._filter_cache[guild_id] = filters
        return filters

    async def _get_badwords(self, guild_id: int) -> set[str]:
        if guild_id in self._word_cache:
            return self._word_cache[guild_id]

        rows = await db.fetch("SELECT word FROM automod_words WHERE guild_id = ?", guild_id)
        words = {r["word"].lower() for r in rows}
        self._word_cache[guild_id] = words
        return words

    async def _get_whitelists(self, guild_id: int) -> set[int]:
        if guild_id in self._whitelist_cache:
            return self._whitelist_cache[guild_id]

        rows = await db.fetch("SELECT target_id FROM automod_whitelists WHERE guild_id = ?", guild_id)
        targets = {r["target_id"] for r in rows}
        self._whitelist_cache[guild_id] = targets
        return targets

    async def _is_whitelisted(self, message: discord.Message) -> bool:
        if not isinstance(message.author, discord.Member):
            return True
        if message.author.guild_permissions.administrator or message.author.id == message.guild.owner_id:
            return True
        if message.author.guild_permissions.manage_guild:
            return True

        whitelisted = await self._get_whitelists(message.guild.id)
        if message.channel.id in whitelisted or message.author.id in whitelisted:
            return True
        for role in message.author.roles:
            if role.id in whitelisted:
                return True
        return False

    async def _punish(self, message: discord.Message, filter_name: str, action: str, details: str):
        try:
            await message.delete()
        except Exception:
            pass

        # Perform action
        member = message.author
        if action == "timeout" and isinstance(member, discord.Member):
            try:
                until = discord.utils.utcnow() + timedelta(minutes=5)
                await member.timeout(until, reason=f"Automod: {filter_name}")
            except Exception:
                pass
        elif action == "kick" and isinstance(member, discord.Member):
            try:
                await member.kick(reason=f"Automod: {filter_name}")
            except Exception:
                pass

        # Send transient chat notice
        try:
            embed = discord.Embed(
                title=f"[AUTOMOD] {filter_name.upper()} Triggered",
                description=f"{member.mention}, your message violated chat guidelines ({details}). Action: `{action.upper()}`.",
                color=THEME_COLOR
            )
            notice = await message.channel.send(embed=embed)
            await notice.delete(delay=4)
        except Exception:
            pass

        # Send log to configured channel if present
        cfg = await db.fetchrow("SELECT log_channel FROM automod_config WHERE guild_id = ?", message.guild.id)
        if cfg and cfg["log_channel"]:
            log_ch = message.guild.get_channel(cfg["log_channel"])
            if log_ch:
                log_embed = discord.Embed(
                    title="[AUTOMOD AUDIT] Violation Intercepted",
                    color=THEME_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
                log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                log_embed.add_field(name="Rule", value=filter_name, inline=True)
                log_embed.add_field(name="Action Taken", value=action.upper(), inline=True)
                content_preview = message.content[:400] if message.content else "[No text content]"
                log_embed.add_field(name="Content", value=f"```{content_preview}```", inline=False)
                try:
                    await log_ch.send(embed=log_embed)
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Check bypass
        if await self._is_whitelisted(message):
            return

        filters = await self._get_guild_filters(message.guild.id)
        if not filters:
            return

        content = message.content or ""

        # 1. Anti-Invite
        inv_rule = filters.get("anti_invites")
        if inv_rule and inv_rule["enabled"] and INVITE_REGEX.search(content):
            await self._punish(message, "Anti-Invites", inv_rule["action"], "Discord server invite links prohibited")
            return

        # 2. Anti-Link
        link_rule = filters.get("anti_links")
        if link_rule and link_rule["enabled"] and URL_REGEX.search(content):
            await self._punish(message, "Anti-Links", link_rule["action"], "External links prohibited")
            return

        # 3. Bad Words / Keyword Blacklist
        words = await self._get_badwords(message.guild.id)
        if words:
            content_lower = content.lower()
            for w in words:
                if w in content_lower:
                    bw_rule = filters.get("badwords", {"action": "delete"})
                    await self._punish(message, "Blacklisted Word", bw_rule["action"], "Prohibited term detected")
                    return

        # 4. Anti-Caps
        caps_rule = filters.get("anti_caps")
        if caps_rule and caps_rule["enabled"] and len(content) >= 8:
            letters = [c for c in content if c.isalpha()]
            threshold = caps_rule.get("threshold", 70)
            if letters and (sum(1 for c in letters if c.isupper()) / len(letters) * 100) >= threshold:
                await self._punish(message, "Anti-Caps", caps_rule["action"], f"Uppercase exceeded {threshold}%")
                return

        # 5. Anti-Massmention
        mention_rule = filters.get("anti_massmention")
        if mention_rule and mention_rule["enabled"]:
            total_mentions = len(message.mentions) + len(message.role_mentions)
            limit = mention_rule.get("threshold", 5)
            if total_mentions >= limit:
                await self._punish(message, "Mass Mentions", mention_rule["action"], f"Mentions ({total_mentions}) exceeded limit ({limit})")
                return

        # 6. Anti-Emoji Spam
        emoji_rule = filters.get("anti_emojispam")
        if emoji_rule and emoji_rule["enabled"]:
            emojis = EMOJI_REGEX.findall(content)
            limit = emoji_rule.get("threshold", 6)
            if len(emojis) >= limit:
                await self._punish(message, "Emoji Spam", emoji_rule["action"], f"Emoji count ({len(emojis)}) exceeded limit ({limit})")
                return

        # 7. Anti-Zalgo
        zalgo_rule = filters.get("anti_zalgo")
        if zalgo_rule and zalgo_rule["enabled"] and ZALGO_REGEX.search(content):
            await self._punish(message, "Anti-Zalgo", zalgo_rule["action"], "Distorted zalgo characters detected")
            return

        # 8. Anti-Attachments
        att_rule = filters.get("anti_attachments")
        if att_rule and att_rule["enabled"] and message.attachments:
            await self._punish(message, "Anti-Attachments", att_rule["action"], "File attachments blocked in this channel")
            return

        # 9. Newline Spam
        newline_rule = filters.get("anti_newlines")
        if newline_rule and newline_rule["enabled"]:
            limit = newline_rule.get("threshold", 8)
            if content.count("\n") >= limit:
                await self._punish(message, "Newline Spam", newline_rule["action"], f"Newlines ({content.count(chr(10))}) exceeded limit ({limit})")
                return

        # 10. Character Limit
        charlimit_rule = filters.get("anti_charlimit")
        if charlimit_rule and charlimit_rule["enabled"]:
            limit = charlimit_rule.get("threshold", 1500)
            if len(content) > limit:
                await self._punish(message, "Character Limit", charlimit_rule["action"], f"Length ({len(content)}) exceeded limit ({limit})")
                return

        # 11. Velocity Anti-Spam
        spam_rule = filters.get("anti_spam")
        if spam_rule and spam_rule["enabled"]:
            now = time.monotonic()
            key = (message.guild.id, message.author.id)
            history = [t for t in self._message_times[key] if now - t < 3.0]
            history.append(now)
            self._message_times[key] = history
            threshold = spam_rule.get("threshold", 5)
            if len(history) >= threshold:
                await self._punish(message, "Anti-Spam", spam_rule["action"], "Message rate exceeded limit")
                return

    # ═══════════════════════════════════════════════════════════════
    #  COMMAND SUITE
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="automod", aliases=["am"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod_cmd(self, ctx: commands.Context):
        """View active automod configuration and filters."""
        filters = await self._get_guild_filters(ctx.guild.id)
        words = await self._get_badwords(ctx.guild.id)
        whitelists = await self._get_whitelists(ctx.guild.id)
        cfg = await db.fetchrow("SELECT log_channel FROM automod_config WHERE guild_id = ?", ctx.guild.id)

        embed = discord.Embed(
            title=f"[AUTOMOD] Security Matrix for {ctx.guild.name}",
            description="Autonomous moderation and content regulation rules.",
            color=THEME_COLOR
        )

        log_ch_str = f"<#{cfg['log_channel']}>" if (cfg and cfg["log_channel"]) else "`Not configured`"
        embed.add_field(name="Audit Log Channel", value=log_ch_str, inline=True)
        embed.add_field(name="Blacklisted Words", value=f"`{len(words)} registered`", inline=True)
        embed.add_field(name="Whitelisted Entities", value=f"`{len(whitelists)} registered`", inline=True)

        def _status(name: str) -> str:
            f = filters.get(name)
            if not f or not f["enabled"]:
                return "`Disabled`"
            thresh_str = f" ({f['threshold']})" if "threshold" in f and f["threshold"] else ""
            return f"`Enabled` -> `{f['action'].upper()}`{thresh_str}"

        embed.add_field(name="Anti-Spam", value=_status("anti_spam"), inline=True)
        embed.add_field(name="Anti-Invites", value=_status("anti_invites"), inline=True)
        embed.add_field(name="Anti-Links", value=_status("anti_links"), inline=True)
        embed.add_field(name="Anti-Caps", value=_status("anti_caps"), inline=True)
        embed.add_field(name="Mass Mentions", value=_status("anti_massmention"), inline=True)
        embed.add_field(name="Emoji Spam", value=_status("anti_emojispam"), inline=True)
        embed.add_field(name="Anti-Zalgo", value=_status("anti_zalgo"), inline=True)
        embed.add_field(name="Anti-Attachments", value=_status("anti_attachments"), inline=True)
        embed.add_field(name="Newline Spam", value=_status("anti_newlines"), inline=True)

        embed.set_footer(text=f"Use '{ctx.prefix}automod <rule> <on|off>' to toggle individual filters.")
        await ctx.reply(embed=embed, mention_author=False)

    async def _set_rule(self, guild_id: int, filter_name: str, enabled: bool, action: str = "delete", threshold: int = 5):
        await db.execute(
            """
            INSERT INTO automod_filters (guild_id, filter_name, enabled, action, threshold)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, filter_name) DO UPDATE SET
            enabled = excluded.enabled,
            action = excluded.action,
            threshold = excluded.threshold
            """ if not db.is_postgres else """
            INSERT INTO automod_filters (guild_id, filter_name, enabled, action, threshold)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, filter_name) DO UPDATE SET
            enabled = EXCLUDED.enabled,
            action = EXCLUDED.action,
            threshold = EXCLUDED.threshold
            """,
            guild_id, filter_name, enabled, action, threshold
        )
        self._filter_cache.pop(guild_id, None)

    @automod_cmd.command(name="antispam")
    @commands.has_permissions(manage_guild=True)
    async def am_antispam(self, ctx: commands.Context, state: str, threshold: int = 5, action: str = "delete"):
        """Configure anti-spam burst detection."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_spam", enabled, action.lower(), threshold)
        await ctx.reply(f"[OK] Anti-Spam filter set to `{'Enabled' if enabled else 'Disabled'}` (Limit: {threshold} msgs/3s, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="antiinvites", aliases=["antiinvite"])
    @commands.has_permissions(manage_guild=True)
    async def am_antiinvites(self, ctx: commands.Context, state: str, action: str = "delete"):
        """Configure discord server invite links blocking."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_invites", enabled, action.lower())
        await ctx.reply(f"[OK] Anti-Invites filter set to `{'Enabled' if enabled else 'Disabled'}` (Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="antilinks", aliases=["antilink"])
    @commands.has_permissions(manage_guild=True)
    async def am_antilinks(self, ctx: commands.Context, state: str, action: str = "delete"):
        """Configure external link filtering."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_links", enabled, action.lower())
        await ctx.reply(f"[OK] Anti-Links filter set to `{'Enabled' if enabled else 'Disabled'}` (Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="anticaps")
    @commands.has_permissions(manage_guild=True)
    async def am_anticaps(self, ctx: commands.Context, state: str, threshold_percent: int = 70, action: str = "delete"):
        """Configure excessive capital letters filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_caps", enabled, action.lower(), threshold_percent)
        await ctx.reply(f"[OK] Anti-Caps filter set to `{'Enabled' if enabled else 'Disabled'}` (Threshold: {threshold_percent}%, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="massmention")
    @commands.has_permissions(manage_guild=True)
    async def am_massmention(self, ctx: commands.Context, state: str, limit: int = 5, action: str = "delete"):
        """Configure mass mention limit filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_massmention", enabled, action.lower(), limit)
        await ctx.reply(f"[OK] Mass-Mention filter set to `{'Enabled' if enabled else 'Disabled'}` (Limit: {limit} mentions, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="emojispam")
    @commands.has_permissions(manage_guild=True)
    async def am_emojispam(self, ctx: commands.Context, state: str, limit: int = 6, action: str = "delete"):
        """Configure emoji spam threshold filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_emojispam", enabled, action.lower(), limit)
        await ctx.reply(f"[OK] Emoji-Spam filter set to `{'Enabled' if enabled else 'Disabled'}` (Limit: {limit} emojis, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="zalgo")
    @commands.has_permissions(manage_guild=True)
    async def am_zalgo(self, ctx: commands.Context, state: str, action: str = "delete"):
        """Configure zalgo / text glitch filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_zalgo", enabled, action.lower())
        await ctx.reply(f"[OK] Anti-Zalgo filter set to `{'Enabled' if enabled else 'Disabled'}` (Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="attachments")
    @commands.has_permissions(manage_guild=True)
    async def am_attachments(self, ctx: commands.Context, state: str, action: str = "delete"):
        """Configure attachment blocking filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_attachments", enabled, action.lower())
        await ctx.reply(f"[OK] Anti-Attachments filter set to `{'Enabled' if enabled else 'Disabled'}` (Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="newlines")
    @commands.has_permissions(manage_guild=True)
    async def am_newlines(self, ctx: commands.Context, state: str, limit: int = 8, action: str = "delete"):
        """Configure newline / wall of text filter."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_newlines", enabled, action.lower(), limit)
        await ctx.reply(f"[OK] Anti-Newlines filter set to `{'Enabled' if enabled else 'Disabled'}` (Limit: {limit} newlines, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="charlimit")
    @commands.has_permissions(manage_guild=True)
    async def am_charlimit(self, ctx: commands.Context, state: str, max_chars: int = 1500, action: str = "delete"):
        """Configure maximum message character length."""
        enabled = state.lower() in ("on", "true", "enable", "1")
        await self._set_rule(ctx.guild.id, "anti_charlimit", enabled, action.lower(), max_chars)
        await ctx.reply(f"[OK] Character Limit filter set to `{'Enabled' if enabled else 'Disabled'}` (Max: {max_chars} chars, Action: {action.upper()}).", mention_author=False)

    @automod_cmd.command(name="logging", aliases=["log"])
    @commands.has_permissions(manage_guild=True)
    async def am_logging(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or remove automod incident audit log channel."""
        ch_id = channel.id if channel else None
        await db.execute(
            """
            INSERT INTO automod_config (guild_id, log_channel) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel = excluded.log_channel
            """ if not db.is_postgres else """
            INSERT INTO automod_config (guild_id, log_channel) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel = EXCLUDED.log_channel
            """,
            ctx.guild.id, ch_id
        )
        if channel:
            await ctx.reply(f"[OK] Automod audit log destination set to {channel.mention}.", mention_author=False)
        else:
            await ctx.reply("[OK] Automod audit logging disabled.", mention_author=False)

    @automod_cmd.group(name="words", aliases=["badwords", "word"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def am_words_group(self, ctx: commands.Context):
        """Manage blacklisted keywords."""
        words = await self._get_badwords(ctx.guild.id)
        if not words:
            await ctx.reply("[INFO] No blacklisted words configured.", mention_author=False)
            return

        word_str = ", ".join(f"`{w}`" for w in sorted(words))
        if len(word_str) > 3900:
            word_str = word_str[:3900] + "..."
        embed = discord.Embed(
            title=f"[AUTOMOD] Blacklisted Words ({len(words)})",
            description=word_str,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @am_words_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def am_words_add(self, ctx: commands.Context, *, word: str):
        """Add a keyword to the automod blacklist."""
        clean = word.strip().lower()
        await db.execute(
            "INSERT INTO automod_words (guild_id, word) VALUES (?, ?) ON CONFLICT DO NOTHING",
            ctx.guild.id, clean
        )
        self._word_cache.pop(ctx.guild.id, None)
        await ctx.reply(f"[OK] Added `{clean}` to automod blacklisted terms.", mention_author=False)

    @am_words_group.command(name="remove", aliases=["delete", "del"])
    @commands.has_permissions(manage_guild=True)
    async def am_words_remove(self, ctx: commands.Context, *, word: str):
        """Remove a keyword from the automod blacklist."""
        clean = word.strip().lower()
        await db.execute("DELETE FROM automod_words WHERE guild_id = ? AND word = ?", ctx.guild.id, clean)
        self._word_cache.pop(ctx.guild.id, None)
        await ctx.reply(f"[OK] Removed `{clean}` from blacklist.", mention_author=False)

    @am_words_group.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def am_words_clear(self, ctx: commands.Context):
        """Purge all blacklisted keywords for this server."""
        await db.execute("DELETE FROM automod_words WHERE guild_id = ?", ctx.guild.id)
        self._word_cache.pop(ctx.guild.id, None)
        await ctx.reply("[OK] Cleared all blacklisted words.", mention_author=False)

    @automod_cmd.group(name="whitelist", aliases=["wl"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def am_whitelist_group(self, ctx: commands.Context):
        """View automod whitelist bypasses."""
        rows = await db.fetch("SELECT target_id, target_type FROM automod_whitelists WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            await ctx.reply("[INFO] No roles, channels, or users are whitelisted from automod.", mention_author=False)
            return

        entries = []
        for r in rows:
            t_type = r["target_type"]
            tid = r["target_id"]
            if t_type == "channel":
                entries.append(f"• Channel: <#{tid}> (`{tid}`)")
            elif t_type == "role":
                entries.append(f"• Role: <@&{tid}> (`{tid}`)")
            else:
                entries.append(f"• User: <@{tid}> (`{tid}`)")

        embed = discord.Embed(
            title=f"[AUTOMOD] Whitelist Bypasses ({len(rows)})",
            description="\n".join(entries),
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @am_whitelist_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def am_wl_add(self, ctx: commands.Context, target: Union[discord.TextChannel, discord.Role, discord.Member]):
        """Whitelist a channel, role, or user from automod checks."""
        t_type = "channel" if isinstance(target, discord.TextChannel) else ("role" if isinstance(target, discord.Role) else "user")
        await db.execute(
            "INSERT INTO automod_whitelists (guild_id, target_id, target_type) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            ctx.guild.id, target.id, t_type
        )
        self._whitelist_cache.pop(ctx.guild.id, None)
        await ctx.reply(f"[OK] Whitelisted {target.mention} from automod inspection.", mention_author=False)

    @am_whitelist_group.command(name="remove", aliases=["del"])
    @commands.has_permissions(manage_guild=True)
    async def am_wl_remove(self, ctx: commands.Context, target: Union[discord.TextChannel, discord.Role, discord.Member]):
        """Remove a channel, role, or user from the automod whitelist."""
        await db.execute("DELETE FROM automod_whitelists WHERE guild_id = ? AND target_id = ?", ctx.guild.id, target.id)
        self._whitelist_cache.pop(ctx.guild.id, None)
        await ctx.reply(f"[OK] Removed {target.mention} from automod whitelist.", mention_author=False)

    @am_whitelist_group.command(name="reset", aliases=["clear"])
    @commands.has_permissions(manage_guild=True)
    async def am_wl_reset(self, ctx: commands.Context):
        """Clear all automod whitelist exceptions."""
        await db.execute("DELETE FROM automod_whitelists WHERE guild_id = ?", ctx.guild.id)
        self._whitelist_cache.pop(ctx.guild.id, None)
        await ctx.reply("[OK] Reset all automod whitelist exceptions.", mention_author=False)

    @automod_cmd.command(name="reset")
    @commands.has_permissions(manage_guild=True)
    async def am_reset(self, ctx: commands.Context):
        """Reset all server automod filters and settings back to defaults."""
        await db.execute("DELETE FROM automod_filters WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM automod_words WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM automod_whitelists WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM automod_config WHERE guild_id = ?", ctx.guild.id)
        self._filter_cache.pop(ctx.guild.id, None)
        self._word_cache.pop(ctx.guild.id, None)
        self._whitelist_cache.pop(ctx.guild.id, None)
        await ctx.reply("[OK] All automod configuration and filter rules have been reset.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Automod(bot))
