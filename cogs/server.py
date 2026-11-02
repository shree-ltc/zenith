"""
Server administration tools: channel nuking, lockdowns, dehoist, and role listings.
"""

from typing import Optional
import discord
from discord.ext import commands

from ui.embeds import ZenithEmbed
from ui.colors import Color
from ui.views import ConfirmView


class Server(commands.Cog):
    """Server-wide administrative workflows and structural maintenance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke_command(self, ctx: commands.Context):
        """Recreates the current channel from scratch to erase all history, preserving permissions."""
        confirm_view = ConfirmView(ctx.author.id, timeout=30.0)
        confirm_embed = ZenithEmbed.warning(
            "Confirm Channel Nuke",
            f"Are you absolutely sure you want to nuke {ctx.channel.mention}?\n"
            "This will clone the channel settings and permanently delete all previous message history."
        )
        msg = await ctx.reply(embed=confirm_embed, view=confirm_view, mention_author=False)
        await confirm_view.wait()

        if confirm_view.value is True:
            old_channel = ctx.channel
            pos = old_channel.position
            new_channel = await old_channel.clone(reason=f"Zenith Nuke by {ctx.author}")
            await old_channel.delete(reason=f"Zenith Nuke by {ctx.author}")
            await new_channel.edit(position=pos)

            nuke_embed = ZenithEmbed.success(
                "Channel Nuked",
                f"This channel has been recreated by {ctx.author.mention}."
            )
            await new_channel.send(embed=nuke_embed)
        else:
            await msg.edit(embed=ZenithEmbed.info("Cancelled", "Nuke sequence aborted."), view=None)

    @commands.command(name="lockdown")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown_command(self, ctx: commands.Context):
        """Locks down every text channel in the server simultaneously."""
        status_msg = await ctx.reply(embed=ZenithEmbed.warning("Initiating Lockdown", "Securing all public text channels..."), mention_author=False)
        locked = 0

        for channel in ctx.guild.text_channels:
            if channel.overwrites_for(ctx.guild.default_role).send_messages is not False:
                try:
                    await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"Zenith Server Lockdown by {ctx.author}")
                    locked += 1
                except Exception:
                    pass

        await status_msg.edit(embed=ZenithEmbed.success("Server Lockdown Complete", f"Secured **{locked}** text channels from member messaging."))

    @commands.command(name="unlockdown")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockdown_command(self, ctx: commands.Context):
        """Restores public messaging across all server channels."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Lifting Lockdown", "Restoring channel permissions..."), mention_author=False)
        unlocked = 0

        for channel in ctx.guild.text_channels:
            if channel.overwrites_for(ctx.guild.default_role).send_messages is False:
                try:
                    await channel.set_permissions(ctx.guild.default_role, send_messages=None, reason=f"Zenith Lockdown Lifted by {ctx.author}")
                    unlocked += 1
                except Exception:
                    pass

        await status_msg.edit(embed=ZenithEmbed.success("Lockdown Lifted", f"Re-opened **{unlocked}** channels to community messaging."))

    @commands.command(name="dehoist")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def dehoist_command(self, ctx: commands.Context):
        """Removes hoisting special characters (!, @, #, $, ?, .) from member nicknames."""
        status_msg = await ctx.reply(embed=ZenithEmbed.info("Dehoisting", "Scanning member list for hoisted characters..."), mention_author=False)
        hoist_chars = ("!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_", "+", "=", "[", "]", "{", "}", ";", ":", "'", '"', "<", ">", ",", ".", "/", "?", "`", "~")
        count = 0

        for member in ctx.guild.members:
            if member.top_role < ctx.guild.me.top_role and not member.bot:
                name = member.display_name
                if name.startswith(hoist_chars):
                    clean_name = name.lstrip("".join(hoist_chars)).strip() or "Dehoisted User"
                    try:
                        await member.edit(nick=clean_name, reason="Zenith Dehoist System")
                        count += 1
                    except Exception:
                        pass

        await status_msg.edit(embed=ZenithEmbed.success("Dehoist Finished", f"Cleaned nicknames for **{count}** members."))

    @commands.command(name="emojis", aliases=["emojilist"])
    async def emojis_command(self, ctx: commands.Context):
        """Displays total custom emojis available in this guild."""
        emojis = ctx.guild.emojis
        if not emojis:
            return await ctx.reply(embed=ZenithEmbed.info("No Emojis", "This guild has no custom emojis uploaded."), mention_author=False)

        animated = sum(1 for e in emojis if e.animated)
        static = len(emojis) - animated
        emoji_sample = " ".join(str(e) for e in emojis[:50])
        if len(emojis) > 50:
            emoji_sample += f"\n*...and {len(emojis) - 50} more.*"

        embed = ZenithEmbed(
            title=f"Custom Emojis [{len(emojis)}]",
            description=f"Static: **{static}** | Animated: **{animated}**\n\n{emoji_sample}",
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="inrole")
    async def inrole_command(self, ctx: commands.Context, *, role: discord.Role):
        """Lists all members assigned to a specific role."""
        members = role.members
        if not members:
            return await ctx.reply(embed=ZenithEmbed.info("Empty Role", f"No members currently possess {role.mention}."), mention_author=False)

        sample = ", ".join(m.mention for m in members[:40])
        if len(members) > 40:
            sample += f" *(+{len(members) - 40} more)*"

        embed = ZenithEmbed(
            title=f"Members in @{role.name} [{len(members)}]",
            description=sample,
            color=role.color if role.color.value != 0 else Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="boosters")
    async def boosters_command(self, ctx: commands.Context):
        """Lists all server nitro boosters."""
        boosters = ctx.guild.premium_subscribers
        if not boosters:
            return await ctx.reply(embed=ZenithEmbed.info("No Boosters", "This server currently has no active nitro boosters."), mention_author=False)

        desc = "\n".join(f"• {m.mention} — Boosting since <t:{int(m.premium_since.timestamp())}:R>" for m in boosters if m.premium_since)
        embed = ZenithEmbed(
            title=f"Server Boosters [{len(boosters)}]",
            description=desc,
            color=discord.Colour.from_rgb(244, 127, 255)  # Nitro Pink
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))
