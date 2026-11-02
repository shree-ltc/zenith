"""
Interactive help command displaying categories in a select menu.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, List, Dict
import discord
from discord.ext import commands
from discord import ui

from ui.embeds import ZenithEmbed
from ui.colors import Color

CATEGORY_MAPPING = {
    "security": {
        "label": "Security & Antinuke",
        "description": "Antinuke, whitelist, snapshots, and extra owners",
        "cogs": ["Antinuke", "ExtraOwner"]
    },
    "mainrole": {
        "label": "Mainrole Protection",
        "description": "Lock down @everyone and verified member roles",
        "cogs": ["Mainrole"]
    },
    "antibetray": {
        "label": "Anti-Betray",
        "description": "Autonomous rogue staff velocity neutralization",
        "cogs": ["AntiBetray"]
    },
    "fakepermission": {
        "label": "Fake Permissions",
        "description": "Virtual moderator permissions and daily quotas",
        "cogs": ["FakePermission"]
    },
    "roles": {
        "label": "Role Management",
        "description": "Role editing, toggling, and mass role operations",
        "cogs": ["Role"]
    },
    "moderation": {
        "label": "Moderation",
        "description": "Bans, kicks, timeouts, warnings, locks, and purges",
        "cogs": ["Moderation"]
    },
    "automod": {
        "label": "Automod",
        "description": "Anti-spam, link filters, invite blocks, and caps",
        "cogs": ["Automod"]
    },
    "music": {
        "label": "Music",
        "description": "High-fidelity audio streaming, queue, and autoplay",
        "cogs": ["Music"]
    },
    "tickets": {
        "label": "Tickets",
        "description": "Support ticket panels and transcript logs",
        "cogs": ["Tickets"]
    },
    "server": {
        "label": "Server Tools",
        "description": "Channel locks, slowmode, and server configs",
        "cogs": ["Server"]
    },
    "voice": {
        "label": "Voice Channels",
        "description": "Dynamic join-to-create temporary voice lounges",
        "cogs": ["Voice"]
    },
    "economy": {
        "label": "Economy",
        "description": "Currency, banking, jobs, shifts, and leaderboard",
        "cogs": ["Economy"]
    },
    "utility": {
        "label": "Utility",
        "description": "Server, member, avatar, and system lookups",
        "cogs": ["Utility"]
    },
    "welcome": {
        "label": "Welcome",
        "description": "Member greetings and join autoroles",
        "cogs": ["Welcome"]
    },
    "giveaways": {
        "label": "Giveaways",
        "description": "Community prize drawings and timed giveaways",
        "cogs": ["Giveaways"]
    },
    "fun": {
        "label": "Fun & Games",
        "description": "Mini-games, coinflips, and trivia",
        "cogs": ["Fun"]
    },
}


class HelpSelect(ui.Select):
    def __init__(self, cog: "Help", ctx: commands.Context):
        self.help_cog = cog
        self.ctx = ctx

        options = [
            discord.SelectOption(
                label="Home",
                description="Overview and system summary",
                value="home"
            )
        ]

        for key, data in CATEGORY_MAPPING.items():
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"][:100],
                    value=key
                )
            )

        super().__init__(
            placeholder="Select a category to view commands...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "Only the command author can interact with this selector."),
                ephemeral=True
            )

        selected = self.values[0]

        if selected == "home":
            embed = self.help_cog.get_home_embed(self.ctx)
            return await interaction.response.edit_message(embed=embed, view=self.view)

        cat_info = CATEGORY_MAPPING.get(selected)
        if not cat_info:
            embed = ZenithEmbed.error("Category Not Found", "No commands registered in this category.")
            return await interaction.response.edit_message(embed=embed, view=self.view)

        all_cmds: List[commands.Command] = []
        for cog_name in cat_info["cogs"]:
            target_cog = self.help_cog.bot.get_cog(cog_name)
            if target_cog:
                all_cmds.extend([c for c in target_cog.get_commands() if not c.hidden])

        embed = ZenithEmbed(
            title=f"[{cat_info['label'].upper()}]",
            description=(
                f"{cat_info['description']}.\n"
                f"Prefix: `{self.ctx.prefix}` | Run `{self.ctx.prefix}help <command>` for detailed syntax.\n"
            ),
            color=0x0F0F13
        )

        if not all_cmds:
            embed.description += "\n*No public commands available in this module.*"
        else:
            for cmd in all_cmds:
                name = f"{self.ctx.prefix}{cmd.qualified_name}"
                desc = cmd.help or cmd.brief or "No description provided."
                if isinstance(cmd, commands.Group) and cmd.commands:
                    sub_names = ", ".join(f"`{sub.name}`" for sub in cmd.commands if not sub.hidden)
                    desc = f"{desc}\nSubcommands: {sub_names}"

                embed.add_field(name=f"`{name}`", value=desc, inline=False)

        embed.set_footer(text="Zenith Suite | Developed by Shree")
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
                f"Registered Commands: `{total_commands}+`\n"
                "Select a category from the dropdown menu to inspect modules.\n"
                f"Run `{ctx.prefix}help <command>` for complete arguments and flags."
            ),
            color=0x0F0F13
        )

        embed.add_field(
            name="Security & Governance",
            value="`Antinuke`, `Mainrole`, `AntiBetray`, `FakePermission`, `Automod`",
            inline=False
        )
        embed.add_field(
            name="Administration & Roles",
            value="`Moderation`, `Roles`, `Server`, `Tickets`, `Server Logs`",
            inline=False
        )
        embed.add_field(
            name="Engagement & Media",
            value="`Music`, `Economy`, `Utility`, `Voice`, `Giveaways`, `Welcome`, `Fun`, `AFK`",
            inline=False
        )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Zenith Autonomous Defense | Developed by Shree")
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
            color=0x0F0F13
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

        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    if bot.get_command("help"):
        bot.remove_command("help")
    await bot.add_cog(Help(bot))
