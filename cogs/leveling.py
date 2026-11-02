"""
Advanced Leveling and Experience Engine for Zenith.
Includes dynamic XP calculation, text rank progress bars, role rewards, and server leaderboards.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
import random
from typing import Optional, List, Dict
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


def xp_for_level(level: int) -> int:
    """Standard logarithmic level formula: 5 * (L^2) + 50 * L + 100."""
    return 5 * (level ** 2) + (50 * level) + 100


def progress_bar(current: int, total: int, length: int = 14) -> str:
    """Generate a clean ASCII progress bar."""
    if total <= 0:
        return "[" + "=" * length + "]"
    ratio = min(max(current / total, 0.0), 1.0)
    filled = int(ratio * length)
    empty = length - filled
    return "[" + "=" * filled + "-" * empty + "]"


class Leveling(commands.Cog):
    """Server activity leveling and role rewards engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cooldowns to prevent spam XP exploitation: {(guild_id, user_id): last_xp_time}
        self._cooldowns: Dict[tuple[int, int], float] = {}

    # ---------------------------------------------------------
    # LISTENER
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.content:
            return

        now = time.monotonic()
        key = (message.guild.id, message.author.id)
        if now - self._cooldowns.get(key, 0.0) < 60.0:
            return

        self._cooldowns[key] = now
        guild_id = message.guild.id
        user_id = message.author.id

        row = await db.fetchrow("SELECT xp, level FROM user_levels WHERE guild_id = ? AND user_id = ?", guild_id, user_id)
        xp = row["xp"] if row else 0
        level = row["level"] if row else 0

        gained_xp = random.randint(15, 25)
        new_xp = xp + gained_xp

        needed = xp_for_level(level)
        leveled_up = False

        if new_xp >= needed:
            level += 1
            new_xp -= needed
            leveled_up = True

        await db.execute(
            """
            INSERT INTO user_levels (guild_id, user_id, xp, level, last_xp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                xp = excluded.xp,
                level = excluded.level,
                last_xp = excluded.last_xp
            """,
            guild_id, user_id, new_xp, level, time.time()
        )

        if leveled_up:
            # Check for role rewards
            reward_row = await db.fetchrow("SELECT role_id FROM level_rewards WHERE guild_id = ? AND level = ?", guild_id, level)
            if reward_row and message.guild.me.guild_permissions.manage_roles:
                role = message.guild.get_role(reward_row["role_id"])
                if role and role < message.guild.me.top_role:
                    try:
                        await message.author.add_roles(role, reason=f"Zenith Level {level} Reward")
                    except Exception:
                        pass

            # Announce level up
            cfg = await db.fetchrow("SELECT channel_id FROM level_config WHERE guild_id = ?", guild_id)
            target_ch = message.guild.get_channel(cfg["channel_id"]) if cfg and cfg.get("channel_id") else message.channel

            if target_ch and target_ch.permissions_for(message.guild.me).send_messages:
                embed = discord.Embed(
                    title="[LEVEL UP]",
                    description=f"Congratulations {message.author.mention}, you advanced to **Level {level}**.",
                    color=ACCENT_COLOR
                )
                embed.set_footer(text="Zenith Leveling Suite | Developed by Shree")
                try:
                    await target_ch.send(embed=embed)
                except Exception:
                    pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.command(name="rank", aliases=["lvl", "level"])
    @commands.guild_only()
    async def rank_command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display level, experience, progress bar, and server rank."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT xp, level FROM user_levels WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)

        xp = row["xp"] if row else 0
        level = row["level"] if row else 0
        needed = xp_for_level(level)

        # Calculate server rank position
        higher_rows = await db.fetch(
            "SELECT COUNT(*) as rank_pos FROM user_levels WHERE guild_id = ? AND (level > ? OR (level = ? AND xp > ?))",
            ctx.guild.id, level, level, xp
        )
        rank_pos = (higher_rows[0]["rank_pos"] if higher_rows else 0) + 1

        bar = progress_bar(xp, needed, length=12)
        pct = int((xp / needed) * 100) if needed > 0 else 100

        embed = discord.Embed(
            title=f"[RANK CARD - {target.display_name}]",
            description=(
                f"**Server Rank:** `#{rank_pos}`\n"
                f"**Level:** `{level}`\n"
                f"**Experience:** `{xp:,} / {needed:,}` XP (`{pct}%`)\n\n"
                f"`{bar}`"
            ),
            color=ACCENT_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Zenith Leveling Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="levels", aliases=["top", "xplb", "leaderboard_levels"])
    @commands.guild_only()
    async def levels_leaderboard(self, ctx: commands.Context):
        """Display the server experience and level leaderboard."""
        rows = await db.fetch(
            "SELECT user_id, level, xp FROM user_levels WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            ctx.guild.id
        )

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO LEVEL DATA]", description="No chat activity recorded yet.", color=ACCENT_COLOR))

        lines = []
        for i, r in enumerate(rows, 1):
            lines.append(f"`{i:02d}.` <@{r['user_id']}> — **Level {r['level']}** (`{r['xp']:,}` XP)")

        embed = discord.Embed(
            title="[SERVER LEVEL LEADERBOARD]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Leveling Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.group(name="leveling", invoke_without_command=True)
    @commands.guild_only()
    async def leveling_group(self, ctx: commands.Context):
        """Leveling administration and role reward controls."""
        embed = discord.Embed(
            title="[LEVELING MANAGEMENT]",
            description="Manage XP rewards, level up announcement channels, and administrative overrides.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}leveling channel <#channel>` - Set announcement channel\n"
                f"`{ctx.prefix}leveling rewards add <level> <@role>` - Bind role reward\n"
                f"`{ctx.prefix}leveling rewards remove <level>` - Delete role reward\n"
                f"`{ctx.prefix}leveling rewards list` - Display configured rewards\n"
                f"`{ctx.prefix}leveling setlevel <@user> <level>` - Set user level\n"
                f"`{ctx.prefix}leveling reset <@user>` - Reset user progress"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @leveling_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def leveling_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or view the level up announcement channel."""
        if channel is None:
            await db.execute("UPDATE level_config SET channel_id = NULL WHERE guild_id = ?", ctx.guild.id)
            return await ctx.send(embed=discord.Embed(title="[ANNOUNCEMENT CHANNEL]", description="Level ups will be posted in the active chat channel.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO level_config (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            ctx.guild.id, channel.id
        )
        embed = discord.Embed(title="[ANNOUNCEMENT CHANNEL SET]", description=f"Level ups will be announced in {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @leveling_group.group(name="rewards", invoke_without_command=True)
    @commands.guild_only()
    async def rewards_group(self, ctx: commands.Context):
        """Level role rewards overview."""
        rows = await db.fetch("SELECT level, role_id FROM level_rewards WHERE guild_id = ? ORDER BY level ASC", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO ROLE REWARDS]", description="Zero level role rewards configured.", color=ACCENT_COLOR))

        lines = [f"• **Level {r['level']}:** <@&{r['role_id']}>" for r in rows]
        embed = discord.Embed(title="[LEVEL ROLE REWARDS]", description="\n".join(lines), color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rewards_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rewards_add(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role reward granted when a member reaches a level."""
        if level < 1 or level > 1000:
            return await ctx.send(embed=discord.Embed(title="[INVALID LEVEL]", description="Level must be between 1 and 1000.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO level_rewards (guild_id, level, role_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id
            """,
            ctx.guild.id, level, role.id
        )
        embed = discord.Embed(title="[REWARD BOUND]", description=f"Members reaching **Level {level}** will receive {role.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rewards_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rewards_remove(self, ctx: commands.Context, level: int):
        """Remove a role reward for a level."""
        await db.execute("DELETE FROM level_rewards WHERE guild_id = ? AND level = ?", ctx.guild.id, level)
        embed = discord.Embed(title="[REWARD REMOVED]", description=f"Removed role reward for Level {level}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @leveling_group.command(name="setlevel")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_setlevel(self, ctx: commands.Context, member: discord.Member, level: int):
        """Manually override a member's level."""
        if level < 0:
            return await ctx.send(embed=discord.Embed(title="[INVALID LEVEL]", description="Level cannot be negative.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO user_levels (guild_id, user_id, xp, level, last_xp) VALUES (?, ?, 0, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET level = excluded.level, xp = 0
            """,
            ctx.guild.id, member.id, level, time.time()
        )
        embed = discord.Embed(title="[LEVEL OVERRIDDEN]", description=f"Set {member.mention}'s level to **{level}**.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @leveling_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_reset(self, ctx: commands.Context, member: discord.Member):
        """Reset a member's experience and level to zero."""
        await db.execute("DELETE FROM user_levels WHERE guild_id = ? AND user_id = ?", ctx.guild.id, member.id)
        embed = discord.Embed(title="[LEVEL RESET]", description=f"Reset experience for {member.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @leveling_group.command(name="addxp")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_addxp(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Add raw XP to a member."""
        if amount <= 0:
            return await ctx.send("[ERROR] Amount must be greater than zero.")

        await db.execute(
            """
            INSERT INTO user_levels (guild_id, user_id, xp, level, last_xp) VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = user_levels.xp + excluded.xp
            """,
            ctx.guild.id, member.id, amount, time.time()
        )
        await ctx.send(embed=discord.Embed(title="[OK] XP Added", description=f"Added **{amount:,} XP** to {member.mention}.", color=ACCENT_COLOR))

    @leveling_group.command(name="removexp")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_removexp(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Remove raw XP from a member."""
        if amount <= 0:
            return await ctx.send("[ERROR] Amount must be greater than zero.")

        await db.execute(
            "UPDATE user_levels SET xp = MAX(0, xp - ?) WHERE guild_id = ? AND user_id = ?",
            amount, ctx.guild.id, member.id
        )
        await ctx.send(embed=discord.Embed(title="[OK] XP Deducted", description=f"Removed **{amount:,} XP** from {member.mention}.", color=ACCENT_COLOR))

    @leveling_group.command(name="setxp")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_setxp(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Set a member's exact XP count."""
        if amount < 0:
            return await ctx.send("[ERROR] Amount cannot be negative.")

        await db.execute(
            """
            INSERT INTO user_levels (guild_id, user_id, xp, level, last_xp) VALUES (?, ?, ?, 0, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp
            """,
            ctx.guild.id, member.id, amount, time.time()
        )
        await ctx.send(embed=discord.Embed(title="[OK] XP Set", description=f"Set {member.mention}'s XP to **{amount:,}**.", color=ACCENT_COLOR))

    @leveling_group.command(name="resetall")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_resetall(self, ctx: commands.Context):
        """Purge all server member leveling and experience data."""
        await db.execute("DELETE FROM user_levels WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Leveling Purged", description="All member levels and XP have been reset to zero.", color=ACCENT_COLOR))

    @leveling_group.command(name="toggle")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def leveling_toggle(self, ctx: commands.Context, state: str):
        """Toggle whether leveling is active on the server."""
        val = state.lower() in ("on", "true", "enable", "1")
        await db.execute(
            """
            INSERT INTO level_config (guild_id, enabled) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = excluded.enabled
            """,
            ctx.guild.id, val
        )
        status_str = "Enabled" if val else "Disabled"
        await ctx.send(embed=discord.Embed(title="[OK] Leveling Toggled", description=f"Leveling system is now `{status_str}`.", color=ACCENT_COLOR))

    @rewards_group.command(name="list")
    @commands.guild_only()
    async def rewards_list(self, ctx: commands.Context):
        """List all configured level role rewards."""
        rows = await db.fetch("SELECT level, role_id FROM level_rewards WHERE guild_id = ? ORDER BY level ASC", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[REWARDS LIST]", description="No role rewards configured.", color=ACCENT_COLOR))

        desc = []
        for r in rows:
            desc.append(f"• **Level {r['level']}** -> <@&{r['role_id']}>")

        embed = discord.Embed(
            title=f"[LEVEL REWARDS] {ctx.guild.name} ({len(rows)})",
            description="\n".join(desc),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @rewards_group.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rewards_clear(self, ctx: commands.Context):
        """Clear all level role rewards."""
        await db.execute("DELETE FROM level_rewards WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Rewards Cleared", description="Removed all level role reward configurations.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
