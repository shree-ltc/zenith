"""
Mini-games and casual entertainment commands.
"""

import random
from typing import Optional
import discord
from discord.ext import commands
from discord import ui

from ui.embeds import ZenithEmbed
from ui.colors import Color


class RPSView(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=30.0)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "Start your own game with `z!rps`."),
                ephemeral=True
            )
            return False
        return True

    async def handle_choice(self, interaction: discord.Interaction, player_choice: str):
        choices = ["Rock", "Paper", "Scissors"]
        bot_choice = random.choice(choices)

        for child in self.children:
            child.disabled = True

        if player_choice == bot_choice:
            result = "Tie game."
            color = Color.WARNING
        elif (
            (player_choice == "Rock" and bot_choice == "Scissors") or
            (player_choice == "Paper" and bot_choice == "Rock") or
            (player_choice == "Scissors" and bot_choice == "Paper")
        ):
            result = "You won."
            color = Color.SUCCESS
        else:
            result = "Zenith won."
            color = Color.ERROR

        embed = ZenithEmbed(title="Rock, Paper, Scissors", color=color)
        embed.add_field(name="Your Move", value=player_choice, inline=True)
        embed.add_field(name="Zenith's Move", value=bot_choice, inline=True)
        embed.add_field(name="Result", value=result, inline=False)

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
        embed = ZenithEmbed(title="Magic 8-Ball", color=Color.PRIMARY)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="coinflip", aliases=["flip", "coin"])
    async def coinflip_command(self, ctx: commands.Context):
        """Flips a coin."""
        outcome = random.choice(["Heads", "Tails"])
        embed = ZenithEmbed(
            title="Coin Toss",
            description=f"The coin landed on **{outcome}**.",
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="roll", aliases=["dice"])
    async def roll_command(self, ctx: commands.Context, sides: int = 6):
        """Rolls a dice with the given number of sides (default 6)."""
        if sides < 2 or sides > 1000:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Dice", "Sides must be between 2 and 1000."), mention_author=False)

        val = random.randint(1, sides)
        embed = ZenithEmbed(
            title="Dice Roll",
            description=f"Result: **{val}** (1-{sides})",
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rps")
    async def rps_command(self, ctx: commands.Context):
        """Plays Rock, Paper, Scissors against the bot."""
        embed = ZenithEmbed(
            title="Rock, Paper, Scissors",
            description="Choose your move below.",
            color=Color.PRIMARY
        )
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
        embed = ZenithEmbed(
            title="Roast",
            description=f"{user.mention}: {random.choice(roasts)}",
            color=Color.WARNING
        )
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
        embed = ZenithEmbed(
            title="Quote",
            description=f"\"{text}\"\n\n— **{author}**",
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
