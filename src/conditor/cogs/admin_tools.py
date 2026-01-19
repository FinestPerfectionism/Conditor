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

    @commands.is_owner()
    @commands.hybrid_command(name="force_resync", with_app_command=True)
    async def force_resync(self, ctx: commands.Context, guild_id: int, client_id: Optional[int] = None):
        """Force copy globals to a guild and sync immediately. Owner-only.

        Usage: `C!force_resync <guild_id> [client_id]` or `/force_resync guild_id client_id(optional)`
        Optionally returns an invite URL if `client_id` or the running bot's id is available.
        """
        await ctx.defer(ephemeral=True)
        try:
            guild = discord.Object(id=guild_id)
            # copy globals to the target guild and sync
            self.bot.tree.copy_global_to_guild(guild)
            await self.bot.tree.sync(guild=guild)
            cmds = list(self.bot.tree.get_commands(guild=guild))
            msg = f"Force-synced commands to guild {guild_id}. Count={len(cmds)}"
            cid = client_id or (getattr(self.bot.user, "id", None))
            if cid:
                invite = f"https://discord.com/oauth2/authorize?client_id={cid}&scope=bot%20applications.commands&permissions=0"
                msg += f"\nInvite URL: {invite}"
            await ctx.followup.send(msg)
        except Exception as e:
            await ctx.followup.send(f"Force resync failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminTools(bot))
