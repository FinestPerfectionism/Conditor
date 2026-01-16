import discord
from discord.ext import commands
from typing import Optional


class AdminTools(commands.Cog):
    """Admin utilities for managing application commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.is_owner()
    @commands.hybrid_command(name="sync_commands", with_app_command=True)
    async def sync_commands(self, ctx: commands.Context, guild_id: Optional[int] = None):
        """Sync application commands. Owner-only.

        Usage: `C!sync_commands` or `/sync_commands guild_id:optional`
        If `guild_id` is provided the bot will copy globals to that guild and sync there for instant visibility.
        """
        await ctx.defer(ephemeral=True)
        try:
            if guild_id:
                guild = discord.Object(id=guild_id)
                self.bot.tree.copy_global_to_guild(guild)
                await self.bot.tree.sync(guild=guild)
                cmds = list(self.bot.tree.get_commands(guild=guild))
                await ctx.followup.send(f"Synced commands to guild {guild_id}. Count={len(cmds)}")
            else:
                await self.bot.tree.sync()
                cmds = list(self.bot.tree.get_commands())
                await ctx.followup.send(f"Synced global commands. Count={len(cmds)}")
        except Exception as e:
            await ctx.followup.send(f"Sync failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminTools(bot))
