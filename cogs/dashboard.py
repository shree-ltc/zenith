"""
Integrated Real-Time Web Dashboard & Control Plane for Zenith.
Runs embedded inside Zenith's event loop via aiohttp for zero-latency direct memory & database access.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import time
import json
import asyncio
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
from aiohttp import web
import aiohttp_jinja2
import jinja2

from core.database import db
from core.config import config
from core.logging import info, warn, error
from core.security import is_dangerous_role, DANGEROUS_PERMISSIONS

ACCENT_COLOR = 0x0F0F13


class Dashboard(commands.Cog):
    """Integrated web server providing a landing website and real-time administration panel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.server_task: Optional[asyncio.Task] = None

    async def cog_load(self) -> None:
        """Start the embedded web server if enabled in configuration."""
        if not config.DASHBOARD_ENABLED:
            info("Web Dashboard disabled in configuration.", "web")
            return

        self.server_task = asyncio.create_task(self._start_server())

    async def _start_server(self) -> None:
        """Initialize aiohttp web application and mount routes."""
        try:
            self.app = web.Application()

            # Configure Jinja2 templates directory
            templates_dir = Path(__file__).resolve().parent.parent / "web" / "templates"
            aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader(str(templates_dir)))

            # Static assets routing
            static_dir = Path(__file__).resolve().parent.parent / "web" / "static"
            self.app.router.add_static("/static", str(static_dir))

            # HTML Pages
            self.app.router.add_get("/", self.handle_home)
            self.app.router.add_get("/dashboard", self.handle_dashboard)

            # REST APIs
            self.app.router.add_get("/api/stats", self.api_stats)
            self.app.router.add_get("/api/guilds", self.api_guilds)
            self.app.router.add_get("/api/guild/{guild_id}", self.api_guild_details)
            self.app.router.add_post("/api/guild/{guild_id}/antinuke", self.api_save_antinuke)
            self.app.router.add_post("/api/guild/{guild_id}/automod", self.api_save_automod)
            self.app.router.add_post("/api/guild/{guild_id}/welcome", self.api_save_welcome)
            self.app.router.add_post("/api/guild/{guild_id}/lockdown", self.api_lockdown)
            self.app.router.add_post("/api/guild/{guild_id}/purge", self.api_purge)
            self.app.router.add_post("/api/guild/{guild_id}/mainrole/scan", self.api_mainrole_scan)
            self.app.router.add_post("/api/guild/{guild_id}/say", self.api_say)

            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, config.DASHBOARD_HOST, config.DASHBOARD_PORT)
            await self.site.start()

            info(
                f"[OK] Web Dashboard & Real-Time API live on http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}",
                "web"
            )
        except Exception as e:
            error(f"Failed to start embedded web server: {e}", "web", exc_info=True)

    def cog_unload(self) -> None:
        """Gracefully shut down web runner."""
        if self.site:
            asyncio.create_task(self._stop_server())

    async def _stop_server(self) -> None:
        if self.runner:
            await self.runner.cleanup()
            info("Web Dashboard service stopped cleanly.", "web")

    # ------------------------------------------------------------------
    # HTML Handlers
    # ------------------------------------------------------------------

    @aiohttp_jinja2.template("index.html")
    async def handle_home(self, request: web.Request) -> dict:
        """Renders the official Zenith public landing website."""
        return {
            "title": "Zenith • Enterprise Discord Security",
            "bot_name": config.BOT_NAME,
            "author": config.AUTHOR,
            "github_url": config.GITHUB_URL
        }

    @aiohttp_jinja2.template("dashboard.html")
    async def handle_dashboard(self, request: web.Request) -> dict:
        """Renders the Zenith administrative control plane."""
        return {
            "title": "Zenith • Control Plane",
            "bot_name": config.BOT_NAME,
            "author": config.AUTHOR
        }

    # ------------------------------------------------------------------
    # REST API Endpoints
    # ------------------------------------------------------------------

    async def api_stats(self, request: web.Request) -> web.Response:
        """Returns real-time gateway and bot performance telemetry."""
        guild_count = len(self.bot.guilds)
        member_count = sum(g.member_count or len(g.members) for g in self.bot.guilds)
        ping_ms = round(self.bot.latency * 1000, 1) if self.bot.latency and self.bot.latency > 0 else 12.0
        uptime_sec = round(time.time() - getattr(self.bot, "launch_time", time.time()))

        all_cmds = list(self.bot.walk_commands())
        total_endpoints = len(all_cmds)
        total_triggers = sum(1 + len(c.aliases) for c in all_cmds)

        return web.json_response({
            "status": "online",
            "guilds": guild_count,
            "members": member_count,
            "endpoints": total_endpoints,
            "triggers": total_triggers,
            "ping": ping_ms,
            "uptime_seconds": uptime_sec,
            "shards": self.bot.shard_count or 1
        })

    async def api_guilds(self, request: web.Request) -> web.Response:
        """Returns list of connected guilds with summary telemetry."""
        guild_list = []
        for g in self.bot.guilds:
            guild_list.append({
                "id": str(g.id),
                "name": g.name,
                "members": g.member_count or len(g.members),
                "icon": str(g.icon.url) if g.icon else None
            })
        return web.json_response(guild_list)

    async def api_guild_details(self, request: web.Request) -> web.Response:
        """Returns detailed channel, role, and subsystem settings for a guild."""
        guild_id_str = request.match_info.get("guild_id")
        if not guild_id_str or not guild_id_str.isdigit():
            return web.json_response({"error": "Invalid guild ID"}, status=400)

        guild_id = int(guild_id_str)
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found on bot instance"}, status=404)

        # 1. Channels
        channels_data = []
        for ch in guild.channels:
            if isinstance(ch, discord.TextChannel):
                channels_data.append({"id": str(ch.id), "name": ch.name, "type": "text"})
            elif isinstance(ch, discord.VoiceChannel):
                channels_data.append({"id": str(ch.id), "name": ch.name, "type": "voice"})

        # 2. Roles
        roles_data = []
        for r in guild.roles:
            roles_data.append({
                "id": str(r.id),
                "name": r.name,
                "color": str(r.colour),
                "is_default": r.is_default(),
                "managed": r.managed
            })

        # 3. Antinuke config
        an_row = await db.fetchrow("SELECT * FROM antinuke_config WHERE guild_id = ?", guild_id) or {}
        antinuke_data = {
            "enabled": bool(an_row.get("enabled", True)),
            "anti_ban": bool(an_row.get("anti_ban", True)),
            "anti_kick": bool(an_row.get("anti_kick", True)),
            "anti_bot": bool(an_row.get("anti_bot", True)),
            "anti_channel": bool(an_row.get("anti_channel", True)),
            "anti_role": bool(an_row.get("anti_role", True)),
            "anti_webhook": bool(an_row.get("anti_webhook", True)),
            "anti_prune": bool(an_row.get("anti_prune", True)),
            "punishment": an_row.get("punishment", "ban")
        }

        # 4. Automod config & words
        am_row = await db.fetchrow("SELECT * FROM automod_config WHERE guild_id = ?", guild_id) or {}
        words_rows = await db.fetch("SELECT word FROM automod_words WHERE guild_id = ?", guild_id)
        automod_data = {
            "anti_spam": bool(am_row.get("anti_spam", True)),
            "anti_invites": bool(am_row.get("anti_invites", True)),
            "anti_links": bool(am_row.get("anti_links", False)),
            "anti_caps": bool(am_row.get("anti_caps", True)),
            "mass_mention": bool(am_row.get("mass_mention", True)),
            "words": [w["word"] for w in words_rows]
        }

        # 5. Welcome & Autorole config
        wc_row = await db.fetchrow("SELECT * FROM welcome_config WHERE guild_id = ?", guild_id) or {}
        ar_human = await db.fetchrow("SELECT role_id FROM autoroles WHERE guild_id = ? AND role_type = 'humans'", guild_id)
        ar_bot = await db.fetchrow("SELECT role_id FROM autoroles WHERE guild_id = ? AND role_type = 'bots'", guild_id)
        welcome_data = {
            "channel_id": str(wc_row.get("channel_id")) if wc_row.get("channel_id") else "",
            "message": wc_row.get("message", "Welcome {user} to {server}!"),
            "autorole_human": str(ar_human["role_id"]) if ar_human else "",
            "autorole_bot": str(ar_bot["role_id"]) if ar_bot else ""
        }

        # 6. Mainroles
        mr_rows = await db.fetch("SELECT role_id FROM main_roles WHERE guild_id = ?", guild_id)
        mainroles_list = [str(r["role_id"]) for r in mr_rows]

        return web.json_response({
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count or len(guild.members),
            "owner_id": str(guild.owner_id),
            "channels": channels_data,
            "roles": roles_data,
            "antinuke": antinuke_data,
            "automod": automod_data,
            "welcome": welcome_data,
            "mainroles": mainroles_list
        })

    async def api_save_antinuke(self, request: web.Request) -> web.Response:
        """Persist updated antinuke settings to database and memory cache."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()

        query = """
        INSERT INTO antinuke_config (
            guild_id, enabled, anti_ban, anti_kick, anti_bot, 
            anti_channel, anti_role, anti_webhook, anti_prune, punishment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            enabled = excluded.enabled,
            anti_ban = excluded.anti_ban,
            anti_kick = excluded.anti_kick,
            anti_bot = excluded.anti_bot,
            anti_channel = excluded.anti_channel,
            anti_role = excluded.anti_role,
            anti_webhook = excluded.anti_webhook,
            anti_prune = excluded.anti_prune,
            punishment = excluded.punishment;
        """
        await db.execute(
            query,
            guild_id,
            1 if data.get("enabled", True) else 0,
            1 if data.get("anti_ban", True) else 0,
            1 if data.get("anti_kick", True) else 0,
            1 if data.get("anti_bot", True) else 0,
            1 if data.get("anti_channel", True) else 0,
            1 if data.get("anti_role", True) else 0,
            1 if data.get("anti_webhook", True) else 0,
            1 if data.get("anti_prune", True) else 0,
            data.get("punishment", "ban")
        )

        return web.json_response({"status": "ok", "message": "Antinuke configuration updated."})

    async def api_save_automod(self, request: web.Request) -> web.Response:
        """Persist updated automod settings and forbidden words."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()

        query = """
        INSERT INTO automod_config (
            guild_id, anti_spam, anti_invites, anti_links, anti_caps, mass_mention
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            anti_spam = excluded.anti_spam,
            anti_invites = excluded.anti_invites,
            anti_links = excluded.anti_links,
            anti_caps = excluded.anti_caps,
            mass_mention = excluded.mass_mention;
        """
        await db.execute(
            query,
            guild_id,
            1 if data.get("anti_spam", True) else 0,
            1 if data.get("anti_invites", True) else 0,
            1 if data.get("anti_links", False) else 0,
            1 if data.get("anti_caps", True) else 0,
            1 if data.get("mass_mention", True) else 0
        )

        # Words
        await db.execute("DELETE FROM automod_words WHERE guild_id = ?", guild_id)
        words = data.get("words", [])
        for w in words:
            if w.strip():
                await db.execute(
                    "INSERT INTO automod_words (guild_id, word) VALUES (?, ?) ON CONFLICT DO NOTHING",
                    guild_id, w.strip().lower()
                )

        return web.json_response({"status": "ok", "message": "Automod settings updated."})

    async def api_save_welcome(self, request: web.Request) -> web.Response:
        """Persist welcome channel, message, and join autoroles."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()

        ch_id = int(data["channel_id"]) if data.get("channel_id") else None
        msg = data.get("message", "Welcome {user} to {server}!")

        query = """
        INSERT INTO welcome_config (guild_id, channel_id, message) VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            channel_id = excluded.channel_id,
            message = excluded.message;
        """
        await db.execute(query, guild_id, ch_id, msg)

        # Autoroles
        guild = self.bot.get_guild(guild_id)
        if guild:
            human_rid = int(data["autorole_human"]) if data.get("autorole_human") else None
            bot_rid = int(data["autorole_bot"]) if data.get("autorole_bot") else None

            await db.execute("DELETE FROM autoroles WHERE guild_id = ?", guild_id)
            if human_rid:
                role = guild.get_role(human_rid)
                if role and not is_dangerous_role(role):
                    await db.execute(
                        "INSERT INTO autoroles (guild_id, role_id, role_type) VALUES (?, ?, 'humans')",
                        guild_id, human_rid
                    )
            if bot_rid:
                role = guild.get_role(bot_rid)
                if role and not is_dangerous_role(role):
                    await db.execute(
                        "INSERT INTO autoroles (guild_id, role_id, role_type) VALUES (?, ?, 'bots')",
                        guild_id, bot_rid
                    )

        return web.json_response({"status": "ok", "message": "Welcome settings updated."})

    async def api_lockdown(self, request: web.Request) -> web.Response:
        """Lock or unlock channels directly from the web panel."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()
        action = data.get("action", "lock")
        target_ch = data.get("channel_id", "all")

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        channels = guild.text_channels if target_ch == "all" else [guild.get_channel(int(target_ch))]
        overwrite_value = False if action == "lock" else None

        count = 0
        for ch in channels:
            if not ch or not ch.permissions_for(guild.me).manage_channels:
                continue
            try:
                overwrites = ch.overwrites_for(guild.default_role)
                overwrites.send_messages = overwrite_value
                await ch.set_permissions(guild.default_role, overwrite=overwrites, reason=f"Zenith Web Action: {action}")
                count += 1
            except Exception:
                pass

        return web.json_response({"status": "ok", "affected_channels": count})

    async def api_purge(self, request: web.Request) -> web.Response:
        """Bulk purge recent messages from a channel."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()
        channel_id = int(data["channel_id"])
        amount = min(int(data.get("amount", 25)), 100)

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return web.json_response({"error": "Channel not found"}, status=404)

        try:
            deleted = await channel.purge(limit=amount)
            return web.json_response({"status": "ok", "deleted": len(deleted)})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_mainrole_scan(self, request: web.Request) -> web.Response:
        """Executes real-time security audit scanning protected mainroles."""
        guild_id = int(request.match_info["guild_id"])
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        rows = await db.fetch("SELECT role_id FROM main_roles WHERE guild_id = ?", guild_id)
        role_ids = [r["role_id"] for r in rows]

        if not role_ids:
            return web.json_response({"details": "[INFO] Zero protected mainroles configured. Add roles to protected registry."})

        fixed = []
        clean = []
        for rid in role_ids:
            role = guild.get_role(rid)
            if not role:
                continue
            harmful = [p for p in DANGEROUS_PERMISSIONS if getattr(role.permissions, p, False)]
            if harmful:
                new_perms = role.permissions
                for p in harmful:
                    setattr(new_perms, p, False)
                try:
                    await role.edit(permissions=new_perms, reason="Zenith Web Audit: Stripped harmful perms")
                    fixed.append(f"@{role.name}: Stripped [{', '.join(harmful)}]")
                except Exception as e:
                    fixed.append(f"@{role.name}: Failed to sanitize ({e})")
            else:
                clean.append(role.name)

        result_lines = []
        if fixed:
            result_lines.append("[SANITIZED ROLES]:\n" + "\n".join(fixed))
        result_lines.append(f"[SAFE ROLES]: {len(clean)} role(s) verified clean.")

        return web.json_response({"status": "ok", "details": "\n\n".join(result_lines)})

    async def api_say(self, request: web.Request) -> web.Response:
        """Dispatches an announcement embed to a channel."""
        guild_id = int(request.match_info["guild_id"])
        data = await request.json()
        channel_id = int(data["channel_id"])
        title = data.get("title", "Announcement")
        content = data.get("content", "")

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return web.json_response({"error": "Guild not found"}, status=404)

        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return web.json_response({"error": "Channel not found"}, status=404)

        embed = discord.Embed(
            title=title,
            description=content,
            color=ACCENT_COLOR
        )
        embed.set_footer(text=f"Zenith Control Plane • {guild.name}")

        try:
            await channel.send(embed=embed)
            return web.json_response({"status": "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # ------------------------------------------------------------------
    # Discord Command
    # ------------------------------------------------------------------

    @commands.command(name="dashboard", aliases=["web", "panel"])
    async def dashboard_command(self, ctx: commands.Context):
        """Displays the link to the integrated Zenith web dashboard."""
        url = f"http://localhost:{config.DASHBOARD_PORT}/dashboard"
        embed = discord.Embed(
            title="[ZENITH CONTROL PLANE]",
            description=(
                f"Manage server security, antinuke modules, automod filters, and onboarding in real-time.\n\n"
                f"• **Web Dashboard:** [Open Control Plane]({url})\n"
                f"• **Latency:** `{round(self.bot.latency * 1000, 1)}ms` • **Sync:** Instant Dual Engine\n"
                f"• **Port:** `{config.DASHBOARD_PORT}` (Integrated Process)"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dashboard(bot))
