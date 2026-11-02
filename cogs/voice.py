"""
Join-to-create temporary voice channels with automated room cleanup.
"""

from typing import Optional
import discord
from discord.ext import commands

from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color


class Voice(commands.Cog):
    """Dynamic voice hub and room governance."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Monitors voice state transitions to create or destroy temporary rooms."""
        # 1. Member connects or switches channel
        if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
            # Check if after.channel is a TempVC Hub
            hub_row = await db.fetchrow(
                "SELECT hub_channel_id, category_id, default_name FROM tempvc_config WHERE guild_id = ? AND hub_channel_id = ?",
                member.guild.id, after.channel.id
            )
            if hub_row:
                category = member.guild.get_channel(hub_row["category_id"])
                room_name = f"{member.display_name}'s Lounge"

                # Setup room with creator as manager
                overwrites = {
                    member.guild.default_role: discord.PermissionOverwrite(connect=True, speak=True),
                    member: discord.PermissionOverwrite(connect=True, speak=True, manage_channels=True, move_members=True)
                }

                temp_channel = await member.guild.create_voice_channel(
                    name=room_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Zenith TempVC generated for {member}"
                )

                # Track active channel in database
                await db.execute(
                    "INSERT INTO tempvc_active (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
                    temp_channel.id, member.guild.id, member.id
                )

                # Move member into their fresh private room
                try:
                    await member.move_to(temp_channel, reason="Zenith TempVC relocation.")
                except Exception:
                    pass

        # 2. Member leaves or switches channel -> Check if previous channel was a TempVC and is now empty
        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            active_row = await db.fetchrow(
                "SELECT owner_id FROM tempvc_active WHERE channel_id = ?",
                before.channel.id
            )
            if active_row:
                # If channel is deserted, safely delete it
                if len(before.channel.members) == 0:
                    await db.execute("DELETE FROM tempvc_active WHERE channel_id = ?", before.channel.id)
                    try:
                        await before.channel.delete(reason="Zenith TempVC: Cleaned deserted room.")
                    except Exception:
                        pass

    # ═══════════════════════════════════════════════════════════════
    #  VOICE ROOM OWNER CONTROLS
    # ═══════════════════════════════════════════════════════════════

    async def _get_voice_room(self, ctx: commands.Context) -> Optional[discord.VoiceChannel]:
        """Validates that the author is actively inside a temp room they own."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(embed=ZenithEmbed.error("Not Connected", "You must be inside a voice channel to execute this."), mention_author=False)
            return None

        channel = ctx.author.voice.channel
        row = await db.fetchrow("SELECT owner_id FROM tempvc_active WHERE channel_id = ?", channel.id)
        if not row:
            await ctx.reply(embed=ZenithEmbed.error("Not a Temp Room", "This voice channel is not managed by Zenith TempVC."), mention_author=False)
            return None

        if row["owner_id"] != ctx.author.id and not ctx.author.guild_permissions.manage_channels:
            await ctx.reply(embed=ZenithEmbed.error("Not Room Owner", "Only the owner of this voice room can modify its settings."), mention_author=False)
            return None

        return channel

    @commands.group(name="voice", aliases=["vc", "tempvc"], invoke_without_command=True)
    async def voice_group(self, ctx: commands.Context):
        """Displays voice room controls."""
        embed = ZenithEmbed(
            title="Zenith Voice Channel Controls",
            description=(
                f"• `{ctx.prefix}voice lock` — Restricts entry to permitted users\n"
                f"• `{ctx.prefix}voice unlock` — Re-opens channel to everyone\n"
                f"• `{ctx.prefix}voice rename <name>` — Changes your channel's title\n"
                f"• `{ctx.prefix}voice limit <number>` — Sets user capacity (0-99)\n"
                f"• `{ctx.prefix}voice permit <@user>` — Grants entry into locked room\n"
                f"• `{ctx.prefix}voice reject <@user>` — Ejects user from your room\n"
                f"• `{ctx.prefix}voice claim` — Claims deserted room ownership"
            ),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @voice_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def tempvc_setup(self, ctx: commands.Context, hub_channel: discord.VoiceChannel, category: discord.CategoryChannel):
        """Designates a voice channel as the dynamic generator hub."""
        if db.is_postgres:
            query = """
            INSERT INTO tempvc_config (guild_id, hub_channel_id, category_id) VALUES (?, ?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET
                hub_channel_id = EXCLUDED.hub_channel_id,
                category_id = EXCLUDED.category_id;
            """
        else:
            query = """
            INSERT INTO tempvc_config (guild_id, hub_channel_id, category_id) VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                hub_channel_id = excluded.hub_channel_id,
                category_id = excluded.category_id;
            """
        await db.execute(query, ctx.guild.id, hub_channel.id, category.id)
        embed = ZenithEmbed.success("TempVC Hub Activated", f"Members joining {hub_channel.mention} will spawn private rooms in **{category.name}**.")
        await ctx.reply(embed=embed, mention_author=False)

    @voice_group.command(name="lock")
    async def voice_lock(self, ctx: commands.Context):
        """Prevents unauthorized members from joining your room."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(ctx.guild.default_role, connect=False)
        await ctx.reply(embed=ZenithEmbed.success("Room Locked", "Your voice channel is now private. Use `z!voice permit @user` to invite friends."), mention_author=False)

    @voice_group.command(name="unlock")
    async def voice_unlock(self, ctx: commands.Context):
        """Restores public entry to your voice room."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(ctx.guild.default_role, connect=None)
        await ctx.reply(embed=ZenithEmbed.success("Room Unlocked", "Anyone can now join your voice channel."), mention_author=False)

    @voice_group.command(name="rename")
    async def voice_rename(self, ctx: commands.Context, *, new_name: str):
        """Renames your temporary voice channel."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        clean_name = new_name.strip()[:32]
        await ch.edit(name=clean_name)
        await ctx.reply(embed=ZenithEmbed.success("Room Renamed", f"Channel renamed to **{clean_name}**."), mention_author=False)

    @voice_group.command(name="limit")
    async def voice_limit(self, ctx: commands.Context, capacity: int):
        """Sets the maximum number of occupants (0 to 99)."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        if capacity < 0 or capacity > 99:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Limit", "Capacity must be between 0 (unlimited) and 99."), mention_author=False)

        await ch.edit(user_limit=capacity)
        limit_text = "Unlimited" if capacity == 0 else f"{capacity} users"
        await ctx.reply(embed=ZenithEmbed.success("Capacity Adjusted", f"User limit set to **{limit_text}**."), mention_author=False)

    @voice_group.command(name="permit")
    async def voice_permit(self, ctx: commands.Context, target: discord.Member):
        """Allows a specific member to enter your locked voice channel."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(target, connect=True)
        await ctx.reply(embed=ZenithEmbed.success("Permission Granted", f"{target.mention} can now join your locked room."), mention_author=False)

    @voice_group.command(name="reject", aliases=["kick"])
    async def voice_reject(self, ctx: commands.Context, target: discord.Member):
        """Disconnects a user from your voice room and blocks re-entry."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(target, connect=False)
        if target.voice and target.voice.channel == ch:
            await target.move_to(None, reason="Zenith Voice: Ejected by room owner.")
        await ctx.reply(embed=ZenithEmbed.success("Member Ejected", f"{target.mention} has been removed and blocked from your room."), mention_author=False)

    @voice_group.command(name="hide")
    async def voice_hide(self, ctx: commands.Context):
        """Make your temporary voice channel invisible to @everyone."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(ctx.guild.default_role, view_channel=False)
        await ctx.reply(embed=ZenithEmbed.success("Room Hidden", "Your voice channel is now hidden from the public channel list."), mention_author=False)

    @voice_group.command(name="unhide")
    async def voice_unhide(self, ctx: commands.Context):
        """Make your temporary voice channel visible to @everyone."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        await ch.set_permissions(ctx.guild.default_role, view_channel=None)
        await ctx.reply(embed=ZenithEmbed.success("Room Visible", "Your voice channel is now visible on the server list."), mention_author=False)

    @voice_group.command(name="bitrate")
    async def voice_bitrate(self, ctx: commands.Context, kbps: int):
        """Adjust the audio quality bitrate of your voice room."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        max_bitrate = int(ctx.guild.bitrate_limit / 1000)
        if kbps < 8 or kbps > max_bitrate:
            return await ctx.reply(f"[ERROR] Bitrate must be between 8 and {max_bitrate} kbps.", mention_author=False)

        await ch.edit(bitrate=kbps * 1000)
        await ctx.reply(embed=ZenithEmbed.success("Bitrate Adjusted", f"Channel audio quality set to **{kbps} kbps**."), mention_author=False)

    @voice_group.command(name="claim")
    async def voice_claim(self, ctx: commands.Context):
        """Claim ownership of a room if the original creator left."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply("[ERROR] You must be inside a voice channel.", mention_author=False)

        ch = ctx.author.voice.channel
        row = await db.fetchrow("SELECT owner_id FROM tempvc_active WHERE channel_id = ?", ch.id)
        if not row:
            return await ctx.reply("[ERROR] This is not an active temporary voice channel.", mention_author=False)

        current_owner = ctx.guild.get_member(row["owner_id"])
        if current_owner and current_owner in ch.members:
            return await ctx.reply(f"[ERROR] The original owner ({current_owner.mention}) is still in the room.", mention_author=False)

        await db.execute("UPDATE tempvc_active SET owner_id = ? WHERE channel_id = ?", ctx.author.id, ch.id)
        await ch.set_permissions(ctx.author, connect=True, speak=True, manage_channels=True, move_members=True)
        await ctx.reply(embed=ZenithEmbed.success("Room Claimed", f"You are now the owner of {ch.mention}."), mention_author=False)

    @voice_group.command(name="transfer")
    async def voice_transfer(self, ctx: commands.Context, member: discord.Member):
        """Transfer room ownership to another member in the channel."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        if member not in ch.members:
            return await ctx.reply(f"[ERROR] {member.mention} is not currently in this voice room.", mention_author=False)

        await db.execute("UPDATE tempvc_active SET owner_id = ? WHERE channel_id = ?", member.id, ch.id)
        await ch.set_permissions(member, connect=True, speak=True, manage_channels=True, move_members=True)
        await ctx.reply(embed=ZenithEmbed.success("Ownership Transferred", f"Transferred room ownership to {member.mention}."), mention_author=False)

    @voice_group.command(name="status", aliases=["info"])
    async def voice_status(self, ctx: commands.Context):
        """View settings and status of the current voice channel."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        row = await db.fetchrow("SELECT owner_id FROM tempvc_active WHERE channel_id = ?", ch.id)
        owner = ctx.guild.get_member(row["owner_id"]) if row else None

        embed = discord.Embed(
            title=f"[VOICE STATUS] {ch.name}",
            color=0x0F0F13
        )
        embed.add_field(name="Owner", value=f"{owner.mention if owner else 'Unknown'}", inline=True)
        embed.add_field(name="Capacity", value=f"{len(ch.members)}/{ch.user_limit or 'Unlimited'}", inline=True)
        embed.add_field(name="Bitrate", value=f"{ch.bitrate // 1000} kbps", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @voice_group.command(name="muteall")
    async def voice_muteall(self, ctx: commands.Context):
        """Mute all members in your voice room."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        count = 0
        for m in ch.members:
            if m.id != ctx.author.id:
                try:
                    await m.edit(mute=True, reason=f"Mute all by {ctx.author}")
                    count += 1
                except Exception:
                    pass
        await ctx.reply(embed=ZenithEmbed.success("Mute All Complete", f"Muted **{count}** occupants in room."), mention_author=False)

    @voice_group.command(name="unmuteall")
    async def voice_unmuteall(self, ctx: commands.Context):
        """Unmute all members in your voice room."""
        ch = await self._get_voice_room(ctx)
        if not ch:
            return
        count = 0
        for m in ch.members:
            if m.id != ctx.author.id:
                try:
                    await m.edit(mute=False, reason=f"Unmute all by {ctx.author}")
                    count += 1
                except Exception:
                    pass
        await ctx.reply(embed=ZenithEmbed.success("Unmute All Complete", f"Unmuted **{count}** occupants in room."), mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Voice(bot))
