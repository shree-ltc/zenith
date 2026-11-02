"""
User Profiles, Custom Bios, Community Reputation, and Marriage Matrix for Zenith.
Allows members to establish bios, award reputation merits, and manage virtual relationships.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from __future__ import annotations

import time
from typing import Optional
import discord
from discord import ui
from discord.ext import commands

from core.database import db
from core.config import config

THEME_COLOR = 0x0F0F13


class ProposalView(ui.View):
    def __init__(self, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=60.0)
        self.proposer = proposer
        self.target = target

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.target:
            return await interaction.response.send_message("This proposal is not for you.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        # Link spouses
        await db.execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, spouse_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET spouse_id = excluded.spouse_id
            """,
            interaction.guild_id, self.proposer.id, self.target.id
        )
        await db.execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, spouse_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET spouse_id = excluded.spouse_id
            """,
            interaction.guild_id, self.target.id, self.proposer.id
        )

        embed = discord.Embed(
            title="[MARRIAGE CONCLUDED]",
            description=f"{self.target.mention} accepted {self.proposer.mention}'s proposal. Congratulations.",
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.target:
            return await interaction.response.send_message("This proposal is not for you.", ephemeral=True)

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="[PROPOSAL DECLINED]",
            description=f"{self.target.mention} declined {self.proposer.mention}'s proposal.",
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)


class Profiles(commands.Cog):
    """User profiles, bios, community reputation, and relations."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["myprofile", "userprofile"])
    @commands.guild_only()
    async def user_profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display a member's community profile."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT * FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)

        bio = row["bio"] if row and row.get("bio") else "No bio configured."
        rep = row["rep"] if row and row.get("rep") else 0
        spouse_id = row["spouse_id"] if row and row.get("spouse_id") else None

        # Leveling metrics
        lvl_row = await db.fetchrow("SELECT level, xp FROM user_levels WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        level = lvl_row["level"] if lvl_row else 0
        xp = lvl_row["xp"] if lvl_row else 0

        # Economy metrics
        eco_row = await db.fetchrow("SELECT wallet, bank FROM user_economy WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        wallet = eco_row["wallet"] if eco_row else 0
        bank = eco_row["bank"] if eco_row else 0

        spouse_str = f"<@{spouse_id}>" if spouse_id else "Single"

        embed = discord.Embed(
            title=f"[PROFILE] {target.display_name}",
            description=f"> {bio}\n",
            color=THEME_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Reputation", value=f"**+{rep}** Points", inline=True)
        embed.add_field(name="Marital Status", value=spouse_str, inline=True)
        embed.add_field(name="Level & XP", value=f"Level **{level}** ({xp:,} XP)", inline=True)
        embed.add_field(name="Financial Net Worth", value=f"${(wallet + bank):,}", inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:D>" if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="Roles", value=f"{len(target.roles) - 1} roles", inline=True)
        embed.set_footer(text="Zenith Profiles | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="setbio", aliases=["bio"])
    @commands.guild_only()
    async def set_bio(self, ctx: commands.Context, *, bio: str):
        """Set your custom profile biography."""
        if len(bio) > 300:
            return await ctx.send(embed=discord.Embed(title="[BIO TOO LONG]", description="Bio must be 300 characters or fewer.", color=THEME_COLOR))

        await db.execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, bio) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET bio = excluded.bio
            """,
            ctx.guild.id, ctx.author.id, bio
        )
        embed = discord.Embed(title="[BIO UPDATED]", description=f"Updated your biography to:\n> {bio}", color=THEME_COLOR)
        embed.set_footer(text="Zenith Profiles | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="rep", aliases=["reputation", "+rep"])
    @commands.guild_only()
    async def give_rep(self, ctx: commands.Context, member: discord.Member):
        """Award a reputation point to another member (24-hour cooldown)."""
        if member == ctx.author or member.bot:
            return await ctx.send(embed=discord.Embed(title="[INVALID RECIPIENT]", description="You cannot award reputation to yourself or bots.", color=THEME_COLOR))

        row = await db.fetchrow("SELECT last_rep FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        last_rep = row["last_rep"] if row and row.get("last_rep") else 0
        now = time.time()

        if now - last_rep < 86400:
            remaining = int(86400 - (now - last_rep))
            hours = remaining // 3600
            mins = (remaining % 3600) // 60
            return await ctx.send(embed=discord.Embed(title="[COOLDOWN ACTIVE]", description=f"You can award reputation again in **{hours}h {mins}m**.", color=THEME_COLOR))

        await db.execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, last_rep) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET last_rep = excluded.last_rep
            """,
            ctx.guild.id, ctx.author.id, now
        )

        await db.execute(
            """
            INSERT INTO user_profiles (guild_id, user_id, rep) VALUES (?, ?, 1)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET rep = user_profiles.rep + 1
            """,
            ctx.guild.id, member.id
        )

        embed = discord.Embed(
            title="[REPUTATION AWARDED]",
            description=f"{ctx.author.mention} awarded +1 reputation to {member.mention}.",
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith Profiles | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="marry", aliases=["propose"])
    @commands.guild_only()
    async def propose_marriage(self, ctx: commands.Context, target: discord.Member):
        """Propose marriage to another member."""
        if target == ctx.author or target.bot:
            return await ctx.send(embed=discord.Embed(title="[INVALID PARTNER]", description="You cannot marry yourself or bots.", color=THEME_COLOR))

        row1 = await db.fetchrow("SELECT spouse_id FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        if row1 and row1.get("spouse_id"):
            return await ctx.send(embed=discord.Embed(title="[ALREADY MARRIED]", description=f"You are already married to <@{row1['spouse_id']}>. Divorce first.", color=THEME_COLOR))

        row2 = await db.fetchrow("SELECT spouse_id FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        if row2 and row2.get("spouse_id"):
            return await ctx.send(embed=discord.Embed(title="[TARGET MARRIED]", description=f"{target.mention} is already married to someone else.", color=THEME_COLOR))

        view = ProposalView(ctx.author, target)
        embed = discord.Embed(
            title="[MARRIAGE PROPOSAL]",
            description=f"{target.mention}, {ctx.author.mention} has proposed to you. Do you accept?",
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith Profiles | Developed by Shree")
        await ctx.send(content=target.mention, embed=embed, view=view)

    @commands.command(name="divorce")
    @commands.guild_only()
    async def divorce_spouse(self, ctx: commands.Context):
        """Divorce your current spouse."""
        row = await db.fetchrow("SELECT spouse_id FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        if not row or not row["spouse_id"]:
            return await ctx.send(embed=discord.Embed(title="[NOT MARRIED]", description="You are currently single.", color=THEME_COLOR))

        spouse_id = row["spouse_id"]
        await db.execute("UPDATE user_profiles SET spouse_id = NULL WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        await db.execute("UPDATE user_profiles SET spouse_id = NULL WHERE guild_id = ? AND user_id = ?", ctx.guild.id, spouse_id)

        embed = discord.Embed(
            title="[DIVORCE FINALIZED]",
            description=f"{ctx.author.mention} divorced <@{spouse_id}>.",
            color=THEME_COLOR
        )
        embed.set_footer(text="Zenith Profiles | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="profilereset")
    @commands.guild_only()
    async def profile_reset(self, ctx: commands.Context):
        """Reset your bio and reputation profile data."""
        await db.execute("UPDATE user_profiles SET bio = 'No bio configured.' WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        await ctx.send(embed=discord.Embed(title="[OK] Profile Reset", description="Your profile bio has been reset to defaults.", color=THEME_COLOR))

    @commands.command(name="reptop", aliases=["repleaderboard", "toprep"])
    @commands.guild_only()
    async def rep_leaderboard(self, ctx: commands.Context):
        """View the highest reputation members in this server."""
        rows = await db.fetch("SELECT user_id, rep FROM user_profiles WHERE guild_id = ? AND rep > 0 ORDER BY rep DESC LIMIT 10", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[REPUTATION MATRIX]", description="No reputation has been awarded yet in this server.", color=THEME_COLOR))

        lines = [f"**#{idx}** <@{r['user_id']}> — **+{r['rep']} Rep**" for idx, r in enumerate(rows, start=1)]
        embed = discord.Embed(
            title=f"[REPUTATION LEADERBOARD] {ctx.guild.name}",
            description="\n".join(lines),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="marriagelist", aliases=["marriages"])
    @commands.guild_only()
    async def marry_list(self, ctx: commands.Context):
        """List married couples in this server."""
        rows = await db.fetch("SELECT user_id, spouse_id FROM user_profiles WHERE guild_id = ? AND spouse_id IS NOT NULL", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[MARRIAGES]", description="No married members on this server.", color=THEME_COLOR))

        seen = set()
        couples = []
        for r in rows:
            pair = tuple(sorted([r["user_id"], r["spouse_id"]]))
            if pair not in seen:
                seen.add(pair)
                couples.append(f"• <@{pair[0]}> & <@{pair[1]}>")

        embed = discord.Embed(
            title=f"[SERVER COUPLES] ({len(couples)})",
            description="\n".join(couples[:25]),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="badges")
    @commands.guild_only()
    async def badges_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View badges and achievements earned by a user."""
        target = member or ctx.author
        badges = []
        if target.id == ctx.guild.owner_id:
            badges.append("`[Server Owner]`")
        if target.guild_permissions.administrator:
            badges.append("`[Administrator]`")
        if target.premium_since:
            badges.append("`[Nitro Booster]`")
        if target.id in config.OWNER_IDS:
            badges.append("`[Core Architect]`")

        row = await db.fetchrow("SELECT rep FROM user_profiles WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        if row and row["rep"] >= 10:
            badges.append("`[Community Veteran]`")

        if not badges:
            badges.append("`[Standard Member]`")

        embed = discord.Embed(
            title=f"[BADGES] {target.display_name}",
            description=" ".join(badges),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profiles(bot))
