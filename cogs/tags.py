"""
Tag and Custom Command engine for Zenith.
Allows communities to store, retrieve, alias, and manage reusable snippet responses.
"""

from __future__ import annotations

import time
from typing import Optional

import discord
from discord.ext import commands

from core.database import db

THEME_COLOR = 0x0F0F13


class Tags(commands.Cog):
    """Custom command and server tag system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory cache: (guild_id, tag_name_lower) -> dict
        self._tag_cache: dict[tuple[int, str], dict] = {}
        # In-memory alias cache: (guild_id, alias_lower) -> target_name
        self._alias_cache: dict[tuple[int, str], str] = {}

    async def _resolve_tag(self, guild_id: int, name: str) -> Optional[dict]:
        name = name.lower().strip()
        # Check alias
        alias_key = (guild_id, name)
        if alias_key in self._alias_cache:
            name = self._alias_cache[alias_key]
        else:
            row = await db.fetchrow(
                "SELECT target_name FROM guild_tag_aliases WHERE guild_id = ? AND alias = ?",
                guild_id, name
            )
            if row:
                name = row["target_name"].lower()
                self._alias_cache[alias_key] = name

        # Check tag cache
        tag_key = (guild_id, name)
        if tag_key in self._tag_cache:
            return self._tag_cache[tag_key]

        # Fetch from DB
        row = await db.fetchrow(
            "SELECT name, content, author_id, uses, created_at FROM guild_tags WHERE guild_id = ? AND LOWER(name) = ?",
            guild_id, name
        )
        if row:
            data = dict(row)
            self._tag_cache[tag_key] = data
            return data
        return None

    @commands.group(name="tag", invoke_without_command=True)
    async def tag_group(self, ctx: commands.Context, *, tag_name: Optional[str] = None):
        """Retrieve and send a tag snippet, or inspect tag commands."""
        if not tag_name:
            embed = discord.Embed(
                title="[TAG SYSTEM] Tag Index",
                description="Manage and retrieve reusable server tag responses.",
                color=THEME_COLOR
            )
            embed.add_field(
                name="Retrieval",
                value="`tag <name>` - Display tag content\n`tag raw <name>` - View raw unparsed source\n`tag info <name>` - View metadata and stats",
                inline=False
            )
            embed.add_field(
                name="Management",
                value="`tag add <name> <content>` - Create new tag\n`tag edit <name> <content>` - Edit tag\n`tag delete <name>` - Delete tag\n`tag transfer <name> <user>` - Transfer ownership",
                inline=False
            )
            embed.add_field(
                name="Aliases & Directory",
                value="`tag alias add <tag> <alias>` - Create alias\n`tag alias remove <alias>` - Remove alias\n`tag list [user]` - View tag listing\n`tag search <query>` - Search tags",
                inline=False
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        tag = await self._resolve_tag(ctx.guild.id, tag_name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{tag_name}' was not found.", mention_author=False)
            return

        # Increment uses
        await db.execute(
            "UPDATE guild_tags SET uses = uses + 1 WHERE guild_id = ? AND LOWER(name) = ?",
            ctx.guild.id, tag["name"].lower()
        )
        tag["uses"] += 1
        await ctx.send(tag["content"])

    @tag_group.command(name="get")
    async def tag_get(self, ctx: commands.Context, *, name: str):
        """Explicitly fetch and send a tag."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' was not found.", mention_author=False)
            return

        await db.execute(
            "UPDATE guild_tags SET uses = uses + 1 WHERE guild_id = ? AND LOWER(name) = ?",
            ctx.guild.id, tag["name"].lower()
        )
        tag["uses"] += 1
        await ctx.send(tag["content"])

    @tag_group.command(name="add", aliases=["create", "new"])
    async def tag_add(self, ctx: commands.Context, name: str, *, content: str):
        """Create a new server tag."""
        name_clean = name.strip()
        if len(name_clean) > 50:
            await ctx.reply("[ERROR] Tag name must be 50 characters or fewer.", mention_author=False)
            return

        existing = await self._resolve_tag(ctx.guild.id, name_clean)
        if existing:
            await ctx.reply(f"[ERROR] A tag or alias named '{name_clean}' already exists.", mention_author=False)
            return

        now = time.time()
        await db.execute(
            "INSERT INTO guild_tags (guild_id, name, content, author_id, uses, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ctx.guild.id, name_clean, content, ctx.author.id, 0, now
        )
        self._tag_cache[(ctx.guild.id, name_clean.lower())] = {
            "name": name_clean,
            "content": content,
            "author_id": ctx.author.id,
            "uses": 0,
            "created_at": now
        }

        embed = discord.Embed(
            title="[OK] Tag Created",
            description=f"Tag `{name_clean}` has been stored successfully.",
            color=THEME_COLOR
        )
        embed.add_field(name="Author", value=ctx.author.mention, inline=True)
        embed.add_field(name="Length", value=f"{len(content)} characters", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="edit", aliases=["modify"])
    async def tag_edit(self, ctx: commands.Context, name: str, *, new_content: str):
        """Edit content of an existing tag owned by you or as staff."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        is_owner = tag["author_id"] == ctx.author.id
        is_mod = ctx.author.guild_permissions.manage_guild or ctx.author.id == ctx.guild.owner_id
        if not (is_owner or is_mod):
            await ctx.reply("[ERROR] You do not own this tag and lack Manage Server permissions.", mention_author=False)
            return

        actual_name = tag["name"]
        await db.execute(
            "UPDATE guild_tags SET content = ? WHERE guild_id = ? AND LOWER(name) = ?",
            new_content, ctx.guild.id, actual_name.lower()
        )
        tag["content"] = new_content
        self._tag_cache[(ctx.guild.id, actual_name.lower())] = tag

        embed = discord.Embed(
            title="[OK] Tag Updated",
            description=f"Tag `{actual_name}` was updated successfully.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="delete", aliases=["remove", "del"])
    async def tag_delete(self, ctx: commands.Context, *, name: str):
        """Delete an existing tag."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        is_owner = tag["author_id"] == ctx.author.id
        is_mod = ctx.author.guild_permissions.manage_guild or ctx.author.id == ctx.guild.owner_id
        if not (is_owner or is_mod):
            await ctx.reply("[ERROR] You do not own this tag and lack Manage Server permissions.", mention_author=False)
            return

        actual_name = tag["name"]
        await db.execute("DELETE FROM guild_tags WHERE guild_id = ? AND LOWER(name) = ?", ctx.guild.id, actual_name.lower())
        await db.execute("DELETE FROM guild_tag_aliases WHERE guild_id = ? AND LOWER(target_name) = ?", ctx.guild.id, actual_name.lower())

        self._tag_cache.pop((ctx.guild.id, actual_name.lower()), None)
        to_del = [k for k, v in self._alias_cache.items() if k[0] == ctx.guild.id and v.lower() == actual_name.lower()]
        for k in to_del:
            self._alias_cache.pop(k, None)

        embed = discord.Embed(
            title="[OK] Tag Deleted",
            description=f"Tag `{actual_name}` and associated aliases have been permanently removed.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="raw")
    async def tag_raw(self, ctx: commands.Context, *, name: str):
        """Inspect the raw markdown formatting of a tag."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        content = discord.utils.escape_markdown(tag["content"])
        if len(content) > 1900:
            content = content[:1900] + "..."
        await ctx.reply(f"```{content}```", mention_author=False)

    @tag_group.command(name="info", aliases=["stats"])
    async def tag_info(self, ctx: commands.Context, *, name: str):
        """View author, usage count, and timestamp metadata for a tag."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        author = ctx.guild.get_member(tag["author_id"])
        author_str = f"{author} (`{tag['author_id']}`)" if author else f"`{tag['author_id']}`"

        embed = discord.Embed(
            title=f"[TAG INFO] {tag['name']}",
            color=THEME_COLOR
        )
        embed.add_field(name="Creator", value=author_str, inline=True)
        embed.add_field(name="Uses", value=str(tag["uses"]), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(tag['created_at'])}:R>", inline=True)

        aliases = await db.fetch(
            "SELECT alias FROM guild_tag_aliases WHERE guild_id = ? AND LOWER(target_name) = ?",
            ctx.guild.id, tag["name"].lower()
        )
        if aliases:
            embed.add_field(name="Aliases", value=", ".join(f"`{a['alias']}`" for a in aliases), inline=False)

        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="list")
    async def tag_list(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """List tags created in this server or by a specific member."""
        if member:
            rows = await db.fetch(
                "SELECT name, uses FROM guild_tags WHERE guild_id = ? AND author_id = ? ORDER BY uses DESC LIMIT 50",
                ctx.guild.id, member.id
            )
            title = f"[TAGS] Registered by {member.display_name}"
        else:
            rows = await db.fetch(
                "SELECT name, uses FROM guild_tags WHERE guild_id = ? ORDER BY uses DESC LIMIT 50",
                ctx.guild.id
            )
            title = f"[TAGS] Registry for {ctx.guild.name}"

        if not rows:
            await ctx.reply("[INFO] No tags registered in this query scope.", mention_author=False)
            return

        tag_list_str = "\n".join(f"• `{r['name']}` ({r['uses']} uses)" for r in rows)
        if len(tag_list_str) > 3900:
            tag_list_str = tag_list_str[:3900] + "\n..."

        embed = discord.Embed(
            title=title,
            description=tag_list_str,
            color=THEME_COLOR
        )
        embed.set_footer(text=f"Total listed: {len(rows)} | Use 'tag <name>' to view")
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="search")
    async def tag_search(self, ctx: commands.Context, *, query: str):
        """Search registered tags by keyword."""
        query_pattern = f"%{query.lower()}%"
        rows = await db.fetch(
            "SELECT name, uses FROM guild_tags WHERE guild_id = ? AND LOWER(name) LIKE ? ORDER BY uses DESC LIMIT 20",
            ctx.guild.id, query_pattern
        )
        if not rows:
            await ctx.reply(f"[INFO] No tags matching '{query}' were found.", mention_author=False)
            return

        tag_str = "\n".join(f"• `{r['name']}` ({r['uses']} uses)" for r in rows)
        embed = discord.Embed(
            title=f"[TAG SEARCH] Matches for '{query}'",
            description=tag_str,
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="claim")
    async def tag_claim(self, ctx: commands.Context, *, name: str):
        """Claim ownership of an abandoned tag if the previous creator left the server."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        current_author = ctx.guild.get_member(tag["author_id"])
        if current_author:
            await ctx.reply(f"[ERROR] The creator ({current_author.mention}) is still an active member of this server.", mention_author=False)
            return

        actual_name = tag["name"]
        await db.execute(
            "UPDATE guild_tags SET author_id = ? WHERE guild_id = ? AND LOWER(name) = ?",
            ctx.author.id, ctx.guild.id, actual_name.lower()
        )
        tag["author_id"] = ctx.author.id
        self._tag_cache[(ctx.guild.id, actual_name.lower())] = tag

        embed = discord.Embed(
            title="[OK] Tag Claimed",
            description=f"Ownership of tag `{actual_name}` was transferred to {ctx.author.mention}.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.command(name="transfer")
    async def tag_transfer(self, ctx: commands.Context, member: discord.Member, *, name: str):
        """Transfer tag ownership to another server member."""
        tag = await self._resolve_tag(ctx.guild.id, name)
        if not tag:
            await ctx.reply(f"[ERROR] Tag '{name}' not found.", mention_author=False)
            return

        is_owner = tag["author_id"] == ctx.author.id
        is_mod = ctx.author.guild_permissions.manage_guild or ctx.author.id == ctx.guild.owner_id
        if not (is_owner or is_mod):
            await ctx.reply("[ERROR] You do not own this tag and lack Manage Server permissions.", mention_author=False)
            return

        actual_name = tag["name"]
        await db.execute(
            "UPDATE guild_tags SET author_id = ? WHERE guild_id = ? AND LOWER(name) = ?",
            member.id, ctx.guild.id, actual_name.lower()
        )
        tag["author_id"] = member.id
        self._tag_cache[(ctx.guild.id, actual_name.lower())] = tag

        embed = discord.Embed(
            title="[OK] Tag Transferred",
            description=f"Tag `{actual_name}` ownership successfully transferred to {member.mention}.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_group.group(name="alias", invoke_without_command=True)
    async def tag_alias_group(self, ctx: commands.Context):
        """Manage tag aliases."""
        await ctx.send_help(ctx.command)

    @tag_alias_group.command(name="add")
    async def tag_alias_add(self, ctx: commands.Context, tag_name: str, alias_name: str):
        """Create a shortcut alias pointing to an existing tag."""
        tag = await self._resolve_tag(ctx.guild.id, tag_name)
        if not tag:
            await ctx.reply(f"[ERROR] Target tag '{tag_name}' does not exist.", mention_author=False)
            return

        alias_clean = alias_name.strip()
        existing = await self._resolve_tag(ctx.guild.id, alias_clean)
        if existing:
            await ctx.reply(f"[ERROR] Name '{alias_clean}' is already taken by a tag or alias.", mention_author=False)
            return

        await db.execute(
            "INSERT INTO guild_tag_aliases (guild_id, alias, target_name) VALUES (?, ?, ?)",
            ctx.guild.id, alias_clean.lower(), tag["name"]
        )
        self._alias_cache[(ctx.guild.id, alias_clean.lower())] = tag["name"]

        embed = discord.Embed(
            title="[OK] Alias Created",
            description=f"Alias `{alias_clean}` now points to tag `{tag['name']}`.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @tag_alias_group.command(name="remove", aliases=["delete"])
    async def tag_alias_remove(self, ctx: commands.Context, alias_name: str):
        """Remove a shortcut tag alias."""
        alias_clean = alias_name.strip().lower()
        row = await db.fetchrow(
            "SELECT target_name FROM guild_tag_aliases WHERE guild_id = ? AND alias = ?",
            ctx.guild.id, alias_clean
        )
        if not row:
            await ctx.reply(f"[ERROR] Alias '{alias_name}' was not found.", mention_author=False)
            return

        await db.execute(
            "DELETE FROM guild_tag_aliases WHERE guild_id = ? AND alias = ?",
            ctx.guild.id, alias_clean
        )
        self._alias_cache.pop((ctx.guild.id, alias_clean), None)

        embed = discord.Embed(
            title="[OK] Alias Removed",
            description=f"Alias `{alias_clean}` was successfully deleted.",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tags(bot))
