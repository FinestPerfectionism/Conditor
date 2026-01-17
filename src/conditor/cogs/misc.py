import re
from typing import Optional
import discord
from discord.ext import commands

FEEDBACK_CHANNEL_ID = 1462000202410889340

# Basic banned-word filter; expand as needed
BANNED_WORDS = {"shota", "lolicoin", "badword1"}


def _parse_color(candidate: Optional[str]) -> Optional[int]:
    if not candidate:
        return None
    c = candidate.strip()
    if c.startswith("#"):
        c = c[1:]
    if re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return int(c, 16)
    return None


def contains_banned(text: str) -> bool:
    t = re.sub(r"[^a-z0-9]", "", text.lower())
    for w in BANNED_WORDS:
        if w in t:
            return True
    return False


class MiscCog(commands.Cog):
    """Utility commands: embed, say, feedback (prefix + slash/hybrid)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _respond(self, ctx: commands.Context, content=None, embed=None, ephemeral=False):
        inter = getattr(ctx, "interaction", None)
        if inter and inter.response and not inter.response.is_done():
            await inter.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        else:
            await ctx.send(content=content, embed=embed)

    @commands.command(name="embed")
    async def embed_prefix(self, ctx: commands.Context, *, text: str):
        parts = text.rsplit(" ", 1)
        color = None
        content = text
        if len(parts) == 2:
            maybe_color = parts[1]
            parsed = _parse_color(maybe_color)
            if parsed is not None:
                color = parsed
                content = parts[0]

        emb = discord.Embed(description=content)
        if color is not None:
            emb.colour = discord.Colour(color)
        emb.set_footer(text=f"Sent by {ctx.author}")
        await ctx.send(embed=emb)

    @commands.hybrid_command(name="embed", with_app_command=True)
    async def embed_slash(self, ctx: commands.Context, text: str, color: Optional[str] = None):
        parsed = _parse_color(color)
        emb = discord.Embed(description=text)
        if parsed is not None:
            emb.colour = discord.Colour(parsed)
        emb.set_footer(text=f"Sent by {ctx.author}")
        await self._respond(ctx, embed=emb, ephemeral=False)

    @commands.command(name="say")
    async def say_prefix(self, ctx: commands.Context, *, text: str):
        if contains_banned(text):
            await ctx.send("Message contains forbidden content.")
            return
        try:
            if ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="say", with_app_command=True)
    async def say_slash(self, ctx: commands.Context, text: str):
        if contains_banned(text):
            await self._respond(ctx, content="Message contains forbidden content.", ephemeral=True)
            return
        await self._respond(ctx, content=text)

    @commands.command(name="feedback")
    async def feedback_prefix(self, ctx: commands.Context, *, text: str):
        await self._post_feedback(ctx, text)

    @commands.hybrid_command(name="feedback", with_app_command=True)
    async def feedback_slash(self, ctx: commands.Context, text: str):
        await self._post_feedback(ctx, text)

    async def _post_feedback(self, ctx: commands.Context, text: str):
        channel = self.bot.get_channel(FEEDBACK_CHANNEL_ID)
        if channel is None:
            await self._respond(ctx, content=f"Feedback channel (id {FEEDBACK_CHANNEL_ID}) not found.")
            return

        embed = discord.Embed(title="User Feedback", description=text, color=discord.Colour.blue())
        embed.add_field(name="From", value=f"{ctx.author} ({ctx.author.id})", inline=False)
        embed.add_field(name="Server", value=f"{ctx.guild.name if ctx.guild else 'DM'}", inline=False)
        embed.set_footer(text="Conditor Feedback")
        try:
            await channel.send(embed=embed)
            await self._respond(ctx, content="Thanks — your feedback was posted.", ephemeral=True)
        except discord.Forbidden:
            await self._respond(ctx, content="Bot lacks permission to post feedback.")


async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
