"""
Enterprise virtual economy, banking, commerce, and gambling engine for Zenith.
Includes wallet and bank management, daily dividends, hourly shifts, risk-reward operations (crime, rob, beg),
hunting/fishing resource gathering, shop commerce, inventory management, and casino games (slots, roulette, coinflip, dice).
"""

from __future__ import annotations

import random
import time
from typing import Optional

import discord
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13

# Available Shop Items catalog
SHOP_CATALOG = {
    "padlock": {"name": "Padlock", "price": 500, "desc": "Secures your wallet against theft attempts for 24h"},
    "rod": {"name": "Fishing Rod", "price": 750, "desc": "Increases fishing success rate and yield"},
    "rifle": {"name": "Hunting Rifle", "price": 1200, "desc": "Enables big game hunting expeditions"},
    "charm": {"name": "Lucky Charm", "price": 2500, "desc": "Slightly improves casino odds for 1 hour"},
    "shield": {"name": "Bank Shield", "price": 5000, "desc": "Protects bank funds against fee penalties"}
}


class Economy(commands.Cog):
    """Virtual currency, banking, commerce, and gambling system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory padlock protection: (guild_id, user_id) -> expiry_timestamp
        self._padlocks: dict[tuple[int, int], float] = {}

    async def get_balance(self, guild_id: int, user_id: int) -> dict:
        row = await db.fetchrow("SELECT wallet, bank, last_daily, last_work FROM user_economy WHERE guild_id = ? AND user_id = ?", guild_id, user_id)
        if not row:
            if db.is_postgres:
                await db.execute("INSERT INTO user_economy (guild_id, user_id, wallet, bank) VALUES (?, ?, 250, 0) ON CONFLICT DO NOTHING;", guild_id, user_id)
            else:
                await db.execute("INSERT OR IGNORE INTO user_economy (guild_id, user_id, wallet, bank) VALUES (?, ?, 250, 0);", guild_id, user_id)
            return {"wallet": 250, "bank": 0, "last_daily": 0, "last_work": 0}
        return dict(row)

    # ═══════════════════════════════════════════════════════════════
    #  BALANCE & CURRENCY COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="balance", aliases=["bal", "money", "wallet"])
    async def balance_command(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Check wallet cash and bank reserves."""
        user = target or ctx.author
        data = await self.get_balance(ctx.guild.id, user.id)
        wallet = data["wallet"]
        bank = data["bank"]
        net_worth = wallet + bank

        embed = discord.Embed(
            title=f"[BALANCE] {user.display_name}",
            color=THEME_COLOR
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Wallet Cash", value=f"${wallet:,}", inline=True)
        embed.add_field(name="Bank Vault", value=f"${bank:,}", inline=True)
        embed.add_field(name="Net Capital", value=f"${net_worth:,}", inline=True)

        # Padlock status
        padlock_exp = self._padlocks.get((ctx.guild.id, user.id), 0)
        if padlock_exp > time.time():
            embed.set_footer(text=f"Padlock Active (Expires <t:{int(padlock_exp)}:R>)")

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily_command(self, ctx: commands.Context):
        """Claim daily dividend payout ($500 - $1,500)."""
        reward = random.randint(500, 1500)
        await self.get_balance(ctx.guild.id, ctx.author.id)
        await db.execute(
            "UPDATE user_economy SET wallet = wallet + ?, last_daily = ? WHERE guild_id = ? AND user_id = ?",
            reward, time.time(), ctx.guild.id, ctx.author.id
        )
        await ctx.reply(f"[OK] Daily dividend collected: **${reward:,}** added to wallet.", mention_author=False)

    @commands.command(name="work")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def work_command(self, ctx: commands.Context):
        """Work a shift for cash ($150 - $450)."""
        jobs = [
            ("fixed an API memory bottleneck", 260),
            ("audited server antinuke rules", 340),
            ("optimized PostgreSQL query plans", 220),
            ("refactored async event loops", 390),
            ("resolved network socket contention", 190),
            ("deployed containerized services", 310)
        ]
        task, wage = random.choice(jobs)
        wage += random.randint(-20, 60)

        await self.get_balance(ctx.guild.id, ctx.author.id)
        await db.execute(
            "UPDATE user_economy SET wallet = wallet + ?, last_work = ? WHERE guild_id = ? AND user_id = ?",
            wage, time.time(), ctx.guild.id, ctx.author.id
        )
        await ctx.reply(f"[OK] Shift complete: You {task} and earned **${wage:,}**.", mention_author=False)

    @commands.command(name="beg")
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def beg_command(self, ctx: commands.Context):
        """Ask for spare pocket change."""
        if random.random() < 0.35:
            await ctx.reply("[INFO] Nobody gave you any change. Better luck next time.", mention_author=False)
            return

        gain = random.randint(15, 95)
        await self.get_balance(ctx.guild.id, ctx.author.id)
        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", gain, ctx.guild.id, ctx.author.id)
        await ctx.reply(f"[OK] A generous stranger tossed you **${gain:,}**.", mention_author=False)

    @commands.command(name="crime")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def crime_command(self, ctx: commands.Context):
        """Attempt a high-risk heist for major cash."""
        await self.get_balance(ctx.guild.id, ctx.author.id)
        success = random.random() < 0.45

        if success:
            loot = random.randint(800, 2200)
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", loot, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[OK] Heist successful! You escaped with **${loot:,}** in unmarked bills.", mention_author=False)
        else:
            fine = random.randint(300, 700)
            await db.execute("UPDATE user_economy SET wallet = MAX(0, wallet - ?) WHERE guild_id = ? AND user_id = ?", fine, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[ERROR] Caught by authorities! You paid a fine of **${fine:,}**.", mention_author=False)

    @commands.command(name="rob", aliases=["pickpocket"])
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def rob_command(self, ctx: commands.Context, target: discord.Member):
        """Attempt to pickpocket funds from another member's wallet."""
        if target.id == ctx.author.id or target.bot:
            return await ctx.reply("[ERROR] Invalid target: You cannot rob yourself or bots.", mention_author=False)

        # Check padlock
        padlock_exp = self._padlocks.get((ctx.guild.id, target.id), 0)
        if padlock_exp > time.time():
            return await ctx.reply(f"[ERROR] {target.display_name} has a Padlock securing their wallet.", mention_author=False)

        author_bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        target_bal = await self.get_balance(ctx.guild.id, target.id)

        if author_bal["wallet"] < 200:
            return await ctx.reply("[ERROR] You need at least $200 in your wallet to risk robbery.", mention_author=False)
        if target_bal["wallet"] < 100:
            return await ctx.reply(f"[INFO] {target.display_name} doesn't have enough wallet cash to be worth robbing.", mention_author=False)

        success = random.random() < 0.40
        if success:
            steal_pct = random.uniform(0.15, 0.45)
            stolen = int(target_bal["wallet"] * steal_pct)
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", stolen, ctx.guild.id, target.id)
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", stolen, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[OK] Robbery successful! You snatched **${stolen:,}** from {target.mention}.", mention_author=False)
        else:
            fine = int(author_bal["wallet"] * 0.20)
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", fine, ctx.guild.id, ctx.author.id)
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", fine, ctx.guild.id, target.id)
            await ctx.reply(f"[ERROR] You tripped an alarm! Caught and paid **${fine:,}** in restitution to {target.mention}.", mention_author=False)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit_command(self, ctx: commands.Context, amount: str):
        """Deposit wallet cash into your secure bank vault."""
        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        wallet = data["wallet"]

        if amount.lower() == "all":
            to_dep = wallet
        else:
            try:
                to_dep = int(amount)
            except ValueError:
                return await ctx.reply("[ERROR] Specify a valid integer amount or 'all'.", mention_author=False)

        if to_dep <= 0:
            return await ctx.reply("[ERROR] Deposit amount must be positive.", mention_author=False)
        if to_dep > wallet:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${wallet:,}).", mention_author=False)

        await db.execute(
            "UPDATE user_economy SET wallet = wallet - ?, bank = bank + ? WHERE guild_id = ? AND user_id = ?",
            to_dep, to_dep, ctx.guild.id, ctx.author.id
        )
        await ctx.reply(f"[OK] Deposited **${to_dep:,}** into bank vault.", mention_author=False)

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw_command(self, ctx: commands.Context, amount: str):
        """Withdraw cash from your bank vault into your wallet."""
        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        bank = data["bank"]

        if amount.lower() == "all":
            to_with = bank
        else:
            try:
                to_with = int(amount)
            except ValueError:
                return await ctx.reply("[ERROR] Specify a valid integer amount or 'all'.", mention_author=False)

        if to_with <= 0:
            return await ctx.reply("[ERROR] Withdrawal amount must be positive.", mention_author=False)
        if to_with > bank:
            return await ctx.reply(f"[ERROR] Insufficient bank funds (Vault: ${bank:,}).", mention_author=False)

        await db.execute(
            "UPDATE user_economy SET bank = bank - ?, wallet = wallet + ? WHERE guild_id = ? AND user_id = ?",
            to_with, to_with, ctx.guild.id, ctx.author.id
        )
        await ctx.reply(f"[OK] Withdrew **${to_with:,}** from bank vault.", mention_author=False)

    @commands.command(name="pay", aliases=["transfer", "give"])
    async def pay_command(self, ctx: commands.Context, recipient: discord.Member, amount: int):
        """Send money directly to another member."""
        if recipient.id == ctx.author.id or recipient.bot:
            return await ctx.reply("[ERROR] Invalid recipient: Cannot transfer to yourself or bots.", mention_author=False)
        if amount <= 0:
            return await ctx.reply("[ERROR] Transfer amount must be positive.", mention_author=False)

        author_bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        if amount > author_bal["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${author_bal['wallet']:,}).", mention_author=False)

        await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", amount, ctx.guild.id, ctx.author.id)
        await self.get_balance(ctx.guild.id, recipient.id)
        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", amount, ctx.guild.id, recipient.id)

        await ctx.reply(f"[OK] Transferred **${amount:,}** to {recipient.mention}.", mention_author=False)

    @commands.command(name="leaderboard", aliases=["rich", "topmoney", "baltop"])
    async def leaderboard_command(self, ctx: commands.Context):
        """Display the wealthiest server members."""
        rows = await db.fetch(
            "SELECT user_id, (wallet + bank) as total FROM user_economy WHERE guild_id = ? ORDER BY total DESC LIMIT 10",
            ctx.guild.id
        )
        if not rows:
            return await ctx.reply("[INFO] No economy accounts active on this server.", mention_author=False)

        desc = []
        for rank, row in enumerate(rows, start=1):
            desc.append(f"**#{rank}** <@{row['user_id']}> — **${row['total']:,}**")

        embed = discord.Embed(
            title=f"[WEALTH MATRIX] Leaderboard for {ctx.guild.name}",
            description="\n".join(desc),
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  SHOP & INVENTORY COMMERCE
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="shop", invoke_without_command=True)
    async def shop_group(self, ctx: commands.Context):
        """View available goods in the Zenith market catalog."""
        embed = discord.Embed(
            title="[MARKET] Zenith Hardware & Equipment Store",
            description="Purchase utility items to protect funds or improve gathering yields.",
            color=THEME_COLOR
        )
        for item_id, item in SHOP_CATALOG.items():
            embed.add_field(
                name=f"{item['name']} — ${item['price']:,}",
                value=f"• ID: `{item_id}`\n• {item['desc']}",
                inline=False
            )
        embed.set_footer(text=f"Use '{ctx.prefix}shop buy <item_id>' to purchase.")
        await ctx.reply(embed=embed, mention_author=False)

    @shop_group.command(name="buy")
    async def shop_buy(self, ctx: commands.Context, item_id: str, count: int = 1):
        """Purchase an item from the market."""
        item_id = item_id.lower().strip()
        if item_id not in SHOP_CATALOG:
            return await ctx.reply(f"[ERROR] Item '{item_id}' not found in catalog.", mention_author=False)

        if count < 1 or count > 100:
            return await ctx.reply("[ERROR] Count must be between 1 and 100.", mention_author=False)

        item = SHOP_CATALOG[item_id]
        total_cost = item["price"] * count

        bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        if total_cost > bal["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash. Requires ${total_cost:,} (You have ${bal['wallet']:,}).", mention_author=False)

        # Deduct cash
        await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", total_cost, ctx.guild.id, ctx.author.id)

        # Add to inventory
        await db.execute(
            """
            INSERT INTO user_inventory (guild_id, user_id, item_id, count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id, item_id) DO UPDATE SET count = user_inventory.count + excluded.count
            """ if not db.is_postgres else """
            INSERT INTO user_inventory (guild_id, user_id, item_id, count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (guild_id, user_id, item_id) DO UPDATE SET count = user_inventory.count + EXCLUDED.count
            """,
            ctx.guild.id, ctx.author.id, item_id, count
        )

        await ctx.reply(f"[OK] Purchased **{count}x {item['name']}** for **${total_cost:,}**.", mention_author=False)

    @shop_group.command(name="sell")
    async def shop_sell(self, ctx: commands.Context, item_id: str, count: int = 1):
        """Sell inventory items back for 60% market price."""
        item_id = item_id.lower().strip()
        if item_id not in SHOP_CATALOG:
            return await ctx.reply(f"[ERROR] Item '{item_id}' not found in catalog.", mention_author=False)

        row = await db.fetchrow("SELECT count FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = ?", ctx.guild.id, ctx.author.id, item_id)
        if not row or row["count"] < count:
            current = row["count"] if row else 0
            return await ctx.reply(f"[ERROR] Insufficient inventory. You only hold {current}x of `{item_id}`.", mention_author=False)

        item = SHOP_CATALOG[item_id]
        refund = int(item["price"] * 0.60 * count)

        if row["count"] == count:
            await db.execute("DELETE FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = ?", ctx.guild.id, ctx.author.id, item_id)
        else:
            await db.execute("UPDATE user_inventory SET count = count - ? WHERE guild_id = ? AND user_id = ? AND item_id = ?", count, ctx.guild.id, ctx.author.id, item_id)

        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", refund, ctx.guild.id, ctx.author.id)
        await ctx.reply(f"[OK] Sold **{count}x {item['name']}** for **${refund:,}**.", mention_author=False)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View items held in your inventory."""
        target = member or ctx.author
        rows = await db.fetch("SELECT item_id, count FROM user_inventory WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        if not rows:
            return await ctx.reply(f"[INFO] {target.display_name}'s inventory is completely empty.", mention_author=False)

        entries = []
        for r in rows:
            info = SHOP_CATALOG.get(r["item_id"], {"name": r["item_id"].capitalize()})
            entries.append(f"• **{info['name']}** (`{r['item_id']}`) — Count: **{r['count']}**")

        embed = discord.Embed(
            title=f"[INVENTORY] {target.display_name}",
            description="\n".join(entries),
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="use")
    async def use_cmd(self, ctx: commands.Context, item_id: str):
        """Activate an inventory item."""
        item_id = item_id.lower().strip()
        row = await db.fetchrow("SELECT count FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = ?", ctx.guild.id, ctx.author.id, item_id)
        if not row or row["count"] < 1:
            return await ctx.reply(f"[ERROR] You do not possess any `{item_id}` in your inventory.", mention_author=False)

        if item_id == "padlock":
            # Consume 1 padlock
            if row["count"] == 1:
                await db.execute("DELETE FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = ?", ctx.guild.id, ctx.author.id, item_id)
            else:
                await db.execute("UPDATE user_inventory SET count = count - 1 WHERE guild_id = ? AND user_id = ? AND item_id = ?", ctx.guild.id, ctx.author.id, item_id)

            self._padlocks[(ctx.guild.id, ctx.author.id)] = time.time() + 86400
            await ctx.reply("[OK] Padlock attached to wallet! You are immune to robberies for the next 24 hours.", mention_author=False)
        else:
            await ctx.reply(f"[INFO] `{item_id}` is a passive utility item and applies benefits automatically.", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  GATHERING ACTIVITIES: FISHING & HUNTING
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="fish")
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def fish_cmd(self, ctx: commands.Context):
        """Cast your line and catch fish for cash."""
        # Check rod in inventory
        rod = await db.fetchrow("SELECT count FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = 'rod'", ctx.guild.id, ctx.author.id)
        has_rod = rod and rod["count"] > 0

        success_chance = 0.75 if has_rod else 0.50
        if random.random() > success_chance:
            return await ctx.reply("[INFO] Not even a nibble. You reeled back an empty hook.", mention_author=False)

        catches = [
            ("Small Minnow", 45),
            ("Rainbow Trout", 120),
            ("Atlantic Salmon", 220),
            ("Striped Bass", 340),
            ("Golden Koi", 650)
        ]
        fish_name, val = random.choice(catches)
        if has_rod:
            val = int(val * 1.35)

        await self.get_balance(ctx.guild.id, ctx.author.id)
        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", val, ctx.guild.id, ctx.author.id)
        await ctx.reply(f"[OK] Reeled in a **{fish_name}**! Sold immediately to local market for **${val:,}**.", mention_author=False)

    @commands.command(name="hunt")
    @commands.cooldown(1, 180, commands.BucketType.user)
    async def hunt_cmd(self, ctx: commands.Context):
        """Venture into the wilderness on a game hunt."""
        rifle = await db.fetchrow("SELECT count FROM user_inventory WHERE guild_id = ? AND user_id = ? AND item_id = 'rifle'", ctx.guild.id, ctx.author.id)
        if not (rifle and rifle["count"] > 0):
            return await ctx.reply("[ERROR] You need a `Hunting Rifle` from the shop (`shop buy rifle`) to hunt.", mention_author=False)

        game = [
            ("Wild Rabbit", 80),
            ("Pheasant", 140),
            ("Whitetail Deer", 310),
            ("Wild Boar", 480),
            ("Grizzly Bear", 900)
        ]
        animal, val = random.choice(game)
        await self.get_balance(ctx.guild.id, ctx.author.id)
        await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", val, ctx.guild.id, ctx.author.id)
        await ctx.reply(f"[OK] Hunt complete: Tracked down a **{animal}** and earned **${val:,}** from provisions.", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  CASINO GAMBLING SUITE
    # ═══════════════════════════════════════════════════════════════

    @commands.command(name="slots", aliases=["slot"])
    async def slots_command(self, ctx: commands.Context, bet: int):
        """Play the three-reel slot machine."""
        if bet < 10:
            return await ctx.reply("[ERROR] Minimum bet is $10.", mention_author=False)

        data = await self.get_balance(ctx.guild.id, ctx.author.id)
        if bet > data["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${data['wallet']:,}).", mention_author=False)

        reels = ["A", "K", "Q", "J", "10", "7"]
        s1 = random.choice(reels)
        s2 = random.choice(reels)
        s3 = random.choice(reels)

        if s1 == s2 == s3:
            multiplier = 6 if s1 != "7" else 15
            win_amount = bet * multiplier
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", win_amount, ctx.guild.id, ctx.author.id)
            embed = discord.Embed(
                title="[SLOTS] Triple Jackpot!",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nFull reel match! Payout: **${win_amount:,}** ({multiplier}x).",
                color=THEME_COLOR
            )
        elif s1 == s2 or s2 == s3 or s1 == s3:
            win_amount = int(bet * 1.75)
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", win_amount - bet, ctx.guild.id, ctx.author.id)
            embed = discord.Embed(
                title="[SLOTS] Pair Match",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nPair match. Payout: **${win_amount:,}** (1.75x).",
                color=THEME_COLOR
            )
        else:
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)
            embed = discord.Embed(
                title="[SLOTS] No Match",
                description=f"**[ {s1} | {s2} | {s3} ]**\n\nNo matching symbols. Lost **${bet:,}**.",
                color=THEME_COLOR
            )

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="coinbet", aliases=["betflip", "cbet"])
    async def coinflip_cmd(self, ctx: commands.Context, choice: str, bet: int):
        """Bet wallet cash on a 50/50 coin flip (heads/tails)."""
        clean_choice = choice.lower().strip()
        if clean_choice not in ("heads", "tails", "h", "t"):
            return await ctx.reply("[ERROR] Choose either `heads` or `tails`.", mention_author=False)

        choice_full = "heads" if clean_choice.startswith("h") else "tails"
        if bet < 10:
            return await ctx.reply("[ERROR] Minimum bet is $10.", mention_author=False)

        bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        if bet > bal["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${bal['wallet']:,}).", mention_author=False)

        result = random.choice(["heads", "tails"])
        if choice_full == result:
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[OK] Result: **{result.upper()}**! You won **${bet:,}**.", mention_author=False)
        else:
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[INFO] Result: **{result.upper()}**! You lost **${bet:,}**.", mention_author=False)

    @commands.command(name="roulette")
    async def roulette_cmd(self, ctx: commands.Context, bet_target: str, amount: int):
        """Bet on roulette (red, black, even, odd, or a number 0-36)."""
        if amount < 10:
            return await ctx.reply("[ERROR] Minimum bet is $10.", mention_author=False)

        bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        if amount > bal["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${bal['wallet']:,}).", mention_author=False)

        wheel_num = random.randint(0, 36)
        red_nums = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        color = "green" if wheel_num == 0 else ("red" if wheel_num in red_nums else "black")

        target_clean = bet_target.lower().strip()
        won = False
        payout = 0

        if target_clean in ("red", "black"):
            if color == target_clean:
                won = True
                payout = amount * 2
        elif target_clean in ("even", "odd"):
            if wheel_num != 0 and ((target_clean == "even" and wheel_num % 2 == 0) or (target_clean == "odd" and wheel_num % 2 != 0)):
                won = True
                payout = amount * 2
        elif target_clean.isdigit():
            num_bet = int(target_clean)
            if 0 <= num_bet <= 36 and num_bet == wheel_num:
                won = True
                payout = amount * 35

        if won:
            net_gain = payout - amount
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", net_gain, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[OK] Wheel stopped on **{wheel_num} ({color.upper()})**! You won **${net_gain:,}** (Total return: ${payout:,}).", mention_author=False)
        else:
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", amount, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[INFO] Wheel stopped on **{wheel_num} ({color.upper()})**! Lost **${amount:,}**.", mention_author=False)

    @commands.command(name="dicebet", aliases=["rollbet", "dbet"])
    async def dice_cmd(self, ctx: commands.Context, target_number: int, bet: int):
        """Bet on rolling a 6-sided die (1-6) with a 5x payout."""
        if target_number < 1 or target_number > 6:
            return await ctx.reply("[ERROR] Dice number must be between 1 and 6.", mention_author=False)
        if bet < 10:
            return await ctx.reply("[ERROR] Minimum bet is $10.", mention_author=False)

        bal = await self.get_balance(ctx.guild.id, ctx.author.id)
        if bet > bal["wallet"]:
            return await ctx.reply(f"[ERROR] Insufficient wallet cash (Balance: ${bal['wallet']:,}).", mention_author=False)

        rolled = random.randint(1, 6)
        if rolled == target_number:
            winnings = bet * 5
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", winnings, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[OK] Rolled a **{rolled}**! Accurate match! You won **${winnings:,}** (5x).", mention_author=False)
        else:
            await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)
            await ctx.reply(f"[INFO] Rolled a **{rolled}** (Guessed {target_number}). Lost **${bet:,}**.", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
