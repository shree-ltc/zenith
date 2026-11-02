"""
ui/views.py - Interactive Discord UI Components for Zenith

Provides bulletproof, reusable UI views (Paginators, Confirmations, Menus).
"""

from typing import List, Optional, Callable, Any
import discord
from discord import ui
from ui.embeds import ZenithEmbed


class PaginatorView(ui.View):
    """Clean interactive embed paginator supporting arbitrary page lists."""

    def __init__(self, pages: List[discord.Embed], author_id: int, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0

        # Update counter on initialization
        self._update_counter_label()

    def _update_counter_label(self) -> None:
        self.page_counter.label = f"Page {self.current_page + 1} / {len(self.pages)}"
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Restricts navigation controls to the original command invoker."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "You cannot control this menu."),
                ephemeral=True
            )
            return False
        return True

    @ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_page = 0
        self._update_counter_label()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_counter_label()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(label="Page 1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: ui.Button):
        pass

    @ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_counter_label()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_button(self, interaction: discord.Interaction, button: ui.Button):
        self.current_page = len(self.pages) - 1
        self._update_counter_label()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(emoji="🗑️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self) -> None:
        """Disables buttons once the view times out to conserve resources."""
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = True
        try:
            # Attempt to update the message view if it still exists
            pass
        except Exception:
            pass


class ConfirmView(ui.View):
    """Reusable modal-style confirmation with Accept / Cancel buttons."""

    def __init__(self, author_id: int, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.value: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "Only the requester can confirm this prompt."),
                ephemeral=True
            )
            return False
        return True

    @ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✓")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✕")
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()
