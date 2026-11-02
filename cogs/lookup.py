"""
Entity Inspection & Metadata Lookup Engine for Zenith.
Detailed diagnostics for users, channels, roles, custom emojis, server banners, and permissions.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from typing import Optional
import discord
from discord.ext import commands

from core.security import is_dangerous_role

ACCENT_COLOR = 0x0F0F13


class Lookup(commands.Cog):
    """Deep inspection and metadata extraction for Discord entities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="userlookup", aliases=["uinfo", "who"])
    @commands.guild_only()
    async def whois_user(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display comprehensive account metadata and permissions."""
        target = member or ctx.author

        key_perms = []
        if target.guild_permissions.administrator:
            key_perms.append("Administrator")
        if target.guild_permissions.manage_guild:
            key_perms.append("Manage Server")
        if target.guild_permissions.manage_roles:
            key_perms.append("Manage Roles")
        if target.guild_permissions.manage_channels:
            key_perms.append("Manage Channels")
        if target.guild_permissions.ban_members:
            key_perms.append("Ban Members")
        if target.guild_permissions.kick_members:
            key_perms.append("Kick Members")
        if target.guild_permissions.moderate_members:
            key_perms.append("Moderate Members")

        perms_str = ", ".join(key_perms) if key_perms else "Standard Member"

        roles_filtered = [r.mention for r in target.roles if not r.is_default()]
        roles_str = ", ".join(roles_filtered[:15]) if roles_filtered else "None"
        if len(roles_filtered) > 15:
            roles_str += f" (+{len(roles_filtered) - 15} more)"

        embed = discord.Embed(
            title=f"[METADATA] {target.display_name} ({target})",
            color=ACCENT_COLOR
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="User ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(target.created_at.timestamp())}:D>\n(<t:{int(target.created_at.timestamp())}:R>)", inline=True)
        embed.add_field(name="Server Joined", value=f"<t:{int(target.joined_at.timestamp())}:D>\n(<t:{int(target.joined_at.timestamp())}:R>)" if target.joined_at else "Unknown", inline=True)
        embed.add_field(name="Highest Role", value=target.top_role.mention, inline=True)
        embed.add_field(name="Key Permissions", value=perms_str, inline=True)
        embed.add_field(name=f"Roles [{len(roles_filtered)}]", value=roles_str, inline=False)
        embed.set_footer(text="Zenith Lookup | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="channelinfo", aliases=["chinfo", "cinfo"])
    @commands.guild_only()
    async def channel_info(self, ctx: commands.Context, channel: Optional[discord.abc.GuildChannel] = None):
        """Display technical parameters of a channel."""
        ch = channel or ctx.channel
        cat_str = ch.category.name if ch.category else "None"

        embed = discord.Embed(
            title=f"[CHANNEL METADATA] #{ch.name}",
            color=ACCENT_COLOR
        )
        embed.add_field(name="Channel ID", value=f"`{ch.id}`", inline=True)
        embed.add_field(name="Category", value=cat_str, inline=True)
        embed.add_field(name="Position", value=str(ch.position), inline=True)
        embed.add_field(name="Created", value=f"<t:{int(ch.created_at.timestamp())}:D>", inline=True)

        if isinstance(ch, discord.TextChannel):
            embed.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s", inline=True)
            embed.add_field(name="NSFW", value="Yes" if ch.is_nsfw() else "No", inline=True)
            if ch.topic:
                embed.add_field(name="Topic", value=ch.topic[:200], inline=False)
        elif isinstance(ch, discord.VoiceChannel):
            embed.add_field(name="Bitrate", value=f"{ch.bitrate // 1000} kbps", inline=True)
            embed.add_field(name="User Limit", value=str(ch.user_limit) if ch.user_limit else "Unlimited", inline=True)

        embed.set_footer(text="Zenith Lookup | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="roleinfo", aliases=["rinfo"])
    @commands.guild_only()
    async def role_info(self, ctx: commands.Context, role: discord.Role):
        """Display role permissions, hierarchy index, and member count."""
        dangerous = is_dangerous_role(role)
        status = "Dangerous / Administrative" if dangerous else "Standard"

        embed = discord.Embed(
            title=f"[ROLE METADATA] @{role.name}",
            color=role.colour if role.colour.value != 0 else ACCENT_COLOR
        )
        embed.add_field(name="Role ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Color Hex", value=f"`{str(role.colour).upper()}`", inline=True)
        embed.add_field(name="Position", value=f"`{role.position}` / `{len(ctx.guild.roles)}`", inline=True)
        embed.add_field(name="Member Count", value=f"`{len(role.members)}` members", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Privilege Status", value=f"`[{status}]`", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:D>", inline=True)
        embed.set_footer(text="Zenith Lookup | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="servericon", aliases=["sicon"])
    @commands.guild_only()
    async def server_icon(self, ctx: commands.Context):
        """Extract high-resolution server icon asset."""
        if not ctx.guild.icon:
            return await ctx.send(embed=discord.Embed(title="[NO ICON]", description="This server has no icon configured.", color=ACCENT_COLOR))

        embed = discord.Embed(title=f"[SERVER ICON] {ctx.guild.name}", color=ACCENT_COLOR)
        embed.set_image(url=ctx.guild.icon.url)
        embed.description = f"[Direct Image Link]({ctx.guild.icon.url})"
        await ctx.send(embed=embed)

    @commands.command(name="serverbanner", aliases=["sbanner"])
    @commands.guild_only()
    async def server_banner(self, ctx: commands.Context):
        """Extract high-resolution server banner asset."""
        if not ctx.guild.banner:
            return await ctx.send(embed=discord.Embed(title="[NO BANNER]", description="This server has no banner configured.", color=ACCENT_COLOR))

        embed = discord.Embed(title=f"[SERVER BANNER] {ctx.guild.name}", color=ACCENT_COLOR)
        embed.set_image(url=ctx.guild.banner.url)
        embed.description = f"[Direct Image Link]({ctx.guild.banner.url})"
        await ctx.send(embed=embed)

    @commands.command(name="useravatar", aliases=["userpfp", "avatarlookup"])
    async def user_avatar(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Display avatar asset for a member."""
        target = member or ctx.author
        embed = discord.Embed(title=f"[AVATAR] {target.display_name}", color=ACCENT_COLOR)
        embed.set_image(url=target.display_avatar.url)
        embed.description = f"[Direct Asset Link]({target.display_avatar.url})"
        await ctx.send(embed=embed)

    @commands.command(name="membercount", aliases=["mc", "members"])
    @commands.guild_only()
    async def member_count(self, ctx: commands.Context):
        """Display detailed server member census."""
        total = ctx.guild.member_count or len(ctx.guild.members)
        humans = sum(1 for m in ctx.guild.members if not m.bot)
        bots = sum(1 for m in ctx.guild.members if m.bot)

        h_pct = int((humans / total) * 100) if total > 0 else 0
        b_pct = int((bots / total) * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"[MEMBER CENSUS - {ctx.guild.name}]",
            description=(
                f"**Total Population:** `{total:,}`\n"
                f"• Humans: `{humans:,}` (`{h_pct}%`)\n"
                f"• Automated Bots: `{bots:,}` (`{b_pct}%`)"
            ),
            color=ACCENT_COLOR
        )
        embed.set_footer(text="Zenith Lookup | Developed by Shree")
        await ctx.send(embed=embed)

    @commands.command(name="permissions", aliases=["perms"])
    @commands.guild_only()
    async def user_perms(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Audit all permissions for a user in the active channel."""
        target = member or ctx.author
        channel_perms = ctx.channel.permissions_for(target)

        granted = [name.replace("_", " ").title() for name, value in channel_perms if value]
        denied = [name.replace("_", " ").title() for name, value in channel_perms if not value]

        embed = discord.Embed(
            title=f"[PERMISSIONS AUDIT] {target.display_name} in #{ctx.channel.name}",
            color=ACCENT_COLOR
        )
        embed.add_field(name=f"Granted [{len(granted)}]", value=", ".join(granted[:20]) or "None", inline=False)
        embed.add_field(name=f"Denied [{len(denied)}]", value=", ".join(denied[:20]) or "None", inline=False)
        embed.set_footer(text="Zenith Lookup | Developed by Shree")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Lookup(bot))
