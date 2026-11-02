"""
Server infrastructure and guild assets management for Zenith.
Includes channel recreation (nuke), emergency lockdowns, dehoisting, asset lookups (icon, banner, splash),
role distributions, boosters, channel categorizations, and pruning estimates.
"""

from __future__ import annotations

from typing import Optional
import discord
from discord.ext import commands

from ui.views import ConfirmView

THEME_COLOR = 0x0F0F13


class Server(commands.Cog):
    """Server-wide administrative workflows and structural maintenance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def nuke_command(self, ctx: commands.Context):
        """Recreates the current channel from scratch to erase history, preserving permissions."""
        confirm_view = ConfirmView(ctx.author.id, timeout=30.0)
        confirm_embed = discord.Embed(
            title="[CONFIRMATION REQUIRED] Channel Nuke",
            description=f"Are you sure you want to nuke {ctx.channel.mention}?\nThis will clone all channel permissions and erase past message history.",
            color=THEME_COLOR
        )
        msg = await ctx.reply(embed=confirm_embed, view=confirm_view, mention_author=False)
        await confirm_view.wait()

        if confirm_view.value is True:
            old_channel = ctx.channel
            pos = old_channel.position
            new_channel = await old_channel.clone(reason=f"Nuke by {ctx.author}")
            await old_channel.delete(reason=f"Nuke by {ctx.author}")
            await new_channel.edit(position=pos)

            embed = discord.Embed(
                title="[OK] Channel Nuked",
                description=f"This channel has been freshly recreated by {ctx.author.mention}.",
                color=THEME_COLOR
            )
            await new_channel.send(embed=embed)
        else:
            await msg.edit(content="[INFO] Channel nuke aborted.", embed=None, view=None)

    @commands.command(name="lockdown")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown_command(self, ctx: commands.Context):
        """Locks down every text channel in the server simultaneously."""
        status_msg = await ctx.reply("[INFO] Securing public channels across server...", mention_author=False)
        locked = 0

        for channel in ctx.guild.text_channels:
            if channel.overwrites_for(ctx.guild.default_role).send_messages is not False:
                try:
                    await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"Server Lockdown by {ctx.author}")
                    locked += 1
                except Exception:
                    pass

        embed = discord.Embed(
            title="[OK] Server Lockdown Active",
            description=f"Locked **{locked}** text channels against `@everyone` messaging.",
            color=THEME_COLOR
        )
        await status_msg.edit(content=None, embed=embed)

    @commands.command(name="unlockdown")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockdown_command(self, ctx: commands.Context):
        """Restores public messaging across all server channels."""
        status_msg = await ctx.reply("[INFO] Restoring channel permissions...", mention_author=False)
        unlocked = 0

        for channel in ctx.guild.text_channels:
            if channel.overwrites_for(ctx.guild.default_role).send_messages is False:
                try:
                    await channel.set_permissions(ctx.guild.default_role, send_messages=None, reason=f"Lockdown lifted by {ctx.author}")
                    unlocked += 1
                except Exception:
                    pass

        embed = discord.Embed(
            title="[OK] Server Lockdown Lifted",
            description=f"Re-opened **{unlocked}** text channels.",
            color=THEME_COLOR
        )
        await status_msg.edit(content=None, embed=embed)

    @commands.command(name="dehoist")
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def dehoist_command(self, ctx: commands.Context):
        """Removes hoisting special characters from member nicknames."""
        status_msg = await ctx.reply("[INFO] Scanning member list for hoisted characters...", mention_author=False)
        hoist_chars = ("!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_", "+", "=", "[", "]", "{", "}", ";", ":", "'", '"', "<", ">", ",", ".", "/", "?", "`", "~")
        count = 0

        for member in ctx.guild.members:
            if member.top_role < ctx.guild.me.top_role and not member.bot:
                name = member.display_name
                if name.startswith(hoist_chars):
                    clean_name = name.lstrip("".join(hoist_chars)).strip() or "Dehoisted Member"
                    try:
                        await member.edit(nick=clean_name, reason="Dehoist System")
                        count += 1
                    except Exception:
                        pass

        embed = discord.Embed(
            title="[OK] Dehoist Sequence Completed",
            description=f"Sanitized nicknames for **{count}** members.",
            color=THEME_COLOR
        )
        await status_msg.edit(content=None, embed=embed)

    @commands.command(name="emojis", aliases=["emojilist"])
    async def emojis_command(self, ctx: commands.Context):
        """Displays custom emojis available in this guild."""
        emojis = ctx.guild.emojis
        if not emojis:
            return await ctx.reply("[INFO] This guild has no custom emojis uploaded.", mention_author=False)

        animated = sum(1 for e in emojis if e.animated)
        static = len(emojis) - animated
        emoji_sample = " ".join(str(e) for e in emojis[:50])
        if len(emojis) > 50:
            emoji_sample += f"\n*...and {len(emojis) - 50} more.*"

        embed = discord.Embed(
            title=f"[SERVER EMOJIS] Count: {len(emojis)}",
            description=f"Static: **{static}** | Animated: **{animated}**\n\n{emoji_sample}",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="inrole")
    async def inrole_command(self, ctx: commands.Context, *, role: discord.Role):
        """Lists members assigned to a specific role."""
        members = role.members
        if not members:
            return await ctx.reply(f"[INFO] No members currently possess role {role.mention}.", mention_author=False)

        sample = ", ".join(m.mention for m in members[:40])
        if len(members) > 40:
            sample += f" *(+{len(members) - 40} more)*"

        embed = discord.Embed(
            title=f"[ROLE MEMBERS] @{role.name} ({len(members)})",
            description=sample,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="boosters")
    async def boosters_command(self, ctx: commands.Context):
        """Lists active Nitro boosters in this server."""
        boosters = ctx.guild.premium_subscribers
        if not boosters:
            return await ctx.reply("[INFO] This server currently has no active Nitro boosters.", mention_author=False)

        desc = "\n".join(f"• {m.mention} — Boosting since <t:{int(m.premium_since.timestamp())}:R>" for m in boosters if m.premium_since)
        if len(desc) > 3900:
            desc = desc[:3900] + "\n..."

        embed = discord.Embed(
            title=f"[NITRO BOOSTERS] Level {ctx.guild.premium_tier} ({len(boosters)} Boosters)",
            description=desc,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)



    @commands.command(name="serversplash", aliases=["guildsplash", "splash"])
    async def serversplash_cmd(self, ctx: commands.Context):
        """Display the server's invite splash background."""
        if not ctx.guild.splash:
            return await ctx.reply("[INFO] This server does not have an invite splash background.", mention_author=False)

        embed = discord.Embed(
            title=f"[INVITE SPLASH] {ctx.guild.name}",
            description=f"[Direct Asset Link]({ctx.guild.splash.url})",
            color=THEME_COLOR
        )
        embed.set_image(url=ctx.guild.splash.url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverroles", aliases=["guildroles", "roleslist"])
    async def serverroles_cmd(self, ctx: commands.Context):
        """Display an index of all server roles ordered by hierarchy."""
        roles = [r.mention for r in reversed(ctx.guild.roles) if r.name != "@everyone"]
        if not roles:
            return await ctx.reply("[INFO] No custom roles found in this server.", mention_author=False)

        desc = ", ".join(roles[:60])
        if len(roles) > 60:
            desc += f" *(+{len(roles) - 60} more)*"

        embed = discord.Embed(
            title=f"[SERVER ROLES] Total: {len(ctx.guild.roles) - 1}",
            description=desc,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverfeatures", aliases=["features"])
    async def serverfeatures_cmd(self, ctx: commands.Context):
        """List Discord-enabled features unlocked by this guild."""
        features = ctx.guild.features
        if not features:
            return await ctx.reply("[INFO] This server has no special Discord features unlocked.", mention_author=False)

        desc = "\n".join(f"• `{feat}`" for feat in sorted(features))
        embed = discord.Embed(
            title=f"[SERVER FEATURES] {ctx.guild.name} ({len(features)})",
            description=desc,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="serverprune", aliases=["prunecheck"])
    @commands.has_permissions(administrator=True)
    async def serverprune_cmd(self, ctx: commands.Context, days: int = 7):
        """Estimate the count of inactive members that would be pruned."""
        if days < 1 or days > 30:
            return await ctx.reply("[ERROR] Prune estimation days must be between 1 and 30.", mention_author=False)

        try:
            estimate = await ctx.guild.estimate_pruned_members(days=days)
            embed = discord.Embed(
                title=f"[PRUNE ESTIMATE] Inactivity: {days} Days",
                description=f"Approximately **{estimate}** inactive members with no roles would be removed by a prune.",
                color=THEME_COLOR
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Could not fetch prune estimate: {e}", mention_author=False)

    @commands.group(name="category", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def category_group(self, ctx: commands.Context):
        """Category management suite."""
        await ctx.send_help(ctx.command)

    @category_group.command(name="create")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def cat_create(self, ctx: commands.Context, *, name: str):
        """Create a new channel category."""
        try:
            cat = await ctx.guild.create_category(name=name, reason=f"Created by {ctx.author}")
            await ctx.reply(f"[OK] Category `{cat.name}` created successfully.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to create category: {e}", mention_author=False)

    @category_group.command(name="delete")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def cat_delete(self, ctx: commands.Context, *, category: discord.CategoryChannel):
        """Delete an existing channel category."""
        try:
            name = category.name
            await category.delete(reason=f"Deleted by {ctx.author}")
            await ctx.reply(f"[OK] Category `{name}` deleted.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to delete category: {e}", mention_author=False)

    @category_group.command(name="rename")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def cat_rename(self, ctx: commands.Context, category: discord.CategoryChannel, *, new_name: str):
        """Rename an existing category."""
        try:
            old = category.name
            await category.edit(name=new_name, reason=f"Renamed by {ctx.author}")
            await ctx.reply(f"[OK] Category `{old}` renamed to `{new_name}`.", mention_author=False)
        except Exception as e:
            await ctx.reply(f"[ERROR] Failed to rename category: {e}", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Server(bot))
