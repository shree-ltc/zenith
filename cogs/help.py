"""
cogs/help.py - Interactive Categorized Help System for Zenith

Provides an intuitive UI featuring a category dropdown select menu,
detailed command syntax, aliases, and permission requirements.
"""

from typing import Optional
import discord
from discord.ext import commands
from discord import ui

from ui.embeds import ZenithEmbed
from ui.colors import Color


class HelpSelect(ui.Select):
    """Dropdown menu for browsing command categories."""

    def __init__(self, cog: "Help", ctx: commands.Context):
        self.help_cog = cog
        self.ctx = ctx

        options = [
            discord.SelectOption(
                label="Home",
                description="Overview of Zenith and quick navigation",
                emoji="🏠",
                value="home"
            ),
            discord.SelectOption(
                label="Security & Antinuke",
                description="Raid prevention, anti-ban, anti-bot, quarantine",
                emoji="🛡️",
                value="Antinuke"
            ),
            discord.SelectOption(
                label="Automod",
                description="Real-time spam, link, invite, and caps filtering",
                emoji="⚙️",
                value="Automod"
            ),
            discord.SelectOption(
                label="Moderation",
                description="Bans, timeouts, kicks, warnings, purge, and role tools",
                emoji="🔨",
                value="Moderation"
            ),
            discord.SelectOption(
                label="Tickets",
                description="Interactive support ticket panels & transcripts",
                emoji="🎫",
                value="Tickets"
            ),
            discord.SelectOption(
                label="Utility & Server Info",
                description="User, server, avatar, role lookups and snipe tools",
                emoji="📊",
                value="Utility"
            ),
            discord.SelectOption(
                label="Voice & TempVC",
                description="Join-to-create voice channels with custom controls",
                emoji="🔊",
                value="Voice"
            ),
            discord.SelectOption(
                label="Welcome & Autorole",
                description="Automated greetings, welcome cards, and join roles",
                emoji="👋",
                value="Welcome"
            ),
            discord.SelectOption(
                label="Giveaways",
                description="Interactive giveaways with countdowns and rerolls",
                emoji="🎉",
                value="Giveaways"
            ),
            discord.SelectOption(
                label="Fun & Games",
                description="Trivia, 8ball, coinflips, rock-paper-scissors",
                emoji="🎲",
                value="Fun"
            ),
        ]

        super().__init__(
            placeholder="Select a category to view commands...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "Only the requester can use this menu."),
                ephemeral=True
            )

        selected = self.values[0]

        if selected == "home":
            embed = self.help_cog.get_home_embed(self.ctx)
            return await interaction.response.edit_message(embed=embed, view=self.view)

        # Retrieve commands belonging to selected Cog
        target_cog = self.help_cog.bot.get_cog(selected)
        if not target_cog:
            embed = ZenithEmbed.error("Category Not Found", "No commands registered in this category.")
            return await interaction.response.edit_message(embed=embed, view=self.view)

        # Collect unique command names
        cmds = [
            c for c in target_cog.get_commands() 
            if not c.hidden
        ]

        embed = ZenithEmbed(
            title=f"{selected} Commands",
            description=f"Showing all commands registered under **{selected}**.\n"
                        f"Use `{self.ctx.prefix}help <command>` for detailed syntax and flags.\n\n",
            color=Color.PRIMARY
        )

        for cmd in cmds:
            name = f"{self.ctx.prefix}{cmd.qualified_name}"
            desc = cmd.help or cmd.brief or "No description provided."
            # Show subcommands if it's a command group
            if isinstance(cmd, commands.Group) and cmd.commands:
                sub_names = ", ".join(f"`{sub.name}`" for sub in cmd.commands if not sub.hidden)
                desc = f"{desc}\n*Subcommands:* {sub_names}"

            embed.add_field(name=f"`{name}`", value=desc, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(ui.View):
    """View container carrying the HelpSelect dropdown menu."""

    def __init__(self, cog: "Help", ctx: commands.Context):
        super().__init__(timeout=180.0)
        self.add_item(HelpSelect(cog, ctx))
        self.ctx = ctx

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            # We don't hold the original message reference directly, so quietly pass
            pass
        except Exception:
            pass


class Help(commands.Cog):
    """Custom categorized interactive help manual."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_home_embed(self, ctx: commands.Context) -> discord.Embed:
        """Constructs the welcoming front page of the help manual."""
        total_commands = len([c for c in self.bot.commands if not c.hidden])

        embed = ZenithEmbed(
            title="Zenith — Command Directory",
            description=(
                "Welcome to **Zenith**, a production-grade Discord security, moderation, "
                "and server automation system.\n\n"
                f"• **Current Prefix:** `{ctx.prefix}`\n"
                f"• **Available Commands:** `{total_commands}+ active`\n"
                "• **Navigation:** Select a category from the dropdown below to explore modules.\n"
                "• **Detailed Query:** Run `z!help <command>` for usage examples & arguments."
            ),
            color=Color.PRIMARY
        )

        embed.add_field(
            name="🛡️ Protection & Governance",
            value="`Antinuke`, `Automod`, `Moderation`, `Server Logs`",
            inline=False
        )
        embed.add_field(
            name="⚙️ Automation & Infrastructure",
            value="`Tickets`, `TempVC`, `Welcome`, `Autorole`, `Giveaways`",
            inline=False
        )
        embed.add_field(
            name="📊 Information & Engagement",
            value="`Utility`, `Fun & Games`, `AFK System`",
            inline=False
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        return embed

    @commands.command(name="help", aliases=["commands", "cmds", "h"])
    async def help_command(self, ctx: commands.Context, *, command_query: Optional[str] = None):
        """Displays the interactive command manual or inspects a specific command."""
        if not command_query:
            embed = self.get_home_embed(ctx)
            view = HelpView(self, ctx)
            return await ctx.reply(embed=embed, view=view, mention_author=False)

        # Lookup specific command
        cmd = self.bot.get_command(command_query)
        if not cmd:
            embed = ZenithEmbed.error(
                "Command Not Found",
                f"No command named `{command_query}` exists in Zenith's registry."
            )
            return await ctx.reply(embed=embed, mention_author=False)

        # Detailed single-command view
        embed = ZenithEmbed(
            title=f"Command: {ctx.prefix}{cmd.qualified_name}",
            description=cmd.help or "No detailed description provided.",
            color=Color.PRIMARY
        )

        # Usage signature
        usage = f"`{ctx.prefix}{cmd.qualified_name} {cmd.signature}`".strip()
        embed.add_field(name="Syntax", value=usage, inline=False)

        # Aliases
        if cmd.aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{a}`" for a in cmd.aliases),
                inline=True
            )

        # Cooldown info
        if cmd._buckets and cmd._buckets._cooldown:
            embed.add_field(
                name="Cooldown",
                value=f"{cmd._buckets._cooldown.per:.0f} seconds",
                inline=True
            )

        # Subcommands if group
        if isinstance(cmd, commands.Group) and cmd.commands:
            sub_list = "\n".join(
                f"• `{ctx.prefix}{cmd.qualified_name} {sub.name}` — {sub.help or 'No info'}"
                for sub in cmd.commands if not sub.hidden
            )
            embed.add_field(name="Subcommands", value=sub_list, inline=False)

        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
