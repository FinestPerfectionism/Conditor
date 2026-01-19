import asyncio
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List

import discord
from discord.ext import commands
from src.conditor.i18n import Localizer
from src.conditor import storage
from src.conditor.rate_limiter import run_with_rate_limit
from src.conditor.permissions import apply_channel_overwrites, ensure_bot_role_position
import io


PERMISSION_PROFILES = {
    "admin": discord.Permissions(administrator=True),
    "moderation": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True),
    "member": discord.Permissions(send_messages=True, read_messages=True),
}


class ProgressReporter:
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        self.message = None

    async def start(self, text: str):
        self.message = await self.ctx.send(text)

    async def update(self, content: str):
        if self.message:
            try:
                await self.message.edit(content=content)
            except discord.HTTPException:
                await self.ctx.send(content)
        else:
            await self.ctx.send(content)

    async def error(self, text: str):
        await self.ctx.send(f"Error: {text}")
        if self.message:
            try:
                await self.message.edit(content=f"Failed: {text}")
            except Exception:
                pass


class BuildJob:
    def __init__(self, guild: discord.Guild, template: Dict[str, Any], reporter: ProgressReporter, localizer: Localizer, dry_run: bool = False):
        self.guild = guild
        self.template = template
        self.reporter = reporter
        self.localizer = localizer
        self.dry_run = dry_run

    async def run(self):
        await self.reporter.update(self.localizer.get("estimate_ops", total_ops=0, eta=0))
        # Basic validations
        if not getattr(self.guild.me, "guild_permissions", None) or not self.guild.me.guild_permissions.manage_guild:
            await self.reporter.error(self.localizer.get("missing_permissions", permission="Manage Guild"))
            return
        role_defs = self.template.get("roles", [])
        cat_defs = self.template.get("categories", [])
        ch_defs = self.template.get("channels", [])

        total_ops = len(role_defs) + len(cat_defs) + len(ch_defs)
        base_delay = max(0.2, min(1.5, 0.15 * math.sqrt(max(1, total_ops))))
        eta = int(total_ops * base_delay)

        await self.reporter.update(self.localizer.get("estimate_ops", total_ops=total_ops, eta=eta))

        # Roles
        created_roles = {}
        for i, rd in enumerate(sorted(role_defs, key=lambda r: -r.get("position", 0))):
            name = rd.get("name") or rd.get("name_key")
            color = rd.get("color", "#000000")
            profile = rd.get("profile")
            perms = PERMISSION_PROFILES.get(profile, discord.Permissions())
            await self.reporter.update(self.localizer.get("forging_roles", current=i+1, total=len(role_defs)))
            if not self.dry_run:
                try:
                    async def _create_role():
                        return await self.guild.create_role(name=name, colour=discord.Colour.from_str(color), permissions=perms, reason="Conditor build")

                    role = await run_with_rate_limit(self.guild.id, _create_role)
                    created_roles[rd.get("key", name)] = role
                except Exception as exc:
                    await self.reporter.error(self.localizer.get("failed_role_create", name=name, reason=str(exc)))
                    raise
            await asyncio.sleep(base_delay * 1.2)

        # Categories (merge by name)
        existing_cats = {c.name: c for c in self.guild.categories}
        category_map = {}
        for i, cd in enumerate(sorted(cat_defs, key=lambda c: c.get("position", 0))):
            name = cd.get("name") or cd.get("name_key")
            await self.reporter.update(self.localizer.get("organising_categories", current=i+1, total=len(cat_defs)))
            if name in existing_cats:
                category_map[name] = existing_cats[name]
            else:
                if not self.dry_run:
                    try:
                        async def _create_cat():
                            return await self.guild.create_category(name)

                        category_map[name] = await run_with_rate_limit(self.guild.id, _create_cat)
                    except Exception as exc:
                        await self.reporter.error(self.localizer.get("failed_channel_create", name=name, reason=str(exc)))
                        raise
            await asyncio.sleep(base_delay)

        # Channels
        for i, ch in enumerate(ch_defs):
            name = ch.get("name") or ch.get("name_key")
            ctype = ch.get("type", "text")
            cat_name = ch.get("category") or ch.get("category_key")
            category = category_map.get(cat_name)
            await self.reporter.update(self.localizer.get("constructing_channels", current=i+1, total=len(ch_defs)))
            if not self.dry_run:
                try:
                    # create channel via rate-limited wrapper
                    async def _create_channel():
                        if ctype == "text":
                            return await self.guild.create_text_channel(name, category=category)
                        elif ctype == "voice":
                            return await self.guild.create_voice_channel(name, category=category)
                        elif ctype == "announcement":
                            return await self.guild.create_text_channel(name, category=category, news=True)
                        else:
                            return await self.guild.create_text_channel(name, category=category)

                    new_ch = await run_with_rate_limit(self.guild.id, _create_channel)
                    # apply overwrites if present
                    overwrites = ch.get("overwrites") or ch.get("overrides")
                    if overwrites:
                        try:
                            await apply_channel_overwrites(self.guild, new_ch, overwrites)
                        except Exception as exc:
                            await self.reporter.error(self.localizer.get("failed_channel_create", name=name, reason=str(exc)))
                            raise
                except discord.HTTPException as exc:
                    await self.reporter.error(self.localizer.get("failed_channel_create", name=name, reason=str(exc)))
                    raise
            await asyncio.sleep(base_delay)

        # Permissions application and localization would be next — simplified here
        await self.reporter.update(self.localizer.get("binding_permissions"))
        await asyncio.sleep(base_delay * 1.3)

        await self.reporter.update(self.localizer.get("snapshotting"))
        await asyncio.sleep(0.5)

        await self.reporter.update(self.localizer.get("build_complete", roles=len(created_roles), channels=len(ch_defs)))


