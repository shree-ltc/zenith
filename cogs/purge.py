"""
High-velocity message purification and channel sanitization engine for Zenith.
Supports granular filtering by bots, embeds, mentions, reactions, files, images, links, invites, and keywords.
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional

import discord
from discord.ext import commands

THEME_COLOR = 0x0F0F13
URL_REGEX = re.compile(r"https?://\S+")
INVITE_REGEX = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9]+")
EMOJI_REGEX = re.compile(r"<a?:[a-zA-Z0-9_]+:[0-9]+>|[\U00010000-\U0010ffff]")


class Purge(commands.Cog):
    """Channel message cleanup and sanitization commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _do_purge(self, ctx: commands.Context, limit: int, check=None, name: str = "Messages") -> None:
        if limit < 1 or limit > 1000:
            await ctx.reply("[ERROR] Please specify an amount between 1 and 1000.", mention_author=False)
            return

        try:
            # We add 1 to limit to consume the invocation command itself
            deleted = await ctx.channel.purge(limit=limit + 1, check=check)
            # Filter out command invocation from count if included
            count = len(deleted)
            if any(m.id == ctx.message.id for m in deleted):
                count -= 1

            embed = discord.Embed(
                title="[OK] Channel Purged",
                description=f"Purged **{count}** {name.lower()} from {ctx.channel.mention}.",
                color=THEME_COLOR
            )
            msg = await ctx.send(embed=embed)
            await asyncio.sleep(3.5)
            try:
                await msg.delete()
            except Exception:
                pass
        except discord.Forbidden:
            await ctx.reply("[ERROR] Zenith lacks `Manage Messages` permission in this channel.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Purge failed: {e}", mention_author=False)

    @commands.command(name="clear", aliases=["purge", "c"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge recent messages in the active channel."""
        await self._do_purge(ctx, amount)

    @commands.command(name="clearall", aliases=["purgeall"])
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearall_cmd(self, ctx: commands.Context):
        """Purge up to 1000 recent messages in the channel."""
        await self._do_purge(ctx, 1000, name="recent messages")

    @commands.command(name="clearuser", aliases=["purgeuser"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearuser_cmd(self, ctx: commands.Context, member: discord.Member, amount: int = 100):
        """Purge messages authored strictly by a specific user."""
        await self._do_purge(ctx, amount, check=lambda m: m.author.id == member.id, name=f"messages from {member.display_name}")

    @commands.command(name="clearbots", aliases=["purgebots", "cleartrash"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearbots_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages authored strictly by bots."""
        await self._do_purge(ctx, amount, check=lambda m: m.author.bot, name="bot messages")

    @commands.command(name="clearembeds", aliases=["clearembed", "purgeembeds"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearembed_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing rich embeds."""
        await self._do_purge(ctx, amount, check=lambda m: bool(m.embeds), name="embed messages")

    @commands.command(name="clearmentions", aliases=["purgementions", "clearment"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearmentions_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing user or role mentions."""
        await self._do_purge(ctx, amount, check=lambda m: bool(m.mentions or m.role_mentions or m.mention_everyone), name="mention messages")

    @commands.command(name="clearreactions", aliases=["purgereactions"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearreactions_cmd(self, ctx: commands.Context, amount: int = 50):
        """Remove all emoji reactions from recent messages."""
        if amount < 1 or amount > 200:
            return await ctx.reply("[ERROR] Provide a count between 1 and 200.", mention_author=False)

        count = 0
        async for msg in ctx.channel.history(limit=amount + 1):
            if msg.reactions:
                try:
                    await msg.clear_reactions()
                    count += 1
                except Exception:
                    pass

        embed = discord.Embed(
            title="[OK] Reactions Cleared",
            description=f"Cleared reactions from **{count}** messages in {ctx.channel.mention}.",
            color=THEME_COLOR
        )
        notice = await ctx.send(embed=embed)
        await asyncio.sleep(3.5)
        try:
            await notice.delete()
        except Exception:
            pass

    @commands.command(name="clearfiles", aliases=["purgefiles", "clearattachments"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearfiles_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing file attachments."""
        await self._do_purge(ctx, amount, check=lambda m: bool(m.attachments), name="attachment messages")

    @commands.command(name="clearimages", aliases=["purgeimages", "clearimgs"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearimages_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing images (attachments or image embeds)."""
        def has_image(m: discord.Message) -> bool:
            if any(a.content_type and a.content_type.startswith("image") for a in m.attachments):
                return True
            if any(e.type == "image" or e.image or e.thumbnail for e in m.embeds):
                return True
            return False

        await self._do_purge(ctx, amount, check=has_image, name="image messages")

    @commands.command(name="clearemojis", aliases=["clearemoji", "purgeemojis"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearemoji_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing custom or standard emojis."""
        await self._do_purge(ctx, amount, check=lambda m: bool(EMOJI_REGEX.search(m.content)), name="emoji messages")

    @commands.command(name="clearcontains", aliases=["clearcontain", "purgecontains", "clearmatch"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearcontain_cmd(self, ctx: commands.Context, text: str, amount: int = 100):
        """Purge messages containing a specific phrase."""
        needle = text.lower()
        await self._do_purge(ctx, amount, check=lambda m: needle in m.content.lower(), name=f"messages matching '{text}'")

    @commands.command(name="clearinvites", aliases=["purgeinvites"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearinvites_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing Discord server invites."""
        await self._do_purge(ctx, amount, check=lambda m: bool(INVITE_REGEX.search(m.content)), name="invite messages")

    @commands.command(name="clearlinks", aliases=["purgelinks"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearlinks_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages containing web URLs."""
        await self._do_purge(ctx, amount, check=lambda m: bool(URL_REGEX.search(m.content)), name="link messages")

    @commands.command(name="clearwebhooks", aliases=["purgewebhooks"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearwebhooks_cmd(self, ctx: commands.Context, amount: int = 100):
        """Purge messages sent via webhooks."""
        await self._do_purge(ctx, amount, check=lambda m: m.webhook_id is not None, name="webhook messages")

    @commands.command(name="clearuntil", aliases=["purgeuntil"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clearuntil_cmd(self, ctx: commands.Context, message_id: int):
        """Purge all messages up to a specific message ID."""
        try:
            target_msg = await ctx.channel.fetch_message(message_id)
        except Exception:
            return await ctx.reply(f"[ERROR] Target message `{message_id}` was not found in this channel.", mention_author=False)

        deleted = await ctx.channel.purge(after=target_msg, limit=500)
        embed = discord.Embed(
            title="[OK] Clear Until Complete",
            description=f"Purged **{len(deleted)}** messages up to `{message_id}`.",
            color=THEME_COLOR
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(3.5)
        try:
            await msg.delete()
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Purge(bot))
