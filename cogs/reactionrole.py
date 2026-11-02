"""
Reaction Role Binding Engine for Zenith.
Supports self-assignable roles linked to message emoji reactions with memory caching.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db
from core.security import is_dangerous_role, validate_role_hierarchy

ACCENT_COLOR = 0x0F0F13


class ReactionRole(commands.Cog):
    """Self-assignable role dispatch via emoji reactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # RAM Cache: {(message_id, emoji): role_id}
        self._cache: Dict[tuple[int, str], int] = {}

    async def cog_load(self) -> None:
        """Preload reaction role mappings into cache."""
        rows = await db.fetch("SELECT message_id, emoji, role_id FROM reaction_roles")
        for r in rows:
            self._cache[(r["message_id"], r["emoji"])] = r["role_id"]

    # ---------------------------------------------------------
    # LISTENERS
    # ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return

        emoji_str = str(payload.emoji)
        key = (payload.message_id, emoji_str)

        if key in self._cache:
            role_id = self._cache[key]
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            role = guild.get_role(role_id)
            if role and role < guild.me.top_role and guild.me.guild_permissions.manage_roles:
                try:
                    await payload.member.add_roles(role, reason="Zenith Reaction Role Self-Assignment")
                except Exception:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        emoji_str = str(payload.emoji)
        key = (payload.message_id, emoji_str)

        if key in self._cache:
            role_id = self._cache[key]
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member or member.bot:
                return

            role = guild.get_role(role_id)
            if role and role < guild.me.top_role and guild.me.guild_permissions.manage_roles:
                try:
                    await member.remove_roles(role, reason="Zenith Reaction Role Removal")
                except Exception:
                    pass

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.group(name="reactionrole", aliases=["rr"], invoke_without_command=True)
    @commands.guild_only()
    async def rr_group(self, ctx: commands.Context):
        """Reaction role management manual."""
        embed = discord.Embed(
            title="[REACTION ROLE SYSTEM]",
            description="Bind emoji reactions on messages to automated self-assignable roles.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Configuration Commands",
            value=(
                f"`{ctx.prefix}rr add <msg_id> <emoji> <@role>` - Bind role to emoji\n"
                f"`{ctx.prefix}rr remove <msg_id> <emoji>` - Unbind role from emoji\n"
                f"`{ctx.prefix}rr clear <msg_id>` - Purge all bindings on a message\n"
                f"`{ctx.prefix}rr create <#channel> <title> <desc>` - Spawn an embed prompt\n"
                f"`{ctx.prefix}rr list` - View active reaction role bindings\n"
                f"`{ctx.prefix}rr info <msg_id>` - Inspect message bindings\n"
                f"`{ctx.prefix}rr reset` - Clear all reaction roles across server"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rr_group.command(name="add")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rr_add(self, ctx: commands.Context, message_id: int, emoji: str, role: discord.Role):
        """Bind a reaction emoji to a role on a target message."""
        ok, err = validate_role_hierarchy(ctx.author, role)
        if not ok:
            return await ctx.send(embed=discord.Embed(title="[HIERARCHY ERROR]", description=err, color=ACCENT_COLOR))

        if is_dangerous_role(role):
            return await ctx.send(embed=discord.Embed(
                title="[SECURITY RESTRICTION]",
                description="Elevated administrative roles cannot be distributed via reaction roles.",
                color=ACCENT_COLOR
            ))

        target_msg = None
        for channel in ctx.guild.text_channels:
            try:
                target_msg = await channel.fetch_message(message_id)
                if target_msg:
                    break
            except Exception:
                continue

        if not target_msg:
            return await ctx.send(embed=discord.Embed(title="[MESSAGE NOT FOUND]", description=f"Could not locate message `{message_id}` in this server.", color=ACCENT_COLOR))

        try:
            await target_msg.add_reaction(emoji)
        except Exception as e:
            return await ctx.send(embed=discord.Embed(title="[EMOJI ERROR]", description=f"Could not add reaction `{emoji}`: {e}", color=ACCENT_COLOR))

        await db.execute(
            """
            INSERT INTO reaction_roles (guild_id, message_id, emoji, role_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id, emoji) DO UPDATE SET role_id = excluded.role_id
            """,
            ctx.guild.id, message_id, emoji, role.id
        )
        self._cache[(message_id, emoji)] = role.id

        embed = discord.Embed(
            title="[REACTION ROLE BOUND]",
            description=f"Reaction `{emoji}` on Message `{message_id}` will grant {role.mention}.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rr_group.command(name="remove", aliases=["rm", "del"])
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rr_remove(self, ctx: commands.Context, message_id: int, emoji: str):
        """Remove a reaction role mapping."""
        await db.execute("DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ? AND emoji = ?", ctx.guild.id, message_id, emoji)
        self._cache.pop((message_id, emoji), None)

        embed = discord.Embed(
            title="[REACTION ROLE REMOVED]",
            description=f"Unlinked reaction `{emoji}` on Message `{message_id}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rr_group.command(name="clear")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def rr_clear(self, ctx: commands.Context, message_id: int):
        """Purge all reaction role bindings for a message."""
        await db.execute("DELETE FROM reaction_roles WHERE guild_id = ? AND message_id = ?", ctx.guild.id, message_id)
        to_del = [k for k in self._cache if k[0] == message_id]
        for k in to_del:
            del self._cache[k]

        embed = discord.Embed(
            title="[REACTION ROLES CLEARED]",
            description=f"Purged all reaction role bindings on message `{message_id}`.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rr_group.command(name="create")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True, manage_channels=True)
    async def rr_create(self, ctx: commands.Context, channel: discord.TextChannel, title: str, *, description: str):
        """Create a dedicated reaction role prompt embed."""
        embed = discord.Embed(title=title, description=description, color=ACCENT_COLOR)
        embed.set_footer(text="React to acquire roles | Zenith Suite")
        msg = await channel.send(embed=embed)

        reply_embed = discord.Embed(
            title="[PROMPT CREATED]",
            description=(
                f"Published reaction role embed to {channel.mention} (Message ID: `{msg.id}`).\n"
                f"Now bind roles using: `{ctx.prefix}rr add {msg.id} <emoji> <@role>`."
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=reply_embed)

    @rr_group.command(name="list")
    @commands.guild_only()
    async def rr_list(self, ctx: commands.Context):
        """List active reaction role bindings."""
        rows = await db.fetch("SELECT message_id, emoji, role_id FROM reaction_roles WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO REACTION ROLES]", description="No reaction roles configured.", color=ACCENT_COLOR))

        lines = [f"• Message `{r['message_id']}`: `{r['emoji']}` -> <@&{r['role_id']}>" for r in rows]
        embed = discord.Embed(
            title="[REACTION ROLE REGISTRY]",
            description="\n".join(lines[:25]),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @rr_group.command(name="info")
    @commands.guild_only()
    async def rr_info(self, ctx: commands.Context, message_id: int):
        """Inspect mapped roles and emojis for a specific message."""
        rows = await db.fetch("SELECT emoji, role_id FROM reaction_roles WHERE guild_id = ? AND message_id = ?", ctx.guild.id, message_id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO BINDINGS]", description=f"No reaction roles bound to message `{message_id}`.", color=ACCENT_COLOR))

        lines = [f"• `{r['emoji']}` -> <@&{r['role_id']}>" for r in rows]
        embed = discord.Embed(
            title=f"[REACTION ROLES] Message {message_id}",
            description="\n".join(lines),
            color=ACCENT_COLOR
        )
        await ctx.send(embed=embed)

    @rr_group.command(name="reset")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def rr_reset(self, ctx: commands.Context):
        """Purge all reaction role bindings on the server."""
        await db.execute("DELETE FROM reaction_roles WHERE guild_id = ?", ctx.guild.id)
        to_del = [k for k in self._cache]
        # Remove keys matching guild messages
        await ctx.send(embed=discord.Embed(title="[OK] Reaction Roles Reset", description="Cleared all reaction role configurations.", color=ACCENT_COLOR))


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionRole(bot))
