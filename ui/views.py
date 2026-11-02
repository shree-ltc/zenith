"""
Reusable UI views for interactive pagination and user confirmation.
"""

from typing import List, Optional
import discord
from discord import ui
from ui.embeds import ZenithEmbed


class PaginatorView(ui.View):
    def __init__(self, pages: List[discord.Embed], author_id: int, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.page_counter.label = f"{self.current_page + 1}/{len(self.pages)}"
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=ZenithEmbed.error("Access Denied", "You cannot control this menu."),
                ephemeral=True
            )
            return False
        return True

    @ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_counter(self, interaction: discord.Interaction, button: ui.Button):
        pass

    @ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(label="Dismiss", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = True


class ConfirmView(ui.View):
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

    @ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()
