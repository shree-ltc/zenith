"""
ui/components.py - Zenith Discord Components V2 Architecture
Engineered by Shree (Discord ID: 1465912900710305822)

Obsidian minimalist dark theme (accent_color: 0x000000).
Buttons, dropdowns, and interactive controls are nested inside Container via ActionRow.
Zero decorative emojis - clean ASCII indicators and Markdown styling.
"""

from __future__ import annotations

import os
from typing import Optional, List, Dict, Any, Union, Callable

import discord
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
    MediaGallery,
)
from discord import UnfurledMediaItem

# Obsidian Accent Color Palette (Default 0x000000 / Configurable via ACCENT_COLOR)
BLACK = discord.Colour(int(os.getenv("ACCENT_COLOR", "000000"), 16))
DEFAULT_ACCENT = BLACK

# Indicator Constants (Strictly ASCII / Non-decorative)
TAG_OK = "[OK]"
TAG_ERROR = "[ERROR]"
TAG_DENIED = "[DENIED]"
TAG_WARN = "[WARN]"
TAG_INFO = "[INFO]"
TAG_BUS = "[SECURITY BUS]"


# ─────────────────────────────────────────────────────────────────────────────
# Core Builders
# ─────────────────────────────────────────────────────────────────────────────

def build_container(*items: ui.Item, accent_color: Optional[Union[discord.Colour, int]] = None) -> Container:
    """Creates a Components V2 Container with obsidian styling."""
    color = accent_color if accent_color is not None else DEFAULT_ACCENT
    return Container(*items, accent_color=color)


def build_view(*containers: Container, timeout: Optional[float] = 180.0) -> LayoutView:
    """Wraps Containers into a Discord LayoutView."""
    view = LayoutView(timeout=timeout)
    for c in containers:
        view.add_item(c)
    return view


def embed_to_container(embed: discord.Embed, buttons: Optional[List[Button]] = None) -> Container:
    """
    Transforms a standard discord.Embed into a Components V2 Container.
    Places any interactive buttons inside the Container via ActionRow.
    """
    accent = embed.color if embed.color is not None else DEFAULT_ACCENT
    container = Container(accent_color=accent)

    title_text = f"### {embed.title}" if embed.title else ""
    desc_text = embed.description or ""
    full_text = f"{title_text}\n{desc_text}".strip()

    # Section with Thumbnail if an image/thumbnail is present
    if embed.thumbnail and embed.thumbnail.url:
        section = Section(
            TextDisplay(full_text if full_text else "No description"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=embed.thumbnail.url))
        )
        container.add_item(section)
    elif full_text:
        container.add_item(TextDisplay(full_text))

    # Convert Embed fields to clean separated TextDisplays
    for field in embed.fields:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"**{field.name}**\n{field.value}"))

    # Place interactive buttons inside the Container
    if buttons:
        container.add_item(Separator())
        container.add_item(ActionRow(*buttons))

    # Footer note
    if embed.footer and embed.footer.text:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {embed.footer.text}"))

    return container


# ─────────────────────────────────────────────────────────────────────────────
# Standard Feedback Containers (Return {"view": LayoutView})
# ─────────────────────────────────────────────────────────────────────────────

