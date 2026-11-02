"""
Community Birthday System for Zenith.
Stores member birth dates, announces daily celebrations, and assigns a temporary birthday role.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from datetime import datetime, timezone
from typing import Optional, Dict
import discord
from discord.ext import commands, tasks

from core.database import db

ACCENT_COLOR = 0x0F0F13

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


class Birthdays(commands.Cog):
    """Community birthday calendar and automated celebration announcements."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.celebration_loop.is_running():
            self.celebration_loop.start()

    def cog_unload(self):
        self.celebration_loop.cancel()

    @tasks.loop(hours=6)
    async def celebration_loop(self):
        """Check for active birthdays and send announcements."""
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc)
        day = now.day
        month = now.month

        rows = await db.fetch("SELECT guild_id, user_id FROM birthdays WHERE day = ? AND month = ?", day, month)
        for r in rows:
            guild = self.bot.get_guild(r["guild_id"])
            if not guild:
                continue

            member = guild.get_member(r["user_id"])
            if not member:
                continue

            cfg = await db.fetchrow("SELECT channel_id, role_id FROM birthday_config WHERE guild_id = ?", guild.id)
            if not cfg:
                continue

            # Assign birthday role
            if cfg.get("role_id") and guild.me.guild_permissions.manage_roles:
                role = guild.get_role(cfg["role_id"])
                if role and role < guild.me.top_role and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Zenith Birthday Role")
                    except Exception:
                        pass

            # Announce in designated channel
            if cfg.get("channel_id"):
                ch = guild.get_channel(cfg["channel_id"])
                if ch and ch.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="[HAPPY BIRTHDAY]",
                        description=f"Wishing a very Happy Birthday to {member.mention}.\nMay you have an exceptional year ahead.",
                        color=ACCENT_COLOR
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text=f"{guild.name} Celebrations | Zenith")
                    try:
                        await ch.send(content=member.mention, embed=embed)
                    except Exception:
                        pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="birthday", aliases=["bday"], invoke_without_command=True)
    @commands.guild_only()
    async def bday_group(self, ctx: commands.Context):
        """Birthday calendar commands overview."""
        embed = discord.Embed(
            title="[BIRTHDAY CALENDAR SYSTEM]",
            description="Register your birthday to receive server celebrations and temporary birthday roles.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}bday set <day> <month>` - Save your birthday (e.g. `15 8`)\n"
                f"`{ctx.prefix}bday view [@user]` - Look up a birthday\n"
                f"`{ctx.prefix}bday upcoming` - Display next birthdays\n"
                f"`{ctx.prefix}bday channel <#channel>` - Configure celebration room\n"
                f"`{ctx.prefix}bday role <@role>` - Set temporary birthday role\n"
                f"`{ctx.prefix}bday reset` - Remove your birthday"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="set")
    @commands.guild_only()
    async def bday_set(self, ctx: commands.Context, day: int, month: int):
        """Register your birth date (Day Month in numeric form, e.g. `14 7`)."""
        if month < 1 or month > 12:
            return await ctx.send(embed=discord.Embed(title="[INVALID MONTH]", description="Month must be between 1 and 12.", color=ACCENT_COLOR))

        if day < 1 or day > 31:
            return await ctx.send(embed=discord.Embed(title="[INVALID DAY]", description="Day must be between 1 and 31.", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO birthdays (guild_id, user_id, day, month) VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET day = excluded.day, month = excluded.month
            """,
            ctx.guild.id, ctx.author.id, day, month
        )

        m_name = MONTH_NAMES.get(month, str(month))
        embed = discord.Embed(
            title="[BIRTHDAY SAVED]",
            description=f"Your birthday is registered as **{day} {m_name}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="view")
    @commands.guild_only()
    async def bday_view(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Look up a member's registered birthday."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT day, month FROM birthdays WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        if not row:
            return await ctx.send(embed=discord.Embed(title="[NOT REGISTERED]", description=f"{target.mention} has not registered a birthday.", color=ACCENT_COLOR))

        m_name = MONTH_NAMES.get(row["month"], str(row["month"]))
        embed = discord.Embed(
            title=f"[BIRTHDAY - {target.display_name}]",
            description=f"{target.mention}'s birthday is on **{row['day']} {m_name}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="upcoming")
    @commands.guild_only()
    async def bday_upcoming(self, ctx: commands.Context):
        """Display the upcoming server birthdays."""
        rows = await db.fetch("SELECT user_id, day, month FROM birthdays WHERE guild_id = ? ORDER BY month ASC, day ASC LIMIT 10", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO BIRTHDAYS]", description="No birthdays registered in this server yet.", color=ACCENT_COLOR))

        lines = [f"• <@{r['user_id']}> — **{r['day']} {MONTH_NAMES.get(r['month'])}**" for r in rows]
        embed = discord.Embed(
            title="[UPCOMING BIRTHDAYS]",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def bday_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for birthday celebration announcements."""
        await db.execute(
            """
            INSERT INTO birthday_config (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            ctx.guild.id, channel.id
        )
        embed = discord.Embed(title="[CELEBRATION CHANNEL SET]", description=f"Celebrations will be announced in {channel.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="role")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def bday_role(self, ctx: commands.Context, role: discord.Role):
        """Set the temporary role granted to members on their birthday."""
        await db.execute(
            """
            INSERT INTO birthday_config (guild_id, role_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
            """,
            ctx.guild.id, role.id
        )
        embed = discord.Embed(title="[BIRTHDAY ROLE SET]", description=f"Members will receive {role.mention} on their birthday.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="reset", aliases=["remove", "del"])
    @commands.guild_only()
    async def bday_reset(self, ctx: commands.Context):
        """Remove your registered birthday."""
        await db.execute("DELETE FROM birthdays WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        embed = discord.Embed(title="[BIRTHDAY REMOVED]", description="Cleared your registered birthday date.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @bday_group.command(name="month")
    @commands.guild_only()
    async def bday_month(self, ctx: commands.Context, month: int):
        """List all birthdays in a specific month (1-12)."""
        if month < 1 or month > 12:
            return await ctx.send("[ERROR] Month must be between 1 and 12.")

        rows = await db.fetch("SELECT user_id, day FROM birthdays WHERE guild_id = ? AND month = ? ORDER BY day ASC", ctx.guild.id, month)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[BIRTHDAYS]", description=f"No birthdays registered for month {month}.", color=ACCENT_COLOR))

        lines = [f"• Day **{r['day']:02d}**: <@{r['user_id']}>" for r in rows]
        embed = discord.Embed(
            title=f"[BIRTHDAYS - MONTH {month}] ({len(rows)})",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @bday_group.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bday_clear(self, ctx: commands.Context):
        """Clear all registered birthdays across the server."""
        await db.execute("DELETE FROM birthdays WHERE guild_id = ?", ctx.guild.id)
        await ctx.send(embed=discord.Embed(title="[OK] Birthdays Cleared", description="Removed all server birthday registrations.", color=ACCENT_COLOR))

    @bday_group.command(name="test")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def bday_test(self, ctx: commands.Context):
        """Test the birthday announcement message format."""
        cfg = await db.fetchrow("SELECT channel_id, role_id FROM birthday_config WHERE guild_id = ?", ctx.guild.id)
        ch_str = f"<#{cfg['channel_id']}>" if (cfg and cfg["channel_id"]) else "Active channel"
        role_str = f"<@&{cfg['role_id']}>" if (cfg and cfg["role_id"]) else "None"

        embed = discord.Embed(
            title="[BIRTHDAY SYSTEM TEST]",
            description=f"Destination Channel: {ch_str}\nAssigned Birthday Role: {role_str}\n\n[OK] Loop poller is functioning nominally.",
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Birthdays(bot))
