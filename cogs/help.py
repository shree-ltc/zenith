"""
cogs/help.py - Zenith Components V2 Command Directory
Engineered by Shree (Discord ID: 1465912900710305822)

Pure Discord Components V2 implementation with obsidian styling.
Category dropdown selector and link/navigation buttons are nested inside Container.
Zero decorative emojis - clean ASCII indicators.
"""

from __future__ import annotations

import os
from typing import Optional, List, Dict
import discord
from discord.ext import commands
from discord import ui
from discord.ui import (
    LayoutView,
    Container,
    Section,
    TextDisplay,
    Separator,
    Thumbnail,
    ActionRow,
    Button,
    Select,
)
from discord import UnfurledMediaItem

from ui.components import (
    DEFAULT_ACCENT,
    TAG_OK,
    TAG_ERROR,
    TAG_DENIED,
    TAG_WARN,
    build_container,
)

SUPPORT_URL = os.getenv("SUPPORT_SERVER", "https://discord.gg/zenith")
INVITE_URL = os.getenv(
    "INVITE_URL",
    "https://discord.com/oauth2/authorize?client_id=1298918870039527435&permissions=8&integration_type=0&scope=bot+applications.commands"
)
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://github.com/shree-ltc/zenith")

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
    "moderation": {
        "label": "Moderation & Cases",
        "description": "Bans, kicks, timeouts, warnings, locks, cases, and purges",
        "cogs": ["Moderation", "Cases", "Purge"]
    },
    "roles": {
        "label": "Role Suite & Reaction Roles",
        "description": "Role editing, mass assignment, autoroles, and reaction roles",
        "cogs": ["Role", "Autorole", "ReactionRole"]
    },
    "automod": {
        "label": "Automod Matrix",
        "description": "Anti-spam, link filters, invite blocks, and caps",
        "cogs": ["Automod"]
    },
    "automation": {
        "label": "Automation & Custom Tags",
        "description": "Tags, autoresponder triggers, autoreactions, and sticky messages",
        "cogs": ["Tags", "Autoresponder", "Autoreact", "StickyMessage"]
    },
    "ignore": {
        "label": "Ignore Controls",
        "description": "Blacklist channels, commands, and users with bypass rules",
        "cogs": ["Ignore"]
    },
    "tracker": {
        "label": "Invite & Stats Tracker",
        "description": "Invite attribution, message counters, and live VC stats",
        "cogs": ["Tracker", "ServerStats"]
    },
    "music": {
        "label": "Music & Audio",
        "description": "High-fidelity audio streaming, queue, and autoplay",
        "cogs": ["Music"]
    },
    "voice": {
        "label": "Voice Lounges & Moderation",
        "description": "Join-to-create temp channels and mass voice controls",
        "cogs": ["Voice", "VoiceActivity"]
    },
    "leveling": {
        "label": "Leveling & XP",
        "description": "Experience ranks, progress bars, and level role rewards",
        "cogs": ["Leveling"]
    },
    "economy": {
        "label": "Economy & Market",
        "description": "Currency, banking, jobs, shifts, shop, inventory, and casino",
        "cogs": ["Economy"]
    },
    "games": {
        "label": "Games & Challenges",
        "description": "Tic-Tac-Toe, Blackjack, Connect-4, Fastclick, Wordle, and Typeracer",
        "cogs": ["Games"]
    },
    "birthdays": {
        "label": "Birthdays Calendar",
        "description": "Birthday registrations, role assignments, and announcements",
        "cogs": ["Birthdays"]
    },
    "suggestions": {
        "label": "Suggestions System",
        "description": "Community ideas, voting, and staff decision management",
        "cogs": ["Suggestions"]
    },
    "starboard": {
        "label": "Starboard Suite",
        "description": "Community spotlight, threshold filters, and starboard pins",
        "cogs": ["Starboard"]
    },
    "tickets": {
        "label": "Support Tickets",
        "description": "Interactive ticket panels, category routing, and transcripts",
        "cogs": ["Tickets"]
    },
    "utility": {
        "label": "Utility & Diagnostics",
        "description": "Serverinfo, userinfo, telemetry, reminders, and node stats",
        "cogs": ["Utility", "Lookup", "General", "Telemetry"]
    },
}


