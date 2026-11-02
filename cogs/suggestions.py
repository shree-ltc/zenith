"""
Community Suggestions Subsystem for Zenith.
Accepts user ideas, collects community feedback, and allows staff to accept, deny, or consider ideas.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class Suggestions(commands.Cog):
    """Community ideas and suggestion lifecycle management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="suggest", aliases=["idea"])
    @commands.guild_only()
    async def make_suggestion(self, ctx: commands.Context, *, content: str):
        """Submit a community suggestion for server improvement."""
        cfg = await db.fetchrow("SELECT channel_id FROM suggestions_config WHERE guild_id = ?", ctx.guild.id)
        if not cfg or not cfg.get("channel_id"):
            return await ctx.send(embed=discord.Embed(title="[NOT CONFIGURED]", description="Suggestions channel is not configured on this server.", color=ACCENT_COLOR))

        sug_channel = ctx.guild.get_channel(cfg["channel_id"])
        if not sug_channel:
            return await ctx.send(embed=discord.Embed(title="[CHANNEL MISSING]", description="Configured suggestions channel no longer exists.", color=ACCENT_COLOR))

        embed = discord.Embed(
            title="[COMMUNITY SUGGESTION]",
            description=content,
            color=ACCENT_COLOR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{ctx.author.display_name} ({ctx.author})", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Status", value="`[PENDING REVIEW]`", inline=False)
        embed.set_footer(text=f"Submitted by {ctx.author.id}")

        msg = await sug_channel.send(embed=embed)
        await msg.add_reaction("▲")
        await msg.add_reaction("▼")

        await db.execute(
            """
            INSERT INTO suggestions (guild_id, user_id, message_id, content, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            ctx.guild.id, ctx.author.id, msg.id, content
        )

        row = await db.fetchrow("SELECT id FROM suggestions WHERE message_id = ?", msg.id)
        sug_id = row["id"] if row else msg.id

        await ctx.send(embed=discord.Embed(
            title="[SUGGESTION SUBMITTED]",
            description=f"Your suggestion has been logged as **#{sug_id}** in {sug_channel.mention}.",
            color=ACCENT_COLOR
        ))

    @commands.group(name="suggestion", aliases=["sug"], invoke_without_command=True)
    @commands.guild_only()
    async def suggestion_group(self, ctx: commands.Context):
        """Suggestions management commands."""
        embed = discord.Embed(
            title="[SUGGESTIONS SYSTEM]",
            description="Manage community feedback and suggestion lifecycles.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}suggest <idea>` - Submit a new suggestion\n"
                f"`{ctx.prefix}suggestion channel <#channel>` - Set suggestions channel\n"
                f"`{ctx.prefix}suggestion accept <id> [reason]` - Accept a suggestion\n"
                f"`{ctx.prefix}suggestion deny <id> [reason]` - Reject a suggestion\n"
                f"`{ctx.prefix}suggestion consider <id> [reason]` - Consider a suggestion"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @suggestion_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Configure the suggestions submission room."""
        await db.execute(
            """
            INSERT INTO suggestions_config (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            ctx.guild.id, channel.id
        )
        embed = discord.Embed(title="[SUGGESTIONS CHANNEL SET]", description=f"Suggestions will now post to {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    async def _update_status(self, ctx: commands.Context, sug_id: int, status_label: str, color_hex: int, reason: Optional[str] = None):
        row = await db.fetchrow("SELECT * FROM suggestions WHERE guild_id = ? AND id = ?", ctx.guild.id, sug_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT FOUND]", description=f"No suggestion found with ID `#{sug_id}`.", color=ACCENT_COLOR))

        cfg = await db.fetchrow("SELECT channel_id FROM suggestions_config WHERE guild_id = ?", ctx.guild.id)
        if not cfg or not cfg.get("channel_id"):
            return await ctx.send(embed=discord.Embed(title="[CONFIG ERROR]", description="Suggestions channel is not configured.", color=ACCENT_COLOR))

        ch = ctx.guild.get_channel(cfg["channel_id"])
        if not ch:
            return await ctx.send(embed=discord.Embed(title="[CHANNEL MISSING]", description="Suggestions channel not found.", color=ACCENT_COLOR))

        try:
            msg = await ch.fetch_message(row["message_id"])
            embed = msg.embeds[0]
            embed.color = color_hex
            embed.set_field_at(0, name="Status", value=f"`[{status_label.upper()}]`", inline=False)
            if reason:
                embed.add_field(name="Staff Reason", value=reason, inline=False)
            await msg.edit(embed=embed)
        except Exception:
            pass

        await db.execute("UPDATE suggestions SET status = ?, reason = ? WHERE id = ?", status_label.lower(), reason, sug_id)
        await ctx.send(embed=discord.Embed(title=f"[SUGGESTION {status_label.upper()}]", description=f"Suggestion `#{sug_id}` has been updated to **{status_label}**.", color=color_hex))

    @suggestion_group.command(name="accept")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_accept(self, ctx: commands.Context, sug_id: int, *, reason: Optional[str] = "Approved by staff."):
        """Mark a community suggestion as accepted."""
        await self._update_status(ctx, sug_id, "ACCEPTED", 0x00FF00, reason)

    @suggestion_group.command(name="deny", aliases=["reject"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_deny(self, ctx: commands.Context, sug_id: int, *, reason: Optional[str] = "Declined by staff."):
        """Mark a community suggestion as denied."""
        await self._update_status(ctx, sug_id, "DENIED", 0xFF0000, reason)

    @suggestion_group.command(name="consider")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_consider(self, ctx: commands.Context, sug_id: int, *, reason: Optional[str] = "Under consideration."):
        """Mark a community suggestion as considered."""
        await self._update_status(ctx, sug_id, "CONSIDERED", 0x5865F2, reason)

    @suggestion_group.command(name="info")
    @commands.guild_only()
    async def sug_info(self, ctx: commands.Context, sug_id: int):
        """View submission metadata and content for a suggestion."""
        row = await db.fetchrow("SELECT * FROM suggestions WHERE guild_id = ? AND id = ?", ctx.guild.id, sug_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT FOUND]", description=f"Suggestion `#{sug_id}` was not found.", color=ACCENT_COLOR))

        user = ctx.guild.get_member(row["user_id"]) or await self.bot.fetch_user(row["user_id"])
        embed = discord.Embed(
            title=f"[SUGGESTION #{row['id']}] Status: {row['status'].upper()}",
            description=row["content"],
            color=ACCENT_COLOR
        )
        embed.add_field(name="Author", value=f"{user} (`{row['user_id']}`)", inline=True)
        if row.get("reason"):
            embed.add_field(name="Staff Response", value=row["reason"], inline=False)
        await ctx.send(embed=embed)

    @suggestion_group.command(name="list")
    @commands.guild_only()
    async def sug_list(self, ctx: commands.Context, status: Optional[str] = None):
        """List suggestions by status or recent submissions."""
        if status:
            rows = await db.fetch("SELECT id, user_id, content, status FROM suggestions WHERE guild_id = ? AND LOWER(status) = ? ORDER BY id DESC LIMIT 15", ctx.guild.id, status.lower())
            title = f"[SUGGESTIONS] Status: {status.upper()}"
        else:
            rows = await db.fetch("SELECT id, user_id, content, status FROM suggestions WHERE guild_id = ? ORDER BY id DESC LIMIT 15", ctx.guild.id)
            title = f"[SUGGESTIONS] Recent Submissions ({ctx.guild.name})"

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[SUGGESTIONS]", description="No matching suggestions found.", color=ACCENT_COLOR))

        lines = [f"• **#{r['id']}** `[{r['status'].upper()}]` — {r['content'][:45]}" for r in rows]
        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @suggestion_group.command(name="delete", aliases=["del", "rm"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_delete(self, ctx: commands.Context, sug_id: int):
        """Delete a suggestion record."""
        row = await db.fetchrow("SELECT id FROM suggestions WHERE guild_id = ? AND id = ?", ctx.guild.id, sug_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT FOUND]", description=f"Suggestion `#{sug_id}` was not found.", color=ACCENT_COLOR))

        await db.execute("DELETE FROM suggestions WHERE guild_id = ? AND id = ?", ctx.guild.id, sug_id)
        await ctx.send(embed=discord.Embed(title="[OK] Suggestion Deleted", description=f"Deleted suggestion `#{sug_id}`.", color=ACCENT_COLOR))

    @suggestion_group.command(name="comment")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sug_comment(self, ctx: commands.Context, sug_id: int, *, comment: str):
        """Add a staff comment or update to a suggestion."""
        row = await db.fetchrow("SELECT * FROM suggestions WHERE guild_id = ? AND id = ?", ctx.guild.id, sug_id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT FOUND]", description=f"Suggestion `#{sug_id}` was not found.", color=ACCENT_COLOR))

        await db.execute("UPDATE suggestions SET reason = ? WHERE guild_id = ? AND id = ?", comment, ctx.guild.id, sug_id)
        await ctx.send(embed=discord.Embed(title="[OK] Comment Added", description=f"Updated response on Suggestion `#{sug_id}` to:\n> {comment}", color=ACCENT_COLOR))

    @suggestion_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sug_reset(self, ctx: commands.Context):
        """Clear suggestions channel and purge historical submissions."""
        await db.execute("DELETE FROM suggestions WHERE guild_id = ?", ctx.guild.id)
        await db.execute("DELETE FROM suggestions_config WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Suggestions Reset", description="Cleared all server suggestions and settings.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
