"""
Starboard System for Zenith.
Showcases popular and noteworthy community messages when they receive a threshold of star reactions.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class Starboard(commands.Cog):
    """Pins community-voted messages into a starboard showcase channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return

        cfg = await db.fetchrow("SELECT * FROM starboard_config WHERE guild_id = ?", payload.guild_id)
        if not cfg or not cfg.get("channel_id"):
            return

        target_emoji = cfg.get("emoji", "\u2b50")
        if str(payload.emoji) != target_emoji and payload.emoji.name not in ("star", "\u2b50") and target_emoji != "star":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        # Do not starboard messages in the starboard channel itself
        if channel.id == cfg["channel_id"]:
            return

        try:
            msg = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        if msg.author.bot:
            return

        if not cfg.get("self_star", False) and payload.user_id == msg.author.id:
            return

        # Count reactions
        star_reaction = next((r for r in msg.reactions if str(r.emoji) == str(payload.emoji) or str(r.emoji) == "\u2b50"), None)
        star_count = star_reaction.count if star_reaction else 1

        threshold = cfg.get("threshold", 3)
        if star_count < threshold:
            return

        star_ch = guild.get_channel(cfg["channel_id"])
        if not star_ch or not isinstance(star_ch, discord.TextChannel):
            return

        existing = await db.fetchrow("SELECT star_message_id FROM starboard_messages WHERE guild_id = ? AND orig_message_id = ?", guild.id, msg.id)

        embed = discord.Embed(
            description=msg.content or "*[Attachment / Embed]*",
            color=ACCENT_COLOR,
            timestamp=msg.created_at
        )
        embed.set_author(name=f"{msg.author.display_name} ({msg.author})", icon_url=msg.author.display_avatar.url)
        embed.add_field(name="Source", value=f"[Jump to Message]({msg.jump_url})", inline=True)

        if msg.attachments:
            embed.set_image(url=msg.attachments[0].url)

        embed.set_footer(text=f"Starred in #{channel.name}")
        content = f"**[STARRED]** `{star_count}` stars | {channel.mention}"

        if existing:
            try:
                board_msg = await star_ch.fetch_message(existing["star_message_id"])
                await board_msg.edit(content=content, embed=embed)
                await db.execute("UPDATE starboard_messages SET stars_count = ? WHERE orig_message_id = ?", star_count, msg.id)
            except Exception:
                pass
        else:
            try:
                board_msg = await star_ch.send(content=content, embed=embed)
                await db.execute(
                    """
                    INSERT INTO starboard_messages (guild_id, orig_message_id, star_message_id, stars_count)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(orig_message_id) DO UPDATE SET stars_count = excluded.stars_count
                    """,
                    guild.id, msg.id, board_msg.id, star_count
                )
            except Exception:
                pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="starboard", invoke_without_command=True)
    @commands.guild_only()
    async def starboard_group(self, ctx: commands.Context):
        """Starboard configuration overview."""
        cfg = await db.fetchrow("SELECT * FROM starboard_config WHERE guild_id = ?", ctx.guild.id)
        ch_str = f"<#{cfg['channel_id']}>" if cfg and cfg.get("channel_id") else "None configured"
        threshold = cfg.get("threshold", 3) if cfg else 3
        selfstar = "Allowed" if cfg and cfg.get("self_star") else "Blocked"

        embed = discord.Embed(
            title="[STARBOARD CONFIGURATION]",
            description="Highlight popular community messages voted with star reactions.",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Starboard Channel", value=ch_str, inline=True)
        embed.add_field(name="Reaction Threshold", value=f"`{threshold}` stars", inline=True)
        embed.add_field(name="Self-Starring", value=f"`{selfstar}`", inline=True)
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}starboard channel <#channel>` - Set starboard channel\n"
                f"`{ctx.prefix}starboard threshold <count>` - Set star requirement\n"
                f"`{ctx.prefix}starboard selfstar <true/false>` - Toggle self-starring\n"
                f"`{ctx.prefix}starboard reset` - Clear starboard configuration"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @starboard_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sb_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set destination channel for starboard posts."""
        await db.execute(
            """
            INSERT INTO starboard_config (guild_id, channel_id, threshold, self_star) VALUES (?, ?, 3, FALSE)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            ctx.guild.id, channel.id
        )
        embed = discord.Embed(title="[STARBOARD CHANNEL SET]", description=f"Starboard messages will post to {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @starboard_group.command(name="threshold")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sb_threshold(self, ctx: commands.Context, count: int):
        """Set the number of star reactions required to pin a message."""
        if count < 1 or count > 50:
            return await ctx.send(embed=discord.Embed(title="[INVALID COUNT]", description="Threshold must be between 1 and 50.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO starboard_config (guild_id, threshold) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET threshold = excluded.threshold
            """,
            ctx.guild.id, count
        )
        embed = discord.Embed(title="[THRESHOLD UPDATED]", description=f"Messages now require **{count}** stars to be posted.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @starboard_group.command(name="selfstar")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sb_selfstar(self, ctx: commands.Context, allow: bool):
        """Toggle whether users can star their own messages."""
        await db.execute(
            """
            INSERT INTO starboard_config (guild_id, self_star) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET self_star = excluded.self_star
            """,
            ctx.guild.id, allow
        )
        status = "allowed" if allow else "blocked"
        embed = discord.Embed(title="[SELF-STAR UPDATED]", description=f"Self-starring is now **{status}**.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @starboard_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sb_reset(self, ctx: commands.Context):
        """Clear starboard configuration."""
        await db.execute("DELETE FROM starboard_config WHERE guild_id = ?", ctx.guild.id)
        embed = discord.Embed(title="[STARBOARD RESET]", description="Starboard configuration has been reset.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @starboard_group.command(name="status", aliases=["config", "info"])
    @commands.guild_only()
    async def sb_status(self, ctx: commands.Context):
        """View active starboard configuration and statistics."""
        cfg = await db.fetchrow("SELECT * FROM starboard_config WHERE guild_id = ?", ctx.guild.id)
        if not cfg or not cfg["channel_id"]:
            return await ctx.send(embed=discord.Embed(title="[STARBOARD STATUS]", description="Starboard is currently unconfigured.", color=ACCENT_COLOR))

        count_row = await db.fetchrow("SELECT COUNT(*) as c FROM starboard_messages WHERE guild_id = ?", ctx.guild.id)
        total_starred = count_row["c"] if count_row else 0

        embed = discord.Embed(
            title=f"[STARBOARD STATUS] {ctx.guild.name}",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Channel", value=f"<#{cfg['channel_id']}>", inline=True)
        embed.add_field(name="Threshold", value=f"**{cfg['threshold']}** stars", inline=True)
        embed.add_field(name="Self-Star", value="Allowed" if cfg["self_star"] else "Blocked", inline=True)
        embed.add_field(name="Total Starred", value=f"**{total_starred}** posts", inline=True)
        await ctx.send(embed=embed)

    @starboard_group.command(name="emoji")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def sb_emoji(self, ctx: commands.Context, emoji: str):
        """Configure custom reaction emoji for starboard tracking."""
        await db.execute(
            """
            INSERT INTO starboard_config (guild_id, emoji) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET emoji = excluded.emoji
            """,
            ctx.guild.id, emoji
        )
        await ctx.send(embed=discord.Embed(title="[OK] Starboard Emoji Updated", description=f"Starboard trigger set to `{emoji}`.", color=ACCENT_COLOR))

    @starboard_group.command(name="lock")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def sb_lock(self, ctx: commands.Context, message_id: int):
        """Prevent a message from being added to the starboard."""
        await db.execute(
            "INSERT INTO starboard_messages (guild_id, orig_message_id, star_message_id, stars_count) VALUES (?, ?, 0, -1) ON CONFLICT DO NOTHING",
            ctx.guild.id, message_id
        )
        await ctx.send(embed=discord.Embed(title="[OK] Message Locked", description=f"Message `{message_id}` will not appear on starboard.", color=ACCENT_COLOR))

    @starboard_group.command(name="unlock")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def sb_unlock(self, ctx: commands.Context, message_id: int):
        """Unlock a previously locked starboard message."""
        await db.execute("DELETE FROM starboard_messages WHERE guild_id = ? AND orig_message_id = ? AND stars_count = -1", ctx.guild.id, message_id)
        await ctx.send(embed=discord.Embed(title="[OK] Message Unlocked", description=f"Message `{message_id}` can now be starred.", color=ACCENT_COLOR))

    @starboard_group.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sb_clear(self, ctx: commands.Context):
        """Clear all historical starboard post records."""
        await db.execute("DELETE FROM starboard_messages WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Starboard Cleared", description="Purged all tracked starboard posts.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Starboard(bot))
