"""
Text transformation, encoding converters, and ASCII utilities for Zenith.
Includes Morse code, Binary, Base64, Hexadecimal, Hashes (MD5, SHA1, SHA256),
ROT13, SpongeBob mocking, Leetspeak, Reverse, Upside-down, and Word metrics.
Developed by Shree (Discord ID: 1465912900710305822).
"""

from __future__ import annotations

import base64
import codecs
import hashlib
from typing import Optional
import discord
from discord.ext import commands

THEME_COLOR = 0x0F0F13

MORSE_CODE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..',
    '9': '----.', '0': '-----', ' ': '/'
}
REVERSE_MORSE = {v: k for k, v in MORSE_CODE.items()}

LEET_MAP = {
    'a': '4', 'A': '4', 'e': '3', 'E': '3', 'i': '1', 'I': '1',
    'o': '0', 'O': '0', 's': '5', 'S': '5', 't': '7', 'T': '7'
}

UPSIDE_DOWN_MAP = {
    'a': '\u0250', 'b': 'q', 'c': '\u0254', 'd': 'p', 'e': '\u01dd', 'f': '\u025f',
    'g': '\u0183', 'h': '\u0265', 'i': '\u0131', 'j': '\u027e', 'k': '\u029e',
    'l': 'l', 'm': '\u026f', 'n': 'u', 'o': 'o', 'p': 'd', 'q': 'b', 'r': '\u0279',
    's': 's', 't': '\u0287', 'u': 'n', 'v': '\u028c', 'w': '\u028d', 'x': 'x',
    'y': '\u028e', 'z': 'z', 'A': '\u2200', 'B': 'q', 'C': '\u0186', 'D': 'p',
    'E': '\u018e', 'F': '\u2132', 'G': '\u2141', 'H': 'H', 'I': 'I', 'J': '\u017f',
    'K': '\u029e', 'L': '\u02e5', 'M': 'W', 'N': 'N', 'O': 'O', 'P': 'd',
    'Q': 'b', 'R': '\u1d1a', 'S': 'S', 'T': '\u22a5', 'U': '\u2229', 'V': '\u039b',
    'W': 'M', 'X': 'X', 'Y': '\u2144', 'Z': 'Z', '?': '\u00bf', '!': '\u00a1',
    '.': '\u02d9', ',': '\'', '\'': ',', '"': ',,', '(': ')', ')': '(',
    '[': ']', ']': '[', '{': '}', '}': '{', '<': '>', '>': '<', '_': '\u203e'
}


