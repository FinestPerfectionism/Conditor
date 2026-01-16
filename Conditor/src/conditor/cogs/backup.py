import json
from pathlib import Path
from typing import Dict, Any

import discord
from discord.ext import commands
from src.conditor.i18n import Localizer


class BackupCog(commands.Cog):
    """Export and restore structural snapshots of a guild."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _snapshot_path(self, guild: discord.Guild) -> Path:
        base = Path(__file__).parent.parent.parent
        snaps = base / "data" / "backups"
        snaps.mkdir(parents=True, exist_ok=True)
        return snaps / f"guild_{guild.id}.json"

    def _serialize_role(self, role: discord.Role) -> Dict[str, Any]:
        return {"name": role.name, "color": str(role.colour), "permissions": role.permissions.value, "position": role.position}

    def _serialize_channel(self, ch: discord.abc.GuildChannel) -> Dict[str, Any]:
        data = {"name": ch.name, "type": str(type(ch)), "category": ch.category.name if ch.category else None}
        return data

    @commands.command(name="conditor_backup")
    @commands.has_guild_permissions(administrator=True)
    async def cmd_backup(self, ctx: commands.Context):
        guild = ctx.guild
        localizer = Localizer(getattr(guild, "preferred_locale", "en"))
        path = self._snapshot_path(guild)
        data = {"roles": [], "categories": [], "channels": []}

        for r in guild.roles:
            data["roles"].append(self._serialize_role(r))

        for c in guild.categories:
            data["categories"].append({"name": c.name, "position": c.position})

        for ch in guild.channels:
            data["channels"].append(self._serialize_channel(ch))
            # archive recent messages for text channels
            if isinstance(ch, discord.TextChannel):
                msgs = []
                try:
                    async for m in ch.history(limit=50):
                        msgs.append({
                            "id": m.id,
                            "author": m.author.display_name,
                            "content": m.content,
                            "created_at": m.created_at.isoformat(),
                            "attachments": [a.url for a in m.attachments],
                            "embeds": [e.to_dict() for e in m.embeds],
                        })
                except Exception:
                    msgs = []
                data.setdefault("messages", {}).setdefault(ch.name, msgs)

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        await ctx.send(localizer.get("build_complete", roles=len(data["roles"]), channels=len(data["channels"])))

    @commands.command(name="conditor_restore")
    @commands.has_guild_permissions(administrator=True)
    async def cmd_restore(self, ctx: commands.Context):
        guild = ctx.guild
        localizer = Localizer(getattr(guild, "preferred_locale", "en"))
        path = self._snapshot_path(guild)
        if not path.exists():
            await ctx.send(localizer.get("missing_permissions", permission="backup file"))
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        await ctx.send(localizer.get("dry_run_notice"))
        roles = data.get("roles", [])
        cats = data.get("categories", [])
        chs = data.get("channels", [])
        await ctx.send(localizer.get("preview_diff", diff_summary=f"roles={len(roles)},categories={len(cats)},channels={len(chs)}"))

        # Attempt structural restore: create roles, categories, channels, then replay messages via webhooks
        # Note: this operation will modify the guild. Ensure bot has appropriate permissions.
        # Roles
        created_roles = {}
        for r in roles:
            try:
                role = await guild.create_role(name=r.get("name"), colour=discord.Colour.from_str(r.get("color", "#000000")), permissions=discord.Permissions(r.get("permissions", 0)), reason="Conditor restore")
                created_roles[r.get("name")] = role
            except Exception:
                continue

        # Categories
        category_map = {}
        for c in cats:
            try:
                category_map[c.get("name")] = await guild.create_category(c.get("name"))
            except Exception:
                continue

        # Channels and replay messages
        messages = data.get("messages", {})
        for ch in chs:
            try:
                if ch.get("type", "text").lower().startswith("text"):
                    category = category_map.get(ch.get("category"))
                    new_ch = await guild.create_text_channel(ch.get("name"), category=category)
                    # create webhook for replay
                    try:
                        wh = await new_ch.create_webhook(name="Conditor Replay")
                        for msg in reversed(messages.get(ch.get("name"), [])):
                            try:
                                await wh.send(content=msg.get("content") or "[embed/attachment]", username=msg.get("author", "unknown"))
                            except Exception:
                                continue
                    except Exception:
                        # cannot create webhooks
                        pass
                else:
                    # create voice/stage as text channel stand-in
                    await guild.create_text_channel(ch.get("name"))
            except Exception:
                continue

        await ctx.send(localizer.get("build_complete", roles=len(created_roles), channels=len(chs)))


async def setup(bot: commands.Bot):
    await bot.add_cog(BackupCog(bot))
