import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv("CONDITOR_TOKEN")
GUILD_ID = os.getenv("CONDITOR_GUILD_ID") or os.getenv("CONDITOR_GUILD")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True


class ConditorBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # Load cogs before the bot connects so commands/registers persist in this loop
        try:
            await load_cogs(self)
        except Exception as e:
            print("Failed to load cogs in setup_hook:", e)

        # If a development guild is provided, copy globals to that guild for fast iteration
        try:
            if GUILD_ID:
                try:
                    gid = int(GUILD_ID)
                    guild = discord.Object(id=gid)
                    self.tree.copy_global_to_guild(guild)
                    await self.tree.sync(guild=guild)
                    print(f"Application commands synced to guild {gid}.")
                except Exception as e:
                    print("Failed to sync to guild in setup_hook:", e)
            else:
                await self.tree.sync()
                print("Application commands synced (global) in setup_hook.")
        except Exception as e:
            print("Failed to sync application commands in setup_hook:", e)
        # Debug: list loaded extensions and commands
        try:
            print("Loaded extensions:", list(self.extensions.keys()))
            prefix_cmds = [c.name for c in self.commands]
            app_cmds = [c.name for c in self.tree.get_commands()]
            print(f"Prefix commands (count={len(prefix_cmds)}): {prefix_cmds}")
            print(f"Application commands (count={len(app_cmds)}): {app_cmds}")
        except Exception as e:
            print("Failed to list commands in setup_hook:", e)


# Use 'C!' as the prefix per project convention
bot = ConditorBot(command_prefix="C!", intents=intents)

# Configure bot owners: can be overridden with CONDITOR_OWNER_IDS (comma-separated)
owners_env = os.getenv("CONDITOR_OWNER_IDS") or os.getenv("CONDITOR_OWNERS")
if owners_env:
    try:
        owner_ids = {int(x.strip()) for x in owners_env.split(",") if x.strip()}
    except Exception:
        owner_ids = set()
else:
    owner_ids = {1382187068373074001, 1311394031640776716}
bot.owner_ids = owner_ids
if not getattr(bot, "owner_id", None) and owner_ids:
    bot.owner_id = next(iter(owner_ids))


@bot.tree.command(name="conditor_help")
async def _conditor_help(interaction: discord.Interaction):
    """Basic in-client help for Conditor (slash command)."""
    text = (
        "Conditor bot usage:\n"
        "- Prefix commands: use `C!` (e.g. `C!template_list`)\n"
        "- Slash commands: `/template_edit` (use with a template name)\n"
        "- Admins: use `/template_edit <name>` to edit templates, or `C!template_save`/`C!template_get`.\n"
        "See the README for full instructions and Render deployment notes."
    )
    await interaction.response.send_message(text, ephemeral=True)

# Shared build queue for jobs
build_queue: asyncio.Queue = asyncio.Queue()


@bot.event
async def on_ready():
    # start build worker and ensure application commands are synced
    bot.loop.create_task(build_worker())
    try:
        # If a development guild is provided, copy globals to that guild for fast iteration
        if GUILD_ID:
            try:
                gid = int(GUILD_ID)
                guild = discord.Object(id=gid)
                bot.tree.copy_global_to_guild(guild)
                await bot.tree.sync(guild=guild)
                print(f"Application commands synced to guild {gid}.")
            except Exception as e:
                print("Failed to sync to guild:", e)
        else:
            await bot.tree.sync()
            print("Application commands synced (global).")
    except Exception as e:
        print("Failed to sync application commands:", e)
    # Log registered application commands for debugging
    try:
        cmds = list(bot.tree.get_commands())
        print(f"Registered application commands (count={len(cmds)}): {[c.name for c in cmds]}")
    except Exception:
        pass
    print(f"Bot ready: {bot.user} (guilds: {len(bot.guilds)})")


async def build_worker():
    while True:
        job = await build_queue.get()
        try:
            await job.run()
        except Exception as exc:
            # simple logging
            print("Build job failed:", exc)
        finally:
            build_queue.task_done()


async def load_cogs(bot: commands.Bot):
    here = Path(__file__).parent
    cogs_dir = here / "cogs"
    for p in cogs_dir.glob("*.py"):
        if p.name.startswith("_"):
            continue
        ext = f"src.conditor.cogs.{p.stem}"
        try:
            await bot.load_extension(ext)
            print("Loaded cog:", ext)
        except Exception as e:
            print("Failed to load cog", ext, e)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("CONDITOR_TOKEN not set in environment")
    bot.run(TOKEN)
