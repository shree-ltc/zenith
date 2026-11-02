"""
Interactive Gaming and Challenge Suite for Zenith.
Includes button-driven Tic-Tac-Toe, Blackjack, Fast-Click reflex, Typeracer,
Wordle, Hangman, Trivia, and Rock-Paper-Scissors.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional, List
import discord
from discord import ui
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13


# ═══════════════════════════════════════════════════════════════
#  TIC-TAC-TOE UI COMPONENTS
# ═══════════════════════════════════════════════════════════════

class TicTacToeButton(ui.Button["TicTacToeView"]):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label=".", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: TicTacToeView = self.view

        if interaction.user != view.current_player:
            return await interaction.response.send_message("It is not your turn.", ephemeral=True)

        if view.board[self.y][self.x] != 0:
            return await interaction.response.send_message("That square is already occupied.", ephemeral=True)

        view.board[self.y][self.x] = view.current_val
        self.style = discord.ButtonStyle.danger if view.current_val == 1 else discord.ButtonStyle.primary
        self.label = "X" if view.current_val == 1 else "O"
        self.disabled = True

        winner = view.check_winner()
        if winner is not None:
            if winner == 1:
                content = f"Victory: {view.p1.mention} (X) wins."
            elif winner == 2:
                content = f"Victory: {view.p2.mention} (O) wins."
            else:
                content = "Draw: The board is full with no winner."

            for child in view.children:
                child.disabled = True
            view.stop()
            return await interaction.response.edit_message(content=content, view=view)

        # Switch turns
        if view.current_player == view.p1:
            view.current_player = view.p2
            view.current_val = 2
        else:
            view.current_player = view.p1
            view.current_val = 1

        await interaction.response.edit_message(content=f"Current Turn: {view.current_player.mention} ({'X' if view.current_val == 1 else 'O'})", view=view)


class TicTacToeView(ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=120.0)
        self.p1 = p1
        self.p2 = p2
        self.current_player = p1
        self.current_val = 1
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self) -> Optional[int]:
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != 0:
                return self.board[i][0]
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != 0:
                return self.board[0][i]

        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]

        if all(cell != 0 for row in self.board for cell in row):
            return 0

        return None


# ═══════════════════════════════════════════════════════════════
#  BLACKJACK UI COMPONENTS
# ═══════════════════════════════════════════════════════════════

def calculate_hand(cards: List[int]) -> int:
    total = sum(min(c, 10) if c != 1 else 11 for c in cards)
    aces = cards.count(1)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


class BlackjackView(ui.View):
    def __init__(self, player: discord.Member, bet: int):
        super().__init__(timeout=60.0)
        self.player = player
        self.bet = bet
        self.deck = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10] * 4
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    @ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.player:
            return await interaction.response.send_message("Not your hand.", ephemeral=True)

        self.player_hand.append(self.deck.pop())
        player_score = calculate_hand(self.player_hand)

        if player_score > 21:
            for child in self.children:
                child.disabled = True
            self.stop()
            embed = discord.Embed(
                title="[BLACKJACK - BUST]",
                description=f"Your Hand: `{self.player_hand}` (Score: `{player_score}`)\nYou busted and lost `{self.bet}` credits.",
                color=THEME_COLOR
            )
            return await interaction.response.edit_message(embed=embed, view=self)

        embed = discord.Embed(
            title="[BLACKJACK]",
            description=f"Your Hand: `{self.player_hand}` (Score: `{player_score}`)\nDealer Shows: `[{self.dealer_hand[0]}, ?]`",
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.player:
            return await interaction.response.send_message("Not your hand.", ephemeral=True)

        for child in self.children:
            child.disabled = True
        self.stop()

        player_score = calculate_hand(self.player_hand)
        dealer_score = calculate_hand(self.dealer_hand)

        while dealer_score < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_score = calculate_hand(self.dealer_hand)

        if dealer_score > 21 or player_score > dealer_score:
            outcome = f"Victory: Dealer score is `{dealer_score}`. You won `{self.bet}` credits."
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", self.bet * 2, interaction.guild.id, self.player.id)
        elif player_score == dealer_score:
            outcome = "Push: Tied scores. Bet refunded."
            await db.execute("UPDATE user_economy SET wallet = wallet + ? WHERE guild_id = ? AND user_id = ?", self.bet, interaction.guild.id, self.player.id)
        else:
            outcome = f"Loss: Dealer scored `{dealer_score}`. You lost `{self.bet}` credits."

        embed = discord.Embed(
            title="[BLACKJACK RESULT]",
            description=(
                f"**Your Hand:** `{self.player_hand}` (Score: `{player_score}`)\n"
                f"**Dealer Hand:** `{self.dealer_hand}` (Score: `{dealer_score}`)\n\n"
                f"**Result:** {outcome}"
            ),
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ═══════════════════════════════════════════════════════════════
#  ROCK-PAPER-SCISSORS UI
# ═══════════════════════════════════════════════════════════════

class RPSView(ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=30.0)
        self.author = author

    async def _handle_choice(self, interaction: discord.Interaction, player_choice: str):
        if interaction.user != self.author:
            return await interaction.response.send_message("This game is not for you.", ephemeral=True)

        bot_choice = random.choice(["rock", "paper", "scissors"])
        for child in self.children:
            child.disabled = True

        if player_choice == bot_choice:
            result = f"Tie! Both chose **{player_choice.upper()}**."
        elif (player_choice == "rock" and bot_choice == "scissors") or \
             (player_choice == "paper" and bot_choice == "rock") or \
             (player_choice == "scissors" and bot_choice == "paper"):
            result = f"Victory! You chose **{player_choice.upper()}**, Bot chose **{bot_choice.upper()}**."
        else:
            result = f"Defeat! You chose **{player_choice.upper()}**, Bot chose **{bot_choice.upper()}**."

        embed = discord.Embed(
            title="[ROCK PAPER SCISSORS]",
            description=result,
            color=THEME_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Rock", style=discord.ButtonStyle.secondary)
    async def rock_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_choice(interaction, "rock")

    @ui.button(label="Paper", style=discord.ButtonStyle.secondary)
    async def paper_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_choice(interaction, "paper")

    @ui.button(label="Scissors", style=discord.ButtonStyle.secondary)
    async def scissors_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self._handle_choice(interaction, "scissors")


# ═══════════════════════════════════════════════════════════════
#  GAMES COG DEFINITION
# ═══════════════════════════════════════════════════════════════

class Games(commands.Cog):
    """Interactive multi-player, puzzle, and challenge mini-games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="tictactoe", aliases=["ttt"])
    @commands.guild_only()
    async def tictactoe_command(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge a member to Tic-Tac-Toe."""
        if opponent == ctx.author or opponent.bot:
            return await ctx.send("[ERROR] Challenge a valid human member.")

        view = TicTacToeView(ctx.author, opponent)
        await ctx.send(f"Tic-Tac-Toe match started. Current Turn: {ctx.author.mention} (X)", view=view)

    @commands.command(name="blackjack", aliases=["bj"])
    @commands.guild_only()
    async def blackjack_command(self, ctx: commands.Context, bet: int = 50):
        """Play a round of Blackjack with economy wallet credits."""
        if bet < 10 or bet > 10000:
            return await ctx.send("[ERROR] Bet must be between 10 and 10,000 credits.")

        row = await db.fetchrow("SELECT wallet FROM user_economy WHERE guild_id = ? AND user_id = ?", ctx.guild.id, ctx.author.id)
        wallet = row["wallet"] if row else 0
        if wallet < bet:
            return await ctx.send(f"[ERROR] You need `{bet}` credits in your wallet to play.")

        await db.execute("UPDATE user_economy SET wallet = wallet - ? WHERE guild_id = ? AND user_id = ?", bet, ctx.guild.id, ctx.author.id)

        view = BlackjackView(ctx.author, bet)
        player_score = calculate_hand(view.player_hand)

        embed = discord.Embed(
            title="[BLACKJACK - GAME ACTIVE]",
            description=(
                f"**Your Hand:** `{view.player_hand}` (Score: `{player_score}`)\n"
                f"**Dealer Shows:** `[{view.dealer_hand[0]}, ?]`\n\n"
                f"Choose Hit or Stand below."
            ),
            color=THEME_COLOR
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name="guessnumber", aliases=["guess"])
    @commands.guild_only()
    async def guess_number(self, ctx: commands.Context, max_range: int = 50):
        """Guess a randomly generated number within range."""
        if max_range < 10 or max_range > 500:
            return await ctx.send("[ERROR] Provide a range between 10 and 500.")

        target = random.randint(1, max_range)
        await ctx.send(embed=discord.Embed(
            title="[NUMBER GUESSING]",
            description=f"Generated a number between 1 and {max_range}. Type your guess in chat (30s limit).",
            color=THEME_COLOR
        ))

        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            guess = int(msg.content)
            if guess == target:
                await ctx.send(embed=discord.Embed(title="[CORRECT]", description=f"Target was `{target}`. Well done.", color=THEME_COLOR))
            else:
                await ctx.send(embed=discord.Embed(title="[INCORRECT]", description=f"You guessed `{guess}`. Target was `{target}`.", color=THEME_COLOR))
        except Exception:
            await ctx.send(embed=discord.Embed(title="[TIME EXPIRED]", description=f"Time up. Target was `{target}`.", color=THEME_COLOR))

    @commands.command(name="connectfour", aliases=["c4", "connect4"])
    async def connectfour_cmd(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge an opponent to Connect Four."""
        if opponent == ctx.author or opponent.bot:
            return await ctx.send("[ERROR] Challenge a valid human member.")

        embed = discord.Embed(
            title="[CONNECT FOUR]",
            description=f"Match initiated: {ctx.author.mention} vs {opponent.mention}.\nConnect 4 discs horizontally, vertically, or diagonally to win.",
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name="fastclick", aliases=["reflex"])
    async def fastclick_cmd(self, ctx: commands.Context):
        """Test your reaction time with a reflex button."""
        embed = discord.Embed(
            title="[FAST CLICK] Reaction Benchmark",
            description="Get ready... Click the button as soon as it turns green!",
            color=THEME_COLOR
        )

        class ReflexButton(ui.View):
            def __init__(self, user: discord.Member):
                super().__init__(timeout=15.0)
                self.user = user
                self.ready_time = 0.0
                self.clicked = False

            @ui.button(label="WAIT...", style=discord.ButtonStyle.secondary, disabled=True)
            async def click_btn(self, interaction: discord.Interaction, button: ui.Button):
                if interaction.user != self.user:
                    return await interaction.response.send_message("Not your test.", ephemeral=True)
                if not self.ready_time:
                    return await interaction.response.send_message("Too early!", ephemeral=True)

                self.clicked = True
                reaction_time = round((time.time() - self.ready_time) * 1000)
                button.disabled = True
                button.label = f"{reaction_time} ms!"
                button.style = discord.ButtonStyle.success

                res_embed = discord.Embed(
                    title="[REACTION BENCHMARK]",
                    description=f"Your reflex latency: **{reaction_time} ms**",
                    color=THEME_COLOR
                )
                await interaction.response.edit_message(embed=res_embed, view=self)

        view = ReflexButton(ctx.author)
        msg = await ctx.send(embed=embed, view=view)

        # Sleep random 2 to 5 seconds
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)

        if not view.is_finished() and not view.clicked:
            view.ready_time = time.time()
            btn = view.children[0]
            btn.disabled = False
            btn.label = "CLICK NOW!"
            btn.style = discord.ButtonStyle.success
            try:
                await msg.edit(view=view)
            except Exception:
                pass

    @commands.command(name="typeracer", aliases=["typespeed"])
    async def typeracer_cmd(self, ctx: commands.Context):
        """Benchmark your typing speed in Words Per Minute (WPM)."""
        phrases = [
            "The quick brown fox jumps over the lazy dog.",
            "Distributed networks require fault tolerant consensus mechanisms.",
            "High performance asynchronous engines minimize event loop latency.",
            "Cryptography ensures tamper proof communication across public channels.",
            "Zenith provides enterprise infrastructure for community servers."
        ]
        target_phrase = random.choice(phrases)

        embed = discord.Embed(
            title="[TYPERACER] Speed Challenge",
            description=f"Type the exact sentence below as fast as you can (30s limit):\n\n```\n{target_phrase}\n```",
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

        start = time.time()

        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            elapsed = time.time() - start
            if msg.content.strip() == target_phrase:
                words = len(target_phrase.split())
                wpm = round((words / (elapsed / 60)))
                res = discord.Embed(
                    title="[TYPERACER RESULT]",
                    description=f"Accuracy: **100%**\nTime: **{elapsed:.2f}s**\nSpeed: **{wpm} WPM**",
                    color=THEME_COLOR
                )
                await ctx.send(embed=res)
            else:
                await ctx.send(f"[INCORRECT] Text did not match target phrase. (Time: {elapsed:.2f}s)")
        except asyncio.TimeoutError:
            await ctx.send("[TIME EXPIRED] 30 seconds elapsed.")

    @commands.command(name="trivia")
    async def trivia_cmd(self, ctx: commands.Context):
        """Answer a multiple-choice trivia challenge."""
        questions = [
            {
                "q": "What is the primary hashing algorithm used in Bitcoin proof-of-work?",
                "opts": ["SHA-256", "MD5", "Scrypt", "Blake2b"],
                "ans": "SHA-256"
            },
            {
                "q": "Which data structure uses LIFO (Last In, First Out) ordering?",
                "opts": ["Stack", "Queue", "Heap", "Linked List"],
                "ans": "Stack"
            },
            {
                "q": "What is the default TCP port for encrypted HTTPS traffic?",
                "opts": ["443", "80", "8080", "22"],
                "ans": "443"
            },
            {
                "q": "Which programming language was developed by Guido van Rossum?",
                "opts": ["Python", "Ruby", "Perl", "Go"],
                "ans": "Python"
            }
        ]
        q_data = random.choice(questions)
        options = list(q_data["opts"])
        random.shuffle(options)

        class TriviaView(ui.View):
            def __init__(self, author: discord.Member, correct: str):
                super().__init__(timeout=20.0)
                self.author = author
                self.correct = correct

                for opt in options:
                    btn = ui.Button(label=opt, style=discord.ButtonStyle.secondary)
                    btn.callback = self.make_callback(opt)
                    self.add_item(btn)

            def make_callback(self, choice: str):
                async def _cb(interaction: discord.Interaction):
                    if interaction.user != self.author:
                        return await interaction.response.send_message("Not your trivia.", ephemeral=True)

                    for child in self.children:
                        child.disabled = True

                    if choice == self.correct:
                        res = f"[CORRECT] **{choice}** is the correct answer!"
                    else:
                        res = f"[WRONG] Selected `{choice}`. Correct answer was **{self.correct}**."

                    embed = discord.Embed(title="[TRIVIA RESULT]", description=res, color=THEME_COLOR)
                    await interaction.response.edit_message(embed=embed, view=self)
                return _cb

        view = TriviaView(ctx.author, q_data["ans"])
        embed = discord.Embed(
            title="[TRIVIA CHALLENGE]",
            description=q_data["q"],
            color=THEME_COLOR
        )
        await ctx.send(embed=embed, view=view)

    @commands.command(name="wordle")
    async def wordle_cmd(self, ctx: commands.Context):
        """Play a single-player 5-letter Wordle challenge."""
        word_list = ["APPLE", "BRAIN", "CRANE", "DRIVE", "EARTH", "FLAME", "GHOST", "HEART", "LIGHT", "NIGHT", "POWER", "SHARK", "STORM", "WATER"]
        secret = random.choice(word_list)

        embed = discord.Embed(
            title="[WORDLE] 5-Letter Word Guess",
            description="You have **6 attempts** to guess the 5-letter secret word.\nType your 5-letter guesses in chat.",
            color=THEME_COLOR
        )
        await ctx.send(embed=embed)

        attempts = 0
        max_attempts = 6
        history = []

        def check(m: discord.Message):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content.strip()) == 5 and m.content.strip().isalpha()

        while attempts < max_attempts:
            try:
                msg = await self.bot.wait_for("message", timeout=60.0, check=check)
                guess = msg.content.strip().upper()
                attempts += 1

                # Calculate feedback: G = Green (exact), Y = Yellow (in word), B = Black (not in word)
                feedback = []
                for idx, char in enumerate(guess):
                    if char == secret[idx]:
                        feedback.append(f"[{char}]")
                    elif char in secret:
                        feedback.append(f"({char})")
                    else:
                        feedback.append(f" {char} ")

                line = f"`Attempt {attempts}:` {''.join(feedback)}"
                history.append(line)

                if guess == secret:
                    res_embed = discord.Embed(
                        title="[WORDLE VICTORY]",
                        description=f"Solved in **{attempts}/{max_attempts}** attempts!\n\n" + "\n".join(history),
                        color=THEME_COLOR
                    )
                    return await ctx.send(embed=res_embed)
                else:
                    status_embed = discord.Embed(
                        title=f"[WORDLE] Attempt {attempts}/{max_attempts}",
                        description="\n".join(history) + f"\n\n*`[X]` = Exact, `(X)` = Wrong Position, ` X ` = Not in word*",
                        color=THEME_COLOR
                    )
                    await ctx.send(embed=status_embed)

            except asyncio.TimeoutError:
                return await ctx.send(f"[TIME EXPIRED] Wordle session ended. Secret word was **{secret}**.")

        await ctx.send(f"[DEFEAT] Out of attempts. The secret word was **{secret}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
