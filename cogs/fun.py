"""
Mini-games and casual entertainment commands for Zenith.
Includes Rock Paper Scissors, 8Ball, dice rolls, animal imagery, ship compatibility, and roasts.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import random
from typing import Optional, List
import aiohttp
import discord
from discord.ext import commands
from discord import ui

ACCENT_COLOR = 0x0F0F13


class RPSView(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=30.0)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Start your own game with `z!rps`.", ephemeral=True)
            return False
        return True

    async def handle_choice(self, interaction: discord.Interaction, player_choice: str):
        choices = ["Rock", "Paper", "Scissors"]
        bot_choice = random.choice(choices)

        for child in self.children:
            child.disabled = True

        if player_choice == bot_choice:
            result = "Tie game."
            color = ACCENT_COLOR
        elif (
            (player_choice == "Rock" and bot_choice == "Scissors") or
            (player_choice == "Paper" and bot_choice == "Rock") or
            (player_choice == "Scissors" and bot_choice == "Paper")
        ):
            result = "You won."
            color = 0x00FF00
        else:
            result = "Zenith won."
            color = 0xFF0000

        embed = discord.Embed(title="[ROCK PAPER SCISSORS]", color=color)
        embed.add_field(name="Your Move", value=player_choice, inline=True)
        embed.add_field(name="Zenith's Move", value=bot_choice, inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Rock", style=discord.ButtonStyle.primary)
    async def rock_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "Rock")

    @ui.button(label="Paper", style=discord.ButtonStyle.primary)
    async def paper_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "Paper")

    @ui.button(label="Scissors", style=discord.ButtonStyle.primary)
    async def scissors_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "Scissors")


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="8ball", aliases=["eightball"])
    async def eightball_command(self, ctx: commands.Context, *, question: str):
        """Asks the 8-ball for an answer."""
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]
        answer = random.choice(responses)
        embed = discord.Embed(title="[MAGIC 8-BALL]", color=ACCENT_COLOR)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip_command(self, ctx: commands.Context):
        """Flips a coin."""
        outcome = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="[COIN TOSS]",
            description=f"The coin landed on **{outcome}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="roll", aliases=["dice"])
    async def roll_command(self, ctx: commands.Context, sides: int = 6):
        """Rolls a dice with the given number of sides (default 6)."""
        if sides < 2 or sides > 1000:
            return await ctx.reply(embed=discord.Embed(title="[INVALID DICE]", description="Sides must be between 2 and 1000.", color=ACCENT_COLOR), mention_author=False)

        val = random.randint(1, sides)
        embed = discord.Embed(
            title="[DICE ROLL]",
            description=f"Result: **{val}** (1-{sides})",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rps")
    async def rps_command(self, ctx: commands.Context):
        """Plays Rock, Paper, Scissors against the bot."""
        embed = discord.Embed(
            title="[ROCK PAPER SCISSORS]",
            description="Choose your move below.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        view = RPSView(ctx.author.id)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="roast")
    async def roast_command(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Sends a lighthearted roast."""
        user = target or ctx.author
        roasts = [
            "You bring everyone so much joy when you leave the channel.",
            "I would agree with you, but then we would both be wrong.",
            "If laughter is the best medicine, your code must be curing the world.",
            "You have something on your chin... no, the third one down.",
            "You are like a cloud. When you disappear, it becomes a brighter day."
        ]
        embed = discord.Embed(
            title="[ROAST]",
            description=f"{user.mention}: {random.choice(roasts)}",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="quote")
    async def quote_command(self, ctx: commands.Context):
        """Displays a software engineering quote."""
        quotes = [
            ("Talk is cheap. Show me the code.", "Linus Torvalds"),
            ("Programs must be written for people to read, and only incidentally for machines to execute.", "Harold Abelson"),
            ("Simplicity is prerequisite for reliability.", "Edsger W. Dijkstra"),
            ("Make it work, make it right, make it fast.", "Kent Beck"),
            ("First, solve the problem. Then, write the code.", "John Johnson")
        ]
        text, author = random.choice(quotes)
        embed = discord.Embed(
            title="[QUOTE]",
            description=f"\"{text}\"\n\n— **{author}**",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="choose", aliases=["pick"])
    async def choose_command(self, ctx: commands.Context, *options: str):
        """Randomly pick an option from a list."""
        if len(options) < 2:
            return await ctx.send(embed=discord.Embed(title="[INSUFFICIENT OPTIONS]", description="Provide at least 2 choices.", color=ACCENT_COLOR))

        choice = random.choice(options)
        embed = discord.Embed(
            title="[CHOICE SELECTED]",
            description=f"I choose: **{choice}**",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="ship")
    @commands.guild_only()
    async def ship_members(self, ctx: commands.Context, user1: discord.Member, user2: Optional[discord.Member] = None):
        """Calculate compatibility percentage between members."""
        second = user2 or ctx.author
        percent = random.randint(0, 100)

        bar_len = 12
        filled = int((percent / 100) * bar_len)
        bar = "[" + "=" * filled + "-" * (bar_len - filled) + "]"

        embed = discord.Embed(
            title="[COMPATIBILITY METER]",
            description=f"**{user1.display_name}** + **{second.display_name}**\n\n**Rating:** `{percent}%`\n`{bar}`",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="rate")
    async def rate_item(self, ctx: commands.Context, *, item: str):
        """Rate anything from 0 to 100."""
        score = random.randint(0, 100)
        embed = discord.Embed(
            title="[RATING]",
            description=f"I rate **{item}** a **{score}/100**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="iq")
    async def iq_score(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Generate a random IQ score for a member."""
        user = target or ctx.author
        score = random.randint(50, 160)
        embed = discord.Embed(
            title="[IQ ASSESSMENT]",
            description=f"{user.mention}'s measured IQ is **{score}**.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="simp")
    async def simp_rate(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Calculate simp percentage."""
        user = target or ctx.author
        rate = random.randint(0, 100)
        embed = discord.Embed(
            title="[SIMP METER]",
            description=f"{user.mention} is **{rate}%** simp.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Fun | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="cat")
    async def random_cat(self, ctx: commands.Context):
        """Get a random cat image."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(title="[CAT ASSET]", color=ACCENT_COLOR)
                        embed.set_image(url=data[0]["url"])
                        return await ctx.send(embed=embed)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(title="[API ERROR]", description="Could not fetch cat image.", color=ACCENT_COLOR))

    @commands.command(name="dog")
    async def random_dog(self, ctx: commands.Context):
        """Get a random dog image."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(title="[DOG ASSET]", color=ACCENT_COLOR)
                        embed.set_image(url=data["message"])
                        return await ctx.send(embed=embed)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(title="[API ERROR]", description="Could not fetch dog image.", color=ACCENT_COLOR))

    @commands.command(name="fox")
    async def random_fox(self, ctx: commands.Context):
        """Get a random fox image."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://randomfox.ca/floof/") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(title="[FOX ASSET]", color=ACCENT_COLOR)
                        embed.set_image(url=data["image"])
                        return await ctx.send(embed=embed)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(title="[API ERROR]", description="Could not fetch fox image.", color=ACCENT_COLOR))

    @commands.command(name="meme")
    async def random_meme(self, ctx: commands.Context):
        """Get a random community meme."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(title=f"[{data.get('title', 'COMMUNITY MEME')}]", color=ACCENT_COLOR)
                        embed.set_image(url=data["url"])
                        embed.set_footer(text=f"r/{data.get('subreddit', 'memes')} | Zenith")
                        return await ctx.send(embed=embed)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(title="[API ERROR]", description="Could not fetch meme.", color=ACCENT_COLOR))

    @commands.command(name="joke")
    async def random_joke(self, ctx: commands.Context):
        """Get a programming or general joke."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://v2.jokeapi.dev/joke/Programming,Miscellaneous?blacklistFlags=nsfw,religious,political,racist,sexist,explicit") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("type") == "single":
                            desc = data["joke"]
                        else:
                            desc = f"{data.get('setup')}\n\n> *{data.get('delivery')}*"
                        embed = discord.Embed(title="[JOKE]", description=desc, color=ACCENT_COLOR)
                        embed.set_footer(text="Zenith Fun | Developed by Shree")
                        return await ctx.send(embed=embed)
        except Exception:
            pass
        await ctx.send(embed=discord.Embed(title="[JOKE]", description="Why do programmers prefer dark mode? Because light attracts bugs.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
