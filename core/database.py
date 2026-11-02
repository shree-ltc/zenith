"""
Database abstraction layer.
Uses PostgreSQL and Redis when configured, falling back to SQLite and local cache.
"""

import time
import asyncio
from pathlib import Path
from typing import Any, Optional

import asyncpg
import aiosqlite
import redis.asyncio as aioredis

from core.config import config
from core.logging import info, warn, error, success


class InMemoryCache:
    """Thread-safe in-memory cache with TTL expiration fallback when Redis isn't hosted."""

    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._store:
                return None
            val, expiry = self._store[key]
            if expiry and time.monotonic() > expiry:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        async with self._lock:
            expiry = time.monotonic() + ex if ex else None
            self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return (await self.get(key)) is not None


class Database:
    """Unified database manager abstracting Postgres and SQLite."""

    def __init__(self):
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.sqlite_conn: Optional[aiosqlite.Connection] = None
        self.redis: Optional[aioredis.Redis] = None
        self.memory_cache = InMemoryCache()
        self.is_postgres: bool = False

    async def initialize(self) -> None:
        """Bootstraps database pools and cache clients."""
        # 1. Connect Cache (Redis or fallback)
        if config.REDIS_URL:
            try:
                client = aioredis.from_url(
                    config.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    retry_on_timeout=True
                )
                await client.ping()
                self.redis = client
                success("Connected to Redis cache layer", "database")
            except Exception as e:
                warn(f"Redis connection failed ({e}). Falling back to in-memory TTL cache.", "database")
                self.redis = None
        else:
            info("REDIS_URL not configured. Using local in-memory cache.", "database")

        # 2. Connect Storage (PostgreSQL or fallback to SQLite)
        if config.POSTGRES_URL:
            try:
                self.pg_pool = await asyncpg.create_pool(
                    config.POSTGRES_URL,
                    min_size=5,
                    max_size=20,
                    command_timeout=10
                )
                self.is_postgres = True
                success("Connected to PostgreSQL cluster", "database")
            except Exception as e:
                warn(f"PostgreSQL connection failed ({e}). Switching to local SQLite storage.", "database")
                self.is_postgres = False

        if not self.is_postgres:
            config.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.sqlite_conn = await aiosqlite.connect(config.SQLITE_PATH)
            self.sqlite_conn.row_factory = aiosqlite.Row
            success(f"Connected to local SQLite engine ({config.SQLITE_PATH.name})", "database")

        # 3. Create required tables if they don't exist
        await self._create_tables()

    async def _create_tables(self) -> None:
        """Executes table creation DDL across either PostgreSQL or SQLite."""
        queries = [
            # Guild prefix configuration
            """
            CREATE TABLE IF NOT EXISTS guild_prefixes (
                guild_id BIGINT PRIMARY KEY,
                prefix VARCHAR(10) NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Antinuke settings
            """
            CREATE TABLE IF NOT EXISTS antinuke_config (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                punishment VARCHAR(20) DEFAULT 'ban',
                log_channel BIGINT DEFAULT NULL,
                anti_ban BOOLEAN DEFAULT TRUE,
                anti_kick BOOLEAN DEFAULT TRUE,
                anti_channel BOOLEAN DEFAULT TRUE,
                anti_role BOOLEAN DEFAULT TRUE,
                anti_bot BOOLEAN DEFAULT TRUE,
                anti_webhook BOOLEAN DEFAULT TRUE
            );
            """,
            # Antinuke Whitelist (Extra owners & trusted admins)
            """
            CREATE TABLE IF NOT EXISTS antinuke_whitelist (
                guild_id BIGINT,
                user_id BIGINT,
                role VARCHAR(20) DEFAULT 'trusted',
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            # Automod settings
            """
            CREATE TABLE IF NOT EXISTS automod_config (
                guild_id BIGINT PRIMARY KEY,
                anti_spam BOOLEAN DEFAULT FALSE,
                anti_links BOOLEAN DEFAULT FALSE,
                anti_invites BOOLEAN DEFAULT FALSE,
                anti_caps BOOLEAN DEFAULT FALSE,
                anti_massmention BOOLEAN DEFAULT FALSE,
                mention_threshold INT DEFAULT 5,
                punishment VARCHAR(20) DEFAULT 'timeout'
            );
            """,
            # Ticket setup
            """
            CREATE TABLE IF NOT EXISTS ticket_panels (
                guild_id BIGINT,
                channel_id BIGINT,
                message_id BIGINT,
                category_id BIGINT,
                support_role_id BIGINT,
                panel_title VARCHAR(100),
                panel_desc TEXT,
                PRIMARY KEY (guild_id, message_id)
            );
            """,
            # Active tickets
            """
            CREATE TABLE IF NOT EXISTS active_tickets (
                ticket_channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_by BIGINT DEFAULT NULL
            );
            """,
            # Server logging channels
            """
            CREATE TABLE IF NOT EXISTS server_logs (
                guild_id BIGINT PRIMARY KEY,
                mod_logs BIGINT DEFAULT NULL,
                message_logs BIGINT DEFAULT NULL,
                member_logs BIGINT DEFAULT NULL,
                voice_logs BIGINT DEFAULT NULL,
                role_logs BIGINT DEFAULT NULL
            );
            """,
            # Welcome system
            """
            CREATE TABLE IF NOT EXISTS welcome_config (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                channel_id BIGINT DEFAULT NULL,
                message TEXT DEFAULT 'Welcome {user.mention} to {guild.name}!',
                autorole_human BIGINT DEFAULT NULL,
                autorole_bot BIGINT DEFAULT NULL,
                dm_welcome BOOLEAN DEFAULT FALSE
            );
            """,
            # AFK statuses
            """
            CREATE TABLE IF NOT EXISTS afk_users (
                guild_id BIGINT,
                user_id BIGINT,
                message TEXT DEFAULT 'AFK',
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            # Moderation warnings
            """
            CREATE TABLE IF NOT EXISTS user_warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                moderator_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """ if not self.is_postgres else """
            CREATE TABLE IF NOT EXISTS user_warnings (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                moderator_id BIGINT NOT NULL,
                reason TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Temporary Voice Channels setup
            """
            CREATE TABLE IF NOT EXISTS tempvc_config (
                guild_id BIGINT PRIMARY KEY,
                hub_channel_id BIGINT NOT NULL,
                category_id BIGINT NOT NULL,
                default_name VARCHAR(50) DEFAULT '{user}''s Lounge'
            );
            """,
            # Active temporary voice channels
            """
            CREATE TABLE IF NOT EXISTS tempvc_active (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                owner_id BIGINT NOT NULL
            );
            """,
            # Active Giveaways
            """
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                prize TEXT NOT NULL,
                winners INT DEFAULT 1,
                end_time DOUBLE PRECISION NOT NULL,
                ended BOOLEAN DEFAULT FALSE
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                prize TEXT NOT NULL,
                winners INT DEFAULT 1,
                end_time REAL NOT NULL,
                ended BOOLEAN DEFAULT FALSE
            );
            """,
            # Mainrole protection
            """
            CREATE TABLE IF NOT EXISTS main_roles (
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS mainrole_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT DEFAULT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS mainrole_logs (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                action VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS mainrole_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                action VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Anti-betray system
            """
            CREATE TABLE IF NOT EXISTS antibetray_config (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                threshold INT DEFAULT 3,
                window_sec INT DEFAULT 5,
                action VARCHAR(20) DEFAULT 'ban',
                channel_id BIGINT DEFAULT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS antibetray_logs (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS antibetray_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                user_name VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Fake permissions system
            """
            CREATE TABLE IF NOT EXISTS fp_config (
                guild_id BIGINT PRIMARY KEY,
                role_id BIGINT DEFAULT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS fp_limits (
                guild_id BIGINT NOT NULL,
                action VARCHAR(32) NOT NULL,
                action_limit INT DEFAULT 0,
                PRIMARY KEY (guild_id, action)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS fp_usage (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                action VARCHAR(32) NOT NULL,
                usage_count INT DEFAULT 0,
                date_str VARCHAR(20) NOT NULL,
                PRIMARY KEY (guild_id, user_id, action, date_str)
            );
            """,
            # Extra owners
            """
            CREATE TABLE IF NOT EXISTS extraowners (
                guild_id BIGINT NOT NULL,
                owner_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, owner_id)
            );
            """,
            # Server recovery snapshots
            """
            CREATE TABLE IF NOT EXISTS server_snapshots (
                guild_id BIGINT PRIMARY KEY,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Autoresponder
            """
            CREATE TABLE IF NOT EXISTS autoresponses (
                guild_id BIGINT NOT NULL,
                trigger TEXT NOT NULL,
                response TEXT NOT NULL,
                PRIMARY KEY (guild_id, trigger)
            );
            """,
            # Autoreact
            """
            CREATE TABLE IF NOT EXISTS autoreacts (
                guild_id BIGINT NOT NULL,
                trigger TEXT NOT NULL,
                emoji TEXT NOT NULL,
                PRIMARY KEY (guild_id, trigger)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS channel_autoreacts (
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                emoji TEXT NOT NULL,
                PRIMARY KEY (guild_id, channel_id, emoji)
            );
            """,
            # Autorole
            """
            CREATE TABLE IF NOT EXISTS autoroles (
                guild_id BIGINT NOT NULL,
                role_id BIGINT NOT NULL,
                role_type VARCHAR(20) NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );
            """,
            # Reaction Roles
            """
            CREATE TABLE IF NOT EXISTS reaction_roles (
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                emoji TEXT NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (message_id, emoji)
            );
            """,
            # Ignore System
            """
            CREATE TABLE IF NOT EXISTS ignored_channels (
                guild_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ignored_commands (
                guild_id BIGINT NOT NULL,
                command_name VARCHAR(50) NOT NULL,
                PRIMARY KEY (guild_id, command_name)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ignored_users (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS ignore_bypass (
                guild_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                target_type VARCHAR(10) NOT NULL,
                PRIMARY KEY (guild_id, target_id)
            );
            """,
            # Server Stats
            """
            CREATE TABLE IF NOT EXISTS stats_config (
                guild_id BIGINT PRIMARY KEY,
                category_id BIGINT DEFAULT NULL,
                members_ch BIGINT DEFAULT NULL,
                humans_ch BIGINT DEFAULT NULL,
                bots_ch BIGINT DEFAULT NULL,
                roles_ch BIGINT DEFAULT NULL
            );
            """,
            # Invite & Message Tracker
            """
            CREATE TABLE IF NOT EXISTS invite_tracker (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                inviter_id BIGINT NOT NULL,
                code VARCHAR(20) NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS user_invites (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                regular INT DEFAULT 0,
                leaves INT DEFAULT 0,
                fakes INT DEFAULT 0,
                bonus INT DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS message_stats (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                count INT DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            # Reminders
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                remind_at DOUBLE PRECISION NOT NULL,
                text TEXT NOT NULL
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                remind_at REAL NOT NULL,
                text TEXT NOT NULL
            );
            """,
            # No-Prefix VIP Users
            """
            CREATE TABLE IF NOT EXISTS noprefix (
                user_id BIGINT PRIMARY KEY
            );
            """,
            # Leveling System
            """
            CREATE TABLE IF NOT EXISTS user_levels (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                xp BIGINT DEFAULT 0,
                level INT DEFAULT 0,
                last_xp DOUBLE PRECISION DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS level_rewards (
                guild_id BIGINT NOT NULL,
                level INT NOT NULL,
                role_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, level)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS level_config (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE,
                channel_id BIGINT DEFAULT NULL
            );
            """,
            # Birthdays
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                day INT NOT NULL,
                month INT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS birthday_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT DEFAULT NULL,
                role_id BIGINT DEFAULT NULL
            );
            """,
            # Starboard
            """
            CREATE TABLE IF NOT EXISTS starboard_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT DEFAULT NULL,
                threshold INT DEFAULT 3,
                emoji TEXT DEFAULT 'star',
                self_star BOOLEAN DEFAULT FALSE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS starboard_messages (
                guild_id BIGINT NOT NULL,
                orig_message_id BIGINT PRIMARY KEY,
                star_message_id BIGINT NOT NULL,
                stars_count INT DEFAULT 1
            );
            """,
            # Sticky Messages
            """
            CREATE TABLE IF NOT EXISTS sticky_messages (
                guild_id BIGINT NOT NULL,
                channel_id BIGINT PRIMARY KEY,
                content TEXT NOT NULL,
                last_message_id BIGINT DEFAULT NULL
            );
            """,
            # Suggestions
            """
            CREATE TABLE IF NOT EXISTS suggestions_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT DEFAULT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                reason TEXT DEFAULT NULL
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                reason TEXT DEFAULT NULL
            );
            """,
            # User Profiles & Reputation
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                bio TEXT DEFAULT 'No bio configured.',
                rep INT DEFAULT 0,
                spouse_id BIGINT DEFAULT NULL,
                last_rep DOUBLE PRECISION DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            # Moderation Cases
            """
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                moderator_id BIGINT NOT NULL,
                action VARCHAR(20) NOT NULL,
                reason TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL
            );
            """ if self.is_postgres else """
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                moderator_id BIGINT NOT NULL,
                action VARCHAR(20) NOT NULL,
                reason TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS modlog_config (
                guild_id BIGINT PRIMARY KEY,
                channel_id BIGINT DEFAULT NULL
            );
            """,
            # Voice Time Tracking
            """
            CREATE TABLE IF NOT EXISTS voice_time (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                total_seconds BIGINT DEFAULT 0,
                last_joined DOUBLE PRECISION DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            """,
            # Tags & Custom Commands System
            """
            CREATE TABLE IF NOT EXISTS guild_tags (
                guild_id BIGINT NOT NULL,
                name VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                author_id BIGINT NOT NULL,
                uses INT DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL,
                PRIMARY KEY (guild_id, name)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS guild_tag_aliases (
                guild_id BIGINT NOT NULL,
                alias VARCHAR(50) NOT NULL,
                target_name VARCHAR(50) NOT NULL,
                PRIMARY KEY (guild_id, alias)
            );
            """,
            # AutoMod Granular Configuration
            """
            CREATE TABLE IF NOT EXISTS automod_config (
                guild_id BIGINT PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                log_channel BIGINT DEFAULT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS automod_filters (
                guild_id BIGINT NOT NULL,
                filter_name VARCHAR(32) NOT NULL,
                enabled BOOLEAN DEFAULT FALSE,
                action VARCHAR(20) DEFAULT 'delete',
                threshold INT DEFAULT 5,
                PRIMARY KEY (guild_id, filter_name)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS automod_words (
                guild_id BIGINT NOT NULL,
                word TEXT NOT NULL,
                PRIMARY KEY (guild_id, word)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS automod_whitelists (
                guild_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                target_type VARCHAR(10) NOT NULL,
                PRIMARY KEY (guild_id, target_id)
            );
            """,
            # User Highlights (Keyword alerts)
            """
            CREATE TABLE IF NOT EXISTS user_highlights (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                keyword TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id, keyword)
            );
            """,
            # Economy Inventory
            """
            CREATE TABLE IF NOT EXISTS user_inventory (
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                item_id VARCHAR(32) NOT NULL,
                count INT DEFAULT 1,
                PRIMARY KEY (guild_id, user_id, item_id)
            );
            """
        ]

        for query in queries:
            try:
                await self.execute(query)
            except Exception as e:
                error(f"Error executing schema DDL: {e}", "database")

        # Dynamic schema migrations for existing Postgres tables
        if self.is_postgres:
            migrations = [
                "ALTER TABLE autoroles ADD COLUMN IF NOT EXISTS role_type VARCHAR(20) DEFAULT 'humans';",
                "ALTER TABLE antinuke_config ADD COLUMN IF NOT EXISTS anti_prune BOOLEAN DEFAULT TRUE;"
            ]
            for m in migrations:
                try:
                    await self.execute(m)
                except Exception:
                    pass

    async def execute(self, query: str, *args) -> None:
        """Executes an INSERT, UPDATE, or DELETE query."""
        if self.is_postgres and self.pg_pool:
            # Postgres parameterized syntax uses $1, $2 instead of ?
            pg_query = self._format_postgres_query(query)
            async with self.pg_pool.acquire() as conn:
                await conn.execute(pg_query, *args)
        elif self.sqlite_conn:
            await self.sqlite_conn.execute(query, args)
            await self.sqlite_conn.commit()

    async def fetchrow(self, query: str, *args) -> Optional[dict]:
        """Fetches a single row as a standard dictionary."""
        if self.is_postgres and self.pg_pool:
            pg_query = self._format_postgres_query(query)
            async with self.pg_pool.acquire() as conn:
                row = await conn.fetchrow(pg_query, *args)
                return dict(row) if row else None
        elif self.sqlite_conn:
            async with self.sqlite_conn.execute(query, args) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
        return None

    async def fetch(self, query: str, *args) -> list[dict]:
        """Fetches multiple rows as a list of dictionaries."""
        if self.is_postgres and self.pg_pool:
            pg_query = self._format_postgres_query(query)
            async with self.pg_pool.acquire() as conn:
                rows = await conn.fetch(pg_query, *args)
                return [dict(r) for r in rows]
        elif self.sqlite_conn:
            async with self.sqlite_conn.execute(query, args) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
        return []

    def _format_postgres_query(self, query: str) -> str:
        """Replaces standard '?' parameter placeholders with '$1', '$2', etc. for asyncpg."""
        parts = query.split("?")
        if len(parts) == 1:
            return query
        formatted = ""
        for idx, part in enumerate(parts[:-1]):
            formatted += f"{part}${idx + 1}"
        formatted += parts[-1]
        return formatted

    # Cache Convenience Wrappers
    async def cache_get(self, key: str) -> Optional[Any]:
        if self.redis:
            return await self.redis.get(key)
        return await self.memory_cache.get(key)

    async def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if self.redis:
            await self.redis.set(key, str(value), ex=ttl)
        else:
            await self.memory_cache.set(key, value, ex=ttl)

    async def cache_delete(self, key: str) -> None:
        if self.redis:
            await self.redis.delete(key)
        else:
            await self.memory_cache.delete(key)

    # Prefix Helper with caching
    async def get_prefix(self, guild_id: int) -> str:
        cache_key = f"prefix:{guild_id}"
        cached = await self.cache_get(cache_key)
        if cached:
            return str(cached)

        row = await self.fetchrow("SELECT prefix FROM guild_prefixes WHERE guild_id = ?", guild_id)
        prefix = row["prefix"] if row else config.DEFAULT_PREFIX
        await self.cache_set(cache_key, prefix, ttl=3600)
        return prefix

    async def set_prefix(self, guild_id: int, prefix: str) -> None:
        if self.is_postgres:
            query = """
            INSERT INTO guild_prefixes (guild_id, prefix)
            VALUES (?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET prefix = EXCLUDED.prefix;
            """
        else:
            query = """
            INSERT INTO guild_prefixes (guild_id, prefix)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix;
            """
        await self.execute(query, guild_id, prefix)
        await self.cache_set(f"prefix:{guild_id}", prefix, ttl=3600)

    async def close(self) -> None:
        """Gracefully disconnects from pools."""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.sqlite_conn:
            await self.sqlite_conn.close()
        if self.redis:
            await self.redis.aclose()


# Global database instance
db = Database()
