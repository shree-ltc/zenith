"""
core/database.py - Resilient Hybrid Database & Caching Engine for Zenith

Supports high-throughput PostgreSQL + Redis for production deployments,
while seamlessly falling back to aiosqlite + in-memory TTL caching for
instant plug-and-play development without external dependencies.
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
            """
        ]

        for query in queries:
            try:
                await self.execute(query)
            except Exception as e:
                error(f"Error executing schema DDL: {e}", "database")

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
