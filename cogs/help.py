"""
Interactive help command displaying categories in a select menu.
"""

from typing import Optional
import discord
from discord.ext import commands
from discord import ui

from ui.embeds import ZenithEmbed
from ui.colors import Color


class HelpSelect(ui.Select):
    def __init__(self, cog: "Help", ctx: commands.Context):
        self.help_cog = cog
        self.ctx = ctx

        options = [
            discord.SelectOption(
                label="Home",
                description="Overview and quick navigation",
                value="home"
            ),
            discord.SelectOption(
                label="Security",
                description="Antinuke, whitelist, and raid prevention",
                value="Antinuke"
            ),
            discord.SelectOption(
                label="Automod",
                description="Spam, links, invites, and caps filtering",
                value="Automod"
            ),
            discord.SelectOption(
                label="Moderation",
                description="Bans, timeouts, kicks, warnings, and purges",
                value="Moderation"
            ),
            discord.SelectOption(
                label="Tickets",
                description="Support ticket panels and transcripts",
                value="Tickets"
            ),
            discord.SelectOption(
                label="Server Management",
                description="Nuke, lockdown, dehoist, and role inspection",
                value="Server"
            ),
            discord.SelectOption(
                label="Voice",
                description="Join-to-create temporary voice channels",
                value="Voice"
            ),
            discord.SelectOption(
                label="Economy",
                description="Currency, banking, shifts, and leaderboard",
                value="Economy"
            ),
            discord.SelectOption(
                label="Utility",
                description="Server, member, avatar, and system lookups",
                value="Utility"
            ),
            discord.SelectOption(
                label="Welcome",
                description="Member greetings and join autoroles",
                value="Welcome"
            ),
            discord.SelectOption(
                label="Giveaways",
                description="Community prize drawings",
                value="Giveaways"
            ),
            discord.SelectOption(
                label="Fun",
                description="Mini-games, coinflips, and trivia",
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

        target_cog = self.help_cog.bot.get_cog(selected)
        if not target_cog:
            embed = ZenithEmbed.error("Category Not Found", "No commands registered in this category.")
            return await interaction.response.edit_message(embed=embed, view=self.view)

        cmds = [c for c in target_cog.get_commands() if not c.hidden]

        embed = ZenithEmbed(
            title=f"{selected} Commands",
            description=f"Commands registered under **{selected}**.\n"
                        f"Use `{self.ctx.prefix}help <command>` for syntax and flags.\n\n",
            color=Color.PRIMARY
        )

        for cmd in cmds:
            name = f"{self.ctx.prefix}{cmd.qualified_name}"
            desc = cmd.help or cmd.brief or "No description provided."
            if isinstance(cmd, commands.Group) and cmd.commands:
                sub_names = ", ".join(f"`{sub.name}`" for sub in cmd.commands if not sub.hidden)
                desc = f"{desc}\nSubcommands: {sub_names}"

            embed.add_field(name=f"`{name}`", value=desc, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(ui.View):
    def __init__(self, cog: "Help", ctx: commands.Context):
        super().__init__(timeout=180.0)
        self.add_item(HelpSelect(cog, ctx))
        self.ctx = ctx

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_home_embed(self, ctx: commands.Context) -> discord.Embed:
        total_commands = len([c for c in self.bot.commands if not c.hidden])

        embed = ZenithEmbed(
            title="Zenith — Command Directory",
            description=(
                f"Prefix: `{ctx.prefix}`\n"
                f"Total Commands: `{total_commands}+`\n"
                "Select a category from the dropdown below to explore modules.\n"
                f"Run `{ctx.prefix}help <command>` for detailed arguments."
            ),
            color=Color.PRIMARY
        )

        embed.add_field(
            name="Protection & Governance",
            value="`Antinuke`, `Automod`, `Moderation`, `Server Logs`",
            inline=False
        )
        embed.add_field(
            name="Automation & Tools",
            value="`Tickets`, `TempVC`, `Welcome`, `Autorole`, `Server`, `Giveaways`",
            inline=False
        )
        embed.add_field(
            name="Economy & Engagement",
            value="`Economy`, `Utility`, `Fun`, `AFK`",
            inline=False
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        return embed

    @commands.command(name="help", aliases=["commands", "cmds", "h"])
    async def help_command(self, ctx: commands.Context, *, command_query: Optional[str] = None):
        """Displays command directory or inspects a specific command."""
        if not command_query:
            embed = self.get_home_embed(ctx)
            view = HelpView(self, ctx)
            return await ctx.reply(embed=embed, view=view, mention_author=False)

        cmd = self.bot.get_command(command_query)
        if not cmd:
            embed = ZenithEmbed.error(
                "Command Not Found",
                f"No command named `{command_query}` exists."
            )
            return await ctx.reply(embed=embed, mention_author=False)

        embed = ZenithEmbed(
            title=f"Command: {ctx.prefix}{cmd.qualified_name}",
            description=cmd.help or "No detailed description provided.",
            color=Color.PRIMARY
        )

        usage = f"`{ctx.prefix}{cmd.qualified_name} {cmd.signature}`".strip()
        embed.add_field(name="Syntax", value=usage, inline=False)

        if cmd.aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{a}`" for a in cmd.aliases),
                inline=True
            )

        if cmd._buckets and cmd._buckets._cooldown:
            embed.add_field(
                name="Cooldown",
                value=f"{cmd._buckets._cooldown.per:.0f}s",
                inline=True
            )

        if isinstance(cmd, commands.Group) and cmd.commands:
            sub_list = "\n".join(
                f"`{ctx.prefix}{cmd.qualified_name} {sub.name}` - {sub.help or 'No info'}"
                for sub in cmd.commands if not sub.hidden
            )
            embed.add_field(name="Subcommands", value=sub_list, inline=False)

        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
