"""
Music subsystem using Lavalink with smart autoplay and queue management.
"""

import re
import random
import asyncio
from typing import Optional, Union, List

import discord
from discord.ext import commands
from discord import ui
import lavalink

from core.config import config
from core.database import db
from ui.embeds import ZenithEmbed
from ui.colors import Color
from core.logging import info, warn, error


FORBIDDEN_KEYWORDS = [
    "mashup", "mix", "medley", "slowed", "reverb", "lofi", "remix", 
    "cover", "bass boosted", "sped up", "speed up", "8d", "3d", 
    "nightcore", "edit", "flip", "bootleg", "club mix",
    "nonstop", "non stop", "non-stop", "1 hour", "1hr", "1 hr", "2 hour", "2hr",
    "3 hour", "10 hour", "jukebox", "full album", "compilation", "all songs",
    "audio jukebox", "video jukebox", "mega mix", "megamix", "hits collection",
    "best of", "greatest hits", "vol 1", "vol. 1", "vol 2", "vol. 2", "vol 3", "vol. 3",
    "non stop songs", "top songs collection", "continuous", "continuous mix"
]


def clean_track_title(title: str) -> str:
    title = re.sub(r"[\(\[\{].*?[\)\]\}]", "", title)
    junk_patterns = r"(?i)\b(official|video|lyric|lyrics|audio|hd|4k|full song|mv|music video)\b"
    title = re.sub(junk_patterns, "", title)
    title = re.sub(r"[-_]", " ", title)
    return " ".join(title.split()).strip()


def extract_youtube_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = re.search(
        r"(?:youtube\.com/(?:[^/\n\s]+/\S+/|(?:v|e(?:mbed)?)/|\S*?[?&]v=)|youtu\.be/)([a-zA-Z0-9_-]{11})",
        url,
    )
    return match.group(1) if match else None


