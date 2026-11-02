"""
Support ticket system with persistent buttons and transcript export.
"""

import io
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands
from discord import ui

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color
from ui.views import ConfirmView


class TicketControlView(ui.View):
    """Action bar attached inside every active ticket channel."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="zenith:ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        """Initiates ticket closure with confirmation."""
        confirm_view = ConfirmView(interaction.user.id, timeout=30.0)
        confirm_embed = ZenithEmbed.warning(
            "Close Support Ticket",
            "Are you sure you want to finalize and archive this ticket? The channel will be permanently removed."
        )
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
        await confirm_view.wait()

        if confirm_view.value is True:
            # 1. Fetch opener ID from database
            row = await db.fetchrow(
                "SELECT user_id, opened_at FROM active_tickets WHERE ticket_channel_id = ?",
                interaction.channel_id
            )
            opener_id = row["user_id"] if row else None

            # 2. Generate transcript text buffer
            transcript_lines = [f"=== TICKET TRANSCRIPT FOR #{interaction.channel.name} ==="]
            transcript_lines.append(f"Closed By: {interaction.user} ({interaction.user.id})")
            transcript_lines.append(f"Closed At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n" + ("=" * 50) + "\n")

            async for msg in interaction.channel.history(limit=500, oldest_first=True):
                time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                transcript_lines.append(f"[{time_str}] {msg.author} ({msg.author.id}): {msg.clean_content}")

            transcript_buffer = io.BytesIO("\n".join(transcript_lines).encode("utf-8"))
            transcript_file = discord.File(transcript_buffer, filename=f"transcript-{interaction.channel.name}.txt")

            # 3. Attempt to DM the transcript to the ticket author
            if opener_id:
                try:
                    user = await self.bot.fetch_user(opener_id)
                    dm_embed = ZenithEmbed.info(
                        "Support Ticket Closed",
                        f"Your ticket in **{interaction.guild.name}** has been closed.\n"
                        f"A copy of the complete conversation history is attached below."
                    )
                    await user.send(embed=dm_embed, file=discord.File(io.BytesIO("\n".join(transcript_lines).encode("utf-8")), filename=f"transcript-{interaction.channel.name}.txt"))
                except Exception:
                    pass

            # 4. Clean up database & delete channel
            await db.execute("DELETE FROM active_tickets WHERE ticket_channel_id = ?", interaction.channel_id)
            await interaction.channel.delete(reason=f"Zenith Ticket Closed by {interaction.user}")

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="zenith:ticket:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: ui.Button):
        """Assigns the ticket exclusively to the responding staff member."""
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(
                embed=ZenithEmbed.error("Staff Only", "Only support staff may claim tickets."),
                ephemeral=True
            )

        await db.execute(
            "UPDATE active_tickets SET claimed_by = ? WHERE ticket_channel_id = ?",
            interaction.user.id, interaction.channel_id
        )

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

        embed = ZenithEmbed.success("Ticket Claimed", f"{interaction.user.mention} is now handling this support inquiry.")
        await interaction.channel.send(embed=embed)


class TicketLauncherView(ui.View):
    """Persistent button placed in the community support hub."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="zenith:ticket:create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        """Instantiates a private channel for the user."""
        guild = interaction.guild
        user = interaction.user

        # Prevent duplicate tickets from the same user
        existing = await db.fetchrow(
            "SELECT ticket_channel_id FROM active_tickets WHERE guild_id = ? AND user_id = ?",
            guild.id, user.id
        )
        if existing:
            ch = guild.get_channel(existing["ticket_channel_id"])
            if ch:
                return await interaction.response.send_message(
                    embed=ZenithEmbed.warning("Active Ticket Exists", f"You already have an open ticket in {ch.mention}."),
                    ephemeral=True
                )

        # Retrieve panel setup details
        panel_row = await db.fetchrow("SELECT category_id, support_role_id FROM ticket_panels WHERE guild_id = ?", guild.id)
        category_id = panel_row.get("category_id") if panel_row else None
        support_role_id = panel_row.get("support_role_id") if panel_row else None

        category = guild.get_channel(category_id) if category_id else None
        support_role = guild.get_role(support_role_id) if support_role_id else None

        # Build private permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel_name = f"ticket-{user.name}".lower().replace(" ", "-")[:32]
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Zenith Ticket Opened for {user}"
        )

        # Record in database
        await db.execute(
            "INSERT INTO active_tickets (ticket_channel_id, guild_id, user_id) VALUES (?, ?, ?)",
            ticket_channel.id, guild.id, user.id
        )

        # Greet user in the new channel
        embed = ZenithEmbed(
            title=f"Welcome to Support, {user.display_name}!",
            description=(
                "Thank you for contacting our team. Please outline your question or issue in detail below.\n"
                "A staff member will be with you shortly."
            ),
            color=Color.PRIMARY
        )
        control_view = TicketControlView(self.bot)
        await ticket_channel.send(content=f"{user.mention} | Staff: {support_role.mention if support_role else 'Support'}", embed=embed, view=control_view)

        await interaction.response.send_message(
            embed=ZenithEmbed.success("Ticket Generated", f"Your private support channel is ready: {ticket_channel.mention}."),
            ephemeral=True
        )


