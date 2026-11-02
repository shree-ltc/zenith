"""
Mention Response Handler for Zenith.
Replies with system information, active prefix, and help navigation when the bot is pinged.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class MentionReply(commands.Cog):
    """Responds when the bot is mentioned."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Check if message is strictly mentioning the bot
        if self.bot.user in message.mentions and len(message.content.split()) == 1:
            prefix = await db.get_prefix(message.guild.id)
            uptime_seconds = int(time.time() - getattr(self.bot, "launch_time", time.time()))
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

            embed = discord.Embed(
                title="[ZENITH AUTONOMOUS DEFENSE]",
                description=(
                    f"**Server Prefix:** `{prefix}`\n"
                    f"**Command Directory:** Run `{prefix}help` to explore all modules.\n"
                    f"**System Uptime:** `{uptime_str}`\n"
                    f"**Security Engine:** Active & Monitoring"
                ),
                color=ACCENT_COLOR
            )
            embed.set_footer(text="Developed by Shree (shree-ltc | ID: 1465912900710305822)")
            try:
                await message.reply(embed=embed, mention_author=False)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MentionReply(bot))
