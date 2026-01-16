"""Module entrypoint for Conditor package.

Run with: python -m src.conditor
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from src.conditor import bot as conditor_bot
import asyncio

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conditor.__main__")


def main():
    # Ensure cogs are loaded (load_cogs is async in this runtime)
    try:
        asyncio.run(conditor_bot.load_cogs())
    except Exception:
        # fallback: try running on existing loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(conditor_bot.load_cogs())
    token = os.getenv("CONDITOR_TOKEN")
    if not token:
        log.error("CONDITOR_TOKEN environment variable is not set. Set CONDITOR_TOKEN and restart the bot.")
        raise SystemExit("Missing CONDITOR_TOKEN environment variable")
    try:
        conditor_bot.bot.run(token)
    except Exception as exc:
        log.exception("Failed to start bot: %s", exc)


if __name__ == "__main__":
    main()