class Tickets(commands.Cog):
    """End-to-end ticketing infrastructure."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent views so button interactions work after bot reboots
        self.bot.add_view(TicketLauncherView(bot))
        self.bot.add_view(TicketControlView(bot))

    @commands.group(name="ticket", invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def ticket_group(self, ctx: commands.Context):
        """Displays ticket management manual."""
        embed = ZenithEmbed(
            title="Zenith Support Ticket System",
            description=(
                f"• `{ctx.prefix}ticket setup <channel> <category> <support_role>` — Deploys launcher\n"
                f"• `{ctx.prefix}ticket close` — Closes current ticket channel\n"
                f"• `{ctx.prefix}ticket add <@user>` — Adds member to active ticket\n"
                f"• `{ctx.prefix}ticket remove <@user>` — Ejects member from ticket"
            ),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @ticket_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx: commands.Context, channel: discord.TextChannel, category: discord.CategoryChannel, support_role: discord.Role):
        """Spawns an interactive ticket creation embed in the designated channel."""
        embed = ZenithEmbed(
            title="Need Assistance?",
            description=(
                "Click the **Create Ticket** button below to open a private line of communication "
                "with our dedicated support department.\n\n"
                "• Avoid tagging staff repeatedly.\n"
                "• Provide relevant screenshots and details upfront."
            ),
            color=Color.PRIMARY
        )
        launcher_view = TicketLauncherView(self.bot)
        panel_msg = await channel.send(embed=embed, view=launcher_view)

        # Store configuration in database
        if db.is_postgres:
            query = """
            INSERT INTO ticket_panels (guild_id, channel_id, message_id, category_id, support_role_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (guild_id, message_id) DO UPDATE SET
                category_id = EXCLUDED.category_id,
                support_role_id = EXCLUDED.support_role_id;
            """
        else:
            query = """
            INSERT INTO ticket_panels (guild_id, channel_id, message_id, category_id, support_role_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, message_id) DO UPDATE SET
                category_id = excluded.category_id,
                support_role_id = excluded.support_role_id;
            """
        await db.execute(query, ctx.guild.id, channel.id, panel_msg.id, category.id, support_role.id)

        await ctx.reply(
            embed=ZenithEmbed.success("Ticket Launcher Deployed", f"Interactive ticket embed published to {channel.mention}."),
            mention_author=False
        )

    @ticket_group.command(name="add")
    @commands.has_permissions(manage_channels=True)
    async def ticket_add(self, ctx: commands.Context, member: discord.Member):
        """Grants a user permission to view the current ticket channel."""
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await ctx.reply(embed=ZenithEmbed.success("Member Added", f"Granted {member.mention} access to this ticket."), mention_author=False)

    @ticket_group.command(name="remove")
    @commands.has_permissions(manage_channels=True)
    async def ticket_remove(self, ctx: commands.Context, member: discord.Member):
        """Removes a user's access from the current ticket channel."""
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.reply(embed=ZenithEmbed.success("Member Removed", f"Revoked access for {member.mention}."), mention_author=False)

    @ticket_group.command(name="close")
    @commands.has_permissions(manage_channels=True)
    async def ticket_close(self, ctx: commands.Context, *, reason: Optional[str] = "Resolved"):
        """Close and archive the current ticket channel."""
        row = await db.fetchrow("SELECT user_id FROM active_tickets WHERE ticket_channel_id = ?", ctx.channel.id)
        if not row:
            return await ctx.reply("[ERROR] This command can only be executed inside an active ticket channel.", mention_author=False)

        await ctx.reply(f"[INFO] Ticket closing in 5 seconds. Reason: `{reason}`...", mention_author=False)
        await asyncio.sleep(5)
        await db.execute("DELETE FROM active_tickets WHERE ticket_channel_id = ?", ctx.channel.id)
        try:
            await ctx.channel.delete(reason=f"Closed by {ctx.author}: {reason}")
        except Exception:
            pass

    @ticket_group.command(name="claim")
    @commands.has_permissions(manage_channels=True)
    async def ticket_claim_cmd(self, ctx: commands.Context):
        """Claim ownership of the active ticket as support staff."""
        row = await db.fetchrow("SELECT user_id FROM active_tickets WHERE ticket_channel_id = ?", ctx.channel.id)
        if not row:
            return await ctx.reply("[ERROR] Not an active ticket channel.", mention_author=False)

        await db.execute("UPDATE active_tickets SET claimed_by = ? WHERE ticket_channel_id = ?", ctx.author.id, ctx.channel.id)
        await ctx.reply(f"[OK] Ticket claimed by {ctx.author.mention}.", mention_author=False)

    @ticket_group.command(name="unclaim")
    @commands.has_permissions(manage_channels=True)
    async def ticket_unclaim_cmd(self, ctx: commands.Context):
        """Release staff claim on the active ticket."""
        row = await db.fetchrow("SELECT user_id FROM active_tickets WHERE ticket_channel_id = ?", ctx.channel.id)
        if not row:
            return await ctx.reply("[ERROR] Not an active ticket channel.", mention_author=False)

        await db.execute("UPDATE active_tickets SET claimed_by = NULL WHERE ticket_channel_id = ?", ctx.channel.id)
        await ctx.reply("[OK] Ticket claim released back to general support.", mention_author=False)

    @ticket_group.command(name="rename")
    @commands.has_permissions(manage_channels=True)
    async def ticket_rename_cmd(self, ctx: commands.Context, *, new_name: str):
        """Rename the current ticket channel."""
        row = await db.fetchrow("SELECT user_id FROM active_tickets WHERE ticket_channel_id = ?", ctx.channel.id)
        if not row:
            return await ctx.reply("[ERROR] Not an active ticket channel.", mention_author=False)

        clean = new_name.lower().replace(" ", "-")[:32]
        await ctx.channel.edit(name=clean, reason=f"Renamed by {ctx.author}")
        await ctx.reply(f"[OK] Ticket renamed to `{clean}`.", mention_author=False)

    @ticket_group.command(name="transcript")
    @commands.has_permissions(manage_channels=True)
    async def ticket_transcript_cmd(self, ctx: commands.Context):
        """Export a text transcript of all messages in the ticket."""
        lines = [f"=== TRANSCRIPT: #{ctx.channel.name} ==="]
        lines.append(f"Exported By: {ctx.author} ({ctx.author.id})")
        lines.append(f"Exported At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n" + ("=" * 50) + "\n")

        async for msg in ctx.channel.history(limit=1000, oldest_first=True):
            lines.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author} ({msg.author.id}): {msg.clean_content}")

        buffer = io.BytesIO("\n".join(lines).encode("utf-8"))
        file = discord.File(buffer, filename=f"transcript-{ctx.channel.name}.txt")
        await ctx.reply(content="[OK] Transcript generated successfully.", file=file, mention_author=False)

    @ticket_group.command(name="topic")
    @commands.has_permissions(manage_channels=True)
    async def ticket_topic_cmd(self, ctx: commands.Context, *, topic: str):
        """Set the support inquiry topic for this ticket."""
        await ctx.channel.edit(topic=topic[:1000], reason=f"Topic set by {ctx.author}")
        await ctx.reply(f"[OK] Ticket topic set to: `{topic}`", mention_author=False)

    @ticket_group.command(name="list")
    @commands.has_permissions(manage_channels=True)
    async def ticket_list_cmd(self, ctx: commands.Context):
        """List all active open support tickets."""
        rows = await db.fetch("SELECT ticket_channel_id, user_id, claimed_by FROM active_tickets WHERE guild_id = ?", ctx.guild.id)
        if not rows:
            return await ctx.reply("[INFO] No active support tickets open.", mention_author=False)

        desc = []
        for r in rows:
            claimer = f"Claimed by <@{r['claimed_by']}>" if r['claimed_by'] else "Unclaimed"
            desc.append(f"• <#{r['ticket_channel_id']}> | User: <@{r['user_id']}> | `{claimer}`")

        embed = discord.Embed(
            title=f"[ACTIVE TICKETS] {ctx.guild.name} ({len(rows)})",
            description="\n".join(desc),
            color=0x0F0F13
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
