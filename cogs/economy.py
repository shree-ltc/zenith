"""
Virtual economy system with wallet and bank tracking.
"""

import random
import time
from typing import Optional

import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class Economy(commands.Cog):
    """Virtual currency, banking, and gambling systems."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Initializes economy schema on startup."""
        query = """
        CREATE TABLE IF NOT EXISTS user_economy (
            guild_id BIGINT,
            user_id BIGINT,
            wallet BIGINT DEFAULT 100,
            bank BIGINT DEFAULT 0,
            last_daily DOUBLE PRECISION DEFAULT 0,
            last_work DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """ if db.is_postgres else """
        CREATE TABLE IF NOT EXISTS user_economy (
            guild_id BIGINT,
            user_id BIGINT,
            wallet INTEGER DEFAULT 100,
            bank INTEGER DEFAULT 0,
            last_daily REAL DEFAULT 0,
            last_work REAL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );
        """
        await db.execute(query)

    async def get_balance(self, guild_id: int, user_id: int) -> dict:
        """Retrieves wallet and bank balances, initializing records if absent."""
        row = await db.fetchrow("SELECT wallet, bank, last_daily, last_work FROM user_economy WHERE guild_id = ? AND user_id = ?", guild_id, user_id)
        if not row:
            if db.is_postgres:
                await db.execute("INSERT INTO user_economy (guild_id, user_id, wallet, bank) VALUES (?, ?, 100, 0) ON CONFLICT DO NOTHING;", guild_id, user_id)
            else:
                await db.execute("INSERT OR IGNORE INTO user_economy (guild_id, user_id, wallet, bank) VALUES (?, ?, 100, 0);", guild_id, user_id)
            return {"wallet": 100, "bank": 0, "last_daily": 0, "last_work": 0}
        return dict(row)

    # ═══════════════════════════════════════════════════════════════
    #  BALANCE & CURRENCY COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="balance", aliases=["bal", "money", "wallet"])
    async def balance_command(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Checks wallet cash and bank reserves."""
        user = target or ctx.author
        data = await self.get_balance(ctx.guild.id, user.id)
        wallet = data["wallet"]
        bank = data["bank"]
        net_worth = wallet + bank

        embed = ZenithEmbed(title=f"{user.display_name}'s Balance", color=Color.PRIMARY)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Wallet", value=f"${wallet:,}", inline=True)
        embed.add_field(name="Bank", value=f"${bank:,}", inline=True)
        embed.add_field(name="Net Worth", value=f"${net_worth:,}", inline=True)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_command(self, ctx: commands.Context):
        """Claims daily dividend payout ($500 - $1,500)."""
        reward = random.randint(500, 1500)
        await db.execute(
            "UPDATE user_economy SET wallet = wallet + ?, last_daily = ? WHERE guild_id = ? AND user_id = ?",
            reward, time.time(), ctx.guild.id, ctx.author.id
        )
        embed = ZenithEmbed.success("Daily Claimed", f"Collected daily dividend of **${reward:,}**.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="work")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def work_command(self, ctx: commands.Context):
        """Works an hourly shift for cash ($100 - $400)."""
        jobs = [
            ("fixed a memory leak in a server daemon", 250),
            ("audited an antinuke security module", 320),
            ("optimized database indexing and query speed", 210),
            ("refactored asynchronous connection pools", 380),
            ("resolved network latency bottlenecks", 180),
            ("deployed a high-availability container", 290)
        ]
        task, wage = random.choice(jobs)
        wage += random.randint(-20, 50)

        await db.execute(
            "UPDATE user_economy SET wallet = wallet + ?, last_work = ? WHERE guild_id = ? AND user_id = ?",
            wage, time.time(), ctx.guild.id, ctx.author.id
        )
        embed = ZenithEmbed.success("Shift Completed", f"You {task} and earned **${wage:,}**.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit_command(self, ctx: commands.Context, amount: str):
        """Deposits wallet cash into your secure bank account."""
        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        wallet = data["wallet"]

        if amount.lower() == "all":
            to_dep = wallet
        else:
            try:
                to_dep = int(amount)
            except ValueError:
                return await ctx.reply(embed=ZenithEmbed.error("Invalid Amount", "Specify a valid number or `all`."), mention_author=False)

        if to_dep <= 0:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Amount", "You cannot deposit zero or negative funds."), mention_author=False)
        if to_dep > wallet:
            return await ctx.reply(embed=ZenithEmbed.error("Insufficient Funds", f"You only have **${wallet:,}** in your wallet."), mention_author=False)

        await db.execute(
            "UPDATE user_economy SET wallet = wallet - ?, bank = bank + ? WHERE guild_id = ? AND user_id = ?",
            to_dep, to_dep, ctx.guild.id, ctx.author.id
        )
        embed = ZenithEmbed.success("Deposit Successful", f"Deposited **${to_dep:,}** into your bank.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw_command(self, ctx: commands.Context, amount: str):
        """Withdraws funds from your bank into your wallet."""
        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        bank = data["bank"]

        if amount.lower() == "all":
            to_with = bank
        else:
            try:
                to_with = int(amount)
            except ValueError:
                return await ctx.reply(embed=ZenithEmbed.error("Invalid Amount", "Specify a valid number or `all`."), mention_author=False)

        if to_with <= 0:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Amount", "You cannot withdraw zero or negative funds."), mention_author=False)
        if to_with > bank:
            return await ctx.reply(embed=ZenithEmbed.error("Insufficient Funds", f"You only have **${bank:,}** in your bank account."), mention_author=False)

        await db.execute(
            "UPDATE user_economy SET bank = bank - ?, wallet = wallet + ? WHERE guild_id = ? AND user_id = ?",
            to_with, to_with, ctx.guild.id, ctx.author.id
        )
        embed = ZenithEmbed.success("Withdrawal Successful", f"Withdrew **${to_with:,}** from your bank.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="pay", aliases=["transfer", "give"])
    async def pay_command(self, ctx: commands.Context, recipient: discord.Member, amount: int):
        """Sends money directly to another member."""
        if recipient.id == ctx.author.id or recipient.bot:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Recipient", "You cannot send money to yourself or a bot."), mention_author=False)
        if amount <= 0:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Amount", "Payment amount must be greater than zero."), mention_author=False)

        author_data = await self.get_balance(ctx.guild.id, ctx.author.id)
        if amount > author_data["wallet"]:
            return await ctx.reply(embed=ZenithEmbed.error("Insufficient Funds", "You do not have enough wallet cash for this transaction."), mention_author=False)

        # Deduct from author, credit recipient
        await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", amount, ctx.guild.id, ctx.author.id)
        await self.get_balance(ctx.guild.id, recipient.id)
        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", amount, ctx.guild.id, recipient.id)

        embed = ZenithEmbed.success("Payment Sent", f"Transferred **${amount:,}** to {recipient.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="slots", aliases=["gamble", "slot"])
    async def slots_command(self, ctx: commands.Context, bet: int):
        """Plays the slot game with your wallet cash."""
        if bet < 10:
            return await ctx.reply(embed=ZenithEmbed.error("Minimum Bet", "The minimum bet is **$10**."), mention_author=False)

        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        if bet > data["wallet"]:
            return await ctx.reply(embed=ZenithEmbed.error("Insufficient Funds", "You do not have enough cash in your wallet."), mention_author=False)

        reels = ["A", "K", "Q", "J", "10", "7"]
        s1 = random.choice(reels)
        s2 = random.choice(reels)
        s3 = random.choice(reels)

        if s1 == s2 == s3:
            multiplier = 5 if s1 != "7" else 10
            win_amount = bet * multiplier
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", win_amount, ctx.guild.id, ctx.author.id)
            embed = ZenithEmbed(
                title="Slots: Triple Match",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nFull match. Won **${win_amount:,}** ({multiplier}x).",
                color=Color.SUCCESS
            )
        elif s1 == s2 or s2 == s3 or s1 == s3:
            win_amount = int(bet * 1.5)
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", win_amount - bet, ctx.guild.id, ctx.author.id)
            embed = ZenithEmbed(
                title="Slots: Pair Match",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nPair match. Won **${win_amount:,}** (1.5x).",
                color=Color.PRIMARY
            )
        else:
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)
            embed = ZenithEmbed(
                title="Slots: No Match",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nLost **${bet:,}**.",
                color=Color.ERROR
            )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="leaderboard", aliases=["rich", "topmoney"])
    async def leaderboard_command(self, ctx: commands.Context):
        """Displays the richest members in this server."""
        rows = await db.fetch(
            "SELECT user_id, (wallet + bank) as total FROM user_economy WHERE guild_id = ? ORDER BY total DESC LIMIT 10",
            ctx.guild.id
        )
        if not rows:
            return await ctx.reply(embed=ZenithEmbed.info("Economy Empty", "No accounts currently exist on this server."), mention_author=False)

        desc_lines = []
        for rank, row in enumerate(rows, start=1):
            desc_lines.append(f"**#{rank}** <@{row['user_id']}> - **${row['total']:,}**")

        embed = ZenithEmbed(
            title=f"Wealth Leaderboard — {ctx.guild.name}",
            description="\n".join(desc_lines),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
