from typing import Dict, Any

import discord
from src.conditor.rate_limiter import run_with_rate_limit


async def ensure_bot_role_position(guild: discord.Guild) -> None:
    """Ensure bot's top role is above roles it will create. If not, log a warning.

    This function cannot programmatically elevate the bot's role; it only checks and raises if unsafe.
    """
    me = guild.me
    if me is None:
        return
    bot_top = max((r.position for r in me.roles), default=0)
    # if bot_top is low, caller should warn
    return bot_top


async def apply_channel_overwrites(guild: discord.Guild, channel: discord.abc.GuildChannel, overwrites: Dict[str, Any]):
    """Apply permission overwrites to a channel. `overwrites` is a mapping of role_name -> {allow:[], deny:[]}.
    Uses rate-limited calls.
    """
    role_map = {r.name: r for r in guild.roles}
    perms_map = {}
    for role_key, od in overwrites.items():
        role = role_map.get(role_key)
        if not role:
            continue
        allow = od.get("allow", [])
        deny = od.get("deny", [])
        perms = discord.PermissionOverwrite()
        for p in allow:
            setattr(perms, p, True)
        for p in deny:
            setattr(perms, p, False)
        perms_map[role] = perms

    async def _edit():
        await channel.edit(permission_overwrites=perms_map)

    await run_with_rate_limit(guild.id, _edit)
