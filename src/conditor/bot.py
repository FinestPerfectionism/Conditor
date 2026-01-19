import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
import discord
from discord.ext import commands
import logging

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
            logging.getLogger("conditor.bot").exception("Failed to load cogs in setup_hook")

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
            log = logging.getLogger("conditor.bot")
            log.info("Loaded extensions: %s", list(self.extensions.keys()))
            prefix_cmds = [c.name for c in self.commands]
            app_cmds = [c.name for c in self.tree.get_commands()]
            log.info("Prefix commands (count=%d): %s", len(prefix_cmds), prefix_cmds)
            log.info("Application commands (count=%d): %s", len(app_cmds), app_cmds)
        except Exception:
            logging.getLogger("conditor.bot").exception("Failed to list commands in setup_hook")


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
    from .core.planner.models import BuildPlan
    from .core.executor import Executor
    from .core.executor.discord_handler import make_discord_handler

    executor = Executor(storage_dir=Path(__file__).parent / 'data' / 'runtime')

    while True:
        item = await build_queue.get()
        try:
            # legacy BuildJob support: object with run()
            if hasattr(item, 'run') and callable(getattr(item, 'run')):
                try:
                    await item.run()
                except Exception as exc:
                    print('Build job failed:', exc)
                finally:
                    build_queue.task_done()
                continue

            # plan-based item
            if isinstance(item, dict) and item.get('type') == 'plan':
                plan = item.get('plan')
                dry = item.get('dry_run', False)
                if plan is None:
                    print('Malformed plan item on queue')
                    build_queue.task_done()
                    continue

                # choose guild: prefer guild_id provided when enqueuing the plan
                guild = None
                gid = item.get('guild_id') if isinstance(item, dict) else None
                if gid:
                    try:
                        guild = bot.get_guild(int(gid))
                    except Exception:
                        guild = None
                if guild is None:
                    # fallback to first guild the bot is in
                    if len(bot.guilds) > 0:
                        guild = bot.guilds[0]
                if guild is None:
                    print('No guild available to run plan')
                    build_queue.task_done()
                    continue

                # namespace the resource map using the plan name to avoid cross-plan reuse
                ns = plan.name if hasattr(plan, 'name') else None
                handler = make_discord_handler(bot, guild, storage_dir=executor.storage_dir, namespace=ns)
                try:
                    await executor.run_plan(plan, handler, resume=False)
                except Exception as exc:
                    print('Plan execution failed:', exc)
                finally:
                    build_queue.task_done()
                continue

            # unknown item
            print('Unknown queue item received')
        except Exception as exc:
            print('Build worker error:', exc)
            build_queue.task_done()


async def load_cogs(bot: commands.Bot):
    here = Path(__file__).parent
    cogs_dir = here / "cogs"
    logging.getLogger("conditor.bot").info("Discovered cog files: %s", [p.name for p in cogs_dir.glob("*.py")])
    for p in cogs_dir.glob("*.py"):
        if p.name.startswith("_"):
            continue
        ext = f"{__package__}.cogs.{p.stem}"
        try:
            logging.getLogger("conditor.bot").info("Loading extension: %s", ext)
            await bot.load_extension(ext)
            logging.getLogger("conditor.bot").info("Loaded cog: %s", ext)
        except Exception as e:
            import traceback
            logging.getLogger("conditor.bot").error("Failed to load cog %s: %s", ext, e)
            logging.getLogger("conditor.bot").error(traceback.format_exc())


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("CONDITOR_TOKEN not set in environment")
    bot.run(TOKEN)