class TextTools(commands.Cog):
    """Text transformations, encoding converters, and ASCII utilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="mock")
    async def mock_text(self, ctx: commands.Context, *, text: str):
        """Transform text into sPoNgEbOb cAsE."""
        mocked = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text))
        await ctx.send(mocked)

    @commands.command(name="reverse", aliases=["rev"])
    async def reverse_text(self, ctx: commands.Context, *, text: str):
        """Reverse a string of text."""
        await ctx.send(text[::-1])

    @commands.command(name="vaporwave", aliases=["wide"])
    async def vaporwave_text(self, ctx: commands.Context, *, text: str):
        """Convert text into aesthetic full-width vaporwave typography."""
        result = []
        for char in text:
            code = ord(char)
            if 0x21 <= code <= 0x7E:
                result.append(chr(code + 0xFEE0))
            elif code == 0x20:
                result.append("\u3000")
            else:
                result.append(char)
        await ctx.send("".join(result))

    @commands.command(name="binary")
    async def binary_convert(self, ctx: commands.Context, mode: str, *, text: str):
        """Convert text to or from binary."""
        mode = mode.lower()
        if mode in ("encode", "enc", "e"):
            b = " ".join(format(ord(c), '08b') for c in text)
            await ctx.send(f"```\n{b}\n```")
        elif mode in ("decode", "dec", "d"):
            try:
                decoded = "".join(chr(int(b, 2)) for b in text.split())
                await ctx.send(f"```\n{decoded}\n```")
            except Exception:
                await ctx.send("[ERROR] Invalid binary string.")
        else:
            await ctx.send("[ERROR] Mode must be `encode` or `decode`.")

    @commands.command(name="morse")
    async def morse_convert(self, ctx: commands.Context, mode: str, *, text: str):
        """Convert text to or from Morse code."""
        mode = mode.lower()
        if mode in ("encode", "enc", "e"):
            m = " ".join(MORSE_CODE.get(c.upper(), "") for c in text)
            await ctx.send(f"```\n{m}\n```")
        elif mode in ("decode", "dec", "d"):
            d = "".join(REVERSE_MORSE.get(c, "") for c in text.split())
            await ctx.send(f"```\n{d}\n```")
        else:
            await ctx.send("[ERROR] Mode must be `encode` or `decode`.")

    @commands.command(name="base64", aliases=["b64"])
    async def base64_cmd(self, ctx: commands.Context, mode: str, *, text: str):
        """Encode or decode text with Base64."""
        mode = mode.lower()
        if mode in ("encode", "enc", "e"):
            encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
            await ctx.send(f"```\n{encoded}\n```")
        elif mode in ("decode", "dec", "d"):
            try:
                decoded = base64.b64decode(text.encode("utf-8")).decode("utf-8")
                await ctx.send(f"```\n{decoded}\n```")
            except Exception:
                await ctx.send("[ERROR] Invalid Base64 payload.")
        else:
            await ctx.send("[ERROR] Mode must be `encode` or `decode`.")

    @commands.command(name="hex")
    async def hex_cmd(self, ctx: commands.Context, mode: str, *, text: str):
        """Encode or decode text to hexadecimal."""
        mode = mode.lower()
        if mode in ("encode", "enc", "e"):
            hex_str = text.encode("utf-8").hex()
            await ctx.send(f"```\n{hex_str}\n```")
        elif mode in ("decode", "dec", "d"):
            try:
                decoded = bytes.fromhex(text.replace(" ", "")).decode("utf-8")
                await ctx.send(f"```\n{decoded}\n```")
            except Exception:
                await ctx.send("[ERROR] Invalid hexadecimal payload.")
        else:
            await ctx.send("[ERROR] Mode must be `encode` or `decode`.")

    @commands.command(name="hash")
    async def hash_cmd(self, ctx: commands.Context, algorithm: str, *, text: str):
        """Calculate cryptographic checksum hashes (md5, sha1, sha256, sha512)."""
        algo = algorithm.lower().strip()
        data = text.encode("utf-8")

        if algo == "md5":
            digest = hashlib.md5(data).hexdigest()
        elif algo in ("sha1", "sha-1"):
            digest = hashlib.sha1(data).hexdigest()
        elif algo in ("sha256", "sha-256"):
            digest = hashlib.sha256(data).hexdigest()
        elif algo in ("sha512", "sha-512"):
            digest = hashlib.sha512(data).hexdigest()
        else:
            return await ctx.send("[ERROR] Supported algorithms: `md5`, `sha1`, `sha256`, `sha512`.")

        embed = discord.Embed(
            title=f"[HASH] {algo.upper()}",
            description=f"```{digest}```",
            color=THEME_COLOR
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rot13")
    async def rot13_convert(self, ctx: commands.Context, *, text: str):
        """Apply ROT13 cipher to text."""
        result = codecs.encode(text, 'rot_13')
        await ctx.send(f"```\n{result}\n```")

    @commands.command(name="leet", aliases=["1337"])
    async def leet_cmd(self, ctx: commands.Context, *, text: str):
        """Convert text into 1337speak."""
        converted = "".join(LEET_MAP.get(c, c) for c in text)
        await ctx.send(converted)

    @commands.command(name="upsidedown", aliases=["fliptext"])
    async def upsidedown_cmd(self, ctx: commands.Context, *, text: str):
        """Flip text upside down."""
        converted = "".join(UPSIDE_DOWN_MAP.get(c, c) for c in reversed(text))
        await ctx.send(converted)

    @commands.command(name="spoiler")
    async def spoiler_text(self, ctx: commands.Context, *, text: str):
        """Wrap all words in Discord spoiler markdown."""
        spoilered = " ".join(f"||{word}||" for word in text.split())
        await ctx.send(spoilered)

    @commands.command(name="censor")
    async def censor_cmd(self, ctx: commands.Context, *, text: str):
        """Black out entire text inside markdown spoiler brackets."""
        await ctx.send(f"||{text}||")

    @commands.command(name="wordcount", aliases=["wc", "charcount"])
    async def wordcount_cmd(self, ctx: commands.Context, *, text: str):
        """Calculate word count, character count, and whitespace metrics."""
        words = text.split()
        chars_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
        lines = text.count("\n") + 1

        embed = discord.Embed(
            title="[TEXT METRICS]",
            color=THEME_COLOR
        )
        embed.add_field(name="Words", value=f"{len(words):,}", inline=True)
        embed.add_field(name="Characters (Total)", value=f"{len(text):,}", inline=True)
        embed.add_field(name="Characters (No Space)", value=f"{chars_no_spaces:,}", inline=True)
        embed.add_field(name="Lines", value=f"{lines:,}", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="shrug")
    async def shrug_cmd(self, ctx: commands.Context):
        """Output ASCII shrug."""
        await ctx.send(r"¯\_(ツ)_/¯")

    @commands.command(name="tableflip")
    async def tableflip_cmd(self, ctx: commands.Context):
        """Output ASCII tableflip."""
        await ctx.send("(╯°□°)╯︵ ┻━┻")

    @commands.command(name="unflip")
    async def unflip_cmd(self, ctx: commands.Context):
        """Output ASCII unflip."""
        await ctx.send("┬─┬ノ( º _ ºノ)")


async def setup(bot: commands.Bot):
    await bot.add_cog(TextTools(bot))
