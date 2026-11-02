"""
Moderation Case Tracking and Audit Log Management for Zenith.
Tracks infractions: bans, unbans, kicks, mutes, warnings, with modlog channel integration.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from __future__ import annotations

import time
from typing import Optional
import discord
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13


class Cases(commands.Cog):
    """Case management and moderation audit logging."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def log_case(self, guild: discord.Guild, user_id: int, mod_id: int, action: str, reason: str) -> int:
        """Create a moderation case entry and broadcast to modlog channel."""
        now = time.time()
        await db.execute(
            "INSERT INTO moderation_cases (guild_id, user_id, moderator_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            guild.id, user_id, mod_id, action.lower(), reason, now
        )

        row = await db.fetchrow(
            "SELECT id FROM moderation_cases WHERE guild_id = ? AND user_id = ? AND created_at = ? ORDER BY id DESC LIMIT 1",
            guild.id, user_id, now
        )
        case_id = row["id"] if row else 0

        # Broadcast to modlog channel if configured
        cfg = await db.fetchrow("SELECT channel_id FROM modlog_config WHERE guild_id = ?", guild.id)
        if cfg and cfg.get("channel_id"):
            channel = guild.get_channel(cfg["channel_id"])
            if channel:
                target = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
                mod = guild.get_member(mod_id) or await self.bot.fetch_user(mod_id)

                embed = discord.Embed(
                    title=f"[MODLOG] Case #{case_id} | {action.upper()}",
                    color=THEME_COLOR,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Target", value=f"{target} (`{user_id}`)", inline=True)
                embed.add_field(name="Moderator", value=f"{mod} (`{mod_id}`)", inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.set_footer(text=f"Zenith ModLog | Developed by Shree")
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

        return case_id

    @commands.group(name="case", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_group(self, ctx: commands.Context, case_id: Optional[int] = None):
        """Lookup infraction details for a case."""
        if not case_id:
            embed = discord.Embed(
                title="[CASE SYSTEM] Moderation Records",
                description=(
                    f"• `{ctx.prefix}case <id>` - Inspect case details\n"
                    f"• `{ctx.prefix}case edit <id> <reason>` - Update case reason\n"
                    f"• `{ctx.prefix}case delete <id>` - Delete case\n"
                    f"• `{ctx.prefix}case list [user]` - List recent cases\n"
                    f"• `{ctx.prefix}case total` - Total cases count\n"
                    f"• `{ctx.prefix}case search <query>` - Search cases"
                ),
                color=THEME_COLOR
            )
            return await ctx.send(embed=embed)

        row = await db.fetchrow("SELECT * FROM moderation_cases WHERE guild_id = ? AND id = ?", ctx.guild.id, case_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[CASE NOT FOUND]", description=f"Case `#{case_id}` does not exist.", color=THEME_COLOR))

        user = ctx.guild.get_member(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
        mod = ctx.guild.get_member(row["moderator_id"]) or await self.bot.fetch_user(row["moderator_id"])

        embed = discord.Embed(
            title=f"[CASE #{row['id']}] {row['action'].upper()}",
            color=THEME_COLOR
        )
        embed.add_field(name="Target", value=f"{user} (`{row['user_id']}`)", inline=True)
        embed.add_field(name="Moderator", value=f"{mod} (`{row['moderator_id']}`)", inline=True)
        embed.add_field(name="Action", value=f"`{row['action'].upper()}`", inline=True)
        embed.add_field(name="Timestamp", value=f"<t:{int(row['created_at'])}:F>", inline=True)
        embed.add_field(name="Reason", value=row["reason"], inline=False)
        embed.set_footer(text="Zenith ModLog | Developed by Shree")
        await ctx.send(embed=embed)

    @case_group.command(name="edit")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_edit(self, ctx: commands.Context, case_id: int, *, new_reason: str):
        """Update the reason for a moderation case."""
        row = await db.fetchrow("SELECT id FROM moderation_cases WHERE guild_id = ? AND id = ?", ctx.guild.id, case_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[CASE NOT FOUND]", description=f"Case `#{case_id}` does not exist.", color=THEME_COLOR))

        await db.execute("UPDATE moderation_cases SET reason = ? WHERE guild_id = ? AND id = ?", new_reason, ctx.guild.id, case_id)
        embed = discord.Embed(
            title="[CASE UPDATED]",
            description=f"Updated reason for Case `#{case_id}` to:\n> {new_reason}",
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith ModLog | Developed by Shree")
        await ctx.send(embed=embed)

    @case_group.command(name="delete", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def case_delete(self, ctx: commands.Context, case_id: int):
        """Delete an infraction case."""
        await db.execute("DELETE FROM moderation_cases WHERE guild_id = ? AND id = ?", ctx.guild.id, case_id)
        embed = discord.Embed(title="[CASE DELETED]", description=f"Deleted case record `#{case_id}`.", color=THEME_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @case_group.command(name="reason")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_reason_cmd(self, ctx: commands.Context, case_id: int, *, reason: str):
        """Update or append reason for a moderation case."""
        await self.case_edit(ctx, case_id, new_reason=reason)

    @case_group.command(name="list")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_list_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """List recent moderation cases for server or member."""
        if member:
            rows = await db.fetch("SELECT id, action, reason, moderator_id, created_at FROM moderation_cases WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 20", ctx.guild.id, member.id)
            title = f"[CASES] For {member.display_name}"
        else:
            rows = await db.fetch("SELECT id, action, user_id, reason, created_at FROM moderation_cases WHERE guild_id = ? ORDER BY id DESC LIMIT 20", ctx.guild.id)
            title = f"[CASES] Recent Logs for {ctx.guild.name}"

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[CASES]", description="No matching moderation cases found.", color=THEME_COLOR))

        lines = [f"• **#{r['id']}** `[{r['action'].upper()}]` — {r['reason'][:40]}" for r in rows]
        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @case_group.command(name="total")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_total_cmd(self, ctx: commands.Context):
        """Display total cases registered in this server."""
        row = await db.fetchrow("SELECT COUNT(*) as c FROM moderation_cases WHERE guild_id = ?", ctx.guild.id)
        total = row["c"] if row else 0
        await ctx.send(embed=discord.Embed(title="[CASE METRICS]", description=f"Total recorded moderation incidents: **{total:,}**", color=THEME_COLOR))

    @case_group.command(name="search")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def case_search_cmd(self, ctx: commands.Context, *, query: str):
        """Search moderation cases by action or keyword in reason."""
        pattern = f"%{query.lower()}%"
        rows = await db.fetch(
            "SELECT id, action, user_id, reason FROM moderation_cases WHERE guild_id = ? AND (LOWER(action) LIKE ? OR LOWER(reason) LIKE ?) ORDER BY id DESC LIMIT 15",
            ctx.guild.id, pattern, pattern
        )
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[SEARCH]", description=f"No cases found matching '{query}'.", color=THEME_COLOR))

        lines = [f"• **#{r['id']}** `[{r['action'].upper()}]` user: <@{r['user_id']}> — {r['reason'][:45]}" for r in rows]
        embed = discord.Embed(
            title=f"[CASE SEARCH] Matches for '{query}'",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="modlogs", aliases=["history", "infractions"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def user_modlogs(self, ctx: commands.Context, member: discord.Member):
        """View the chronological moderation history for a member."""
        rows = await db.fetch(
            "SELECT id, action, reason, moderator_id, created_at FROM moderation_cases WHERE guild_id = ? AND user_id = ? ORDER BY id DESC LIMIT 15",
            ctx.guild.id, member.id
        )

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[CLEAN RECORD]", description=f"{member.mention} has no recorded moderation cases.", color=THEME_COLOR))

        lines = [f"`#{r['id']}` **[{r['action']}]** — {r['reason']} (Mod: <@{r['moderator_id']}>) <t:{int(r['created_at'])}:d>" for r in rows]
        embed = discord.Embed(
            title=f"[MODERATION HISTORY - {member.display_name}]",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        embed.set_footer(text=f"Total Infractions: {len(rows)} | Zenith")
        await ctx.send(embed=embed)

    @commands.group(name="modlog", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def modlog_group(self, ctx: commands.Context):
        """Modlog broadcast channel configuration."""
        cfg = await db.fetchrow("SELECT channel_id FROM modlog_config WHERE guild_id = ?", ctx.guild.id)
        ch_str = f"<#{cfg['channel_id']}>" if cfg and cfg.get("channel_id") else "None configured"
        embed = discord.Embed(
            title="[MODLOG BROADCAST CHANNEL]",
            description=f"Current Channel: {ch_str}\nSet via `{ctx.prefix}modlog channel <#channel>`.",
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @modlog_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def modlog_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for case audit logs."""
        await db.execute(
            """
            INSERT INTO modlog_config (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            ctx.guild.id, channel.id
        )
        embed = discord.Embed(title="[MODLOG CHANNEL CONFIGURED]", description=f"Moderation cases will broadcast to {channel.mention}.", color=THEME_COLOR)
        embed.set_footer(text="Zenith ModLog | Developed by Shree")
        await ctx.send(embed=embed)

    @modlog_group.command(name="status", aliases=["info"])
    @commands.guild_only()
    async def modlog_status_cmd(self, ctx: commands.Context):
        """Check active modlog configuration."""
        cfg = await db.fetchrow("SELECT channel_id FROM modlog_config WHERE guild_id = ?", ctx.guild.id)
        ch_str = f"<#{cfg['channel_id']}>" if (cfg and cfg["channel_id"]) else "`Not configured`"
        await ctx.send(embed=discord.Embed(title="[MODLOG CONFIG]", description=f"Active modlog destination: {ch_str}", color=THEME_COLOR))

    @modlog_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def modlog_reset_cmd(self, ctx: commands.Context):
        """Disable modlog channel destination."""
        await db.execute("DELETE FROM modlog_config WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Modlog Reset", description="Modlog logging destination has been removed.", color=THEME_COLOR))

    @commands.command(name="banlist", aliases=["bans"])
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def server_banlist(self, ctx: commands.Context):
        """Display the server ban list."""
        bans = [entry async for entry in ctx.guild.bans(limit=50)]
        if not bans:
            return await ctx.send(embed=discord.Embed(title="[NO BANS]", description="No banned members in this server.", color=THEME_COLOR))

        lines = [f"• **{b.user}** (`{b.user.id}`): {b.reason or 'No reason provided'}" for b in bans[:25]]
        embed = discord.Embed(
            title=f"[SERVER BANS - {len(bans)} TOTAL]",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="mutelist", aliases=["timeouts"])
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def server_mutelist(self, ctx: commands.Context):
        """Display currently timed out members."""
        now = discord.utils.utcnow()
        timed_out = [m for m in ctx.guild.members if m.timed_out_until and m.timed_out_until > now]

        if not timed_out:
            return await ctx.send(embed=discord.Embed(title="[NO ACTIVE TIMEOUTS]", description="No members currently in timeout.", color=THEME_COLOR))

        lines = [f"• {m.mention} (`{m.id}`): until <t:{int(m.timed_out_until.timestamp())}:R>" for m in timed_out[:25]]
        embed = discord.Embed(
            title=f"[ACTIVE TIMEOUTS - {len(timed_out)} TOTAL]",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="warnlist", aliases=["warningslist"])
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def server_warnlist(self, ctx: commands.Context):
        """Display recent warnings recorded across the server."""
        rows = await db.fetch("SELECT id, user_id, reason, moderator_id, created_at FROM user_warnings WHERE guild_id = ? ORDER BY id DESC LIMIT 20", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[WARNINGS]", description="No recorded warnings on this server.", color=THEME_COLOR))

        lines = [f"• **#{r['id']}** user: <@{r['user_id']}> — {r['reason'][:40]}" for r in rows]
        embed = discord.Embed(
            title=f"[SERVER WARNINGS] ({len(rows)})",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Cases(bot))