def normalize_title(title: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", "", title.lower()).split()) if title else ""


def get_core_title(title: str) -> str:
    if not title:
        return ""
    t = re.split(r"[\(\[\-\|]|(?:\b(?:feat|ft|from)\b)", title, flags=re.IGNORECASE)[0]
    t = re.sub(r"[^a-zA-Z0-9\s]", "", t).strip().lower()
    return t


def is_unwanted_track(title: str) -> bool:
    title_lower = title.lower()
    return any(word in title_lower for word in FORBIDDEN_KEYWORDS)


def format_duration(ms: int) -> str:
    secs = max(0, int(ms / 1000))
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def parse_seek_time(time_str: str, current_pos_ms: int = 0) -> Optional[int]:
    time_str = time_str.strip().lower()
    if not time_str:
        return None
    is_relative_plus = time_str.startswith("+")
    is_relative_minus = time_str.startswith("-")
    clean_str = time_str.lstrip("+-")

    if ":" in clean_str:
        parts = clean_str.split(":")
        try:
            if len(parts) == 2:
                mins, secs = int(parts[0]), int(parts[1])
                target_ms = (mins * 60 + secs) * 1000
            elif len(parts) == 3:
                hrs, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
                target_ms = (hrs * 3600 + mins * 60 + secs) * 1000
            else:
                return None
        except ValueError:
            return None
    else:
        match = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$", clean_str)
        if match and any(match.groups()):
            hrs = int(match.group(1) or 0)
            mins = int(match.group(2) or 0)
            secs = int(match.group(3) or 0)
            target_ms = (hrs * 3600 + mins * 60 + secs) * 1000
        else:
            try:
                target_ms = int(clean_str) * 1000
            except ValueError:
                return None

    if is_relative_plus:
        return current_pos_ms + target_ms
    elif is_relative_minus:
        return current_pos_ms - target_ms
    return target_ms


class LavalinkVoiceClient(discord.VoiceClient):
    """Voice client router passing Discord voice state updates to Lavalink."""

    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        self.client = client
        self.channel = channel
        self.lavalink = self.client.lavalink

    async def on_voice_server_update(self, data):
        lavalink_data = {"t": "VOICE_SERVER_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def on_voice_state_update(self, data):
        lavalink_data = {"t": "VOICE_STATE_UPDATE", "d": data}
        await self.lavalink.voice_update_handler(lavalink_data)

    async def connect(self, *, timeout: float = 10.0, reconnect: bool = True, self_deaf: bool = True, self_mute: bool = False) -> None:
        self.lavalink.player_manager.create(guild_id=self.channel.guild.id)
        await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)

    async def disconnect(self, *, force: bool = False) -> None:
        player = self.lavalink.player_manager.get(self.channel.guild.id)
        if not force and player and not player.is_connected:
            return
        await self.channel.guild.change_voice_state(channel=None)
        if player:
            player.channel_id = None
        self.cleanup()


class MusicController(ui.View):
    """Interactive control view displayed under active playback."""

    def __init__(self, player: lavalink.DefaultPlayer, bot: commands.Bot):
        super().__init__(timeout=None)
        self.player = player
        self.bot = bot
        self._update_button_states()

    def _update_button_states(self):
        self.play_pause_button.label = "Resume" if self.player.paused else "Pause"
        self.loop_button.style = discord.ButtonStyle.primary if self.player.loop > 0 else discord.ButtonStyle.secondary
        self.autoplay_button.style = discord.ButtonStyle.primary if self.player.fetch("autoplay", False) else discord.ButtonStyle.secondary
        self.shuffle_button.style = discord.ButtonStyle.primary if getattr(self.player, "shuffle", False) else discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        if not guild or not guild.voice_client:
            await interaction.response.send_message(embed=ZenithEmbed.error("Not Connected", "I am not connected to a voice channel."), ephemeral=True)
            return False
        if not interaction.user.voice or interaction.user.voice.channel.id != guild.voice_client.channel.id:
            await interaction.response.send_message(embed=ZenithEmbed.error("Voice Mismatch", f"You must be in {guild.voice_client.channel.mention} to use controls."), ephemeral=True)
            return False
        return True

    @ui.button(label="Restart", style=discord.ButtonStyle.secondary, row=0)
    async def restart_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.player.seek(0)
        await interaction.response.send_message(embed=ZenithEmbed.success("Track Restarted", "Restarted playback from beginning."), ephemeral=True)

    @ui.button(label="Pause", style=discord.ButtonStyle.primary, row=0)
    async def play_pause_button(self, interaction: discord.Interaction, button: ui.Button):
        new_state = not self.player.paused
        await self.player.set_pause(new_state)
        self._update_button_states()
        await interaction.response.edit_message(view=self)

    @ui.button(label="Skip", style=discord.ButtonStyle.secondary, row=0)
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.player.skip()
        await interaction.response.send_message(embed=ZenithEmbed.success("Track Skipped", "Skipped to next track."), ephemeral=True)

    @ui.button(label="Stop", style=discord.ButtonStyle.danger, row=0)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        self.player.queue.clear()
        await self.player.stop()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect(force=True)
        await interaction.response.send_message(embed=ZenithEmbed.info("Playback Stopped", "Cleared queue and left voice channel."), ephemeral=True)

    @ui.button(label="Queue", style=discord.ButtonStyle.secondary, row=1)
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player.queue:
            return await interaction.response.send_message(embed=ZenithEmbed.info("Queue Empty", "No upcoming tracks in the queue."), ephemeral=True)
        
        lines = [f"`{idx + 1}.` **[{t.title}]({t.uri})** ({format_duration(t.duration)})" for idx, t in enumerate(self.player.queue[:10])]
        if len(self.player.queue) > 10:
            lines.append(f"*...and {len(self.player.queue) - 10} more tracks.*")

        embed = ZenithEmbed(title="Current Queue", description="\n".join(lines), color=Color.PRIMARY)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="Loop", style=discord.ButtonStyle.secondary, row=1)
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        # 0 = Off, 1 = Single Track, 2 = Queue
        new_loop = (self.player.loop + 1) % 3
        self.player.set_loop(new_loop)
        self._update_button_states()
        mode_text = "Off" if new_loop == 0 else "Current Track" if new_loop == 1 else "Queue"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=ZenithEmbed.info("Loop Updated", f"Loop mode set to **{mode_text}**."), ephemeral=True)

    @ui.button(label="Autoplay", style=discord.ButtonStyle.secondary, row=1)
    async def autoplay_button(self, interaction: discord.Interaction, button: ui.Button):
        state = self.player.fetch("autoplay", False)
        new_state = not state
        self.player.store("autoplay", new_state)
        self._update_button_states()
        await interaction.response.edit_message(view=self)
        status_text = "Enabled" if new_state else "Disabled"
        await interaction.followup.send(embed=ZenithEmbed.info("Autoplay", f"Autoplay recommendation is now **{status_text}**."), ephemeral=True)

    @ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.player.queue:
            return await interaction.response.send_message(embed=ZenithEmbed.error("Queue Empty", "No tracks to shuffle."), ephemeral=True)
        random.shuffle(self.player.queue)
        await interaction.response.send_message(embed=ZenithEmbed.success("Queue Shuffled", f"Randomized order of **{len(self.player.queue)}** tracks."), ephemeral=True)


