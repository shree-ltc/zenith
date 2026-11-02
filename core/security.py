"""
Core security utilities and permission validators for Zenith.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional, Tuple
import discord
from core.database import db
from core.config import config

DANGEROUS_PERMISSIONS = [
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "ban_members",
    "kick_members",
    "moderate_members",
    "manage_webhooks",
    "mention_everyone",
    "manage_messages",
    "view_audit_log",
    "manage_events",
    "manage_threads",
    "manage_nicknames",
    "manage_expressions",
]


async def is_extra_owner(guild_id: int, user_id: int) -> bool:
    """Check if a user is registered as an extra owner."""
    row = await db.fetchrow(
        "SELECT 1 FROM extraowners WHERE guild_id = ? AND owner_id = ?",
        guild_id, user_id
    )
    return row is not None


async def is_authorized_admin(user_id: int, guild: Optional[discord.Guild], bot: discord.Client) -> bool:
    """
    Check if a user has ultimate administrative authorization:
    Bot Owner, Server Owner, or Guild Extra Owner.
    """
    if user_id in config.OWNER_IDS:
        return True
    if guild and guild.owner_id == user_id:
        return True
    if guild and await is_extra_owner(guild.id, user_id):
        return True
    return False


def is_dangerous_role(role: discord.Role) -> bool:
    """Check if a role possesses administrative or harmful permissions."""
    if role.permissions.administrator:
        return True
    for perm in DANGEROUS_PERMISSIONS:
        if getattr(role.permissions, perm, False):
            return True
    return False


def validate_role_hierarchy(
    actor: discord.Member,
    target_role: discord.Role,
    is_removal: bool = False
) -> Tuple[bool, str]:
    """
    Validates whether an actor and the bot can manage the given role.
    Returns (True, '') on success, or (False, error_message).
    """
    guild = actor.guild
    me = guild.me

    if not me.guild_permissions.manage_roles:
        return False, "[DENIED] Bot lacks 'Manage Roles' permission."

    if target_role >= me.top_role:
        return False, f"[DENIED] Role {target_role.mention} is higher than or equal to my highest role."

    if target_role.is_default():
        return False, "[DENIED] Default @everyone role cannot be directly assigned or deleted."

    if target_role.managed:
        return False, f"[DENIED] Role {target_role.mention} is managed by an integration/bot and cannot be assigned manually."

    # Server owner bypasses role hierarchy checks
    if actor.id == guild.owner_id or actor.id in config.OWNER_IDS:
        return True, ""

    if target_role >= actor.top_role:
        return False, f"[DENIED] Role {target_role.mention} is higher than or equal to your highest role."

    return True, ""
