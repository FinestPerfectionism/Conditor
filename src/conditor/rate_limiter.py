import asyncio
import math
import random
import time
from typing import Callable, Any

import discord


class RateLimiter:
    """Simple centralized retry manager with per-guild locks and exponential backoff.

    Usage: await RateLimiter.run(guild_id, coro_func, *args, **kwargs)
    where coro_func is an async callable.
    """

    def __init__(self):
        self.locks = {}

    def _get_lock(self, guild_id: int):
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()
        return self.locks[guild_id]

    async def run(self, guild_id: int, func: Callable[..., Any], *args, **kwargs):
        lock = self._get_lock(guild_id)
        # serialize operations per-guild
        async with lock:
            attempt = 0
            base_delay = 0.5
            while True:
                try:
                    return await func(*args, **kwargs)
                except discord.HTTPException as exc:
                    attempt += 1
                    if getattr(exc, "status", None) == 429 or getattr(exc, "code", None) == 429:
                        retry_after = getattr(exc, "retry_after", None) or (base_delay * (2 ** attempt))
                        # jitter
                        jitter = random.uniform(0, 0.5)
                        await asyncio.sleep(retry_after + jitter)
                        continue
                    # other HTTP errors: backoff and retry a few times
                    if attempt >= 4:
                        raise
                    await asyncio.sleep(min(10, base_delay * (2 ** attempt)))
                except Exception:
                    attempt += 1
                    if attempt >= 4:
                        raise
                    await asyncio.sleep(min(5, base_delay * (2 ** attempt)))


# module-level singleton
_rl = RateLimiter()


async def run_with_rate_limit(guild_id: int, func: Callable[..., Any], *args, **kwargs):
    return await _rl.run(guild_id, func, *args, **kwargs)