class Music(commands.Cog):
    """Audio streaming system with Lavalink integration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Initialize Lavalink client if not already attached
        if not hasattr(bot, "lavalink"):
            bot.lavalink = lavalink.Client(bot.user.id if bot.user else 0)
            uri = config.LAVALINK_URI
            password = config.LAVALINK_PASSWORD
            host = uri.replace("https://", "").replace("http://", "")
            port = 443 if uri.startswith("https") else 2333
            if ":" in host:
                parts = host.split(":")
                host = parts[0]
                port = int(parts[1])
            ssl = uri.startswith("https")

            bot.lavalink.add_node(host, port, password, "eu", "default-node", ssl=ssl)
            bot.add_listener(bot.lavalink.voice_update_handler, "on_socket_response")
            bot.lavalink.add_event_hook(self.track_hook)

    async def track_hook(self, event):
        """Dispatches automated playback flow (track start, end, autoplay)."""
        if isinstance(event, lavalink.events.TrackStartEvent):
            player = event.player
            channel_id = player.fetch("channel")
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    track = event.track
                    length = format_duration(track.duration) if not track.stream else "LIVE"
                    requester_id = track.requester
                    embed = ZenithEmbed(
                        title="Now Playing",
                        description=f"**[{track.title}]({track.uri})**\n\nAuthor: `{track.author}`\nDuration: `{length}`\nRequester: <@{requester_id}>",
                        color=Color.PRIMARY
                    )
                    if getattr(track, "artwork_url", None):
                        embed.set_thumbnail(url=track.artwork_url)
                    view = MusicController(player, self.bot)
                    await channel.send(embed=embed, view=view)

        elif isinstance(event, lavalink.events.TrackEndEvent):
            player = event.player
            # Check if queue has finished and autoplay is enabled
            if not player.queue and player.fetch("autoplay", False):
                next_track = await self.get_autoplay_track(player, event.track)
                if next_track:
                    player.add(requester=self.bot.user.id, track=next_track)
                    await player.play()

    async def get_autoplay_track(self, player: lavalink.DefaultPlayer, last_track: lavalink.AudioTrack) -> Optional[lavalink.AudioTrack]:
        """Calculates the optimal related song recommendation based on seed track and artist mix."""
        if not last_track:
            return None

        title = getattr(last_track, "title", "") or ""
        author = getattr(last_track, "author", "") or ""
        source_name = (getattr(last_track, "source_name", "") or "").lower()
        source_uri = getattr(last_track, "uri", "") or ""
        identifier = getattr(last_track, "identifier", "") or ""
        recommended = []

        # 1. Resolve YouTube ID for native YouTube Radio RD mix
        video_id = None
        if source_name == "youtube" and identifier and len(identifier) == 11:
            video_id = identifier
        elif source_name == "youtube":
            video_id = extract_youtube_id(source_uri)

        clean_author = author.strip() if author else ""
        c_seed_query = get_core_title(title) if title else ""

        # 2. Concurrently query radio mix and artist fallback
        fetch_tasks = []
        if video_id:
            radio_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            fetch_tasks.append(asyncio.wait_for(player.node.get_tracks(radio_url), timeout=3.5))

        if clean_author:
            fetch_tasks.append(asyncio.wait_for(player.node.get_tracks(f"ytsearch:{clean_author} songs"), timeout=2.5))
        elif c_seed_query:
            fetch_tasks.append(asyncio.wait_for(player.node.get_tracks(f"ytsearch:{c_seed_query} songs"), timeout=2.5))

        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception) or not res or not getattr(res, "tracks", None):
                continue
            recommended.extend(res.tracks)

        if not recommended:
            return None

        history_ids = set(player.fetch("autoplay_history", []) or [])
        history_titles = set(player.fetch("autoplay_history_titles", []) or [])

        if last_track:
            last_id = getattr(last_track, "identifier", None)
            if last_id:
                history_ids.add(last_id)
            c_seed = get_core_title(getattr(last_track, "title", ""))
            if c_seed:
                history_titles.add(c_seed)

        queued_ids = {t.identifier for t in player.queue if getattr(t, "identifier", None)}
        current_title_norm = normalize_title(title).lower()
        core_seed = get_core_title(title)

        candidates = []
        seen = set()

        for track in recommended:
            t_id = getattr(track, "identifier", None)
            t_title = getattr(track, "title", "") or ""
            t_norm = normalize_title(t_title).lower()
            core_cand = get_core_title(t_title)

            if not t_id or t_id in seen:
                continue
            seen.add(t_id)

            if t_id in history_ids or t_id in queued_ids:
                continue
            if core_cand and core_cand in history_titles:
                continue
            if is_unwanted_track(t_title):
                continue

            # Length bounds: 45s to 9m
            t_duration = getattr(track, "duration", 0) or 0
            if t_duration > 9 * 60 * 1000 or (t_duration > 0 and t_duration < 45 * 1000):
                continue

            if t_norm == current_title_norm:
                continue
            if core_seed and len(core_seed) >= 3 and core_seed == core_cand:
                continue

            candidates.append(track)

        if not candidates:
            return None

        # Pick random top candidate to prevent looping
        selected = candidates[0] if len(candidates) <= 2 else random.choice(candidates[:min(6, len(candidates))])
        history_ids.add(selected.identifier)
        player.store("autoplay_history", list(history_ids)[-50:])
        sel_core = get_core_title(selected.title)
        if sel_core:
            history_titles.add(sel_core)
            player.store("autoplay_history_titles", list(history_titles)[-50:])
        return selected

    async def _ensure_voice(self, ctx: commands.Context) -> bool:
        """Verifies voice channel connection prerequisites."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(embed=ZenithEmbed.error("Not Connected", "Join a voice channel before playing audio."), mention_author=False)
            return False

        if not ctx.guild.voice_client:
            permissions = ctx.author.voice.channel.permissions_for(ctx.guild.me)
            if not permissions.connect or not permissions.speak:
                await ctx.reply(embed=ZenithEmbed.error("Missing Permissions", "I require `Connect` and `Speak` permissions in your voice channel."), mention_author=False)
                return False
            await ctx.author.voice.channel.connect(cls=LavalinkVoiceClient)
        elif ctx.guild.voice_client.channel.id != ctx.author.voice.channel.id:
            await ctx.reply(embed=ZenithEmbed.error("Voice Mismatch", f"You must be in {ctx.guild.voice_client.channel.mention}."), mention_author=False)
            return False

        return True

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx: commands.Context, *, query: str):
        """Searches and queues a song or playlist."""
        if not await self._ensure_voice(ctx):
            return

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.store("channel", ctx.channel.id)

        clean_query = query.strip("<>")
        if not clean_query.startswith("http"):
            search_query = f"ytsearch:{clean_query}"
        else:
            search_query = clean_query

        results = await player.node.get_tracks(search_query)

        if not results or not results.tracks:
            # Fallback search via Deezer if YouTube query yields empty
            if not clean_query.startswith("http"):
                results = await player.node.get_tracks(f"dzsearch:{clean_query}")

        if not results or not results.tracks:
            return await ctx.reply(embed=ZenithEmbed.error("No Results", f"Could not find any tracks matching `{query}`."), mention_author=False)

        if results.load_type == "PLAYLIST_LOADED":
            tracks = results.tracks
            for t in tracks:
                player.add(requester=ctx.author.id, track=t)
            embed = ZenithEmbed.success("Playlist Queued", f"Enqueued **{len(tracks)}** tracks from playlist **{results.playlist_info.name}**.")
            await ctx.reply(embed=embed, mention_author=False)
        else:
            track = results.tracks[0]
            player.add(requester=ctx.author.id, track=track)
            if not player.is_playing:
                embed = ZenithEmbed.success("Starting Playback", f"Loading **[{track.title}]({track.uri})** ({format_duration(track.duration)}).")
            else:
                embed = ZenithEmbed.success("Track Queued", f"Enqueued **[{track.title}]({track.uri})** at position `#{len(player.queue)}`.")
            await ctx.reply(embed=embed, mention_author=False)

        if not player.is_playing:
            await player.play()

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip_command(self, ctx: commands.Context):
        """Skips the active song."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.reply(embed=ZenithEmbed.error("Nothing Playing", "No audio track is currently active."), mention_author=False)
        await player.skip()
        await ctx.reply(embed=ZenithEmbed.success("Track Skipped", "Proceeding to next track in queue."), mention_author=False)

    @commands.command(name="pause")
    async def pause_command(self, ctx: commands.Context):
        """Pauses audio playback."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.reply(embed=ZenithEmbed.error("Nothing Playing", "No audio track is currently active."), mention_author=False)
        await player.set_pause(True)
        await ctx.reply(embed=ZenithEmbed.info("Paused", "Audio stream paused."), mention_author=False)

    @commands.command(name="resume")
    async def resume_command(self, ctx: commands.Context):
        """Resumes paused audio playback."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.is_playing:
            return await ctx.reply(embed=ZenithEmbed.error("Nothing Playing", "No audio track is currently active."), mention_author=False)
        await player.set_pause(False)
        await ctx.reply(embed=ZenithEmbed.info("Resumed", "Audio stream resumed."), mention_author=False)

    @commands.command(name="stop", aliases=["leave", "dc", "disconnect"])
    async def stop_command(self, ctx: commands.Context):
        """Stops playback, clears queue, and leaves voice channel."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if player:
            player.queue.clear()
            await player.stop()
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)
        await ctx.reply(embed=ZenithEmbed.info("Disconnected", "Playback stopped and voice session ended."), mention_author=False)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying_command(self, ctx: commands.Context):
        """Displays information on the current track."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.current:
            return await ctx.reply(embed=ZenithEmbed.info("Nothing Playing", "No track is currently playing."), mention_author=False)

        track = player.current
        position = format_duration(player.position)
        total = format_duration(track.duration) if not track.stream else "LIVE"

        embed = ZenithEmbed(
            title="Now Playing",
            description=f"**[{track.title}]({track.uri})**\n\nAuthor: `{track.author}`\nProgress: `{position} / {total}`\nRequester: <@{track.requester}>",
            color=Color.PRIMARY
        )
        if getattr(track, "artwork_url", None):
            embed.set_thumbnail(url=track.artwork_url)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="queue", aliases=["q"])
    async def queue_command(self, ctx: commands.Context):
        """Lists pending songs in queue."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.queue:
            return await ctx.reply(embed=ZenithEmbed.info("Queue Empty", "No tracks waiting in queue."), mention_author=False)

        lines = [f"`{i + 1}.` **[{t.title}]({t.uri})** ({format_duration(t.duration)})" for i, t in enumerate(player.queue[:15])]
        if len(player.queue) > 15:
            lines.append(f"*...and {len(player.queue) - 15} more tracks.*")

        embed = ZenithEmbed(
            title=f"Server Queue [{len(player.queue)} tracks]",
            description="\n".join(lines),
            color=Color.PRIMARY
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="autoplay", aliases=["ap"])
    async def autoplay_command(self, ctx: commands.Context):
        """Toggles automated song recommendations when queue finishes."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.reply(embed=ZenithEmbed.error("Not Connected", "No active audio player found."), mention_author=False)

        state = player.fetch("autoplay", False)
        new_state = not state
        player.store("autoplay", new_state)

        status_text = "Enabled" if new_state else "Disabled"
        await ctx.reply(embed=ZenithEmbed.success("Autoplay", f"Continuous recommendation stream is now **{status_text}**."), mention_author=False)

    @commands.command(name="volume", aliases=["vol"])
    async def volume_command(self, ctx: commands.Context, volume: int):
        """Sets playback volume level (0-100)."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player:
            return await ctx.reply(embed=ZenithEmbed.error("Not Connected", "No active player found."), mention_author=False)

        if volume < 0 or volume > 100:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Range", "Volume must be set between 0 and 100."), mention_author=False)

        await player.set_volume(volume)
        await ctx.reply(embed=ZenithEmbed.success("Volume Adjusted", f"Output volume set to **{volume}%**."), mention_author=False)

    @commands.command(name="seek")
    async def seek_command(self, ctx: commands.Context, time_str: str):
        """Seeks to a timestamp in current track (e.g. `1:30`, `+30`, `-15`)."""
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if not player or not player.current:
            return await ctx.reply(embed=ZenithEmbed.error("Nothing Playing", "No active audio track."), mention_author=False)

        target_ms = parse_seek_time(time_str, player.position)
        if target_ms is None or target_ms < 0 or target_ms > player.current.duration:
            return await ctx.reply(embed=ZenithEmbed.error("Invalid Timestamp", "Please provide a valid position (e.g. `1:30`, `+30s`)."), mention_author=False)

        await player.seek(target_ms)
        await ctx.reply(embed=ZenithEmbed.success("Position Updated", f"Seeked to `{format_duration(target_ms)}`."), mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