class BuilderCog(commands.Cog):
    """Cog that enqueues and orchestrates builds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _load_template(self, name: str) -> dict:
        # Prefer DB-backed template
        db_content = storage.load_template(name)
        if db_content:
            return json.loads(db_content)
        base = Path(__file__).parent.parent.parent
        tpl_path = base / "data" / "templates" / f"{name}.json"
        if not tpl_path.exists():
            raise FileNotFoundError(str(tpl_path))
        return json.loads(tpl_path.read_text(encoding="utf-8"))

    @commands.command(name="conditor_build")
    @commands.has_guild_permissions(administrator=True)
    async def cmd_build(self, ctx: commands.Context, template_name: str, dry: str = "false"):
        """Queue a Conditor build. Usage: !conditor_build example_template [dry=true]"""
        try:
            tpl = self._load_template(template_name)
        except FileNotFoundError:
            await ctx.send(f"Template not found: {template_name}")
            return

        # determine locale: prefer guild preferred_locale, then template meta, then 'en'
        locale = getattr(ctx.guild, "preferred_locale", None) or tpl.get("meta", {}).get("languages", [None])[0] or "en"
        localizer = Localizer(locale)

        reporter = ProgressReporter(ctx)
        await reporter.start(localizer.get("preflight_preview", roles=len(tpl.get("roles", [])), channels=len(tpl.get("channels", [])), eta=tpl.get("meta", {}).get("estimated_build_seconds", 0)))
        dry_run = dry.lower() in ("true", "1", "yes")

        # compile template into a BuildPlan and enqueue it for execution (include invoking guild id)
        from src.conditor.bot import build_queue
        from src.conditor.core.intent.models import ServerSpec
        from src.conditor.core.planner import compile_spec_to_plan

        spec = ServerSpec()
        spec.extras.setdefault('templates', []).append(tpl)
        plan = compile_spec_to_plan(spec, name=f"build-{tpl.get('meta', {}).get('name', template_name)}")

        # present human approval preview before enqueueing
        preview_lines = [f"Plan: {plan.name} (steps={len(plan.steps)})"]
        for i, s in enumerate(plan.steps[:40]):
            preview_lines.append(f"{i+1}. {s.type.value} -> {s.payload}")
        preview_text = "\n".join(preview_lines)
        if len(preview_text) > 1500:
            preview_text = preview_text[:1400] + "\n... (truncated)"

        # present approval UI using buttons
        class ApprovalView(discord.ui.View):
            def __init__(self, requester_id: int, timeout: float = 300.0):
                super().__init__(timeout=timeout)
                self.requester_id = requester_id
                self.result = None

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                return interaction.user.id == self.requester_id

            @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
            async def approve(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.result = {"approved": True, "user": {"id": interaction.user.id, "name": str(interaction.user)}}
                await interaction.response.edit_message(content=f"Approved by {interaction.user}", view=None)
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.result = {"approved": False, "user": {"id": interaction.user.id, "name": str(interaction.user)}}
                await interaction.response.edit_message(content=f"Cancelled by {interaction.user}", view=None)
                self.stop()

        view = ApprovalView(requester_id=ctx.author.id, timeout=300.0)
        approval_msg = await ctx.send(f"**Preflight plan preview**\n```\n{preview_text}\n```", view=view)

        await view.wait()
        if not getattr(view, 'result', None):
            await ctx.send('Approval timed out — build cancelled.')
            return
        if not view.result.get('approved'):
            await ctx.send('Build cancelled by user.')
            return

        # Approved — record audit and enqueue plan for execution
        from datetime import datetime
        from src.conditor.storage import append_approval
        from pathlib import Path

        ns = plan.name if hasattr(plan, 'name') else None
        safe_ns = None
        if ns:
            safe_ns = ''.join(c for c in ns if c.isalnum() or c in ('_', '-')).strip()
            if safe_ns == '':
                safe_ns = None
        name_part = f"_{safe_ns}" if safe_ns else ''
        runtime_dir = Path(__file__).parent.parent.parent / 'data' / 'runtime'
        runtime_dir.mkdir(parents=True, exist_ok=True)
        map_path = runtime_dir / f"resource_map_{ctx.guild.id}{name_part}.json"
        map_snapshot = None
        try:
            if map_path.exists():
                map_snapshot = json.loads(map_path.read_text(encoding='utf-8'))
        except Exception:
            map_snapshot = None

        audit_entry = {
            'approved_by': {'id': view.result['user']['id'], 'name': view.result['user']['name']},
            'approved_at': datetime.utcnow().isoformat() + 'Z',
            'guild_id': ctx.guild.id,
            'plan_name': plan.name,
            'resource_map': str(map_path),
            'resource_map_snapshot': map_snapshot,
        }
        try:
            append_approval(audit_entry)
        except Exception:
            pass

        await build_queue.put({'type': 'plan', 'plan': plan, 'dry_run': dry_run, 'guild_id': ctx.guild.id})
        await ctx.send(localizer.get("preflight_preview", roles=len(tpl.get("roles", [])), channels=len(tpl.get("channels", [])), eta=tpl.get("meta", {}).get("estimated_build_seconds", 0)))

    @commands.command(name="conditor_simulate")
    @commands.has_guild_permissions(administrator=True)
    async def cmd_simulate(self, ctx: commands.Context, template_name: str, locale: str = "en"):
        """Simulate the build pipeline locally and render localized messages without API calls."""
        try:
            tpl = self._load_template(template_name)
        except FileNotFoundError:
            await ctx.send(f"Template not found: {template_name}")
            return

        localizer = Localizer(locale)
        lines = []
        roles = tpl.get("roles", [])
        cats = tpl.get("categories", [])
        chs = tpl.get("channels", [])
        total_ops = len(roles) + len(cats) + len(chs)
        eta = int(total_ops * max(0.2, min(1.5, 0.15 * math.sqrt(max(1, total_ops)))))
        lines.append(localizer.get("estimate_ops", total_ops=total_ops, eta=eta))

        for i, r in enumerate(roles):
            lines.append(localizer.get("forging_roles", current=i+1, total=len(roles)))

        for i, c in enumerate(cats):
            lines.append(localizer.get("organising_categories", current=i+1, total=len(cats)))

        for i, ch in enumerate(chs):
            lines.append(localizer.get("constructing_channels", current=i+1, total=len(chs)))

        lines.append(localizer.get("binding_permissions"))
        lines.append(localizer.get("snapshotting"))
        lines.append(localizer.get("build_complete", roles=len(roles), channels=len(chs)))

        # Build a JSON preview describing operations and messages
        preview = {
            "template": template_name,
            "locale": localizer.locale,
            "operations": {
                "roles": [r.get("name") or r.get("name_key") for r in roles],
                "categories": [c.get("name") or c.get("name_key") for c in cats],
                "channels": [ch.get("name") or ch.get("name_key") for ch in chs],
            },
            "messages": lines,
        }

        # send messages summary and a downloadable JSON preview
        await ctx.send("Simulation preview (messages shown). Sending JSON preview as attachment.")
        payload = io.BytesIO()
        payload.write(json.dumps(preview, ensure_ascii=False, indent=2).encode("utf-8"))
        payload.seek(0)
        await ctx.send(file=discord.File(payload, filename=f"{template_name}_preview.json"))


async def setup(bot: commands.Bot):
    await bot.add_cog(BuilderCog(bot))

