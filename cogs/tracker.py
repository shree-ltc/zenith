"""
Invite & Message Activity Tracker for Zenith.
Monitors who invited each member, tracks leaves/fakes, and tallies server chat activity.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class Tracker(commands.Cog):
    """Activity tracking for member invites and server messaging."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory invite cache: {guild_id: {code: uses}}
        self._invite_cache: Dict[int, Dict[str, int]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Cache initial invite states when client is ready."""
        for guild in self.bot.guilds:
            if guild.me.guild_permissions.manage_guild:
                try:
                    invs = await guild.invites()
                    self._invite_cache[guild.id] = {i.code: i.uses for i in invs}
                except Exception:
                    pass

    # ---------------------------------------------------------
    # LISTENERS
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if guild.me.guild_permissions.manage_guild:
            try:
                invs = await guild.invites()
                self._invite_cache[guild.id] = {i.code: i.uses for i in invs}
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        if not guild.me.guild_permissions.manage_guild:
            return

        old_invs = self._invite_cache.get(guild.id, {})
        new_invs = {}
        used_invite = None

        try:
            current_invs = await guild.invites()
            for inv in current_invs:
                new_invs[inv.code] = inv.uses
                if inv.code in old_invs and inv.uses > old_invs[inv.code]:
                    used_invite = inv
            self._invite_cache[guild.id] = new_invs
        except Exception:
            return

        if used_invite and used_invite.inviter:
            inviter = used_invite.inviter
            # Store who invited this member
            await db.execute(
                """
                INSERT INTO invite_tracker (guild_id, user_id, inviter_id, code) VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET inviter_id = excluded.inviter_id, code = excluded.code
                """,
                guild.id, member.id, inviter.id, used_invite.code
            )

            # Increment regular invite count
            await db.execute(
                """
                INSERT INTO user_invites (guild_id, user_id, regular, leaves, fakes, bonus)
                VALUES (?, ?, 1, 0, 0, 0)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET regular = user_invites.regular + 1
                """,
                guild.id, inviter.id
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        row = await db.fetchrow("SELECT inviter_id FROM invite_tracker WHERE guild_id = ? AND user_id = ?", guild.id, member.id)
        if row and row["inviter_id"]:
            inviter_id = row["inviter_id"]
            await db.execute(
                """
                INSERT INTO user_invites (guild_id, user_id, regular, leaves, fakes, bonus)
                VALUES (?, ?, 0, 1, 0, 0)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET leaves = user_invites.leaves + 1
                """,
                guild.id, inviter_id
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        await db.execute(
            """
            INSERT INTO message_stats (guild_id, user_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET count = message_stats.count + 1
            """,
            message.guild.id, message.author.id
        )

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.command(name="invites")
    @commands.guild_only()
    async def invites_command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display invite statistics for a member."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT * FROM user_invites WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)

        regular = row["regular"] if row else 0
        leaves = row["leaves"] if row else 0
        fakes = row["fakes"] if row else 0
        bonus = row["bonus"] if row else 0
        net = (regular + bonus) - leaves

        embed = discord.Embed(
            title=f"[INVITES - {target.display_name}]",
            description=(
                f"**Total Net Invites:** `{net}`\n"
                f"• Regular: `{regular}`\n"
                f"• Leaves: `{leaves}`\n"
                f"• Fakes: `{fakes}`\n"
                f"• Bonus: `{bonus}`"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="topinvites", aliases=["inviteslb"])
    @commands.guild_only()
    async def topinvites_command(self, ctx: commands.Context):
        """Display the server invite leaderboard."""
        rows = await db.fetch(
            """
            SELECT user_id, (regular + bonus - leaves) AS net, regular, leaves
            FROM user_invites WHERE guild_id = ?
            ORDER BY net DESC LIMIT 10
            """,
            ctx.guild.id
        )

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO INVITE DATA]", description="No invite activity recorded yet.", color=ACCENT_COLOR))

        lines = []
        for i, r in enumerate(rows, 1):
            lines.append(f"`{i:02d}.` <@{r['user_id']}> — **{r['net']}** invites (`{r['regular']}` joins, `{r['leaves']}` leaves)")

        embed = discord.Embed(
            title="[TOP INVITERS LEADERBOARD]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="messages", aliases=["msgcount"])
    @commands.guild_only()
    async def messages_command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display total message count for a member."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT count FROM message_stats WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        count = row["count"] if row else 0

        embed = discord.Embed(
            title=f"[MESSAGE STATS - {target.display_name}]",
            description=f"{target.mention} has sent **{count:,}** messages in this server.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="topmessages", aliases=["msglb"])
    @commands.guild_only()
    async def topmessages_command(self, ctx: commands.Context):
        """Display the most active message chatters."""
        rows = await db.fetch(
            "SELECT user_id, count FROM message_stats WHERE guild_id = ? ORDER BY count DESC LIMIT 10",
            ctx.guild.id
        )

        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO MESSAGE DATA]", description="No chat activity recorded yet.", color=ACCENT_COLOR))

        lines = [f"`{i:02d}.` <@{r['user_id']}> — **{r['count']:,}** messages" for i, r in enumerate(rows, 1)]
        embed = discord.Embed(
            title="[TOP MESSAGES LEADERBOARD]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.group(name="invitebonus", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bonus_group(self, ctx: commands.Context):
        """Manage administrator bonus invites."""
        embed = discord.Embed(
            title="[BONUS INVITE COMMANDS]",
            description=(
                f"`{ctx.prefix}invitebonus add <user> <amount>` - Add bonus invites\n"
                f"`{ctx.prefix}invitebonus remove <user> <amount>` - Remove bonus invites\n"
                f"`{ctx.prefix}invitebonus reset <user>` - Reset a user's invites"
            ),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @bonus_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bonus_add(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Grant bonus invites to a member."""
        await db.execute(
            """
            INSERT INTO user_invites (guild_id, user_id, regular, leaves, fakes, bonus)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET bonus = user_invites.bonus + excluded.bonus
            """,
            ctx.guild.id, member.id, amount
        )
        embed = discord.Embed(title="[BONUS INVITES GRANTED]", description=f"Added **{amount}** bonus invites to {member.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @bonus_group.command(name="remove")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bonus_remove(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Deduct bonus invites from a member."""
        await db.execute(
            """
            INSERT INTO user_invites (guild_id, user_id, regular, leaves, fakes, bonus)
            VALUES (?, ?, 0, 0, 0, -?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET bonus = user_invites.bonus - ?
            """,
            ctx.guild.id, member.id, amount, amount
        )
        embed = discord.Embed(title="[BONUS INVITES DEDUCTED]", description=f"Removed **{amount}** bonus invites from {member.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @bonus_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bonus_reset(self, ctx: commands.Context, member: discord.Member):
        """Reset all invite statistics for a member."""
        await db.execute("DELETE FROM user_invites WHERE guild_id = ? AND user_id = ?", ctx.guild.id, member.id)
        embed = discord.Embed(title="[INVITES RESET]", description=f"Reset invite statistics for {member.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="invited")
    @commands.guild_only()
    async def invited_command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Lookup who invited a member to this server."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT inviter_id, code FROM invite_tracker WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[INVITE SOURCE]", description=f"No invite origin recorded for {target.mention} (joined before tracker or via discovery/vanity).", color=ACCENT_COLOR))

        inviter = ctx.guild.get_member(row["inviter_id"]) or await self.bot.fetch_user(row["inviter_id"])
        embed = discord.Embed(
            title=f"[INVITER LOOKUP] {target.display_name}",
            description=f"Invited by: {inviter.mention} (`{inviter}`)\nInvite Code: `{row['code']}`",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="messagesreset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def messages_reset(self, ctx: commands.Context, member: discord.Member):
        """Reset chat message count for a member."""
        await db.execute("DELETE FROM message_stats WHERE guild_id = ? AND user_id = ?", ctx.guild.id, member.id)
        embed = discord.Embed(title="[MESSAGES RESET]", description=f"Reset message statistics for {member.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Tracker | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="trackersync")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def tracker_sync(self, ctx: commands.Context):
        """Sync and re-cache all server active invites."""
        try:
            invs = await ctx.guild.invites()
            self._invite_cache[ctx.guild.id] = {i.code: i.uses for i in invs}
            await ctx.send(embed=discord.Embed(title="[OK] Invites Synced", description=f"Re-indexed **{len(invs)}** active invite links for {ctx.guild.name}.", color=ACCENT_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[ERROR]", description=f"Failed to sync invites: {e}", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tracker(bot))
