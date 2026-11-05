"""
ui/views.py - Zenith Components V2 Interactive Views
Engineered by Shree (Discord ID: 1465912900710305822)

All interactive controls (buttons, pagination switches, confirmation toggles)
are housed INSIDE the Components V2 Container via ActionRow.
"""

from __future__ import annotations

from typing import List, Optional, Union, Dict, Any
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
)
from discord import UnfurledMediaItem

from ui.components import (
    DEFAULT_ACCENT,
    TAG_OK,
    TAG_ERROR,
    TAG_DENIED,
    TAG_WARN,
    embed_to_container,
)


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Prompt (Buttons Inside Container)
# ─────────────────────────────────────────────────────────────────────────────

class ConfirmLayoutView(LayoutView):
    """Components V2 confirmation prompt with Confirm & Cancel buttons inside the Container."""

    def __init__(
        self,
        author_id: int,
        prompt_title: str = "Confirm Action",
        prompt_text: str = "Are you sure you want to proceed with this operation?",
        timeout: float = 30.0
    ):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.prompt_title = prompt_title
        self.prompt_text = prompt_text
        self.value: Optional[bool] = None
        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = Container(accent_color=DEFAULT_ACCENT)
        container.add_item(TextDisplay(f"### [PROMPT] {self.prompt_title}"))
        container.add_item(TextDisplay(self.prompt_text))
        container.add_item(Separator())

        # Buttons nested INSIDE Container via ActionRow
        btn_confirm = Button(
            label="Confirm",
            style=discord.ButtonStyle.success,
            custom_id=f"cfm_yes_{id(self)}"
        )
        btn_cancel = Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
            custom_id=f"cfm_no_{id(self)}"
        )
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback = self._on_cancel

        row = ActionRow(btn_confirm, btn_cancel)
        container.add_item(row)
        container.add_item(Separator())
        container.add_item(TextDisplay("-# Zenith Control Plane • Select an option to proceed"))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{TAG_DENIED} You are not authorized to respond to this prompt.",
                ephemeral=True
            )
            return False
        return True

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        self.value = True
        self.stop()
        await interaction.response.defer()

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self.value = False
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self) -> None:
        self.value = False
        self.stop()


async def confirmation_prompt(
    ctx: Any,
    prompt_title: str = "Confirm Action",
    prompt_text: str = "Are you sure you want to proceed?",
    timeout: float = 30.0,
) -> bool:
    """Dispatches a Components V2 confirmation prompt and awaits author response."""
    view = ConfirmLayoutView(
        author_id=ctx.author.id,
        prompt_title=prompt_title,
        prompt_text=prompt_text,
        timeout=timeout
    )
    msg = await ctx.send(view=view)
    await view.wait()
    try:
        await msg.delete()
    except Exception:
        pass
    return bool(view.value)


# ─────────────────────────────────────────────────────────────────────────────
# Paged Container View (Pagination Buttons Inside Container)
# ─────────────────────────────────────────────────────────────────────────────

class PaginatorLayoutView(LayoutView):
    """
    Components V2 multi-page viewer.
    Accepts Containers, Embeds, or Text Pages and puts pagination buttons inside the Container.
    """

    def __init__(
        self,
        pages: List[Union[Container, discord.Embed, str, Dict[str, Any]]],
        author_id: int,
        timeout: float = 120.0
    ):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self._build_page()

    def _build_page(self) -> None:
        self.clear_items()
        page_item = self.pages[self.current_page]

        # Normalize page into a Container
        if isinstance(page_item, Container):
            container = page_item
        elif isinstance(page_item, discord.Embed):
            container = embed_to_container(page_item)
        elif isinstance(page_item, dict):
            # Dict with 'title' and 'body'
            container = Container(accent_color=DEFAULT_ACCENT)
            if "title" in page_item:
                container.add_item(TextDisplay(f"### {page_item['title']}"))
            if "body" in page_item:
                container.add_item(TextDisplay(str(page_item["body"])))
        else:
            # Plain string
            container = Container(accent_color=DEFAULT_ACCENT)
            container.add_item(TextDisplay(str(page_item)))

        # Build Navigation Buttons
        prev_btn = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0),
            custom_id=f"page_prev_{id(self)}"
        )
        counter_btn = Button(
            label=f"{self.current_page + 1}/{len(self.pages)}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"page_cnt_{id(self)}"
        )
        next_btn = Button(
            label="Next",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page == len(self.pages) - 1),
            custom_id=f"page_next_{id(self)}"
        )
        stop_btn = Button(
            label="Dismiss",
            style=discord.ButtonStyle.danger,
            custom_id=f"page_stop_{id(self)}"
        )

        prev_btn.callback = self._on_prev
        next_btn.callback = self._on_next
        stop_btn.callback = self._on_stop

        # Add ActionRow with Buttons INSIDE the Container
        container.add_item(Separator())
        container.add_item(ActionRow(prev_btn, counter_btn, next_btn, stop_btn))
        container.add_item(Separator())
        container.add_item(TextDisplay(f"-# Page {self.current_page + 1} of {len(self.pages)} • Zenith Autonomous Core"))

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                f"{TAG_DENIED} You are not authorized to paginate this view.",
                ephemeral=True
            )
            return False
        return True

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._build_page()
            await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._build_page()
            await interaction.response.edit_message(view=self)

    async def _on_stop(self, interaction: discord.Interaction) -> None:
        self.stop()
        try:
            await interaction.message.delete()
        except Exception:
            pass

    async def on_timeout(self) -> None:
        self.stop()


# Backwards compatibility aliases
ConfirmView = ConfirmLayoutView
PaginatorView = PaginatorLayoutView
