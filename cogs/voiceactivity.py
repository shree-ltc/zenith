"""
Voice Activity Tracking & Mass Voice Operations for Zenith.
Tracks voice channel presence duration and provides bulk audio moderation controls.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
from typing import Optional, Dict
import discord
from discord.ext import commands

from core.database import db

ACCENT_COLOR = 0x0F0F13


class VoiceActivity(commands.Cog):
    """Voice presence tracking and channel moderation suite."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # In-memory session tracking: {(guild_id, user_id): join_timestamp}
        self._voice_sessions: Dict[tuple[int, int], float] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        key = (member.guild.id, member.id)
        now = time.time()

        # Joined a voice channel
        if not before.channel and after.channel:
            self._voice_sessions[key] = now

        # Left voice channel
        elif before.channel and not after.channel:
            join_time = self._voice_sessions.pop(key, None)
            if join_time:
                duration = int(now - join_time)
                await db.execute(
                    """
                    INSERT INTO voice_time (guild_id, user_id, total_seconds)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET total_seconds = voice_time.total_seconds + excluded.total_seconds
                    """,
                    member.guild.id, member.id, duration
                )

    # ---------------------------------------------------------
    # COMMANDS
    # ---------------------------------------------------------

    @commands.command(name="voicetime", aliases=["vctime"])
    @commands.guild_only()
    async def voice_time_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display total time spent in voice channels."""
        target = member or ctx.author
        row = await db.fetchrow("SELECT total_seconds FROM voice_time WHERE guild_id = ? AND user_id = ?", ctx.guild.id, target.id)
        total_sec = row["total_seconds"] if row else 0

        # Add active session time if currently connected
        active_start = self._voice_sessions.get((ctx.guild.id, target.id))
        if active_start:
            total_sec += int(time.time() - active_start)

        hours, rem = divmod(total_sec, 3600)
        mins, secs = divmod(rem, 60)

        embed = discord.Embed(
            title=f"[VOICE PRESENCE - {target.display_name}]",
            description=f"{target.mention} has spent **{hours:,}h {mins}m {secs}s** in voice channels.",
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="topvoice", aliases=["voicelb"])
    @commands.guild_only()
    async def top_voice(self, ctx: commands.Context):
        """Display server voice presence leaderboard."""
        rows = await db.fetch("SELECT user_id, total_seconds FROM voice_time WHERE guild_id = ? ORDER BY total_seconds DESC LIMIT 10", ctx.guild.id)
        if not rows:
            return await ctx.send(embed=discord.Embed(title="[NO DATA]", description="No voice activity recorded yet.", color=ACCENT_COLOR))

        lines = []
        for i, r in enumerate(rows, 1):
            h, rem = divmod(r["total_seconds"], 3600)
            m, _ = divmod(rem, 60)
            lines.append(f"`{i:02d}.` <@{r['user_id']}> — **{h:,}h {m}m**")

        embed = discord.Embed(title="[TOP VOICE LEADERBOARD]", description="\n".join(lines), color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)

    # ---------------------------------------------------------
    # MASS VOICE CONTROLS
    # ---------------------------------------------------------

    @commands.group(name="voicemanage", aliases=["vm", "massvoice"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(move_members=True, mute_members=True)
    async def vm_group(self, ctx: commands.Context):
        """Mass voice channel administrative actions."""
        embed = discord.Embed(
            title="[MASS VOICE CONTROLS]",
            description="Manage voice participants across rooms in bulk.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}vm muteall [vc]` - Server-mute all occupants\n"
                f"`{ctx.prefix}vm unmuteall [vc]` - Unmute all occupants\n"
                f"`{ctx.prefix}vm deafenall [vc]` - Server-deafen all occupants\n"
                f"`{ctx.prefix}vm undeafenall [vc]` - Undeafen all occupants\n"
                f"`{ctx.prefix}vm moveall <from_vc> <to_vc>` - Mass move occupants\n"
                f"`{ctx.prefix}vm kickall [vc]` - Disconnect all occupants"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @vm_group.command(name="muteall")
    @commands.guild_only()
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def vm_muteall(self, ctx: commands.Context, channel: Optional[discord.VoiceChannel] = None):
        """Server-mute all occupants in a voice channel."""
        vc = channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not vc:
            return await ctx.send(embed=discord.Embed(title="[NO CHANNEL]", description="Specify a voice channel or join one.", color=ACCENT_COLOR))

        count = 0
        for m in vc.members:
            if not m.bot:
                try:
                    await m.edit(mute=True, reason=f"Zenith Mass Mute [{ctx.author}]")
                    count += 1
                except Exception:
                    pass

        embed = discord.Embed(title="[MASS MUTE APPLIED]", description=f"Muted `{count}` occupants in {vc.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @vm_group.command(name="unmuteall")
    @commands.guild_only()
    @commands.has_permissions(mute_members=True)
    @commands.bot_has_permissions(mute_members=True)
    async def vm_unmuteall(self, ctx: commands.Context, channel: Optional[discord.VoiceChannel] = None):
        """Unmute all occupants in a voice channel."""
        vc = channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not vc:
            return await ctx.send(embed=discord.Embed(title="[NO CHANNEL]", description="Specify a voice channel or join one.", color=ACCENT_COLOR))

        count = 0
        for m in vc.members:
            if not m.bot:
                try:
                    await m.edit(mute=False, reason=f"Zenith Mass Unmute [{ctx.author}]")
                    count += 1
                except Exception:
                    pass

        embed = discord.Embed(title="[MASS UNMUTE APPLIED]", description=f"Unmuted `{count}` occupants in {vc.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @vm_group.command(name="moveall")
    @commands.guild_only()
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def vm_moveall(self, ctx: commands.Context, from_vc: discord.VoiceChannel, to_vc: discord.VoiceChannel):
        """Mass move all occupants between voice channels."""
        count = 0
        for m in from_vc.members:
            try:
                await m.move_to(to_vc, reason=f"Zenith Mass Move [{ctx.author}]")
                count += 1
            except Exception:
                pass

        embed = discord.Embed(title="[MASS MOVE COMPLETE]", description=f"Moved `{count}` occupants from {from_vc.mention} to {to_vc.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @vm_group.command(name="kickall")
    @commands.guild_only()
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def vm_kickall(self, ctx: commands.Context, channel: Optional[discord.VoiceChannel] = None):
        """Disconnect all members from a voice channel."""
        vc = channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not vc:
            return await ctx.send(embed=discord.Embed(title="[NO CHANNEL]", description="Specify a voice channel or join one.", color=ACCENT_COLOR))

        count = 0
        for m in vc.members:
            try:
                await m.move_to(None, reason=f"Zenith Mass Disconnect [{ctx.author}]")
                count += 1
            except Exception:
                pass

        embed = discord.Embed(title="[MASS DISCONNECT COMPLETE]", description=f"Disconnected `{count}` occupants from {vc.mention}.", color=ACCENT_COLOR)
        embed.set_footer(text="Zenith Voice Suite | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceActivity(bot))
