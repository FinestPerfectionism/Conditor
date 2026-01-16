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

bot = commands.Bot(command_prefix="!", intents=intents)

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


def load_cogs():
    here = Path(__file__).parent
    cogs_dir = here / "cogs"
    for p in cogs_dir.glob("*.py"):
        if p.name.startswith("_"):
            continue
        ext = f"src.conditor.cogs.{p.stem}"
        try:
            bot.load_extension(ext)
            print("Loaded cog:", ext)
        except Exception as e:
            print("Failed to load cog", ext, e)


if __name__ == "__main__":
    load_cogs()
    if not TOKEN:
        raise RuntimeError("CONDITOR_TOKEN not set in environment")
    bot.run(TOKEN)
