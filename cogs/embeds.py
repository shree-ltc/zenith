"""
Custom Embed Architecture for Zenith.
Supports direct JSON dispatching, templates, message editing, and reverse embed decompilation.
Developed by Shree (Discord ID: 1465912900710305822).
"""

import json
from typing import Optional
import discord
from discord.ext import commands

ACCENT_COLOR = 0x0F0F13


class Embeds(commands.Cog):
    """Custom embed builder and JSON dispatcher."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="embed", invoke_without_command=True)
    @commands.guild_only()
    async def embed_group(self, ctx: commands.Context):
        """Custom embed generation overview."""
        embed = discord.Embed(
            title="[EMBED ARCHITECTURE]",
            description="Create, send, and edit rich Discord embeds via parameters or raw JSON.",
            color=ACCENT_COLOR
        )
        embed.add_field(
            name="Available Commands",
            value=(
                f"`{ctx.prefix}embed simple <channel> <title> <description>` - Send basic embed\n"
                f"`{ctx.prefix}embed send <channel> <json>` - Dispatch full JSON embed\n"
                f"`{ctx.prefix}embed edit <message_id> <json>` - Update existing embed\n"
                f"`{ctx.prefix}embed raw <message_id>` - Extract embed JSON structure\n"
                f"`{ctx.prefix}embed template <announcement/rules>` - Get prebuilt JSON"
            ),
            inline=False
        )
        embed.set_footer(text="Zenith Suite | Developed by Shree")
        await ctx.send(embed=embed)

    @embed_group.command(name="simple")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def embed_simple(self, ctx: commands.Context, channel: discord.TextChannel, title: str, *, description: str):
        """Send a clean styled embed to a specified channel."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=ACCENT_COLOR
        )
        embed.set_footer(text=f"{ctx.guild.name} | Zenith")
        msg = await channel.send(embed=embed)
        await ctx.send(embed=discord.Embed(title="[EMBED DISPATCHED]", description=f"Sent embed to {channel.mention} (`{msg.id}`).", color=ACCENT_COLOR))

    @embed_group.command(name="send")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def embed_send(self, ctx: commands.Context, channel: discord.TextChannel, *, json_string: str):
        """Dispatch a full JSON embed payload."""
        try:
            data = json.loads(json_string.strip("`"))
            embed = discord.Embed.from_dict(data)
            msg = await channel.send(embed=embed)
            await ctx.send(embed=discord.Embed(title="[EMBED DISPATCHED]", description=f"Sent JSON embed to {channel.mention} (`{msg.id}`).", color=ACCENT_COLOR))
        except json.JSONDecodeError as e:
            await ctx.send(embed=discord.Embed(title="[JSON PARSE ERROR]", description=f"Invalid JSON: `{e}`", color=ACCENT_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[DISPATCH ERROR]", description=f"Could not dispatch embed: `{e}`", color=ACCENT_COLOR))

    @embed_group.command(name="edit")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def embed_edit(self, ctx: commands.Context, message_id: int, *, json_string: str):
        """Edit an existing bot embed using a new JSON payload."""
        target_msg = None
        for ch in ctx.guild.text_channels:
            try:
                target_msg = await ch.fetch_message(message_id)
                break
            except Exception:
                pass

        if not target_msg:
            return await ctx.send(embed=discord.Embed(title="[MESSAGE NOT FOUND]", description=f"Could not locate message `{message_id}`.", color=ACCENT_COLOR))

        if target_msg.author.id != self.bot.user.id:
            return await ctx.send(embed=discord.Embed(title="[EDIT FORBIDDEN]", description="I can only edit messages authored by Zenith.", color=ACCENT_COLOR))

        try:
            data = json.loads(json_string.strip("`"))
            embed = discord.Embed.from_dict(data)
            await target_msg.edit(embed=embed)
            await ctx.send(embed=discord.Embed(title="[EMBED UPDATED]", description=f"Edited message `{message_id}`.", color=ACCENT_COLOR))
        except json.JSONDecodeError as e:
            await ctx.send(embed=discord.Embed(title="[JSON PARSE ERROR]", description=f"Invalid JSON: `{e}`", color=ACCENT_COLOR))
        except Exception as e:
            await ctx.send(embed=discord.Embed(title="[EDIT ERROR]", description=f"Failed to edit: `{e}`", color=ACCENT_COLOR))

    @embed_group.command(name="raw")
    @commands.guild_only()
    async def embed_raw(self, ctx: commands.Context, message_id: int):
        """Extract the JSON structure of an existing embed."""
        target_msg = None
        for ch in ctx.guild.text_channels:
            try:
                target_msg = await ch.fetch_message(message_id)
                break
            except Exception:
                pass

        if not target_msg or not target_msg.embeds:
            return await ctx.send(embed=discord.Embed(title="[NO EMBED FOUND]", description="Message has no embed content.", color=ACCENT_COLOR))

        raw_dict = target_msg.embeds[0].to_dict()
        formatted_json = json.dumps(raw_dict, indent=2)

        if len(formatted_json) > 1900:
            formatted_json = formatted_json[:1890] + "\n... [truncated]"

        await ctx.send(f"```json\n{formatted_json}\n```")

    @embed_group.command(name="template")
    @commands.guild_only()
    async def embed_template(self, ctx: commands.Context, template_name: str = "announcement"):
        """Get a ready-to-edit JSON embed template."""
        template_name = template_name.lower()
        if template_name in ("rules", "rule"):
            template = {
                "title": "[COMMUNITY GUIDELINES]",
                "description": "Please abide by our server regulations:\n1. Maintain respectful interactions.\n2. No advertising or unsolicited DMs.\n3. Keep topics strictly in designated channels.",
                "color": ACCENT_COLOR,
                "footer": {"text": "Community Staff"}
            }
        else:
            template = {
                "title": "[SERVER ANNOUNCEMENT]",
                "description": "Important notice for all community members.\nEnter detailed update information here.",
                "color": ACCENT_COLOR,
                "fields": [
                    {"name": "Date Effective", "value": "Immediate", "inline": True},
                    {"name": "Applies To", "value": "All Members", "inline": True}
                ],
                "footer": {"text": "Zenith Announcements"}
            }

        await ctx.send(f"```json\n{json.dumps(template, indent=2)}\n```")


async def setup(bot: commands.Bot):
    await bot.add_cog(Embeds(bot))
