"""
Member greeting delivery and automatic role allocation.
"""

from typing import Optional
import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class Welcome(commands.Cog):
    """Member reception and automated initial role allocation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Triggers welcome announcements and applies designated autoroles."""
        guild = member.guild
        cfg = await db.fetchrow("SELECT * FROM welcome_config WHERE guild_id = ?", guild.id)
        if not cfg:
            return

        # 1. Apply Autoroles
        if member.bot and cfg.get("autorole_bot"):
            bot_role = guild.get_role(cfg["autorole_bot"])
            if bot_role and guild.me.top_role > bot_role:
                try:
                    await member.add_roles(bot_role, reason="Zenith Autorole: Bot account joined.")
                except Exception:
                    pass
        elif not member.bot and cfg.get("autorole_human"):
            human_role = guild.get_role(cfg["autorole_human"])
            if human_role and guild.me.top_role > human_role:
                try:
                    await member.add_roles(human_role, reason="Zenith Autorole: Member joined.")
                except Exception:
                    pass

        # 2. Format custom message
        raw_msg = cfg.get("message") or "Welcome {user.mention} to {guild.name}!"
        formatted_msg = (
            raw_msg
            .replace("{user.mention}", member.mention)
            .replace("{user.name}", member.name)
            .replace("{guild.name}", guild.name)
            .replace("{guild.count}", str(guild.member_count or len(guild.members)))
        )

        embed = ZenithEmbed(
            title=f"Welcome to {guild.name}!",
            description=formatted_msg,
            color=Color.PRIMARY
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{guild.member_count or len(guild.members)}")

        # 3. Channel Announcement
        if cfg.get("enabled") and cfg.get("channel_id"):
            channel = guild.get_channel(cfg["channel_id"])
            if channel and isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

        # 4. Direct Message Greetings
        if cfg.get("dm_welcome"):
            try:
                await member.send(embed=embed)
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════
    #  WELCOME MANAGEMENT COMMANDS
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome_group(self, ctx: commands.Context):
        """Displays welcome configuration options."""
        cfg = await db.fetchrow("SELECT * FROM welcome_config WHERE guild_id = ?", ctx.guild.id) or {}
        ch = f"<#{cfg.get('channel_id')}>" if cfg.get("channel_id") else "`Disabled`"
        status = "Enabled" if cfg.get("enabled") else "Disabled"

        embed = ZenithEmbed(
            title="Zenith Welcome Dashboard",
            description=f"Status: **{status}**\nAnnouncement Channel: {ch}",
            color=Color.PRIMARY
        )
        embed.add_field(
            name="Configuration Commands",
            value=(
                f"• `{ctx.prefix}welcome channel <#channel>` — Sets destination\n"
                f"• `{ctx.prefix}welcome message <text>` — Sets greeting message\n"
                f"• `{ctx.prefix}welcome dm <on|off>` — Toggles DM welcome\n"
                f"• `{ctx.prefix}welcome test` — Previews greeting embed"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    @welcome_group.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Sets the announcement channel and activates welcome messaging."""
        if db.is_postgres:
            query = """
            INSERT INTO welcome_config (guild_id, enabled, channel_id) VALUES (?, TRUE, ?)
            ON CONFLICT (guild_id) DO UPDATE SET enabled = TRUE, channel_id = EXCLUDED.channel_id;
            """
        else:
            query = """
            INSERT INTO welcome_config (guild_id, enabled, channel_id) VALUES (?, TRUE, ?)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = TRUE, channel_id = excluded.channel_id;
            """
        await db.execute(query, ctx.guild.id, channel.id)
        embed = ZenithEmbed.success("Welcome Channel Configured", f"Greetings will be sent to {channel.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    @welcome_group.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def welcome_message(self, ctx: commands.Context, *, template: str):
        """Customizes greeting text. Variables: `{user.mention}`, `{user.name}`, `{guild.name}`, `{guild.count}`."""
        if db.is_postgres:
            query = """
            INSERT INTO welcome_config (guild_id, message) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET message = EXCLUDED.message;
            """
        else:
            query = """
            INSERT INTO welcome_config (guild_id, message) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET message = excluded.message;
            """
        await db.execute(query, ctx.guild.id, template)
        embed = ZenithEmbed.success("Message Template Updated", f"New template saved:\n> {template}")
        await ctx.reply(embed=embed, mention_author=False)

    @welcome_group.command(name="test")
    @commands.has_permissions(manage_guild=True)
    async def welcome_test(self, ctx: commands.Context):
        """Previews how the welcome greeting looks using your profile."""
        cfg = await db.fetchrow("SELECT message FROM welcome_config WHERE guild_id = ?", ctx.guild.id)
        raw_msg = cfg.get("message") if cfg else "Welcome {user.mention} to {guild.name}!"
        formatted = (
            raw_msg
            .replace("{user.mention}", ctx.author.mention)
            .replace("{user.name}", ctx.author.name)
            .replace("{guild.name}", ctx.guild.name)
            .replace("{guild.count}", str(ctx.guild.member_count))
        )

        embed = ZenithEmbed(
            title=f"Welcome to {ctx.guild.name}!",
            description=formatted,
            color=Color.PRIMARY
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Member #{ctx.guild.member_count} (Preview)")
        await ctx.reply(content="**[Test Preview]**", embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    #  AUTOROLE SUBSYSTEM
    # ═══════════════════════════════════════════════════════════════

    @commands.group(name="autorole", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def autorole_group(self, ctx: commands.Context):
        """Displays configured join roles."""
        cfg = await db.fetchrow("SELECT autorole_human, autorole_bot FROM welcome_config WHERE guild_id = ?", ctx.guild.id) or {}
        human_r = f"<@&{cfg.get('autorole_human')}>" if cfg.get("autorole_human") else "`None`"
        bot_r = f"<@&{cfg.get('autorole_bot')}>" if cfg.get("autorole_bot") else "`None`"

        embed = ZenithEmbed(
            title="Zenith Autorole System",
            description=f"• **Human Join Role:** {human_r}\n• **Bot Join Role:** {bot_r}",
            color=Color.PRIMARY
        )
        embed.add_field(
            name="Commands",
            value=(
                f"• `{ctx.prefix}autorole human <@role>` — Assigns to new users\n"
                f"• `{ctx.prefix}autorole bot <@role>` — Assigns to invited bots\n"
                f"• `{ctx.prefix}autorole clear` — Disables autoroles"
            ),
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)

    @autorole_group.command(name="human")
    @commands.has_permissions(manage_roles=True)
    async def autorole_human(self, ctx: commands.Context, role: discord.Role):
        """Designates the role assigned to human members on join."""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "I cannot assign a role higher than or equal to my highest role."), mention_author=False)

        if db.is_postgres:
            query = """
            INSERT INTO welcome_config (guild_id, autorole_human) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET autorole_human = EXCLUDED.autorole_human;
            """
        else:
            query = """
            INSERT INTO welcome_config (guild_id, autorole_human) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET autorole_human = excluded.autorole_human;
            """
        await db.execute(query, ctx.guild.id, role.id)
        embed = ZenithEmbed.success("Autorole Configured", f"New members will automatically receive {role.mention}.")
        await ctx.reply(embed=embed, mention_author=False)

    @autorole_group.command(name="bot")
    @commands.has_permissions(manage_roles=True)
    async def autorole_bot(self, ctx: commands.Context, role: discord.Role):
        """Designates the role assigned to invited bots on join."""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply(embed=ZenithEmbed.error("Hierarchy Error", "I cannot assign a role higher than or equal to my highest role."), mention_author=False)

        if db.is_postgres:
            query = """
            INSERT INTO welcome_config (guild_id, autorole_bot) VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET autorole_bot = EXCLUDED.autorole_bot;
            """
        else:
            query = """
            INSERT INTO welcome_config (guild_id, autorole_bot) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET autorole_bot = excluded.autorole_bot;
            """
        await db.execute(query, ctx.guild.id, role.id)
        embed = ZenithEmbed.success("Bot Autorole Configured", f"New bots will automatically receive {role.mention}.")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