class HelpLayoutView(LayoutView):
    """Components V2 interactive Help Directory."""

    def __init__(self, cog: "Help", ctx: commands.Context):
        super().__init__(timeout=180.0)
        self.cog = cog
        self.ctx = ctx
        self.author_id = ctx.author.id
        self.current_category: Optional[str] = None
        self._build_home()

    def _create_dropdown(self, default_val: Optional[str] = None) -> Select:
        options = [
            discord.SelectOption(
                label="Home Overview",
                value="home",
                description="Return to Zenith system directory overview",
                default=(default_val == "home" or default_val is None)
            )
        ]
        for key, data in CATEGORY_MAPPING.items():
            options.append(
                discord.SelectOption(
                    label=data["label"][:100],
                    value=key,
                    description=data["description"][:100],
                    default=(key == default_val)
                )
            )

        dropdown = Select(
            placeholder="Select a module category...",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"help_sel_{id(self)}"
        )
        dropdown.callback = self._on_select
        return dropdown

    def _build_home(self) -> None:
        self.clear_items()
        total_commands = len([c for c in self.cog.bot.commands if not c.hidden])

        intro_text = (
            f"### Zenith Command Directory\n"
            f"• **Server Prefix :** `{self.ctx.prefix}`\n"
            f"• **Active Endpoints :** `{total_commands}+`\n"
            f"• **Architecture :** Sub-millisecond Redis + PostgreSQL cache bus\n\n"
            f"Select a category below to view registered commands and parameters.\n"
            f"Run `{self.ctx.prefix}help <command>` for syntax, aliases, and flags."
        )

        section = Section(
            TextDisplay(intro_text),
            accessory=Thumbnail(media=UnfurledMediaItem(url=self.cog.bot.user.display_avatar.url))
        )

        container = Container(accent_color=DEFAULT_ACCENT)
        container.add_item(section)
        container.add_item(Separator())

        # Module list text
        mod_lines = [
            f"> **`•` {data['label']}** — {data['description']}"
            for data in list(CATEGORY_MAPPING.values())[:6]
        ]
        container.add_item(TextDisplay("\n".join(mod_lines)))
        container.add_item(Separator())

        # Dropdown inside Container
        container.add_item(ActionRow(self._create_dropdown("home")))

        # Interactive buttons inside Container
        invite_btn = Button(label="Invite Bot", style=discord.ButtonStyle.link, url=INVITE_URL)
        support_btn = Button(label="Support Hub", style=discord.ButtonStyle.link, url=SUPPORT_URL)
        close_btn = Button(label="Dismiss", style=discord.ButtonStyle.danger, custom_id=f"help_close_{id(self)}")
        close_btn.callback = self._on_close

        container.add_item(ActionRow(invite_btn, support_btn, close_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# Zenith Autonomous Defense Architecture • Author: Shree"))

        self.add_item(container)

    def _build_category(self, category_key: str) -> None:
        self.clear_items()
        cat_info = CATEGORY_MAPPING.get(category_key)
        if not cat_info:
            return self._build_home()

        all_cmds: List[commands.Command] = []
        for cog_name in cat_info["cogs"]:
            target_cog = self.cog.bot.get_cog(cog_name)
            if target_cog:
                all_cmds.extend([c for c in target_cog.get_commands() if not c.hidden])

        container = Container(accent_color=DEFAULT_ACCENT)
        header_text = (
            f"### [{cat_info['label'].upper()}]\n"
            f"{cat_info['description']}\n"
            f"Prefix: `{self.ctx.prefix}` • Run `{self.ctx.prefix}help <command>` for detailed flags."
        )
        container.add_item(TextDisplay(header_text))
        container.add_item(Separator())

        if not all_cmds:
            container.add_item(TextDisplay("*No public commands currently available in this module.*"))
        else:
            cmd_lines = []
            for cmd in all_cmds:
                sig = f" {cmd.signature}" if cmd.signature else ""
                desc = cmd.help or cmd.brief or "No description provided."
                cmd_lines.append(f"**`{self.ctx.prefix}{cmd.qualified_name}{sig}`**\n> {desc}")

            # Display commands with separators
            chunk_text = "\n\n".join(cmd_lines[:12])
            container.add_item(TextDisplay(chunk_text))
            if len(cmd_lines) > 12:
                container.add_item(TextDisplay(f"-# +{len(cmd_lines) - 12} additional commands in module"))

        container.add_item(Separator())

        # Dropdown inside Container
        container.add_item(ActionRow(self._create_dropdown(category_key)))

        # Buttons inside Container
        home_btn = Button(label="Home Overview", style=discord.ButtonStyle.secondary, custom_id=f"help_home_{id(self)}")
        close_btn = Button(label="Dismiss", style=discord.ButtonStyle.danger, custom_id=f"help_close_{id(self)}")
        home_btn.callback = self._on_home
        close_btn.callback = self._on_close

        container.add_item(ActionRow(home_btn, close_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay("-# Zenith Suite • Developed by Shree"))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{TAG_DENIED} This directory is reserved for the invoking user.",
                ephemeral=True
            )
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        selected = interaction.data.get("values", ["home"])[0]
        if selected == "home":
            self.current_category = None
            self._build_home()
        else:
            self.current_category = selected
            self._build_category(selected)
        await interaction.response.edit_message(view=self)

    async def _on_home(self, interaction: discord.Interaction) -> None:
        self.current_category = None
        self._build_home()
        await interaction.response.edit_message(view=self)

    async def _on_close(self, interaction: discord.Interaction) -> None:
        self.stop()
        try:
            await interaction.message.delete()
        except Exception:
            pass

    async def on_timeout(self) -> None:
        self.stop()


class Help(commands.Cog):
    """Zenith Command Explorer and Interactive Directory."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["commands", "cmds", "h"])
    async def help_command(self, ctx: commands.Context, *, command_query: Optional[str] = None):
        """Displays interactive command directory or inspects a specific command."""
        if not command_query:
            view = HelpLayoutView(self, ctx)
            return await ctx.send(view=view)

        cmd = self.bot.get_command(command_query)
        if not cmd:
            container = Container(accent_color=DEFAULT_ACCENT)
            container.add_item(TextDisplay(f"### {TAG_ERROR} Command Not Found"))
            container.add_item(TextDisplay(f"> No command matching `{command_query}` exists in the registry."))
            view = LayoutView(timeout=None)
            view.add_item(container)
            return await ctx.send(view=view)

        # Build specific command container
        container = Container(accent_color=DEFAULT_ACCENT)
        container.add_item(TextDisplay(f"### Command: {ctx.prefix}{cmd.qualified_name}"))
        container.add_item(TextDisplay(cmd.help or "No description provided for this command."))
        container.add_item(Separator())

        usage = f"`{ctx.prefix}{cmd.qualified_name} {cmd.signature}`".strip()
        container.add_item(TextDisplay(f"**Syntax:**\n{usage}"))

        if cmd.aliases:
            aliases_str = ", ".join(f"`{a}`" for a in cmd.aliases)
            container.add_item(TextDisplay(f"**Aliases:** {aliases_str}"))

        if cmd._buckets and cmd._buckets._cooldown:
            container.add_item(TextDisplay(f"**Cooldown:** `{cmd._buckets._cooldown.per:.0f}s`"))

        if isinstance(cmd, commands.Group) and cmd.commands:
            sub_list = "\n".join(
                f"• `{ctx.prefix}{cmd.qualified_name} {sub.name}` - {sub.help or 'No info'}"
                for sub in cmd.commands if not sub.hidden
            )
            container.add_item(Separator())
            container.add_item(TextDisplay(f"**Subcommands:**\n{sub_list}"))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# Zenith Suite • Developed by Shree"))

        view = LayoutView(timeout=None)
        view.add_item(container)
        await ctx.send(view=view)


async def setup(bot: commands.Bot):
    if bot.get_command("help"):
        bot.remove_command("help")
    await bot.add_cog(Help(bot))