def denied_container(reason: str, footer: Optional[str] = None) -> dict:
    """
    Components V2 Process Denied notification.
    Usage: await ctx.send(**denied_container("Access restricted to Server Owner."))
    """
    container = Container(accent_color=DEFAULT_ACCENT)
    container.add_item(TextDisplay(f"### {TAG_DENIED} Process Denied"))
    container.add_item(TextDisplay(f"> {reason}"))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def error_container(title: str, description: str, footer: Optional[str] = None) -> dict:
    """Components V2 Error notification."""
    container = Container(accent_color=DEFAULT_ACCENT)
    container.add_item(TextDisplay(f"### {TAG_ERROR} {title}"))
    container.add_item(TextDisplay(f"> {description}"))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def success_container(
    title: str,
    description: Optional[str] = None,
    footer: Optional[str] = None,
    buttons: Optional[List[Button]] = None
) -> dict:
    """Components V2 Success notification with optional buttons inside container."""
    container = Container(accent_color=DEFAULT_ACCENT)
    container.add_item(TextDisplay(f"### {TAG_OK} {title}"))

    if description:
        container.add_item(TextDisplay(description))

    if buttons:
        container.add_item(Separator())
        container.add_item(ActionRow(*buttons))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def warning_container(title: str, description: Optional[str] = None, footer: Optional[str] = None) -> dict:
    """Components V2 Warning notification."""
    container = Container(accent_color=DEFAULT_ACCENT)
    container.add_item(TextDisplay(f"### {TAG_WARN} {title}"))

    if description:
        container.add_item(TextDisplay(f"> {description}"))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def action_container(
    title: str,
    lines: Optional[List[str]] = None,
    accent: Optional[discord.Colour] = None,
    footer: Optional[str] = None,
    buttons: Optional[List[Button]] = None,
) -> dict:
    """Generic action result container with bullet points and optional buttons inside."""
    container = Container(accent_color=accent or DEFAULT_ACCENT)
    container.add_item(TextDisplay(f"### {TAG_OK} {title}"))

    if lines:
        container.add_item(TextDisplay("\n".join(lines)))

    if buttons:
        container.add_item(Separator())
        container.add_item(ActionRow(*buttons))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def info_container(
    title: str,
    body: str,
    thumbnail_url: Optional[str] = None,
    footer: Optional[str] = None,
    buttons: Optional[List[Button]] = None,
) -> dict:
    """Components V2 Information container with optional thumbnail accessory."""
    container = Container(accent_color=DEFAULT_ACCENT)

    if thumbnail_url:
        section = Section(
            TextDisplay(f"### {title}\n{body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=thumbnail_url))
        )
        container.add_item(section)
    else:
        container.add_item(TextDisplay(f"### {title}"))
        container.add_item(TextDisplay(body))

    if buttons:
        container.add_item(Separator())
        container.add_item(ActionRow(*buttons))

    if footer:
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# {footer}"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def mod_action_container(
    action: str,
    target_name: str,
    moderator_name: str,
    reason: Optional[str] = None,
    dm_done: bool = False,
    extra_lines: Optional[List[str]] = None,
    bot_avatar: Optional[str] = None,
) -> dict:
    """Moderation incident report container with target diagnostics."""
    dm_status = "[YES]" if dm_done else "[NO]"
    reason_str = reason or "No reason specified"

    body = (
        f"**Target:** {target_name}\n"
        f"-# Moderator: {moderator_name}\n"
        f"**DM Notified:** {dm_status}\n"
        f"**Reason:** {reason_str}"
    )
    if extra_lines:
        body += "\n" + "\n".join(f"**{line}**" for line in extra_lines)

    container = Container(accent_color=DEFAULT_ACCENT)
    if bot_avatar:
        section = Section(
            TextDisplay(f"### {TAG_OK} {action}\n{body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=bot_avatar))
        )
        container.add_item(section)
    else:
        container.add_item(TextDisplay(f"### {TAG_OK} {action}"))
        container.add_item(TextDisplay(body))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# Zenith Security Bus • Audit Log Dispatched"))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


def ping_container(
    ws_ms: int,
    msg_ms: int,
    api_ms: int,
    bot_avatar: Optional[str] = None,
) -> dict:
    """Telemetry latency container."""
    body = (
        f"**Websocket Heartbeat :** `{ws_ms} ms`\n"
        f"**Message Roundtrip   :** `{msg_ms} ms`\n"
        f"**REST API Latency    :** `{api_ms} ms`\n"
        f"-# Zenith High-Performance Execution Bus"
    )

    container = Container(accent_color=DEFAULT_ACCENT)
    if bot_avatar:
        section = Section(
            TextDisplay(f"### {TAG_OK} Gateway Telemetry\n{body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=bot_avatar))
        )
        container.add_item(section)
    else:
        container.add_item(TextDisplay(f"### {TAG_OK} Gateway Telemetry"))
        container.add_item(TextDisplay(body))

    view = LayoutView(timeout=None)
    view.add_item(container)
    return {"view": view}


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Multi-Page Stats System (Components V2)
# ─────────────────────────────────────────────────────────────────────────────

class StatsPagedLayoutView(LayoutView):
    """
    3-Page interactive statistics container:
      Page 0: System runtime, gateway, and memory diagnostics
      Page 1: Team & authorship attribution
      Page 2: Ecosystem & server cluster details
    Controls (Select dropdown + Link buttons) are nested inside the container.
    """

    def __init__(
        self,
        author_id: int,
        bot_name: str,
        bot_avatar: str,
        invite_url: str,
        support_url: str,
        bot_info_body: str,
        team_data: Dict[str, List[tuple]],
        cluster_data: List[tuple],
    ):
        super().__init__(timeout=180.0)
        self.author_id = author_id
        self.bot_name = bot_name
        self.bot_avatar = bot_avatar
        self.invite_url = invite_url
        self.support_url = support_url
        self.bot_info_body = bot_info_body
        self.team_data = team_data
        self.cluster_data = cluster_data
        self.current_page = 0
        self._build()

    def _page_system_info(self) -> Container:
        container = Container(accent_color=DEFAULT_ACCENT)
        section = Section(
            TextDisplay(f"### • {self.bot_name} Core Statistics\n{self.bot_info_body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=self.bot_avatar))
        )
        container.add_item(section)
        container.add_item(Separator())
        self._add_controls(container)
        return container

    def _page_team(self) -> Container:
        container = Container(accent_color=DEFAULT_ACCENT)
        body_parts = []
        for role in ("Architect", "Developer", "Staff"):
            members = self.team_data.get(role, [])
            if not members:
                continue
            body_parts.append(f"**{role}:**")
            for i, (display_name, username, uid) in enumerate(members, start=1):
                profile_url = f"https://discord.com/users/{uid}"
                body_parts.append(f"`{i}.` [{display_name}]({profile_url}) — `{username}`")
            body_parts.append("")

        if not body_parts:
            body_parts = ["*Author: Shree (Discord ID: 1465912900710305822)*"]

        section = Section(
            TextDisplay(f"### • {self.bot_name} Team & Attribution\n" + "\n".join(body_parts)),
            accessory=Thumbnail(media=UnfurledMediaItem(url=self.bot_avatar))
        )
        container.add_item(section)
        container.add_item(Separator())
        self._add_controls(container)
        return container

    def _page_cluster(self) -> Container:
        container = Container(accent_color=DEFAULT_ACCENT)
        lines = []
        for i, (name, val) in enumerate(self.cluster_data, start=1):
            lines.append(f"`{i}.` **{name}** — `{val}`")
        body = "\n".join(lines) if lines else "*Single node cluster active.*"

        section = Section(
            TextDisplay(f"### • {self.bot_name} Cluster Telemetry\n{body}"),
            accessory=Thumbnail(media=UnfurledMediaItem(url=self.bot_avatar))
        )
        container.add_item(section)
        container.add_item(Separator())
        self._add_controls(container)
        return container

    def _add_controls(self, container: Container):
        select = Select(
            placeholder="Switch statistics section...",
            min_values=1,
            max_values=1,
            custom_id="stats_page_select",
            options=[
                discord.SelectOption(
                    label="System Core Info",
                    value="0",
                    description="Hardware, memory, and gateway telemetry",
                    default=(self.current_page == 0)
                ),
                discord.SelectOption(
                    label="Team & Architecture",
                    value="1",
                    description="Engineered by Shree",
                    default=(self.current_page == 1)
                ),
                discord.SelectOption(
                    label="Cluster State",
                    value="2",
                    description="Nodes, shards, and database health",
                    default=(self.current_page == 2)
                ),
            ]
        )
        select.callback = self._on_select
        container.add_item(ActionRow(select))

        # Buttons inside Container
        row = ActionRow(
            Button(label="Invite Bot", style=discord.ButtonStyle.link, url=self.invite_url),
            Button(label="Support Hub", style=discord.ButtonStyle.link, url=self.support_url),
        )
        container.add_item(row)

    def _build(self):
        self.clear_items()
        if self.current_page == 0:
            self.add_item(self._page_system_info())
        elif self.current_page == 1:
            self.add_item(self._page_team())
        else:
            self.add_item(self._page_cluster())

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                f"{TAG_DENIED} You cannot interact with this diagnostics panel.",
                ephemeral=True
            )
        self.current_page = int(interaction.data["values"][0])
        self._build()
        await interaction.response.edit_message(view=self)


def stats_paged_container(
    author_id: int,
    bot_name: str,
    bot_avatar: str,
    invite_url: str,
    support_url: str,
    bot_info_body: str,
    team_data: Dict[str, List[tuple]],
    cluster_data: List[tuple],
) -> StatsPagedLayoutView:
    return StatsPagedLayoutView(
        author_id=author_id,
        bot_name=bot_name,
        bot_avatar=bot_avatar,
        invite_url=invite_url,
        support_url=support_url,
        bot_info_body=bot_info_body,
        team_data=team_data,
        cluster_data=cluster_data,
    )
